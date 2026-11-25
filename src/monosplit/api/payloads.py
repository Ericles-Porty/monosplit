"""JSON payloads of the web interface, built from the MongoDB database (store.py).

The live API and the static export call the same functions, so both show the same
numbers. Every payload is made of plain JSON types.

    index                                   apps, graphs and studies found in the database
    graph/<app>                             classes, edges, statistics and fixed node positions
    study/<experiment>/<app>/<profile>      configuration, attempts, metrics, AH selection,
                                            HDBSCAN references and run-to-run stability
    run/<experiment>/<app>/<profile>/<variant>/<run>
                                            every decomposition of one accepted run, described
                                            service by service
    results/<experiment>/<profile>          every application of an experiment for one profile:
                                            metric summaries, paired differences, AH selection,
                                            stability, pilot checks and, when the experiment
                                            file sets [analysis] inferential, the planned tests

A study is one (experiment, application, LLM profile) triple with stored runs.
"""

from __future__ import annotations

import math
import re
import threading
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

from .. import __version__
from ..analysis import ALPHA, DIRECTION, comparisons, criterion
from ..apps import load_apps
from ..config import config_from_doc
from ..graph import CallGraph
from ..metrics import compute, interface_classes
from ..partition import canonical, services
from ..report import describe_values, pilot_checks, stability_rows, summarize_attempts
from ..store import Store, open_store, study_key, unpair
from .layout import force_layout

METRICS = ("sm", "ifn", "icp", "ned")
CONTROLS = ("ah", "random")
LAYOUT_SEED = 20261104
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class NotFound(LookupError):
    """The requested application, study or run does not exist in the database."""


def safe_id(value: str) -> str:
    """Accept only plain identifiers in the URL (no operators, no path separators)."""
    if not _SAFE_ID.match(value) or ".." in value:
        raise NotFound(f"Invalid identifier: {value!r}")
    return value


def _number(value) -> float | None:
    if value is None or value in ("", "nan"):
        return None
    value = float(value)
    return None if math.isnan(value) else value


def _int(value) -> int | None:
    return None if value is None or value == "" else int(value)


# ---------------------------------------------------------------- discovery

def _studies(store: Store) -> dict[tuple[str, str, str], list[str]]:
    """(experiment, app, profile) -> variants, for every stored variant."""
    found: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for doc in store.variants():
        found[(doc["experiment"], doc["app"], doc["profile"])].append(doc["variant"])
    return {key: _variant_order(variants) for key, variants in found.items()}


def _variant_order(variants) -> list[str]:
    order = {"original": 0, "obfuscated": 1}
    return sorted(variants, key=lambda v: (order.get(v, 9), v))


def _study(store: Store, experiment: str, app: str, profile: str) -> list[str]:
    key = (safe_id(experiment), safe_id(app), safe_id(profile))
    studies = _studies(store)
    if key not in studies:
        raise NotFound(f"No study {'/'.join(key)}")
    return studies[key]


def _meta(store: Store, experiment: str, app: str, profile: str, variant: str) -> dict:
    return (store.variant(study_key(experiment, app, profile, variant)) or {}).get("meta", {})


def _selected_ah(evaluation: dict | None) -> str | None:
    for row in (evaluation or {}).get("ah_selection", []):
        if row.get("selected") in (True, "True"):
            return f"ah:{row['ah_variant']}"
    return None


def _ah_selection(evaluation: dict | None, rule: bool = False) -> list[dict]:
    rows = []
    for r in (evaluation or {}).get("ah_selection", []):
        row = {"variant": f"ah:{r['ah_variant']}", "runs": int(r["runs"]), "median_sm": _number(r["median_sm"]),
               "selected": r["selected"] in (True, "True")}
        if rule:
            row["rule"] = r.get("rule", "")
        rows.append(row)
    return rows


def _partitions(evaluation: dict | None) -> list[dict]:
    return [{**item, "partition": unpair(item["partition"])} for item in (evaluation or {}).get("partitions", [])]


# ---------------------------------------------------------------- descriptions

