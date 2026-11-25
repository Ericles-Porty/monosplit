"""Descriptive pilot report: attempts, K, metrics by method, paired differences and the
pilot completion criteria of the proposal (rascunho, "Critérios para concluir o piloto").

No hypothesis test is run here; the pilot analysis is descriptive. Quartiles use numpy's
default linear interpolation.

Stored in the evaluation document of the study (store.py): attempts_summary,
metrics_summary, differences_summary and report_md. A copy of report.md is written to
work/reports/<experiment>/<app>/<profile>/report.md for reading; the database keeps the record.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from .config import ExperimentConfig
from .evaluate import METRICS, load_accepted
from .graph import CallGraph
from .paths import WORK_DIR
from .selfcheck import metrics_hand_check


def _number(value) -> float | None:
    """A stored number, or None for null, NaN and the empty or 'nan' cells of CSV imports."""
    if value is None or value in ("", "nan"):
        return None
    value = float(value)
    return None if math.isnan(value) else value


def describe_values(values: list[float]) -> dict:
    """n, median, quartiles (numpy's default linear interpolation), IQR, min and max."""
    a = np.asarray(values, dtype=float)
    q1, median, q3 = np.percentile(a, [25, 50, 75])
    return {"n": int(a.size), "median": float(median), "q1": float(q1), "q3": float(q3),
            "iqr": float(q3 - q1), "min": float(a.min()), "max": float(a.max())}


def _fmt(value, digits: int = 3) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _cell(stats: dict | None) -> str:
    """median [Q1; Q3]"""
    if not stats:
        return ""
    return f"{stats['median']:.3f} [{stats['q1']:.3f}; {stats['q3']:.3f}]"


def _table(rows: list[dict], columns: list[str]) -> str:
    head = "| " + " | ".join(columns) + " |"
    rule = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(_fmt(r.get(c)) for c in columns) + " |" for r in rows]
    return "\n".join([head, rule, *body])


def summarize_attempts(variant: str, records: list[dict]) -> dict:
    """Totals of one variant's attempt log; API errors are counted apart from the attempts."""
    answered = [r for r in records if r["status"] != "api_error"]
    reasons = Counter(r["reason"] for r in answered if r["status"] == "invalid")

    def total(field: str):
        values = [r.get(field) for r in answered]
        return None if not values or any(v is None for v in values) else sum(values)

    return {
        "variant": variant,
        "attempts": len(answered),
        "accepted": sum(1 for r in answered if r["status"] == "accepted"),
        "invalid": sum(reasons.values()),
        "invalid_reasons": "; ".join(f"{k}={v}" for k, v in sorted(reasons.items())),
        "api_errors": sum(1 for r in records if r["status"] == "api_error"),
        "k_accepted": " ".join(str(r["k"]) for r in answered if r["status"] == "accepted"),
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "latency_s": total("latency_s"),
        "cost_usd": total("cost_usd"),
        "recorded_tokens": sum(1 for r in answered if r.get("input_tokens") is not None and r.get("output_tokens") is not None),
        "recorded_cost": sum(1 for r in answered if r.get("cost_usd") is not None),
    }


def attempts_summary(config: ExperimentConfig, profile: str) -> list[dict]:
    store = config.store()
    return [summarize_attempts(v, store.attempts(config.key(profile, v))) for v in config.variants]


def stability_rows(graph: CallGraph, runs_by_variant: dict[str, list[dict]]) -> list[dict]:
    """Distinct LLM partitions per variant and the adjusted Rand index between runs.

    Quartiles alone can hide a run that differs from the others; this table cannot.
    """
    from itertools import combinations

    from sklearn.metrics import adjusted_rand_score

    from .partition import canonical

    rows = []
    for variant, runs in runs_by_variant.items():
        labels = {
            r["run"]: tuple(canonical(r["partition"], graph.classes)[c] for c in graph.classes) for r in runs
        }
        scores = [adjusted_rand_score(labels[a], labels[b]) for a, b in combinations(sorted(labels), 2)]
        distinct: dict[tuple, list[int]] = {}
        for run, key in sorted(labels.items()):
            distinct.setdefault(key, []).append(run)
        rows.append(
            {
                "variant": variant,
                "runs": len(runs),
                "distinct_partitions": len(distinct),
                "groups_of_runs": " / ".join(",".join(map(str, g)) for g in distinct.values()),
                "mean_ari": float(np.mean(scores)) if scores else None,
                "min_ari": float(np.min(scores)) if scores else None,
            }
        )
    return rows


