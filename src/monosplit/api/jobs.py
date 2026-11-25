"""Background jobs of the web interface: graph extraction, LLM runs and evaluation.

One worker thread runs the jobs in order, so two jobs never write the same folders at the
same time. Jobs live in memory while the server runs; each one also writes its log to
work/jobs/<id>.log. A job that calls a paid model starts only with the confirmation token
of the cost estimate the user saw (estimate.py); providers that bill nothing (the fake
client, local models: `paid = False`) start without it. An interrupted run resumes where
it stopped when started again.

Kinds:
    extract   {app}                                   clone, build, extract the graph
    full      {config, profile, variants, confirm}    LLM runs, controls, metrics, report
    llm       {config, profile, variants, confirm}    LLM runs only
    evaluate  {config, profile}                       controls, metrics and report
    dry_run   {}                                      full run of the experiment dry_run with the fake client

`config` is the id of an experiment configuration and `profile` the name of an LLM profile,
both stored in the database (Configuration page).
"""

from __future__ import annotations

import itertools
import queue
import re
import threading
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import operations
from ..config import ExperimentConfig, LLMProfile, config_from_doc, profile_from_doc
from ..configstore import ConfigError
from ..estimate import estimate
from ..llm import provider_class
from ..paths import WORK_DIR
from ..prompting import VARIANTS
from ..runner import RunStopped
from ..store import open_store

KINDS = ("extract", "full", "llm", "evaluate", "dry_run")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_LOG = 2000


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    kind: str
    params: dict[str, Any]
    status: str = "queued"  # queued | running | succeeded | failed | cancelled
    created_utc: str = field(default_factory=_now)
    started_utc: str | None = None
    finished_utc: str | None = None
    progress: dict[str, dict] = field(default_factory=dict)
    cost_usd: float = 0.0
    log: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "params": {k: v for k, v in self.params.items() if k != "confirm"},
            "status": self.status,
            "created_utc": self.created_utc,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "progress": self.progress,
            "cost_usd": round(self.cost_usd, 6),
            "log": self.log[-400:],
            "result": self.result,
            "error": self.error,
            "cancel_requested": self.cancel.is_set(),
        }


def resolve_study(params: dict) -> tuple[ExperimentConfig, LLMProfile, list[str]]:
    name = params.get("config") or ""
    profile_name = params.get("profile") or ""
    store = open_store()
    doc = store.config_doc("experiments", name) if _NAME.match(name) else None
    if doc is None:
        raise ConfigError(f"No experiment configuration {name!r}", "config")
    try:
        config = config_from_doc(doc)
    except ValueError as error:
        raise ConfigError(str(error), "config") from None
    profile_doc = store.config_doc("profiles", profile_name) if _NAME.match(profile_name) else None
    if profile_doc is None:
        raise ConfigError(f"No LLM profile {profile_name!r}", "profile")
    try:
        profile = profile_from_doc(profile_doc)
    except ValueError as error:
        raise ConfigError(str(error), "profile") from None
    variants = params.get("variants") or list(config.variants)
    if any(v not in VARIANTS for v in variants):
        raise ConfigError(f"Variants must be among {VARIANTS}", "variants")
    if not config.store().has_graph(config.app):
        raise ConfigError(f"No extracted graph for {config.app}; extract it first", "config")
    return config, profile, [v for v in VARIANTS if v in variants]


