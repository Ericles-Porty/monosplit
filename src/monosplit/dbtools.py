"""Import, dump and restore of the experiment database (`monosplit db ...`).

    uv run python -m monosplit db status
    uv run python -m monosplit db import-config          # config/ and prompts/ of earlier versions
    uv run python -m monosplit db import data            # data/ of earlier versions
    uv run python -m monosplit db dump dump              # readable copy kept in git
    uv run python -m monosplit db restore dump           # into an empty database

import-config: reads config/apps.toml, config/llm/*.toml, config/*.toml and prompts/*.txt
of the earlier file layout into the collections apps, profiles, experiments and prompts.
Paths become names (config/llm/gpt.toml -> gpt, prompts/decomposition_v1.txt ->
decomposition_v1) and the comment lines of each file become its note. It can run again:
documents already stored with the same content are skipped, and a document that differs
from its file is reported and left as it is.

import: reads data/graphs/<app>/ (classes.csv, edges.csv, call_sites.csv, graph.json,
edge_check.csv), data/runs/<experiment>/<app>/<profile>/<variant>/ and
data/results/<experiment>/<app>/<profile>/. It can run again: attempts already stored
are skipped, graphs and evaluations are replaced, and an edge check found in
edge_check.csv replaces the stored one.

dump: one JSON Lines file per collection in <folder>/<database>/, documents in a fixed
order and keys sorted, without MongoDB's _id, so that two dumps of the same data are
byte for byte equal and git diffs show what changed. This is the replication package.

restore: loads a dump into a database that holds no document yet.
"""

from __future__ import annotations

import csv
import json
import re
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .config import name_of
from .extraction.extract import read_edge_check, read_graph_folder
from .prompting import sha256_text
from .runner import read_jsonl
from .store import CONFIG, STUDY, TIMESTAMPS, VARIANT, DuplicateAttempt, Store, study_key

Log = Callable[[str], None]

# CSV columns that hold text even when they look like numbers ("4" in k_accepted).
_TEXT_COLUMNS = {"variant", "method", "control", "control_method", "ah_variant", "rule", "invalid_reasons",
                 "k_accepted", "metric", "scope", "groups_of_runs"}


