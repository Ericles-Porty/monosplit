"""MongoDB storage of the experiment: the primary record of its configuration, graphs, runs
and results.

Start the server with `docker compose up -d` in experimento/ (compose.yaml), or point
MONOSPLIT_MONGO_URI at another MongoDB (default mongodb://127.0.0.1:27017).

Collections (a study is one experiment, application and LLM profile; a variant adds
original or obfuscated names):

    apps          one document per application (experimental object), keyed by id
    profiles      one per LLM profile, keyed by name; names starting with "_" are templates
    prompts       one per prompt version, keyed by name; a version is never overwritten
    experiments   one per experiment configuration, keyed by id
    graphs        one per application: class rows, edges with call counts, call sites,
                  extraction metadata and the manual edge check
    variants      one per variant of a study: the run configuration (meta), the prompt
                  exactly as sent and the prompt-name -> class-name map
    attempts      one per LLM attempt: the log record, the full API response and, when
                  accepted, the partition in class names
    evaluations   one per study: AH selection, paired differences, every partition
                  measured, report summaries and report.md
    metrics       one per (variant, run, method) of the current evaluation of a study
    notes         one per study with a note written by the researcher
    audit         one per change made by the interface or the command line: time, action,
                  target, the previous and the new value

The configuration (apps, profiles, prompts, experiments) and the graphs live in the main
database (CONFIG_DATABASE, GRAPH_DATABASE) for every experiment; runs and results go to
the database named in the experiment (`database`), so the dry run writes to its own
database and never mixes with experimental data. Each database keeps the audit of the
changes made to it.

Integrity without transactions:
- an attempt is a single insert (record, raw response and accepted partition together),
  and the unique index on its number refuses a duplicate when a run is resumed;
- an evaluation writes its metric rows under a new evaluation_id, then switches the
  pointer in `evaluations` with one atomic document replacement, then deletes the old
  rows; readers only follow the pointer, so they never see two evaluations mixed.

Class names contain dots, which MongoDB field names should not carry, so every map keyed
by class name (partitions, alias maps) is stored as a list of [key, value] pairs.

Every read and write of the collections goes through this module.
"""

from __future__ import annotations

import math
import os
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .graph import CallGraph

URI_VARIABLE = "MONOSPLIT_MONGO_URI"
DEFAULT_URI = "mongodb://127.0.0.1:27017"
DEFAULT_DATABASE = "monosplit"
GRAPH_DATABASE = DEFAULT_DATABASE
CONFIG_DATABASE = DEFAULT_DATABASE

STUDY = ("experiment", "app", "profile")
VARIANT = (*STUDY, "variant")
# Configuration collections and the field that identifies a document in each.
CONFIG = {"apps": "id", "profiles": "name", "prompts": "name", "experiments": "id"}
STUDY_COLLECTIONS = ("variants", "attempts", "evaluations", "metrics", "notes")
COLLECTIONS = ("graphs", *STUDY_COLLECTIONS)
AUDIT = "audit"
TIMESTAMPS = ("created_utc", "updated_utc")

_lock = threading.Lock()
_client: Any = None
_stores: dict[tuple[str, str], Store] = {}


class StoreUnavailable(RuntimeError):
    """The MongoDB server does not answer."""


class DuplicateAttempt(RuntimeError):
    """An attempt with this number is already stored for the variant."""


class DocumentExists(RuntimeError):
    """A configuration document with this id or name already exists."""


def uri() -> str:
    return os.environ.get(URI_VARIABLE) or DEFAULT_URI


def _connect():
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    client = MongoClient(uri(), serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, uuidRepresentation="standard")
    try:
        client.admin.command("ping")
    except PyMongoError as error:
        client.close()
        raise StoreUnavailable(
            f"MongoDB does not answer at {uri()} ({type(error).__name__}). "
            "Start it with `docker compose up -d` in experimento/, or set " + URI_VARIABLE + "."
        ) from None
    return client


