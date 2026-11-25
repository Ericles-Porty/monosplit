"""FastAPI application: the JSON API plus the built web interface.

    uv run python -m monosplit web serve                                # http://127.0.0.1:8765/
    uv run python -m monosplit web serve --database monosplit_dry_run

Read routes (GET) serve the database. Configuration, execution and data routes change the
database and can spend money, so every request that is not a GET must:
- carry the header X-MonoSplit-Request: 1, which a page from another site cannot send
  without a CORS preflight that this server never grants;
- come without an Origin header or from a local origin;
- name a local host (127.0.0.1, localhost), which blocks DNS-rebinding attacks.
The server binds to 127.0.0.1 by default. API key values are never returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, configstore, dataedit
from ..configstore import ConfigError
from ..llm import create_client
from ..paths import WEB_DIST
from ..store import DEFAULT_DATABASE, StoreUnavailable, open_store
from . import data as data_payloads
from . import payloads
from .jobs import JobManager, resolve_study

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
WRITE_HEADER = "x-monosplit-request"

_NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>monosplit</title>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; line-height: 1.5">
<h1>monosplit</h1>
<p>The API is running, but the web interface has not been built. In <code>experimento/web</code>, run:</p>
<pre>npm install
npm run build</pre>
<p>Then reload this page. The API is at <a href="/api/index">/api/index</a>.</p>
</body>"""


def _hostname(value: str) -> str:
    return (urlparse(f"//{value}").hostname or "").lower()


def _config_error(error: ConfigError) -> HTTPException:
    return HTTPException(status_code=409 if error.conflict else 400, detail=error.payload())


