"""Operations shared by the command line and the jobs of the web interface."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .apps import build, fetch, get_app, verify_checkout
from .config import ExperimentConfig, LLMProfile
from .evaluate import evaluate
from .extraction.extract import edge_sample, extract, source_root_finder, store_extraction
from .extraction.javap import javap_version
from .extraction.jdk import jdk_version, require_jdk
from .llm import create_client
from .report import write_report
from .runner import run_variant
from .store import open_store

Log = Callable[[str], None]
EDGE_SAMPLE = {"n": 20, "seed": 20261104}

RULES = (
    "Top-level classes of the main sources; nested classes merged; one call = one invocation instruction "
    "or invoking method handle targeting another top-level class of the application, resolved to the "
    "declaring class; self and library calls excluded."
)


def _tail(path: Path, lines: int = 25) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def sample_edges(app_id: str, n: int, seed: int, source: str = "cli") -> int:
    """Draw the edge sample of an application and store it with the graph, nothing
    confirmed yet; the researcher fills it in on the Data page. Returns the sample size."""
    app = get_app(app_id)
    store = open_store()
    doc = store.graph_doc(app.id)
    if doc is None:
        raise RuntimeError(f"No graph for {app.id}; run `monosplit extract {app.id}` first")
    rows = edge_sample(store.graph(app.id), doc.get("call_sites", []), n, seed,
                       source_root_finder(app.checkout, app.source_roots))
    meta = {"n": n, "seed": seed, "created_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    store.set_edge_check(app.id, rows, meta, source=source)
    return len(rows)


def extract_app(app_id: str, log: Log, build_first: bool = True, with_edge_sample: bool = False,
                source: str = "cli") -> dict:
    """Clone (if needed), compile and extract the call graph of an application into the database."""
    app = get_app(app_id)
    log(f"{app.name}: cloning {app.repository} at {app.commit[:7]}")
    fetch(app)
    if build_first:
        log(f"{app.name}: building ({app.build})")
        try:
            build(app)
        except RuntimeError as error:
            raise RuntimeError(f"{error}\n--- last lines of the build log ---\n{_tail(app.build_log)}") from error
    commit = verify_checkout(app)
    jdk = require_jdk()
    log(f"{app.name}: reading the bytecode with javap")
    extraction = extract(jdk, [app.checkout / d for d in app.class_dirs])
    meta = {
        "app": app.id,
        "name": app.name,
        "repository": app.repository,
        "tag": app.tag,
        "commit": commit,
        "source_roots": list(app.source_roots),
        "class_dirs": list(app.class_dirs),
        "jdk": jdk_version(jdk),
        "javap": javap_version(jdk),
        "extractor": f"monosplit {__version__}",
        "rules": RULES,
        "extracted_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    store = open_store()
    store_extraction(store, app.id, extraction, meta, source=source)
    log(f"{app.name}: {extraction.stats['classes']} classes, {extraction.stats['edges']} edges, "
        f"{extraction.stats['calls_in_graph']} calls -> database {store.graph_database}, collection graphs")
    # Never overwrite a checklist that may already hold manual confirmations.
    if with_edge_sample and (store.graph_doc(app.id) or {}).get("edge_check") is None:
        size = sample_edges(app.id, EDGE_SAMPLE["n"], EDGE_SAMPLE["seed"], source=source)
        log(f"{app.name}: sample of {size} edges stored for checking on the Data page")
    return extraction.stats


def run_llm(
    config: ExperimentConfig,
    profile: LLMProfile,
    variants: list[str],
    log: Log,
    progress: Callable[[dict], None] | None = None,
    cancel: threading.Event | None = None,
) -> list[dict]:
    graph = config.graph()
    client = create_client(profile.provider, **profile.client_options)
    summaries = []
    for variant in variants:
        log(f"{variant}: running {profile.provider} {profile.model} until {config.accepted_runs} accepted runs")
        summary = run_variant(client, profile, config, variant, graph, progress=progress, cancel=cancel)
        log(f"{variant}: {summary['accepted']} accepted runs, {summary['failed_runs']} failed runs, {summary['attempts']} attempts")
        summaries.append(summary)
    return summaries


def evaluate_and_report(config: ExperimentConfig, profile_name: str, log: Log) -> Path:
    log("computing the controls and metrics")
    evaluate(config, profile_name)
    report = write_report(config, profile_name)
    log(f"report stored in database {config.database}; copy at {report}")
    return report