def describe(graph: CallGraph, groups: list[list[str]], names: list[str | None], method: str,
             seed: int | None = None) -> dict:
    """A decomposition service by service: sizes, internal edges, calls across services,
    interface classes and the four metrics, computed with the experiment's metric code."""
    assignment = {c: i for i, group in enumerate(groups) for c in group}
    values = compute(graph, assignment)
    interfaces = interface_classes(graph, assignment)
    k = len(groups)
    internal_edges = [0] * k
    internal_calls = [0] * k
    calls_out = [0] * k
    calls_in = [0] * k
    between: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    for (a, b), calls in graph.calls.items():
        i, j = assignment[a], assignment[b]
        if i == j:
            internal_edges[i] += 1
            internal_calls[i] += calls
        else:
            calls_out[i] += calls
            calls_in[j] += calls
            between[(i, j)][0] += 1
            between[(i, j)][1] += calls
    service_rows = [
        {
            "index": i,
            "name": names[i],
            "classes": sorted(group),
            "size": len(group),
            "internal_edges": internal_edges[i],
            "internal_calls": internal_calls[i],
            "calls_out": calls_out[i],
            "calls_in": calls_in[i],
            "interfaces": sorted(c for c in group if c in interfaces),
        }
        for i, group in enumerate(groups)
    ]
    return {
        "method": method,
        "seed": seed,
        "k": values.k,
        "metrics": {m: (None if np.isnan(getattr(values, m)) else getattr(values, m)) for m in METRICS},
        "services": service_rows,
        "assignment": dict(sorted(assignment.items())),
        "interfaces": sorted(interfaces),
        "service_edges": [
            {"source": i, "target": j, "edges": e, "calls": c} for (i, j), (e, c) in sorted(between.items())
        ],
        "cross_calls": sum(calls_out),
        "cross_edges": sum(e for e, _c in between.values()),
    }


def _groups_from_partition(partition: dict[str, int], order: tuple[str, ...]) -> list[list[str]]:
    return services(canonical(partition, order))


def moved_classes(groups_a: list[list[str]], groups_b: list[list[str]]) -> list[str]:
    """Classes of A whose service is not the one matched to theirs in B.

    Services are matched one to one by the largest total overlap (Hungarian algorithm).
    """
    sets_a, sets_b = [set(g) for g in groups_a], [set(g) for g in groups_b]
    overlap = np.array([[len(a & b) for b in sets_b] for a in sets_a])
    rows, cols = linear_sum_assignment(-overlap)
    match = dict(zip(rows.tolist(), cols.tolist()))
    moved = [c for i, a in enumerate(sets_a) for c in a if i not in match or c not in sets_b[match[i]]]
    return sorted(moved)


def _stability(graph: CallGraph, runs: list[dict]) -> dict:
    order = graph.classes
    labels = {r["run"]: [r["partition"][c] for c in order] for r in runs}
    groups = {r["run"]: [s["classes"] for s in r["services"]] for r in runs}
    ids = [r["run"] for r in runs]
    ari = [[round(float(adjusted_rand_score(labels[a], labels[b])), 4) for b in ids] for a in ids]
    moved = {str(a): {str(b): moved_classes(groups[a], groups[b]) for b in ids if b != a} for a in ids}
    return {"runs": ids, "ari": ari, "moved": moved}


# ---------------------------------------------------------------- payloads

_LAYOUTS: dict[tuple[str, str], dict[str, tuple[float, float]]] = {}
_LAYOUT_LOCK = threading.Lock()


def _layout(app: str, fingerprint: str, graph: CallGraph) -> dict[str, tuple[float, float]]:
    """Positions are cached per graph; the fingerprint changes when the graph does."""
    with _LAYOUT_LOCK:
        if (app, fingerprint) not in _LAYOUTS:
            _LAYOUTS[(app, fingerprint)] = force_layout(graph, seed=LAYOUT_SEED)
        return _LAYOUTS[(app, fingerprint)]


def graph_payload(store: Store, app: str) -> dict:
    doc = store.graph_doc(safe_id(app))
    if doc is None:
        raise NotFound(f"No graph for {app}")
    graph = store.graph(app)
    rows = {row["class"]: row for row in doc["classes"]}
    meta = doc.get("meta") or {}
    positions = _layout(app, doc.get("graph_sha256", ""), graph)

    def class_row(name: str) -> dict:
        row = rows.get(name, {})
        package, _, simple = name.rpartition(".")
        return {
            "id": name,
            "simple": row.get("simple_name") or simple,
            "package": row.get("package", package),
            "kind": row.get("kind", "class"),
            "source": row.get("source", ""),
        }

    return {
        "app": app,
        "meta": {k: v for k, v in meta.items() if k != "stats"},
        "stats": meta.get("stats", {"classes": graph.n_classes, "edges": graph.n_edges, "calls_in_graph": graph.total_calls}),
        "classes": [class_row(c) for c in graph.classes],
        "edges": [{"source": a, "target": b, "calls": n} for (a, b), n in sorted(graph.calls.items())],
        "layout": {"seed": LAYOUT_SEED, "positions": {c: list(p) for c, p in positions.items()}},
    }