def _value(column: str, text: str):
    if column in _TEXT_COLUMNS:
        return text
    if text in ("", "nan"):
        return None
    if text in ("True", "False"):
        return text == "True"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _csv_rows(path: Path, keep_empty: bool = True) -> list[dict]:
    """Rows of a CSV written by earlier versions, with numbers and booleans restored.
    keep_empty=False drops empty cells (columns that only some rows had)."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = []
        for row in csv.DictReader(f):
            rows.append({k: _value(k, v) for k, v in row.items() if keep_empty or v != ""})
        return rows


def _metric_rows(path: Path) -> list[dict]:
    rows = []
    for row in _csv_rows(path):
        if row.get("noise_points") is None:
            row.pop("noise_points", None)
        rows.append(row)
    return rows


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------- import of the data files

def import_folder(store: Store, data_dir: Path, log: Log = print) -> dict:
    counts = {"graphs": 0, "edge_checks": 0, "variants": 0, "attempts": 0, "attempts_skipped": 0, "evaluations": 0}

    for folder in sorted(p for p in (data_dir / "graphs").glob("*") if p.is_dir()):
        app = folder.name
        if (folder / "classes.csv").exists() and (folder / "edges.csv").exists():
            store.put_graph(app, **read_graph_folder(folder), source="import")
            counts["graphs"] += 1
        if (folder / "edge_check.csv").exists():
            meta = _read_json(folder / "edge_check_meta.json") if (folder / "edge_check_meta.json").exists() else None
            store.set_edge_check(app, read_edge_check(folder / "edge_check.csv"), meta, source="import", action="import")
            counts["edge_checks"] += 1

    for meta_path in sorted((data_dir / "runs").glob("*/*/*/*/run_meta.json")):
        folder = meta_path.parent
        experiment, app, profile, variant = folder.parts[-4:]
        key = study_key(experiment, app, profile, variant)
        meta = _read_json(meta_path)
        alias = _read_json(folder / "alias_map.json") if (folder / "alias_map.json").exists() else {}
        system = (folder / "prompt_system.txt").read_text(encoding="utf-8") if (folder / "prompt_system.txt").exists() else ""
        user = (folder / "prompt_user.txt").read_text(encoding="utf-8") if (folder / "prompt_user.txt").exists() else ""
        if store.insert_variant(key, meta, system, user, alias):
            counts["variants"] += 1
        accepted = {}
        for path in sorted((folder / "accepted").glob("run_*.json")):
            run = _read_json(path)
            accepted[run["attempt"]] = run
        for record in read_jsonl(folder / "attempts.jsonl"):
            raw_path = folder / "raw" / f"attempt_{record['attempt']:04d}.json"
            raw = _read_json(raw_path) if raw_path.exists() else None
            try:
                store.append_attempt(key, record, raw, accepted.get(record["attempt"]))
                counts["attempts"] += 1
            except DuplicateAttempt:
                counts["attempts_skipped"] += 1
        stored = store.accepted_count(key)
        if stored != len(accepted):
            raise RuntimeError(f"{folder}: {len(accepted)} accepted files but {stored} accepted attempts stored")
        log(f"{experiment}/{app}/{profile}/{variant}: {len(accepted)} accepted runs")

    for metrics_path in sorted((data_dir / "results").glob("*/*/*/metrics.csv")):
        folder = metrics_path.parent
        experiment, app, profile = folder.parts[-3:]
        key = study_key(experiment, app, profile)
        partitions = [
            {**item, "run": item["run"] if item["run"] != "" else None,
             "partition": [[c, s] for c, s in sorted(item["partition"].items())]}
            for item in read_jsonl(folder / "partitions.jsonl")
        ]
        doc = {
            "graph_sha256": (store.graph_doc(app, {"graph_sha256": 1}) or {}).get("graph_sha256"),
            "evaluated_utc": _mtime(metrics_path),
            "ah_selection": _csv_rows(folder / "ah_selection.csv"),
            "paired_differences": _csv_rows(folder / "paired_differences.csv"),
            "partitions": partitions,
        }
        store.save_evaluation(key, doc, _metric_rows(metrics_path))
        report = {
            "attempts_summary": _csv_rows(folder / "attempts_summary.csv"),
            "metrics_summary": _csv_rows(folder / "metrics_summary.csv"),
            "differences_summary": _csv_rows(folder / "differences_summary.csv"),
        }
        if (folder / "report.md").exists():
            report["report_md"] = (folder / "report.md").read_text(encoding="utf-8")
        store.update_evaluation(key, report)
        counts["evaluations"] += 1
        log(f"{experiment}/{app}/{profile}: evaluation imported")
    return counts


# ---------------------------------------------------------------- import of the configuration files

# Comment lines that the earlier interface wrote into every file; they are not notes.
_GENERATED = re.compile(
    r"^(LLM profile|Experiment configuration) \S+, saved by the \w+ interface on \d{4}-\d{2}-\d{2}\.$"
    r"|^A profile with runs keeps its provider"
    r"|^With stored runs, name, app, seed"
)
_ASSIGNMENT = re.compile(r"^[A-Za-z_][\w.-]*\s*=")


def comment_note(text: str, keep_assignments: bool = False) -> str:
    """The comment lines of a TOML file as a note, one paragraph per comment block. Lines
    written by the earlier interface, command examples and, unless kept, commented-out
    settings are left out."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("#"):
            if lines and lines[-1] != "":
                lines.append("")
            continue
        body = line.lstrip("#").strip()
        if _GENERATED.match(body) or body.startswith("uv run "):
            continue
        if not keep_assignments and _ASSIGNMENT.match(body):
            continue
        if body == "" and (not lines or lines[-1] == ""):
            continue
        lines.append(body)
    return "\n".join(lines).strip()


def _profile_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    raw = tomllib.loads(text)
    llm = raw.get("llm", {})
    template = path.stem.startswith("_")
    return {
        "name": path.stem,
        "template": template,
        "provider": llm.get("provider", ""),
        "model": llm.get("model", ""),
        "temperature": float(llm["temperature"]) if llm.get("temperature") is not None else None,
        "max_output_tokens": llm.get("max_output_tokens"),
        "seed": llm.get("seed"),
        "client": dict(raw.get("client", {})),
        "request": dict(raw.get("request", {})),
        "pricing": {k: v for k, v in (raw.get("pricing") or {}).items() if v not in (None, "")},
        "note": comment_note(text, keep_assignments=template),
    }


def _experiment_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    raw = tomllib.loads(text)
    exp = raw.get("experiment", {})
    controls = raw.get("controls", {})
    return {
        "id": path.stem,
        "name": exp.get("name", ""),
        "app": exp.get("app", ""),
        "seed": exp.get("seed"),
        "accepted_runs": exp.get("accepted_runs"),
        "max_retries": exp.get("max_retries", 3),
        "max_failed_runs": exp.get("max_failed_runs", exp.get("accepted_runs")),
        "variants": list(exp.get("variants", ["original"])),
        "database": exp.get("database", "monosplit"),
        "llm": name_of(exp["llm"]) if exp.get("llm") else None,
        "prompt_template": name_of(raw.get("prompt", {}).get("template", "prompts/decomposition_v1.txt")),
        "ah_variants": list(controls.get("ah_variants", ["calls:average"])),
        "ah_primary": controls.get("ah_primary", "auto"),
        "hdbscan_min_cluster_size": controls.get("hdbscan_min_cluster_size", 2),
        "inferential": raw.get("analysis", {}).get("inferential", False),
        "note": comment_note(text),
    }


