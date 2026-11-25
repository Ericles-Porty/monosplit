"""Changes to the stored data that the Data page of the interface allows.

The attempts, API responses, accepted partitions, evaluations and metrics are the evidence
of the experiment: they are written only by the runs and by the evaluation, and the Data
page shows them read-only. What the researcher may change there:

- the edge check of an application: the verdict on each sampled edge (confirmed: yes, no
  or empty) and a note;
- the note of a study, free text;
- a whole study (every variant, attempt, evaluation and note of one experiment,
  application and profile) may be deleted, for example a run made with a wrong
  configuration. A full dump of its database is written to work/backups/<time>/ first.

Each change is written to the audit collection of the database it changes (store.py).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from . import dbtools
from .configstore import ConfigError, _databases
from .paths import WORK_DIR
from .store import DEFAULT_DATABASE, Store, database_names, key_text, open_store, study_key

EDGE_VERDICTS = ("", "yes", "no")
NOTE_LIMIT = 20_000
EDGE_NOTE_LIMIT = 2_000
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_DATABASE = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


def known_databases() -> list[str]:
    """The main database, every database named by an experiment and every monosplit
    database on the server."""
    return sorted({DEFAULT_DATABASE, *_databases(), *database_names()})


def data_store(database: str) -> Store:
    """The store of a known database. Opening a store creates its indexes, so an unknown
    name is refused instead of creating an empty database."""
    if not isinstance(database, str) or not _DATABASE.match(database) or database not in known_databases():
        raise ConfigError(f"Unknown database {database!r}", "database")
    return open_store(database)


def checked_key(experiment: str, app: str, profile: str, variant: str | None = None) -> dict:
    for value, field in ((experiment, "experiment"), (app, "app"), (profile, "profile")):
        if not isinstance(value, str) or not _ID.match(value):
            raise ConfigError(f"Invalid {field}: {value!r}", field)
    if variant is not None and (not isinstance(variant, str) or not _ID.match(variant)):
        raise ConfigError(f"Invalid variant: {variant!r}", "variant")
    return study_key(experiment, app, profile, variant)


# ---------------------------------------------------------------- edge check

def _check_app(app: str) -> str:
    if not isinstance(app, str) or not _ID.match(app):
        raise ConfigError(f"Invalid application: {app!r}", "app")
    return app


def edge_check(app: str) -> dict:
    """The edge sample of an application with the verdicts recorded so far."""
    store = open_store()
    doc = store.graph_doc(_check_app(app), {"edge_check": 1, "edge_check_meta": 1, "meta.name": 1, "meta.commit": 1,
                                            "meta.source_roots": 1})
    if doc is None:
        raise LookupError(f"No graph for {app}")
    rows = doc.get("edge_check")
    verdicts = [r.get("confirmed", "") for r in rows or []]
    return {
        "app": app,
        "name": (doc.get("meta") or {}).get("name") or app,
        "commit": (doc.get("meta") or {}).get("commit"),
        "rows": [{"row": i + 1, **r} for i, r in enumerate(rows or [])],
        "meta": doc.get("edge_check_meta"),
        "sampled": rows is not None,
        "summary": {"yes": verdicts.count("yes"), "no": verdicts.count("no"), "unchecked": verdicts.count("")},
    }


def update_edge_check(app: str, edits: list[dict], source: str = "web") -> dict:
    """Apply verdicts and notes to sampled edges. Each edit names the row (1 to n) and its
    caller and callee, so an edit made on an outdated page is refused."""
    store = open_store()
    doc = store.graph_doc(_check_app(app), {"edge_check": 1})
    if doc is None or doc.get("edge_check") is None:
        raise ConfigError(f"No edge sample for {app}", "app")
    rows = [dict(r) for r in doc["edge_check"]]
    if not isinstance(edits, list):
        raise ConfigError("edits must be a list", "edits")
    for edit in edits:
        index = edit.get("row") if isinstance(edit, dict) else None
        if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= len(rows):
            raise ConfigError(f"Invalid row {index!r}", "row")
        row = rows[index - 1]
        if (edit.get("caller"), edit.get("callee")) != (row["caller"], row["callee"]):
            raise ConfigError(f"Row {index} is not {edit.get('caller')} -> {edit.get('callee')}; reload the page", "row",
                              conflict=True)
        confirmed = edit.get("confirmed", row.get("confirmed", ""))
        if confirmed not in EDGE_VERDICTS:
            raise ConfigError("confirmed must be yes, no or empty", "confirmed")
        notes = edit.get("notes", row.get("notes", ""))
        if not isinstance(notes, str) or len(notes) > EDGE_NOTE_LIMIT:
            raise ConfigError(f"The note must be text of at most {EDGE_NOTE_LIMIT} characters", "notes")
        row["confirmed"], row["notes"] = confirmed, notes.strip()
    store.update_edge_check(app, rows, source=source)
    return edge_check(app)


# ---------------------------------------------------------------- studies

def set_note(database: str, key: dict, text: str, source: str = "web") -> dict:
    store = data_store(database)
    if not isinstance(text, str) or len(text) > NOTE_LIMIT:
        raise ConfigError(f"The note must be text of at most {NOTE_LIMIT} characters", "text")
    if not store.variants(**key):
        raise ConfigError(f"No study {key_text(key)} in {database}", "study")
    store.set_note(key, text.strip(), source=source)
    return store.note(key) or {"text": ""}


def delete_study(database: str, key: dict, confirm: str, source: str = "web",
                 backup_root: Path | None = None) -> dict:
    """Delete one study after writing a full dump of its database. `confirm` must repeat
    the study as experiment/app/profile."""
    store = data_store(database)
    if confirm != key_text(key):
        raise ConfigError(f"Type {key_text(key)} to confirm the deletion", "confirm")
    counts = store.study_counts(key)
    if not any(counts.values()):
        raise ConfigError(f"No study {key_text(key)} in {database}", "study")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = (backup_root or WORK_DIR / "backups") / stamp
    dbtools.dump(store, out)
    backup = out / store.database
    deleted = store.delete_study(key, detail=f"full dump of {database} before the deletion: {backup}", source=source)
    return {"study": key_text(key), "database": database, "deleted": deleted, "backup": str(backup)}
