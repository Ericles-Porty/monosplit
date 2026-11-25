"""Static, read-only copy of the web interface with its data embedded.

    uv run python -m monosplit web export                # writes work/site
    uv run python -m monosplit web export --out <folder>

The output is the built interface (web/dist) plus one JSON file per API response, at
data/<API path>.json. index.html gets a flag that makes the interface read those files
instead of calling /api. Asset paths and routes are relative (hash routes), so the folder
works from any web server or subfolder, such as a GitHub Pages project site.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..paths import WEB_DIST
from ..store import Store
from . import payloads

MARKER = ".monosplit-site"
STATIC_FLAG = "<script>window.MONOSPLIT_STATIC = true;</script>"


def _write(root: Path, api_path: str, payload: dict) -> None:
    path = root / "data" / f"{api_path}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def export_site(out_dir: Path, store: Store, web_dist: Path = WEB_DIST) -> dict:
    if not (web_dist / "index.html").exists():
        raise RuntimeError("Build the web interface first: in experimento/web run `npm install` and `npm run build`")
    if out_dir.exists():
        if not (out_dir / MARKER).exists() and any(out_dir.iterdir()):
            raise RuntimeError(f"{out_dir} exists and is not a previous export; choose another --out")
        shutil.rmtree(out_dir)
    shutil.copytree(web_dist, out_dir)

    index = payloads.index_payload(store)
    _write(out_dir, "index", index)
    counts = {"graphs": 0, "studies": 0, "runs": 0, "results": 0}
    for app in index["apps"]:
        if app["graph"] is not None:
            _write(out_dir, f"graph/{app['id']}", payloads.graph_payload(store, app["id"]))
            counts["graphs"] += 1
    for study in index["studies"]:
        experiment, app, profile = study["experiment"], study["app"], study["profile"]
        _write(out_dir, f"study/{study['id']}", payloads.study_payload(store, experiment, app, profile))
        counts["studies"] += 1
        if not study["has_graph"]:
            continue
        for variant in study["variants"]:
            for run in variant["runs"]:
                payload = payloads.run_payload(store, experiment, app, profile, variant["variant"], run["run"])
                _write(out_dir, f"run/{study['id']}/{variant['variant']}/{run['run']}", payload)
                counts["runs"] += 1
    for experiment, profile in sorted({(s["experiment"], s["profile"]) for s in index["studies"]}):
        _write(out_dir, f"results/{experiment}/{profile}", payloads.results_payload(store, experiment, profile))
        counts["results"] += 1

    page = out_dir / "index.html"
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace("</head>", f"  {STATIC_FLAG}\n  </head>", 1), encoding="utf-8")
    (out_dir / MARKER).write_text(
        json.dumps({"monosplit": __version__, "exported_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "database": store.database, **counts}, indent=2) + "\n",
        encoding="utf-8",
    )
    return counts