def _app_docs(path: Path) -> list[dict]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "id": app_id,
            "name": spec["name"],
            "note": spec.get("note", ""),
            "repository": spec["repository"],
            "tag": spec.get("tag"),
            "commit": spec["commit"],
            "build": spec["build"],
            "build_args": list(spec.get("build_args", [])),
            "source_roots": list(spec["source_roots"]),
            "class_dirs": list(spec["class_dirs"]),
        }
        for app_id, spec in raw.items()
    ]


def _prompt_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {"name": path.stem, "text": text, "sha256": sha256_text(text)}


def config_documents(root: Path) -> dict[str, list[tuple[str, dict]]]:
    """The documents of the configuration files under `root` (config/ and prompts/), each
    with the file it came from."""
    config_dir, prompts_dir = root / "config", root / "prompts"
    found: dict[str, list[tuple[str, dict]]] = {name: [] for name in CONFIG}
    if (config_dir / "apps.toml").exists():
        found["apps"] = [("config/apps.toml", doc) for doc in _app_docs(config_dir / "apps.toml")]
    for path in sorted((config_dir / "llm").glob("*.toml")):
        found["profiles"].append((f"config/llm/{path.name}", _profile_doc(path)))
    for path in sorted(prompts_dir.glob("*.txt")):
        found["prompts"].append((f"prompts/{path.name}", _prompt_doc(path)))
    for path in sorted(config_dir.glob("*.toml")):
        if path.name != "apps.toml":
            found["experiments"].append((f"config/{path.name}", _experiment_doc(path)))
    return found


def import_config(store: Store, root: Path, log: Log = print) -> dict:
    """Load the configuration files of the earlier layout into the database."""
    counts: dict[str, dict] = {}
    for collection, docs in config_documents(root).items():
        field = CONFIG[collection]
        result: dict = {"imported": 0, "unchanged": 0, "different": []}
        for origin, doc in docs:
            name = doc[field]
            stored = store.config_doc(collection, name)
            if stored is None:
                store.put_config(collection, name, doc, create=True, source="import", action="import")
                result["imported"] += 1
                log(f"{collection}: {name} imported from {origin}")
            elif {k: v for k, v in stored.items() if k not in TIMESTAMPS} == doc:
                result["unchanged"] += 1
            else:
                result["different"].append(name)
                log(f"{collection}: {name} differs from {origin}; the stored document was kept")
        counts[collection] = result
    return counts


# ---------------------------------------------------------------- dump and restore

_ORDER = {
    "apps": ("id",),
    "profiles": ("name",),
    "prompts": ("name",),
    "experiments": ("id",),
    "graphs": ("app",),
    "variants": VARIANT,
    "attempts": (*VARIANT, "attempt"),
    "evaluations": STUDY,
    "metrics": (*STUDY, "seq"),
    "notes": STUDY,
    "audit": ("utc", "id"),
}
_NUMERIC = {"attempt", "seq"}


def _line(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def dump(store: Store, out: Path) -> dict:
    folder = out / store.database
    folder.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, collection in store.collections().items():
        fields = _ORDER[name]
        docs = [{k: v for k, v in d.items() if k != "_id"} for d in collection.find({})]
        docs.sort(key=lambda d: tuple(d.get(k, 0) if k in _NUMERIC else str(d.get(k, "")) for k in fields))
        text = "".join(_line(d) + "\n" for d in docs)
        (folder / f"{name}.jsonl").write_text(text, encoding="utf-8", newline="\n")
        counts[name] = len(docs)
    manifest = {"database": store.database, "monosplit": __version__, "counts": counts}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return counts


def restore(store: Store, source: Path) -> dict:
    """`source` is the folder of one database dump (it holds manifest.json)."""
    if not (source / "manifest.json").exists():
        raise RuntimeError(f"{source} is not a database dump (no manifest.json)")
    collections = store.collections()
    used = {name: c.count_documents({}) for name, c in collections.items() if c.count_documents({}, limit=1)}
    if used:
        raise RuntimeError(f"Database {store.database} is not empty ({used}); restore only into an empty database")
    counts = {}
    for name, collection in collections.items():
        path = source / f"{name}.jsonl"
        docs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
        for start in range(0, len(docs), 500):
            collection.insert_many(docs[start:start + 500])
        counts[name] = len(docs)
    return counts