class JobManager:
    def __init__(self, log_dir: Path = WORK_DIR / "jobs") -> None:
        self.log_dir = log_dir
        self._jobs: dict[str, Job] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._prefix = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._worker: threading.Thread | None = None

    # ------------------------------------------------------------ public

    def list(self) -> list[dict]:
        with self._lock:
            return [job.to_dict() for job in reversed(list(self._jobs.values()))]

    def get(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id].to_dict()

    def submit(self, kind: str, params: dict) -> dict:
        if kind not in KINDS:
            raise ConfigError(f"Unknown job kind {kind!r}", "kind")
        params = dict(params)
        if kind == "extract":
            from ..apps import load_apps

            if params.get("app") not in load_apps():
                raise ConfigError(f"Unknown application {params.get('app')!r}", "app")
        elif kind == "dry_run":
            params = {"config": "dry_run", "profile": "fake"}
            resolve_study(params)
        else:
            config, profile, variants = resolve_study(params)
            params["variants"] = variants
            if kind in ("full", "llm") and provider_class(profile.provider).paid:
                expected = estimate(config, profile, variants)["token"]
                if params.get("confirm") != expected:
                    raise ConfigError(
                        "The cost estimate changed or was not confirmed; review the estimate again", "confirm", conflict=True
                    )
        job = Job(id=f"{self._prefix}-{next(self._ids):03d}", kind=kind, params=params)
        with self._lock:
            self._jobs[job.id] = job
        self._log(job, f"queued: {kind} {job.to_dict()['params']}")
        self._queue.put(job.id)
        self._ensure_worker()
        return job.to_dict()

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            job = self._jobs[job_id]
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_utc = _now()
            elif job.status == "running":
                job.cancel.set()
        self._log(job, "cancellation requested; an API call in flight finishes first")
        return self.get(job_id)

    def busy(self) -> bool:
        with self._lock:
            return any(job.status in ("queued", "running") for job in self._jobs.values())

    def wait_idle(self, timeout: float = 60.0) -> None:
        """Block until no job is queued or running (used by tests)."""
        import time

        deadline = time.monotonic() + timeout
        while self.busy():
            if time.monotonic() > deadline:
                raise TimeoutError("jobs still running")
            time.sleep(0.05)

    # ------------------------------------------------------------ worker

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="monosplit-jobs", daemon=True)
            self._worker.start()

    def _log(self, job: Job, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        with self._lock:
            job.log.append(line)
            del job.log[:-_MAX_LOG]
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with (self.log_dir / f"{job.id}.log").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _progress(self, job: Job, event: dict) -> None:
        record = event.get("record") or {}
        with self._lock:
            job.progress[event["variant"]] = {
                "accepted": event["accepted"],
                "target": event["target"],
                "attempts": event["attempts"],
                "failed_runs": event["failed_runs"],
                "last": {k: record.get(k) for k in ("attempt", "run", "status", "reason", "k", "latency_s", "cost_usd")} if record else None,
            }
            if record.get("cost_usd"):
                job.cost_usd += record["cost_usd"]
        if record:
            detail = record.get("reason") or (f"K = {record.get('k')}" if record.get("status") == "accepted" else "")
            self._log(job, f"{event['variant']}: attempt {record.get('attempt')} {record.get('status')} {detail}".rstrip())

    def _work(self) -> None:
        while True:
            job_id = self._queue.get()
            with self._lock:
                job = self._jobs[job_id]
                if job.status == "cancelled":
                    continue
                job.status = "running"
                job.started_utc = _now()
            try:
                result = self._execute(job)
                status, error = "succeeded", None
            except RunStopped as stopped:
                result = None
                status, error = ("cancelled" if job.cancel.is_set() else "failed"), str(stopped)
            except Exception as failure:  # reported to the interface, the worker keeps going
                result = None
                status, error = "failed", f"{type(failure).__name__}: {failure}"
                self._log(job, traceback.format_exc(limit=3).strip())
            with self._lock:
                job.status, job.error, job.result = status, error, result
                job.finished_utc = _now()
            self._log(job, f"{status}{': ' + error if error else ''}")

    def _execute(self, job: Job) -> dict:
        log = lambda message: self._log(job, message)  # noqa: E731
        if job.kind == "extract":
            stats = operations.extract_app(job.params["app"], log, build_first=True, with_edge_sample=True, source="web")
            return {"app": job.params["app"], "stats": stats}
        config, profile, variants = resolve_study(job.params)
        study = f"{config.name}/{config.app}/{profile.name}"
        if job.kind == "evaluate":
            report = operations.evaluate_and_report(config, profile.name, log)
            return {"study": study, "report": str(report)}
        summaries = operations.run_llm(
            config, profile, variants, log, progress=lambda event: self._progress(job, event), cancel=job.cancel
        )
        result: dict[str, Any] = {"study": study, "variants": summaries}
        if job.kind in ("full", "dry_run"):
            result["report"] = str(operations.evaluate_and_report(config, profile.name, log))
        return result