def _attempt_summary(records: list[dict]) -> dict:
    answered = [r for r in records if r.get("status") != "api_error"]

    def total(field: str):
        values = [r.get(field) for r in answered]
        return None if not values or any(v is None for v in values) else round(sum(values), 6)

    return {
        "attempts": len(answered),
        "accepted": sum(1 for r in answered if r["status"] == "accepted"),
        "invalid": sum(1 for r in answered if r["status"] == "invalid"),
        "api_errors": sum(1 for r in records if r.get("status") == "api_error"),
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "latency_s": total("latency_s"),
        "cost_usd": total("cost_usd"),
    }


def index_payload(store: Store) -> dict:
    apps: dict[str, dict] = {}
    for app in load_apps().values():
        apps[app.id] = {"id": app.id, "name": app.name, "repository": app.repository, "tag": app.tag, "commit": app.commit}
    for summary in store.graph_summaries():
        entry = apps.setdefault(summary["app"], {"id": summary["app"], "name": summary["app"], "repository": None, "tag": None, "commit": None})
        entry["graph"] = summary["meta"].get("stats") or {"classes": summary["classes"]}
    for entry in apps.values():
        entry.setdefault("graph", None)

    studies = []
    for (experiment, app, profile), variants in sorted(_studies(store).items()):
        first = _meta(store, experiment, app, profile, variants[0])
        evaluation = store.evaluation(study_key(experiment, app, profile), {"ah_selection": 1})
        variant_rows = []
        for variant in variants:
            key = study_key(experiment, app, profile, variant)
            accepted = store.accepted_runs(key)
            variant_rows.append(
                {
                    "variant": variant,
                    "runs": [{"run": r["run"], "k": r["k"], "attempt": r["attempt"]} for r in accepted],
                    **_attempt_summary(store.attempts(key)),
                }
            )
        llm = first.get("llm", {})
        studies.append(
            {
                "id": f"{experiment}/{app}/{profile}",
                "experiment": experiment,
                "app": app,
                "profile": profile,
                "provider": llm.get("provider"),
                "model": llm.get("model"),
                "temperature": llm.get("temperature"),
                "request_options": llm.get("request_options", {}),
                "prompt_template": first.get("prompt_template"),
                "created_utc": first.get("created_utc"),
                "evaluated": evaluation is not None,
                "ah_selected": _selected_ah(evaluation),
                "has_graph": store.has_graph(app),
                "variants": variant_rows,
            }
        )
    return {"version": __version__, "apps": list(apps.values()), "studies": studies}


def study_payload(store: Store, experiment: str, app: str, profile: str) -> dict:
    variants = _study(store, experiment, app, profile)
    key = study_key(experiment, app, profile)
    evaluation = store.evaluation(key)
    graph = store.graph(app)

    variant_rows = []
    for variant in variants:
        variant_key = study_key(experiment, app, profile, variant)
        meta = _meta(store, experiment, app, profile, variant)
        records = store.attempts(variant_key)
        accepted = store.accepted_runs(variant_key)
        variant_rows.append(
            {
                "variant": variant,
                "meta": meta,
                "summary": _attempt_summary(records),
                "attempts": records,
                "runs": [
                    {"run": r["run"], "attempt": r["attempt"], "k": r["k"],
                     "services": [{"name": s["name"], "size": len(s["classes"])} for s in r["services"]]}
                    for r in accepted
                ],
                "stability": _stability(graph, accepted) if graph is not None and accepted else None,
            }
        )

    metrics_rows = []
    for row in store.metrics(key):
        metrics_rows.append(
            {
                "variant": row["variant"] or "",
                "run": _int(row["run"]),
                "method": row["method"],
                "k": int(row["k"]),
                **{m: _number(row[m]) for m in METRICS},
                "seed": _int(row.get("seed")),
            }
        )
    references = []
    if graph is not None:
        for item in _partitions(evaluation):
            if item["method"].startswith("hdbscan:"):
                groups = _groups_from_partition(item["partition"], graph.classes)
                references.append(describe(graph, groups, [None] * len(groups), item["method"]))
    return {
        "id": f"{experiment}/{app}/{profile}",
        "experiment": experiment,
        "app": app,
        "profile": profile,
        "evaluated": bool(metrics_rows),
        "ah_selected": _selected_ah(evaluation),
        "ah_selection": _ah_selection(evaluation),
        "variants": variant_rows,
        "metrics": metrics_rows,
        "references": references,
    }


