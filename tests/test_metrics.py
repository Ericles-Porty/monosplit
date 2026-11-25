"""Metric values checked against the hand calculation in docs/metrics_worked_example.md."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from monosplit.graph import CallGraph
from monosplit.metrics import (
    compute,
    inter_partition_communication,
    interface_classes,
    interface_number,
    non_extreme_distribution,
    sm_terms,
    structural_modularity,
    structural_modularity_exact,
)


def test_sm_terms_p1(toy_graph, partition_p1):
    m, mu, gamma = sm_terms(toy_graph, partition_p1)
    assert m == [3, 2, 1]
    assert mu == [3, 1, 0]
    assert gamma == {(0, 1): 2, (1, 2): 1, (2, 1): 1}


def test_hand_calculation_p1(toy_graph, partition_p1):
    assert structural_modularity_exact(toy_graph, partition_p1) == Fraction(-1, 36)
    assert interface_classes(toy_graph, partition_p1) == {"D", "E", "F"}
    assert interface_number(toy_graph, partition_p1) == pytest.approx(1.0)
    assert inter_partition_communication(toy_graph, partition_p1) == pytest.approx(1 / 3)
    assert non_extreme_distribution(partition_p1) == pytest.approx(1.0)


def test_hand_calculation_p2(toy_graph, partition_p2):
    assert structural_modularity_exact(toy_graph, partition_p2) == Fraction(1, 4)
    assert interface_classes(toy_graph, partition_p2) == {"C", "E"}
    assert interface_number(toy_graph, partition_p2) == pytest.approx(1.0)
    assert inter_partition_communication(toy_graph, partition_p2) == pytest.approx(1 / 5)


def test_compute_bundles_all_metrics(toy_graph, partition_p2):
    result = compute(toy_graph, partition_p2)
    assert result.k == 2
    assert result.sm == pytest.approx(0.25)
    assert result.icp == pytest.approx(0.2)
    assert result.ned == pytest.approx(1.0)


def test_service_labels_do_not_matter(toy_graph, partition_p1):
    relabelled = {c: {0: "x", 1: "y", 2: "z"}[s] for c, s in partition_p1.items()}
    assert compute(toy_graph, relabelled) == compute(toy_graph, partition_p1)


def test_sm_counts_edges_not_calls():
    one_call = CallGraph.build("XYZ", {("X", "Y"): 1, ("Y", "X"): 1})
    many_calls = CallGraph.build("XYZ", {("X", "Y"): 10, ("Y", "X"): 3})
    partition = {"X": 0, "Y": 0, "Z": 1}
    assert structural_modularity_exact(one_call, partition) == Fraction(1, 4)
    assert structural_modularity_exact(many_calls, partition) == Fraction(1, 4)


def test_icp_counts_calls():
    graph = CallGraph.build("XYZ", {("X", "Y"): 9, ("Y", "Z"): 1})
    assert inter_partition_communication(graph, {"X": 0, "Y": 0, "Z": 1}) == pytest.approx(0.1)
    assert inter_partition_communication(graph, {"X": 0, "Y": 1, "Z": 1}) == pytest.approx(0.9)


def test_sm_is_undefined_for_one_service(toy_graph):
    assert math.isnan(structural_modularity(toy_graph, {c: 0 for c in toy_graph.classes}))


def test_sm_bounds():
    complete = CallGraph.build("AB", {("A", "B"): 1, ("B", "A"): 1})
    # Two singletons fully coupled: cohesion 0, coupling 2 / (2 * 1 * 1) = 1.
    assert structural_modularity_exact(complete, {"A": 0, "B": 1}) == -1


def test_ned_counts_services_with_5_to_20_classes():
    sizes = [5, 20, 21, 4]
    classes = [f"C{i:02d}" for i in range(sum(sizes))]
    partition, start = {}, 0
    for service, size in enumerate(sizes):
        for name in classes[start:start + size]:
            partition[name] = service
        start += size
    assert non_extreme_distribution(partition) == pytest.approx(0.5)


def test_partition_must_cover_graph(toy_graph):
    with pytest.raises(ValueError):
        compute(toy_graph, {"A": 0, "B": 1})


def test_report_self_check_matches(toy_graph):
    from monosplit.selfcheck import WORKED_GRAPH, metrics_hand_check

    assert WORKED_GRAPH == toy_graph
    assert all(row["match"] for row in metrics_hand_check())