def client():
    global _client
    with _lock:
        if _client is None:
            _client = _connect()
        return _client


def set_client(new_client) -> None:
    """Replace the connection (tests use mongomock); clears the cached stores."""
    global _client
    with _lock:
        _client = new_client
        _stores.clear()


def open_store(database: str | None = None, graph_database: str | None = None) -> Store:
    """The store of `database` (default: the main database); graphs come from
    `graph_database` (default: the main database)."""
    key = (database or DEFAULT_DATABASE, graph_database or GRAPH_DATABASE)
    database, graph_database = key
    connection = client()
    with _lock:
        if key not in _stores:
            _stores[key] = Store(connection, database, graph_database)
        return _stores[key]


def database_names() -> list[str]:
    """Databases on the server that hold monosplit data (the main one and its siblings)."""
    names = client().list_database_names()
    return sorted(n for n in names if n == DEFAULT_DATABASE or n.startswith(DEFAULT_DATABASE + "_"))


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def pairs(mapping: dict) -> list[list]:
    """{class: value} -> [[class, value], ...], sorted by key."""
    return [[k, v] for k, v in sorted(mapping.items())]


def unpair(items: Iterable) -> dict:
    return {k: v for k, v in items}


def clean_number(value):
    """NaN is stored as null, as the CSV files left it empty or 'nan'."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def clean_row(row: dict) -> dict:
    return {k: clean_number(v) for k, v in row.items()}


def study_key(experiment: str, app: str, profile: str, variant: str | None = None) -> dict:
    key = {"experiment": experiment, "app": app, "profile": profile}
    if variant is not None:
        key["variant"] = variant
    return key


def key_text(key: dict) -> str:
    return "/".join(str(key[k]) for k in VARIANT if k in key)


def _plain(doc: dict | None, drop: Iterable[str] = ()) -> dict | None:
    if doc is None:
        return None
    skip = {"_id", *drop}
    return {k: v for k, v in doc.items() if k not in skip}


def _content(doc: dict | None) -> dict | None:
    """A configuration document without its timestamps, to compare two versions."""
    return None if doc is None else {k: v for k, v in doc.items() if k not in TIMESTAMPS}


class Store:
    def __init__(self, connection, database: str, graph_database: str | None = None) -> None:
        self.client = connection
        self.database = database
        self.graph_database = graph_database or database
        self.db = connection[database]
        self.gdb = connection[self.graph_database]
        self.cdb = connection[CONFIG_DATABASE]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        for name, field in CONFIG.items():
            self.cdb[name].create_index(field, unique=True)
        self.gdb.graphs.create_index("app", unique=True)
        self.db.variants.create_index([(k, 1) for k in VARIANT], unique=True)
        self.db.attempts.create_index([*((k, 1) for k in VARIANT), ("attempt", 1)], unique=True)
        self.db.evaluations.create_index([(k, 1) for k in STUDY], unique=True)
        self.db.metrics.create_index([("evaluation_id", 1), ("seq", 1)])
        self.db.notes.create_index([(k, 1) for k in STUDY], unique=True)
        for db in {id(d): d for d in (self.db, self.gdb, self.cdb)}.values():
            db[AUDIT].create_index([("utc", 1), ("id", 1)])

    # ------------------------------------------------------------ audit

    @staticmethod
    def _audit(db, action: str, collection: str, target: str, *, before: Any = None, after: Any = None,
               detail: str | None = None, source: str = "web") -> None:
        db[AUDIT].insert_one(
            {
                "id": uuid.uuid4().hex,
                "utc": datetime.now(UTC).isoformat(timespec="microseconds"),
                "action": action,
                "collection": collection,
                "target": target,
                "source": source,
                "before": before,
                "after": after,
                "detail": detail,
            }
        )

    def audit_entries(self, skip: int = 0, limit: int = 100, collection: str | None = None) -> tuple[list[dict], int]:
        """Changes made to this database, newest first."""
        query = {"collection": collection} if collection else {}
        total = self.db[AUDIT].count_documents(query)
        cursor = self.db[AUDIT].find(query).sort([("utc", -1), ("id", -1)]).skip(skip).limit(limit)
        return [_plain(d) for d in cursor], total

    # ------------------------------------------------------------ configuration

    def config_docs(self, collection: str) -> list[dict]:
        field = CONFIG[collection]
        return [_plain(d) for d in self.cdb[collection].find({}).sort(field, 1)]

    def config_doc(self, collection: str, name: str) -> dict | None:
        return _plain(self.cdb[collection].find_one({CONFIG[collection]: name}))

    def config_names(self, collection: str) -> list[str]:
        field = CONFIG[collection]
        return sorted(d[field] for d in self.cdb[collection].find({}, {field: 1}))

    def put_config(self, collection: str, name: str, doc: dict, *, create: bool, source: str = "web",
                   action: str | None = None) -> dict:
        """Create or replace a configuration document and audit the change. Saving a
        document equal to the stored one changes nothing and is not audited."""
        from pymongo.errors import DuplicateKeyError

        field = CONFIG[collection]
        before = self.config_doc(collection, name)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        content = {k: v for k, v in doc.items() if k not in (*TIMESTAMPS, "_id")}
        content[field] = name
        if create:
            if before is not None:
                raise DocumentExists(f"{collection}: {name} already exists")
            new = {**content, "created_utc": now, "updated_utc": now}
            try:
                self.cdb[collection].insert_one(new)
            except DuplicateKeyError:
                raise DocumentExists(f"{collection}: {name} already exists") from None
        else:
            if before is None:
                raise LookupError(f"{collection}: no {name}")
            if _content(before) == content:
                return before
            new = {**content, "created_utc": before.get("created_utc", now), "updated_utc": now}
            self.cdb[collection].replace_one({field: name}, new)
        new = _plain(new)
        self._audit(self.cdb, action or ("create" if create else "update"), collection, name,
                    before=_content(before), after=_content(new), source=source)
        return new

    def delete_config(self, collection: str, name: str, source: str = "web") -> None:
        before = self.config_doc(collection, name)
        if before is None:
            raise LookupError(f"{collection}: no {name}")
        self.cdb[collection].delete_one({CONFIG[collection]: name})
        self._audit(self.cdb, "delete", collection, name, before=_content(before), source=source)

    # ------------------------------------------------------------ graphs

    def put_graph(self, app: str, classes: list[dict], edges: list[dict], call_sites: list[dict], meta: dict,
                  source: str = "cli") -> None:
        """Store the extraction of `app`; a manual edge check already stored is kept."""
        graph = CallGraph.build([r["class"] for r in classes], {(e["caller"], e["callee"]): int(e["calls"]) for e in edges})
        from .runner import graph_fingerprint

        before = (self.gdb.graphs.find_one({"app": app}, {"graph_sha256": 1}) or {}).get("graph_sha256")
        fields = {
            "app": app,
            "classes": classes,
            "edges": [{"caller": a, "callee": b, "calls": n} for (a, b), n in sorted(graph.calls.items())],
            "call_sites": call_sites,
            "meta": meta,
            "graph_sha256": graph_fingerprint(graph),
        }
        self.gdb.graphs.update_one({"app": app}, {"$set": fields}, upsert=True)
        if before != fields["graph_sha256"]:
            stats = meta.get("stats") or {"classes": len(classes), "edges": len(fields["edges"])}
            self._audit(self.gdb, "extract", "graphs", app, before={"graph_sha256": before} if before else None,
                        after={"graph_sha256": fields["graph_sha256"], "stats": stats}, source=source)

    def set_edge_check(self, app: str, rows: list[dict], meta: dict | None, source: str = "cli",
                       action: str = "sample") -> None:
        """Replace the edge check of `app` (a new sample, or one loaded from a file)."""
        result = self.gdb.graphs.update_one({"app": app}, {"$set": {"edge_check": rows, "edge_check_meta": meta}})
        if result.matched_count == 0:
            raise LookupError(f"No graph for {app}")
        self._audit(self.gdb, action, "graphs", f"{app}/edge_check", after={"rows": len(rows), "meta": meta}, source=source)

    def update_edge_check(self, app: str, rows: list[dict], source: str = "web") -> int:
        """Store edited edge-check rows (same edges, same order); returns the rows changed."""
        doc = self.gdb.graphs.find_one({"app": app}, {"edge_check": 1})
        if doc is None or doc.get("edge_check") is None:
            raise LookupError(f"No edge check for {app}")
        old = doc["edge_check"]
        changed = [i for i, (a, b) in enumerate(zip(old, rows, strict=True)) if a != b]
        if not changed:
            return 0
        self.gdb.graphs.update_one({"app": app}, {"$set": {"edge_check": rows}})
        self._audit(self.gdb, "update", "graphs", f"{app}/edge_check",
                    before=[{"row": i + 1, **old[i]} for i in changed],
                    after=[{"row": i + 1, **rows[i]} for i in changed], source=source)
        return len(changed)

    def graph_doc(self, app: str, projection: dict | None = None) -> dict | None:
        return _plain(self.gdb.graphs.find_one({"app": app}, projection))

    def graph(self, app: str) -> CallGraph | None:
        doc = self.gdb.graphs.find_one({"app": app}, {"classes.class": 1, "edges": 1})
        if doc is None:
            return None
        return CallGraph.build(
            [r["class"] for r in doc["classes"]], {(e["caller"], e["callee"]): e["calls"] for e in doc["edges"]}
        )

    def has_graph(self, app: str) -> bool:
        return self.gdb.graphs.count_documents({"app": app}, limit=1) > 0

    def graph_summaries(self) -> list[dict]:
        """App, extraction metadata and number of classes of every stored graph."""
        rows = []
        for doc in self.gdb.graphs.find({}, {"app": 1, "meta": 1, "classes.class": 1, "edge_check": 1}).sort("app", 1):
            rows.append({"app": doc["app"], "meta": doc.get("meta") or {}, "classes": len(doc.get("classes") or []),
                         "edge_check": doc.get("edge_check") is not None})
        return rows

    # ------------------------------------------------------------ variants

    def variant(self, key: dict) -> dict | None:
        return _plain(self.db.variants.find_one(key))

    def insert_variant(self, key: dict, meta: dict, prompt_system: str, prompt_user: str, alias_map: dict) -> bool:
        """Insert the variant document; False when it already exists."""
        from pymongo.errors import DuplicateKeyError

        doc = {**key, "meta": meta, "prompt_system": prompt_system, "prompt_user": prompt_user,
               "alias_map": pairs(alias_map)}
        try:
            self.db.variants.insert_one(doc)
        except DuplicateKeyError:
            return False
        return True

    def discard_variant(self, key: dict) -> bool:
        """Delete a variant document that has no attempt (a run stopped by a configuration
        error on its first call); a variant with attempts is evidence and stays."""
        if self.db.attempts.count_documents(key, limit=1):
            return False
        return self.db.variants.delete_one(key).deleted_count == 1

    def variants(self, **filters) -> list[dict]:
        """Variant documents (without prompts), sorted by study and variant."""
        query = {k: v for k, v in filters.items() if v is not None}
        cursor = self.db.variants.find(query, {"prompt_system": 0, "prompt_user": 0, "alias_map": 0})
        return sorted((_plain(d) for d in cursor), key=lambda d: tuple(d[k] for k in VARIANT))

    def alias_map(self, key: dict) -> dict:
        doc = self.db.variants.find_one(key, {"alias_map": 1})
        return unpair(doc["alias_map"]) if doc else {}

    # ------------------------------------------------------------ attempts

    def append_attempt(self, key: dict, record: dict, raw: dict | None = None, accepted: dict | None = None) -> None:
        from pymongo.errors import DuplicateKeyError

        doc = {**key, **record, "raw": raw}
        if accepted is not None:
            doc["accepted"] = {
                "run": accepted["run"], "k": accepted["k"], "services": accepted["services"],
                "partition": pairs(accepted["partition"]),
            }
        try:
            self.db.attempts.insert_one(doc)
        except DuplicateKeyError:
            raise DuplicateAttempt(f"Attempt {record['attempt']} of {key_text(key)} is already stored") from None

    def attempts(self, key: dict) -> list[dict]:
        """The attempt log of a variant, in attempt order, as the old attempts.jsonl lines."""
        cursor = self.db.attempts.find(key, {"raw": 0, "accepted": 0}).sort("attempt", 1)
        return [_plain(d, VARIANT) for d in cursor]

    def find_attempts(self, filters: dict, skip: int = 0, limit: int = 50) -> tuple[list[dict], int]:
        """Attempts of any study matching `filters` (study fields and status), without the
        API response and the partition; with the number of matches."""
        query = {k: v for k, v in filters.items() if v not in (None, "")}
        total = self.db.attempts.count_documents(query)
        cursor = (
            self.db.attempts.find(query, {"raw": 0, "accepted.partition": 0})
            .sort([*((k, 1) for k in VARIANT), ("attempt", 1)])
            .skip(skip)
            .limit(limit)
        )
        return [_plain(d) for d in cursor], total

    def attempt_doc(self, key: dict, attempt: int) -> dict | None:
        """One attempt with its API response and accepted partition."""
        return _plain(self.db.attempts.find_one({**key, "attempt": attempt}))

    def attempt_counts(self, key: dict) -> dict[str, int]:
        """Attempts of a variant by status (accepted, invalid, api_error)."""
        counts: dict[str, int] = {}
        for doc in self.db.attempts.find(key, {"status": 1}):
            counts[doc.get("status")] = counts.get(doc.get("status"), 0) + 1
        return counts

    def raw(self, key: dict, attempt: int) -> dict | None:
        doc = self.db.attempts.find_one({**key, "attempt": attempt}, {"raw": 1})
        return doc.get("raw") if doc else None

    def accepted_runs(self, key: dict) -> list[dict]:
        """Accepted partitions of a variant, in run order, in class names."""
        cursor = self.db.attempts.find({**key, "status": "accepted"}, {"attempt": 1, "accepted": 1}).sort("attempt", 1)
        runs = []
        for doc in cursor:
            accepted = doc["accepted"]
            runs.append(
                {**{k: key[k] for k in VARIANT}, "run": accepted["run"], "attempt": doc["attempt"], "k": accepted["k"],
                 "services": accepted["services"], "partition": unpair(accepted["partition"])}
            )
        return sorted(runs, key=lambda r: r["run"])

    def accepted_count(self, key: dict) -> int:
        return self.db.attempts.count_documents({**key, "status": "accepted"})

    # ------------------------------------------------------------ evaluations

    def save_evaluation(self, key: dict, doc: dict, metric_rows: list[dict]) -> str:
        """Store a new evaluation of a study and make it the current one."""
        evaluation_id = uuid.uuid4().hex
        if metric_rows:
            self.db.metrics.insert_many(
                [{**key, "evaluation_id": evaluation_id, "seq": i, **clean_row(r)} for i, r in enumerate(metric_rows)]
            )
        previous = self.db.evaluations.find_one_and_replace(
            key, {**key, **doc, "evaluation_id": evaluation_id}, upsert=True
        )
        if previous is not None:
            self.db.metrics.delete_many({"evaluation_id": previous["evaluation_id"]})
        return evaluation_id

    def update_evaluation(self, key: dict, fields: dict) -> None:
        result = self.db.evaluations.update_one(key, {"$set": fields})
        if result.matched_count == 0:
            raise LookupError(f"No evaluation of {key_text(key)}; evaluate first")

    def evaluation(self, key: dict, projection: dict | None = None) -> dict | None:
        return _plain(self.db.evaluations.find_one(key, projection))

    def metrics(self, key: dict) -> list[dict]:
        """Metric rows of the current evaluation of a study, in the order they were computed."""
        current = self.db.evaluations.find_one(key, {"evaluation_id": 1})
        if current is None:
            return []
        cursor = self.db.metrics.find({"evaluation_id": current["evaluation_id"]}).sort("seq", 1)
        return [_plain(d, (*STUDY, "evaluation_id", "seq")) for d in cursor]

    # ------------------------------------------------------------ studies

    def note(self, key: dict) -> dict | None:
        return _plain(self.db.notes.find_one(key), STUDY)

    def set_note(self, key: dict, text: str, source: str = "web") -> None:
        """Write the researcher's note on a study; an empty text removes it."""
        before = self.note(key)
        old = (before or {}).get("text", "")
        if old == text:
            return
        if text:
            self.db.notes.replace_one(key, {**key, "text": text, "updated_utc": now_utc()}, upsert=True)
        else:
            self.db.notes.delete_one(key)
        self._audit(self.db, "update" if before else "create", "notes", key_text(key),
                    before={"text": old} if before else None, after={"text": text} if text else None, source=source)

    def study_counts(self, key: dict) -> dict[str, int]:
        return {name: self.db[name].count_documents(key) for name in STUDY_COLLECTIONS}

    def delete_study(self, key: dict, detail: str | None = None, source: str = "web") -> dict[str, int]:
        """Delete every document of a study (all its variants). The results go first, the
        variants last, so the configuration locks hold until the runs are gone."""
        counts = {}
        for name in ("evaluations", "metrics", "notes", "attempts", "variants"):
            counts[name] = self.db[name].delete_many(key).deleted_count
        self._audit(self.db, "delete", "study", key_text(key), before={"documents": counts}, detail=detail, source=source)
        return counts

    def delete_graph(self, app: str, source: str = "cli") -> None:
        """Delete the extracted graph of `app`, with its edge check."""
        doc = self.graph_doc(app, {"meta": 1})
        if doc is None:
            raise LookupError(f"graphs: no {app}")
        self.gdb["graphs"].delete_one({"app": app})
        self._audit(self.gdb, "delete", "graphs", app, before={"meta": doc.get("meta")}, source=source)

    def clear_audit(self) -> int:
        """Delete the change log of this database (a clean start); returns the entries deleted."""
        return self.db[AUDIT].delete_many({}).deleted_count

    def drop_database(self) -> None:
        """Delete this whole database. Refused for the database holding the configuration."""
        if self.db.name == CONFIG_DATABASE or self.db.name == self.gdb.name:
            raise ValueError(f"{self.db.name} holds the configuration or the graphs and cannot be dropped")
        self.db.client.drop_database(self.db.name)

    # ------------------------------------------------------------ whole database

    def collections(self) -> dict[str, Any]:
        """Every collection that belongs to this database: the configuration in the main
        database, graphs where they are stored, the study collections and the audit."""
        found: dict[str, Any] = {}
        if self.database == CONFIG_DATABASE:
            found.update({name: self.cdb[name] for name in CONFIG})
        if self.graph_database == self.database:
            found["graphs"] = self.gdb.graphs
        found.update({name: self.db[name] for name in STUDY_COLLECTIONS})
        found[AUDIT] = self.db[AUDIT]
        return found

    def counts(self) -> dict[str, int]:
        counts = {name: c.count_documents({}) for name, c in self.collections().items()}
        if "graphs" not in counts:
            counts = {"graphs": self.gdb.graphs.count_documents({}), **counts}
        return counts