def stability_summary(config: ExperimentConfig, profile: str, graph: CallGraph) -> list[dict]:
    return stability_rows(graph, {v: load_accepted(config, profile, v) for v in config.variants})


def pilot_checks(graph: CallGraph, edge_check: list[dict] | None, runs_by_variant: dict[str, list[dict]],
                 attempts: list[dict]) -> dict:
    """Values behind the pilot completion criteria of the proposal (rascunho).
    `edge_check`: rows of the manual edge check stored with the graph (None: not sampled)."""
    hand = metrics_hand_check()
    accepted = [run for runs in runs_by_variant.values() for run in runs]
    checks = edge_check or []
    confirmed = Counter((row.get("confirmed") or "").strip().lower() for row in checks)
    return {
        "hand_check": {"matched": sum(r["match"] for r in hand), "total": len(hand)},
        "coverage": {
            "covering": sum(1 for run in accepted if set(run["partition"]) == set(graph.classes)),
            "accepted": len(accepted),
            "classes": graph.n_classes,
        },
        "recorded": {
            "answered": sum(a["attempts"] for a in attempts),
            "with_tokens": sum(a["recorded_tokens"] for a in attempts),
            "with_cost": sum(a["recorded_cost"] for a in attempts),
        },
        "stability": [
            {k: row[k] for k in ("variant", "runs", "distinct_partitions")}
            for row in stability_rows(graph, runs_by_variant)
        ],
        "edge_sample": {"total": len(checks), "yes": confirmed["yes"], "no": confirmed["no"], "unchecked": confirmed[""]},
    }


def _criteria(config: ExperimentConfig, profile: str, attempts: list[dict]) -> list[dict]:
    graph = config.graph()
    runs = {v: load_accepted(config, profile, v) for v in config.variants}
    edge_check = (config.store().graph_doc(config.app) or {}).get("edge_check")
    c = pilot_checks(graph, edge_check, runs, attempts)
    hand, coverage, recorded, edges = c["hand_check"], c["coverage"], c["recorded"], c["edge_sample"]
    return [
        {"criterion": "Metric code reproduces the hand calculation (docs/metrics_worked_example.md)",
         "status": f"{hand['matched']} of {hand['total']} values match"},
        {"criterion": "Every accepted run assigns each class to exactly one service",
         "status": f"{coverage['covering']} of {coverage['accepted']} accepted runs cover the {coverage['classes']} classes"},
        {"criterion": "Time, tokens and cost recorded per attempt",
         "status": f"time and tokens: {recorded['with_tokens']} of {recorded['answered']} attempts; "
                   f"cost: {recorded['with_cost']} of {recorded['answered']}"},
        {"criterion": "Variation among runs informs whether 10 runs per application suffice",
         "status": "; ".join(
             f"{row['variant']}: {row['distinct_partitions']} distinct partition(s) in {row['runs']} runs"
             for row in c["stability"]
         ) + " (researcher's decision)"},
        {"criterion": f"Edge sample checked in the source code ({edges['total']} edges, edge_check.csv)",
         "status": f"yes: {edges['yes']}, no: {edges['no']}, not checked: {edges['unchecked']}"},
    ]


