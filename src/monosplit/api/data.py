"""Payloads of the Data page: what is stored in each database, browsed read-only, plus the
audit of the changes. The changes themselves are in dataedit.py."""

from __future__ import annotations

from collections import defaultdict

from ..dataedit import known_databases
from ..store import DEFAULT_DATABASE, STUDY, VARIANT, Store, open_store, study_key
from .payloads import experiment_configs

PAGE_LIMIT = 200


def databases_payload() -> dict:
    rows = []
    for name in known_databases():
        store = open_store(name)
        rows.append({"name": name, "main": name == DEFAULT_DATABASE, "counts": store.counts()})
    return {"databases": rows, "default": DEFAULT_DATABASE}


def studies_payload(store: Store) -> dict:
    grouped: dict[tuple, list[str]] = defaultdict(list)
    for doc in store.variants():
        grouped[tuple(doc[k] for k in STUDY)].append(doc["variant"])
    configs: dict[str, list] = {}
    studies = []
    for (experiment, app, profile), variants in sorted(grouped.items()):
        key = study_key(experiment, app, profile)
        rows = []
        for variant in variants:
            counts = store.attempt_counts({**key, "variant": variant})
            rows.append(
                {
                    "variant": variant,
                    "attempts": sum(counts.values()),
                    "accepted": counts.get("accepted", 0),
                    "invalid": counts.get("invalid", 0),
                    "api_errors": counts.get("api_error", 0),
                }
            )
        if experiment not in configs:
            configs[experiment] = experiment_configs(store, experiment)
        evaluation = store.evaluation(key, {"evaluated_utc": 1})
        note = store.note(key)
        studies.append(
            {
                "id": f"{experiment}/{app}/{profile}",
                "experiment": experiment,
                "app": app,
                "profile": profile,
                "variants": rows,
                "evaluated_utc": evaluation.get("evaluated_utc") if evaluation else None,
                "note": (note or {}).get("text", ""),
                "note_updated_utc": (note or {}).get("updated_utc"),
                "configs": [c.id for c in configs[experiment] if c.app == app],
                "documents": store.study_counts(key),
            }
        )
    return {"database": store.database, "studies": studies}


def attempts_payload(store: Store, filters: dict, skip: int = 0, limit: int = 50) -> dict:
    skip, limit = max(0, skip), max(1, min(limit, PAGE_LIMIT))
    query = {k: v for k, v in filters.items() if k in (*VARIANT, "status") and v}
    rows, total = store.find_attempts(query, skip, limit)
    for row in rows:
        row.pop("accepted", None)
    return {"database": store.database, "filters": query, "rows": rows, "total": total, "skip": skip, "limit": limit}


def attempt_payload(store: Store, key: dict, attempt: int) -> dict | None:
    doc = store.attempt_doc(key, attempt)
    if doc is None:
        return None
    accepted = doc.get("accepted")
    if accepted:
        accepted = {**accepted, "partition": [{"class": c, "service": s} for c, s in accepted["partition"]]}
    return {**doc, "accepted": accepted, "database": store.database}


def audit_payload(store: Store, skip: int = 0, limit: int = 50, collection: str | None = None) -> dict:
    skip, limit = max(0, skip), max(1, min(limit, PAGE_LIMIT))
    rows, total = store.audit_entries(skip, limit, collection or None)
    return {"database": store.database, "rows": rows, "total": total, "skip": skip, "limit": limit}
