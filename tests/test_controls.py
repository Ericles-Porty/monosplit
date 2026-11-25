from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from monosplit.controls import (
    ALL_AH_VARIANTS,
    AHVariant,
    _stirling2_rows,
    agglomerative,
    distance_matrix,
    hdbscan_partition,
    random_partition,
)
from monosplit.partition import n_services


def test_stirling_numbers():
    s = _stirling2_rows(6, 6)
    assert [s[4][k] for k in range(5)] == [0, 1, 7, 6, 1]
    assert s[6][3] == 90


@pytest.mark.parametrize("k", [1, 2, 3, 5, 6])
def test_random_partition_has_exactly_k_services(k):
    classes = list("ABCDEF")
    for seed in range(50):
        partition = random_partition(classes, k, seed)
        assert set(partition) == set(classes)
        assert n_services(partition) == k


def test_random_partition_is_reproducible():
    classes = [f"C{i}" for i in range(24)]
    assert random_partition(classes, 5, 123) == random_partition(classes, 5, 123)
    assert random_partition(classes, 5, 123) != random_partition(classes, 5, 124)


def test_random_partition_is_uniform():
    # 4 elements into 2 services: S(4, 2) = 7 partitions, each with probability 1/7.
    classes = list("ABCD")
    counts = Counter(tuple(sorted(random_partition(classes, 2, seed).items())) for seed in range(14000))
    assert len(counts) == 7
    assert all(1800 <= c <= 2200 for c in counts.values()), counts


def test_random_partition_with_k_close_to_n():
    classes = [f"C{i}" for i in range(40)]
    assert n_services(random_partition(classes, 38, 7)) == 38


def test_calls_distance(toy_graph):
    d = distance_matrix(toy_graph, "calls")
    i = {c: n for n, c in enumerate(toy_graph.classes)}
    assert d[i["A"], i["B"]] == pytest.approx(1 / 5)  # 3 + 1 calls
    assert d[i["A"], i["F"]] == pytest.approx(1.0)
    assert np.allclose(d, d.T) and np.all(np.diag(d) == 0)


def test_neighbors_distance(toy_graph):
    d = distance_matrix(toy_graph, "neighbors")
    i = {c: n for n, c in enumerate(toy_graph.classes)}
    # N[A] = {A, B, C}; N[B] = {A, B, E}: Jaccard 2/4.
    assert d[i["A"], i["B"]] == pytest.approx(0.5)
    assert np.allclose(d, d.T) and np.all(np.diag(d) == 0)


@pytest.mark.parametrize("variant", ALL_AH_VARIANTS, ids=lambda v: v.name)
@pytest.mark.parametrize("k", [1, 2, 3, 4, 6])
def test_agglomerative_has_exactly_k_services(toy_graph, variant, k):
    partition = agglomerative(toy_graph, k, variant)
    assert n_services(partition) == k
    assert agglomerative(toy_graph, k, variant) == partition


def test_agglomerative_groups_connected_classes(toy_graph):
    partition = agglomerative(toy_graph, 2, AHVariant("calls", "average"))
    assert partition["A"] == partition["B"] == partition["C"]
    assert partition["D"] == partition["E"] == partition["F"]


def test_variant_parsing():
    assert AHVariant.parse("neighbors:single") == AHVariant("neighbors", "single")
    with pytest.raises(ValueError):
        AHVariant.parse("calls:ward")


def test_hdbscan_assigns_every_class(toy_graph):
    partition, noise = hdbscan_partition(toy_graph, "calls", min_cluster_size=2)
    assert set(partition) == set(toy_graph.classes)
    assert 0 <= noise <= toy_graph.n_classes