def run_payload(store: Store, experiment: str, app: str, profile: str, variant: str, run: int) -> dict:
    variants = _study(store, experiment, app, profile)
    if variant not in variants:
        raise NotFound(f"No variant {variant}")
    key = study_key(experiment, app, profile, variant)
    accepted = next((r for r in store.accepted_runs(key) if r["run"] == int(run)), None)
    if accepted is None:
        raise NotFound(f"No accepted run {run} in {variant}")
    graph = store.graph(app)
    if graph is None:
        raise NotFound(f"No graph for {app}")

    attempt = next((r for r in store.attempts(key) if r["attempt"] == accepted["attempt"]), {})
    raw = store.raw(key, accepted["attempt"])
    output_text = (raw or {}).get("text", "")
    prompt_names = {c: a for a, c in store.alias_map(key).items()}

    groups = [s["classes"] for s in accepted["services"]]
    names = [s["name"] for s in accepted["services"]]
    decompositions = [describe(graph, groups, names, "llm")]
    evaluation = store.evaluation(study_key(experiment, app, profile))
    for item in _partitions(evaluation):
        if item["variant"] == variant and item["run"] == accepted["run"] and item["method"] != "llm":
            control = _groups_from_partition(item["partition"], graph.classes)
            decompositions.append(describe(graph, control, [None] * len(control), item["method"], item.get("seed")))
    return {
        "study": f"{experiment}/{app}/{profile}",
        "variant": variant,
        "run": accepted["run"],
        "attempt": attempt,
        "k": accepted["k"],
        "output_text": output_text,
        "prompt_names": prompt_names if variant != "original" else {},
        "ah_selected": _selected_ah(evaluation),
        "decompositions": decompositions,
    }


# ---------------------------------------------------------------- results

def experiment_configs(store: Store, experiment: str) -> list:
    """Experiment configurations that write `experiment` into the database of `store`."""
    found = []
    for doc in open_store().config_docs("experiments"):
        try:
            config = config_from_doc(doc)
        except Exception:  # an invalid configuration is reported by the configuration page
            continue
        if config.name == experiment and config.database == store.database:
            found.append(config)
    return found


def _analysis_settings(store: Store, experiment: str) -> dict:
    """`inferential` of the experiment configurations that write `experiment` into this database."""
    configs = experiment_configs(store, experiment)
    flags = [c.inferential for c in configs]
    return {"inferential": bool(flags) and all(flags), "configs": [c.id for c in configs]}


def _result_metrics(rows: list[dict], app: str) -> list[dict]:
    return [
        {
            "app": app,
            "variant": row["variant"] or None,
            "run": _int(row["run"]),
            "method": row["method"],
            "k": int(row["k"]),
            **{m: _number(row[m]) for m in METRICS},
            "seed": _int(row.get("seed")),
            "noise_points": _int(row.get("noise_points")),
        }
        for row in rows
    ]


def _result_differences(evaluation: dict | None, app: str) -> list[dict]:
    return [
        {
            "app": app,
            "variant": row["variant"],
            "run": int(row["run"]),
            "control": row["control"],
            "control_method": row["control_method"],
            "k": int(row["k"]),
            **{f"d_{m}": _number(row[f"d_{m}"]) for m in METRICS},
        }
        for row in (evaluation or {}).get("paired_differences", [])
    ]


def _summary(values: list[float | None]) -> dict | None:
    present = [v for v in values if v is not None]
    return describe_values(present) if present else None


def _pairs(metrics: list[dict], apps: list[str], variant: str, selected: dict[str, str | None]) -> dict:
    """(control, metric) -> (LLM values, control values), paired by application and run."""
    rows = {(r["app"], r["variant"], r["run"], r["method"]): r for r in metrics if r["run"] is not None}
    pairs: dict[tuple[str, str], tuple[list[float], list[float]]] = {
        (c, m): ([], []) for c in CONTROLS for m in METRICS
    }
    llm_rows = sorted(
        (r for r in metrics if r["method"] == "llm" and r["variant"] == variant and r["app"] in apps),
        key=lambda r: (apps.index(r["app"]), r["run"]),
    )
    for llm in llm_rows:
        for control in CONTROLS:
            method = selected.get(llm["app"]) if control == "ah" else "random"
            other = rows.get((llm["app"], variant, llm["run"], method))
            if other is None:
                continue
            for metric in METRICS:
                if llm[metric] is not None and other[metric] is not None:
                    pairs[(control, metric)][0].append(llm[metric])
                    pairs[(control, metric)][1].append(other[metric])
    return pairs