def write_report(config: ExperimentConfig, profile: str) -> Path:
    """Store the summaries and report.md in the evaluation; return the path of the readable copy."""
    store = config.store()
    key = config.key(profile)
    evaluation = store.evaluation(key)
    if evaluation is None:
        raise RuntimeError(f"No evaluation of {config.name}/{config.app}/{profile}; run evaluate first")
    metrics = store.metrics(key)
    differences = evaluation.get("paired_differences", [])
    selection = evaluation.get("ah_selection", [])
    attempts = attempts_summary(config, profile)

    long_rows, wide_rows = [], []
    for variant, method in sorted({(r["variant"], r["method"]) for r in metrics if r["variant"]}):
        group = [r for r in metrics if r["variant"] == variant and r["method"] == method]
        wide = {"variant": variant, "method": method, "n": len(group)}
        for name in ("k", *METRICS):
            values = [v for v in (_number(r[name]) for r in group) if v is not None]
            if values:
                stats = describe_values(values)
                long_rows.append({"variant": variant, "method": method, "metric": name, **stats})
                wide[name] = _cell(stats)
        wide_rows.append(wide)

    diff_long, diff_wide = [], []
    for variant, control in sorted({(r["variant"], r["control"]) for r in differences}):
        group = [r for r in differences if r["variant"] == variant and r["control"] == control]
        wide = {"variant": variant, "control": group[0]["control_method"], "n": len(group)}
        for name in METRICS:
            values = [v for v in (_number(r[f"d_{name}"]) for r in group) if v is not None]
            if values:
                stats = describe_values(values)
                signs = {"positive": sum(v > 0 for v in values), "negative": sum(v < 0 for v in values),
                         "zero": sum(v == 0 for v in values)}
                diff_long.append({"variant": variant, "control": control, "metric": name, **stats, **signs})
                wide[f"d_{name}"] = f"{_cell(stats)} (+{signs['positive']}/-{signs['negative']}/0:{signs['zero']})"
        diff_wide.append(wide)

    hdbscan = [{**r, **{m: _number(r[m]) for m in METRICS}} for r in metrics if r["method"].startswith("hdbscan:")]
    meta = (store.variant(config.key(profile, config.variants[0])) or {}).get("meta", {})
    llm = meta.get("llm", {})
    lines = [
        f"# Pilot report: {config.name} / {config.app} / {profile}",
        "",
        "Descriptive analysis only; no hypothesis test is run in the pilot.",
        "",
        f"- Model: {llm.get('provider', '')} `{llm.get('model', '')}`; temperature: "
        f"{llm.get('temperature') if llm.get('temperature') is not None else 'not sent (API default)'}; "
        f"request options: `{json.dumps(llm.get('request_options', {}))}`; SDK: {meta.get('sdk', '')}",
        f"- Prompt template: {meta.get('prompt_template', '')} (sha256 {meta.get('prompt_template_sha256', '')[:12]})",
        "- Cells: median [Q1; Q3]. SM: higher is better; IFN, ICP, NED: lower is better.",
        "- d = LLM value - control value in the same run, with the same K. Counts: (+positive/-negative/0:zero).",
        "",
        "## LLM attempts",
        "",
        _table(attempts, ["variant", "attempts", "accepted", "invalid", "invalid_reasons", "api_errors",
                          "k_accepted", "input_tokens", "output_tokens", "latency_s", "cost_usd"]),
        "",
        "## AH variant selection",
        "",
        _table([{**r, "median_sm": _number(r["median_sm"])} for r in selection],
               ["ah_variant", "runs", "median_sm", "selected", "rule"]),
        "",
        "## Metrics by method",
        "",
        _table(wide_rows, ["variant", "method", "n", "k", *METRICS]),
        "",
        "## Paired differences (LLM - control)",
        "",
        _table(diff_wide, ["variant", "control", "n", *(f"d_{m}" for m in METRICS)]),
        "",
        "## Run-to-run stability of the LLM partitions",
        "",
        "Runs with the same partition are grouped (runs separated by commas, groups by /). "
        "ARI: adjusted Rand index between two runs; 1 = same partition.",
        "",
        _table(stability_summary(config, profile, config.graph()),
               ["variant", "runs", "distinct_partitions", "groups_of_runs", "mean_ari", "min_ari"]),
        "",
        "## HDBSCAN (descriptive reference, outside the pairing by K)",
        "",
        _table(hdbscan, ["method", "k", *METRICS, "noise_points"]),
        "",
        "## Pilot completion criteria",
        "",
        _table(_criteria(config, profile, attempts), ["criterion", "status"]),
        "",
    ]
    text = "\n".join(lines)
    store.update_evaluation(key, {"attempts_summary": attempts, "metrics_summary": long_rows,
                                  "differences_summary": diff_long, "report_md": text})
    copy = WORK_DIR / "reports" / config.name / config.app / profile / "report.md"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(text, encoding="utf-8")
    return copy