def create_app(
    database: str = DEFAULT_DATABASE,
    web_dist: Path = WEB_DIST,
    allowed_hosts: set[str] | None = None,
    jobs: JobManager | None = None,
) -> FastAPI:
    app = FastAPI(title="monosplit", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    hosts = LOCAL_HOSTS | (allowed_hosts or set())
    manager = jobs or JobManager()
    app.state.jobs = manager

    @app.exception_handler(StoreUnavailable)
    async def database_down(_request: Request, error: StoreUnavailable):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if _hostname(request.headers.get("host", "")) not in hosts:
            return JSONResponse({"detail": "Host not allowed"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get(WRITE_HEADER) != "1":
                return JSONResponse({"detail": "Missing X-MonoSplit-Request header"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and (urlparse(origin).hostname or "").lower() not in hosts:
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)

    def read(function, *args):
        try:
            return function(open_store(database), *args)
        except payloads.NotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from None

    def write(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ConfigError as error:
            raise _config_error(error) from None
        except LookupError as error:
            raise HTTPException(status_code=404, detail={"message": str(error), "field": None}) from None

    # ------------------------------------------------------------ read-only data

    @app.get("/api/index")
    def index() -> dict:
        return {**read(payloads.index_payload), "writable": True}

    @app.get("/api/graph/{app_id}")
    def graph(app_id: str) -> dict:
        return read(payloads.graph_payload, app_id)

    @app.get("/api/study/{experiment}/{app_id}/{profile}")
    def study(experiment: str, app_id: str, profile: str) -> dict:
        return read(payloads.study_payload, experiment, app_id, profile)

    @app.get("/api/run/{experiment}/{app_id}/{profile}/{variant}/{run}")
    def run(experiment: str, app_id: str, profile: str, variant: str, run: int) -> dict:
        return read(payloads.run_payload, experiment, app_id, profile, variant, run)

    @app.get("/api/results/{experiment}/{profile}")
    def results(experiment: str, profile: str) -> dict:
        return read(payloads.results_payload, experiment, profile)

    # ------------------------------------------------------------ configuration

    @app.get("/api/config")
    def config_summary() -> dict:
        return configstore.summary()

    @app.put("/api/config/profiles/{name}")
    def save_profile(name: str, body: dict[str, Any] = Body(...)) -> dict:
        return write(configstore.save_profile, name, body.get("data") or {}, bool(body.get("create")))

    @app.delete("/api/config/profiles/{name}")
    def delete_profile(name: str) -> dict:
        write(configstore.delete_profile, name)
        return {"deleted": name}

    @app.post("/api/config/models")
    def list_models(body: dict[str, Any] = Body(...)) -> dict:
        provider = body.get("provider")
        options = {k: v for k, v in (body.get("client") or {}).items() if v not in (None, "")}
        try:
            client = create_client(provider, **options)
            return {"provider": provider, "models": client.list_models()}
        except Exception as error:  # SDK and configuration errors alike
            raise HTTPException(status_code=400, detail={"message": f"{type(error).__name__}: {error}", "field": "model"}) from None

    @app.put("/api/config/experiments/{file}")
    def save_experiment(file: str, body: dict[str, Any] = Body(...)) -> dict:
        return write(configstore.save_experiment, file, body.get("data") or {}, bool(body.get("create")))

    @app.delete("/api/config/experiments/{file}")
    def delete_experiment(file: str) -> dict:
        write(configstore.delete_experiment, file)
        return {"deleted": file}

    @app.post("/api/config/prompts")
    def create_prompt(body: dict[str, Any] = Body(...)) -> dict:
        return write(configstore.create_prompt, body.get("name") or "", body.get("text") or "")

    @app.post("/api/config/prompts/next-name")
    def next_prompt_name(body: dict[str, Any] = Body(...)) -> dict:
        return {"name": configstore.next_prompt_name(str(body.get("base") or "prompt"))}

    @app.post("/api/config/prompts/preview")
    def preview_prompt(body: dict[str, Any] = Body(...)) -> dict:
        return write(
            configstore.preview_prompt,
            body.get("text") or "",
            body.get("app") or "",
            body.get("variant") or "original",
            int(body.get("seed") or 0),
        )

    @app.delete("/api/config/prompts/{name}")
    def delete_prompt(name: str) -> dict:
        write(configstore.delete_prompt, name)
        return {"deleted": name}

    @app.put("/api/config/apps/{app_id}")
    def save_app(app_id: str, body: dict[str, Any] = Body(...)) -> dict:
        return write(configstore.save_app, app_id, body.get("data") or {}, bool(body.get("create")))

    @app.delete("/api/config/apps/{app_id}")
    def delete_app(app_id: str) -> dict:
        write(configstore.delete_app, app_id)
        return {"deleted": app_id}

    @app.post("/api/config/apps/resolve")
    def resolve_tag(body: dict[str, Any] = Body(...)) -> dict:
        return {"commit": write(configstore.resolve_tag, body.get("repository") or "", body.get("tag") or "")}

    # ------------------------------------------------------------ data page

    def data_store(database: str):
        return write(dataedit.data_store, database)

    @app.get("/api/data/databases")
    def data_databases() -> dict:
        return data_payloads.databases_payload()

    @app.get("/api/data/{database}/studies")
    def data_studies(database: str) -> dict:
        return data_payloads.studies_payload(data_store(database))

    @app.get("/api/data/{database}/attempts")
    def data_attempts(database: str, experiment: str = "", app_id: str = "", profile: str = "", variant: str = "",
                      status: str = "", skip: int = 0, limit: int = 50) -> dict:
        filters = {"experiment": experiment, "app": app_id, "profile": profile, "variant": variant, "status": status}
        return data_payloads.attempts_payload(data_store(database), filters, skip, limit)

    @app.get("/api/data/{database}/attempt/{experiment}/{app_id}/{profile}/{variant}/{attempt}")
    def data_attempt(database: str, experiment: str, app_id: str, profile: str, variant: str, attempt: int) -> dict:
        key = write(dataedit.checked_key, experiment, app_id, profile, variant)
        found = data_payloads.attempt_payload(data_store(database), key, attempt)
        if found is None:
            raise HTTPException(status_code=404, detail="No such attempt")
        return found

    @app.get("/api/data/{database}/audit")
    def data_audit(database: str, skip: int = 0, limit: int = 50, collection: str = "") -> dict:
        return data_payloads.audit_payload(data_store(database), skip, limit, collection)

    @app.put("/api/data/{database}/notes/{experiment}/{app_id}/{profile}")
    def data_note(database: str, experiment: str, app_id: str, profile: str, body: dict[str, Any] = Body(...)) -> dict:
        key = write(dataedit.checked_key, experiment, app_id, profile)
        return write(dataedit.set_note, database, key, body.get("text") if body.get("text") is not None else "")

    @app.post("/api/data/{database}/studies/delete")
    def data_delete_study(database: str, body: dict[str, Any] = Body(...)) -> dict:
        if manager.busy():
            raise HTTPException(status_code=409, detail={"message": "A job is queued or running; wait until it ends",
                                                         "field": None})
        key = write(dataedit.checked_key, body.get("experiment"), body.get("app"), body.get("profile"))
        return write(dataedit.delete_study, database, key, body.get("confirm") or "")

    @app.get("/api/data/edge-check/{app_id}")
    def data_edge_check(app_id: str) -> dict:
        return write(dataedit.edge_check, app_id)

    @app.put("/api/data/edge-check/{app_id}")
    def data_save_edge_check(app_id: str, body: dict[str, Any] = Body(...)) -> dict:
        return write(dataedit.update_edge_check, app_id, body.get("edits") or [])

    # ------------------------------------------------------------ execution

    @app.get("/api/jobs")
    def list_jobs() -> dict:
        return {"jobs": manager.list(), "busy": manager.busy()}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            return manager.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="No such job") from None

    @app.post("/api/jobs/estimate")
    def estimate_job(body: dict[str, Any] = Body(...)) -> dict:
        from ..estimate import estimate

        config, profile, variants = write(resolve_study, body)
        return estimate(config, profile, variants)

    @app.post("/api/jobs")
    def submit_job(body: dict[str, Any] = Body(...)) -> dict:
        kind = body.get("kind") or ""
        params = {k: v for k, v in body.items() if k != "kind"}
        return write(manager.submit, kind, params)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        try:
            return manager.cancel(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="No such job") from None

    # ------------------------------------------------------------ interface

    if (web_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        def not_built() -> str:
            return _NOT_BUILT

    return app


def serve(database: str, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    import threading
    import webbrowser

    import uvicorn

    extra = set() if host in ("127.0.0.1", "localhost") else {_hostname(host)}
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    uvicorn.run(create_app(database, allowed_hosts=extra), host=host, port=port, log_level="warning")