def results_payload(store: Store, experiment: str, profile: str, inferential: bool | None = None) -> dict:
    """Every application of `experiment` run with `profile`.

    Summaries use the report's code (numpy's linear quartiles), so the interface and
    report.md show the same numbers. Scopes: "all" (the applications pooled, as in the
    planned analysis) and, with more than one application, each application alone.
    `inferential` overrides the experiment files (tests use it).
    """
    experiment, profile = safe_id(experiment), safe_id(profile)
    studies = {
        key[1]: variants for key, variants in _studies(store).items() if key[0] == experiment and key[2] == profile
    }
    if not studies:
        raise NotFound(f"No study {experiment}/*/{profile}")
    settings = _analysis_settings(store, experiment)
    if inferential is not None:
        settings["inferential"] = inferential
    names = {a.id: a.name for a in load_apps().values()}
    apps = sorted(studies)

    app_rows, metrics, differences, metric_summaries = [], [], [], []
    selected: dict[str, str | None] = {}
    variant_names: list[str] = []
    meta: dict = {}
    for app in apps:
        order = studies[app]
        variant_names += [v for v in order if v not in variant_names]
        meta = meta or _meta(store, experiment, app, profile, order[0])
        key = study_key(experiment, app, profile)
        evaluation = store.evaluation(key, {"partitions": 0})
        graph = store.graph(app)
        graph_doc = store.graph_doc(app, {"meta": 1, "edge_check": 1}) or {}
        graph_meta = graph_doc.get("meta") or {}
        runs = {v: store.accepted_runs(study_key(experiment, app, profile, v)) for v in order}
        attempts = {v: summarize_attempts(v, store.attempts(study_key(experiment, app, profile, v))) for v in order}
        stability = {row["variant"]: row for row in stability_rows(graph, runs)} if graph is not None else {}
        selected[app] = _selected_ah(evaluation)
        app_metrics = _result_metrics(store.metrics(key), app)
        metrics += app_metrics
        differences += _result_differences(evaluation, app)
        for variant, method in sorted({(r["variant"], r["method"]) for r in app_metrics if r["variant"]}):
            group = [r for r in app_metrics if r["variant"] == variant and r["method"] == method]
            for metric in ("k", *METRICS):
                stats = _summary([r[metric] for r in group])
                if stats:
                    metric_summaries.append({"app": app, "variant": variant, "method": method, "metric": metric, **stats})
        app_rows.append(
            {
                "app": app,
                "name": names.get(app, app),
                "graph": graph_meta.get("stats"),
                "evaluated": bool(app_metrics),
                "ah_selected": selected[app],
                "ah_selection": _ah_selection(evaluation, rule=True),
                "variants": [{**attempts[v], "stability": stability.get(v)} for v in order],
                "checks": pilot_checks(graph, graph_doc.get("edge_check"), runs, list(attempts.values())) if graph is not None else None,
            }
        )

    scopes = ["all", *(apps if len(apps) > 1 else [])]
    difference_summaries = []
    for scope in scopes:
        members = apps if scope == "all" else [scope]
        for variant in variant_names:
            for control in CONTROLS:
                group = [d for d in differences if d["app"] in members and d["variant"] == variant and d["control"] == control]
                for metric in METRICS:
                    values = [d[f"d_{metric}"] for d in group if d[f"d_{metric}"] is not None]
                    stats = _summary(values)
                    if stats:
                        difference_summaries.append(
                            {"scope": scope, "variant": variant, "control": control, "metric": metric, **stats,
                             "positive": sum(v > 0 for v in values), "negative": sum(v < 0 for v in values),
                             "zero": sum(v == 0 for v in values)}
                        )

    tests = None
    if settings["inferential"]:
        tests = []
        for scope in scopes:
            members = apps if scope == "all" else [scope]
            for variant in variant_names:
                rows = comparisons(_pairs(metrics, members, variant, selected))
                tests.append({"scope": scope, "variant": variant, "apps": members, "comparisons": rows,
                              "criterion": criterion(rows)})

    llm = meta.get("llm", {})
    return {
        "id": f"{experiment}/{profile}",
        "experiment": experiment,
        "profile": profile,
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "temperature": llm.get("temperature"),
        "request_options": llm.get("request_options", {}),
        "prompt_template": meta.get("prompt_template"),
        "fake": llm.get("provider") == "fake",
        "analysis": {**settings, "alpha": ALPHA, "direction": DIRECTION},
        "variants": variant_names,
        "scopes": scopes,
        "apps": app_rows,
        "metrics": metrics,
        "metric_summaries": metric_summaries,
        "differences": differences,
        "difference_summaries": difference_summaries,
        "tests": tests,
    }
