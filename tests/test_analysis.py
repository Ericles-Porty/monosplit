from __future__ import annotations

import numpy as np
import pytest

from monosplit.analysis import cliffs_delta, cliffs_magnitude, comparisons, criterion, holm, paired_comparison


def test_holm_matches_hand_calculation():
    # Sorted p: 0.005, 0.01, 0.03, 0.04 -> 0.02, 0.03, 0.06, max(0.06, 0.04) = 0.06.
    assert holm([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])


def test_cliffs_delta():
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0
    assert cliffs_delta([4, 5], [1, 2]) == 1
    assert cliffs_delta([1, 2], [4, 5]) == -1
    # 3 > 2, 3 < 4, 1 < 2, 1 < 4: (1 - 3) / 4.
    assert cliffs_delta([3, 1], [2, 4]) == pytest.approx(-0.5)


@pytest.mark.parametrize(
    "delta, label",
    [(0.1, "negligible"), (-0.146, "negligible"), (0.147, "small"), (0.32, "small"),
     (-0.33, "medium"), (0.473, "medium"), (0.474, "large"), (-1.0, "large")],
)
def test_romano_thresholds(delta, label):
    assert cliffs_magnitude(delta) == label


def test_normal_differences_use_the_paired_t_test():
    rng = np.random.default_rng(0)
    control = rng.uniform(0, 1, 40)
    result = paired_comparison(control + rng.normal(0.1, 0.05, 40), control)
    assert result.normal and result.test == "t"
    assert result.p_value < 0.001


def test_skewed_differences_use_wilcoxon():
    rng = np.random.default_rng(1)
    control = rng.uniform(0, 1, 40)
    result = paired_comparison(control + rng.exponential(0.05, 40) ** 3, control)
    assert result.normal is False and result.test == "wilcoxon"


def test_identical_samples_have_no_test():
    result = paired_comparison([0.1, 0.2, 0.3], [0.1, 0.2, 0.3])
    assert result.test == "none" and result.p_value == 1.0


def test_constant_shift_uses_wilcoxon():
    result = paired_comparison([1.1, 2.1, 3.1, 4.1, 5.1], [1, 2, 3, 4, 5])
    assert result.test == "wilcoxon"
    assert result.p_value == pytest.approx(0.0625)


def _shifted(shift: float, n: int = 12) -> tuple[list[float], list[float]]:
    control = [i / n for i in range(n)]
    return [c + shift for c in control], control


def test_comparisons_adjust_every_tested_pair_with_holm():
    pairs = {
        ("ah", "sm"): _shifted(0.2),
        ("ah", "ifn"): _shifted(0.0),
        ("ah", "icp"): ([0.1, 0.2], [0.3, 0.4]),
    }
    rows = comparisons(pairs)
    assert [r["test"] for r in rows] == ["wilcoxon", "none", "insufficient"]
    assert rows[0]["p_holm"] == pytest.approx(holm([rows[0]["p_value"], 1.0])[0])
    assert rows[2]["p_value"] is None and rows[2]["p_holm"] is None and not rows[2]["significant"]


def test_favours_reads_the_preferred_direction_of_each_metric():
    higher = comparisons({("ah", "sm"): _shifted(0.2), ("ah", "icp"): _shifted(0.2)})
    assert [r["favours"] for r in higher] == ["llm", "control"]
    lower = comparisons({("ah", "icp"): _shifted(-0.2)})
    assert lower[0]["favours"] == "llm"


def test_criterion_needs_sm_in_favour_of_the_llm_and_nothing_against_it_in_ifn_and_icp():
    good = comparisons({("ah", "sm"): _shifted(0.2), ("ah", "ifn"): _shifted(-0.2), ("ah", "icp"): _shifted(0.0)})
    assert criterion(good)["ah"] == {
        "sm_favours_llm": True, "sm_effect_at_least_small": True, "no_unfavourable_ifn_icp": True,
        "no_unfavourable_ned": True, "llm_superior": True, "llm_superior_roteiro": True,
    }
    worse_icp = comparisons({("ah", "sm"): _shifted(0.2), ("ah", "icp"): _shifted(0.2)})
    assert criterion(worse_icp)["ah"]["no_unfavourable_ifn_icp"] is False
    assert criterion(worse_icp)["ah"]["llm_superior"] is False
    assert criterion(worse_icp)["ah"]["llm_superior_roteiro"] is False
    assert criterion(comparisons({("random", "sm"): ([0.1], [0.0])}))["random"] is None


def test_criterion_with_ned_fails_when_ned_favours_the_control_and_the_roteiro_criterion_does_not():
    worse_ned = comparisons({("ah", "sm"): _shifted(0.2), ("ah", "ned"): _shifted(0.2)})
    result = criterion(worse_ned)["ah"]
    assert result["no_unfavourable_ned"] is False
    assert result["llm_superior"] is False
    assert result["llm_superior_roteiro"] is True
    better_ned = comparisons({("ah", "sm"): _shifted(0.2), ("ah", "ned"): _shifted(-0.2)})
    assert criterion(better_ned)["ah"]["llm_superior"] is True
