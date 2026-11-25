"""Statistical analysis planned for the full experiment.

The pilot report is descriptive and does not call these tests. They are implemented and
unit-tested now so that the full experiment runs the plan fixed in the roteiro:

1. d = LLM value - control value for each pair (same application, same K).
2. Shapiro-Wilk test on d, alpha = 0.05.
3. Normality rejected: Wilcoxon signed-rank test (two-sided, zero differences dropped,
   as in Wilcoxon 1945). Not rejected: paired t test (two-sided).
4. Holm adjustment over the eight comparisons (four metrics x two controls).
5. Cliff's delta between the LLM values and the control values, read with the
   thresholds of Romano et al. (2006): negligible < 0.147 <= small < 0.33 <= medium
   < 0.474 <= large.
6. Comparison criterion, per control: the LLM is considered superior when SM differs
   significantly in its favour after Holm, Cliff's delta in SM is at least small, no
   significant difference favours the control in IFN or ICP, and none favours it in NED.
   The NED condition was added after the pilot (docs/decisions.md, Deviation): the
   cohesion term of SM rewards partitions with one large service and several tiny ones,
   which NED flags. The criterion of the roteiro, without it, is reported beside it.

`comparisons` runs steps 1 to 5 for every (control, metric) pair and `criterion` applies
step 6. The web interface calls them only for experiments with [analysis] inferential.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

ALPHA = 0.05


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """P(X > Y) - P(X < Y) over all pairs of one value of x and one of y."""
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if xa.size == 0 or ya.size == 0:
        raise ValueError("Both samples must be non-empty")
    diff = xa[:, None] - ya[None, :]
    return float((np.sum(diff > 0) - np.sum(diff < 0)) / diff.size)


def cliffs_magnitude(delta: float) -> str:
    size = abs(delta)
    if size < 0.147:
        return "negligible"
    if size < 0.33:
        return "small"
    if size < 0.474:
        return "medium"
    return "large"


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm (1979) step-down adjusted p-values, in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted


@dataclass
class PairedResult:
    n: int
    n_nonzero: int
    normality_p: float | None
    normal: bool | None
    test: str  # "wilcoxon", "t", or "none" when every difference is zero
    statistic: float | None
    p_value: float | None
    median_diff: float
    mean_diff: float
    cliffs_delta: float
    magnitude: str


def paired_comparison(llm: Sequence[float], control: Sequence[float], alpha: float = ALPHA) -> PairedResult:
    a, b = np.asarray(llm, dtype=float), np.asarray(control, dtype=float)
    if a.shape != b.shape or a.size < 3:
        raise ValueError("Paired samples need the same length, at least 3")
    d = a - b
    delta = cliffs_delta(a, b)
    base = {
        "n": int(d.size),
        "n_nonzero": int(np.count_nonzero(d)),
        "median_diff": float(np.median(d)),
        "mean_diff": float(np.mean(d)),
        "cliffs_delta": delta,
        "magnitude": cliffs_magnitude(delta),
    }
    if np.allclose(d, d[0]):
        # Constant differences: no variance to test normality; a zero shift is no difference.
        if np.allclose(d, 0):
            return PairedResult(normality_p=None, normal=None, test="none", statistic=None, p_value=1.0, **base)
        result = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided")
        return PairedResult(normality_p=None, normal=False, test="wilcoxon",
                            statistic=float(result.statistic), p_value=float(result.pvalue), **base)
    normality_p = float(stats.shapiro(d).pvalue)
    normal = normality_p >= alpha
    if normal:
        result = stats.ttest_rel(a, b)
        test = "t"
    else:
        result = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided")
        test = "wilcoxon"
    return PairedResult(normality_p=normality_p, normal=normal, test=test,
                        statistic=float(result.statistic), p_value=float(result.pvalue), **base)


# Preferred direction of each metric: +1 when higher is better (roteiro, dependent variables).
DIRECTION = {"sm": 1, "ifn": -1, "icp": -1, "ned": -1}
SMALL_EFFECT = 0.147
_EMPTY = {f: None for f in PairedResult.__dataclass_fields__}


def favours(result: PairedResult, metric: str) -> str:
    """Method favoured by the tested location: "llm", "control" or "none".

    The location is the mean difference for the t test and the median difference
    otherwise, read with the preferred direction of the metric.
    """
    if result.test == "none":
        return "none"
    shift = result.mean_diff if result.test == "t" else result.median_diff
    if shift == 0:
        return "none"
    return "llm" if shift * DIRECTION[metric] > 0 else "control"


def comparisons(pairs: dict[tuple[str, str], tuple[Sequence[float], Sequence[float]]],
                alpha: float = ALPHA) -> list[dict]:
    """One row per (control, metric), from LLM values and control values paired by position.

    p-values are adjusted by Holm over every comparison that has a test. A comparison
    with fewer than 3 pairs is reported with test "insufficient" and no p-value.
    """
    rows = []
    for (control, metric), (llm, other) in pairs.items():
        if len(llm) < 3:
            rows.append({"control": control, "metric": metric, **_EMPTY, "n": len(llm), "test": "insufficient",
                         "favours": "none"})
            continue
        result = paired_comparison(llm, other, alpha)
        rows.append({"control": control, "metric": metric, **asdict(result), "favours": favours(result, metric)})
    tested = [r for r in rows if r["p_value"] is not None]
    for row, adjusted in zip(tested, holm([r["p_value"] for r in tested])):
        row["p_holm"] = adjusted
        row["significant"] = adjusted < alpha
    for row in rows:
        row.setdefault("p_holm", None)
        row.setdefault("significant", False)
    return rows


def criterion(rows: list[dict]) -> dict[str, dict | None]:
    """Step 6 for each control; None when SM could not be tested."""
    out: dict[str, dict | None] = {}
    for control in dict.fromkeys(r["control"] for r in rows):
        by_metric = {r["metric"]: r for r in rows if r["control"] == control}
        sm = by_metric.get("sm")
        if sm is None or sm["test"] == "insufficient":
            out[control] = None
            continue
        first = bool(sm["significant"] and sm["favours"] == "llm")
        second = abs(sm["cliffs_delta"]) >= SMALL_EFFECT
        def no_unfavourable(metrics: tuple[str, ...]) -> bool:
            return not any(r["significant"] and r["favours"] == "control" for m, r in by_metric.items() if m in metrics)

        third = no_unfavourable(("ifn", "icp"))
        fourth = no_unfavourable(("ned",))
        out[control] = {
            "sm_favours_llm": first,
            "sm_effect_at_least_small": second,
            "no_unfavourable_ifn_icp": third,
            "no_unfavourable_ned": fourth,
            # Criterion adopted for the full experiment (with NED) and the roteiro's (without it).
            "llm_superior": first and second and third and fourth,
            "llm_superior_roteiro": first and second and third,
        }
    return out
