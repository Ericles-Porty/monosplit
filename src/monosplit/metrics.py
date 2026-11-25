"""Structural quality of a decomposition: SM, IFN, ICP and NED.

Definitions follow Weerasinghe et al. (2026). The counting rules below were fixed in the
pilot (see docs/decisions.md). For a partition with M services, where m_i is the number
of classes of service i:

SM  = (1/M) * sum_i mu_i / m_i^2  -  (1 / (M(M-1)/2)) * sum_{i != j} gamma_ij / (2 m_i m_j)
      mu_i     distinct directed edges between classes of service i
      gamma_ij distinct directed edges from a class of service i to a class of service j,
               summed over ordered pairs (i, j); this equals summing
               (gamma_ij + gamma_ji) / (2 m_i m_j) over unordered pairs.
      The denominators are the largest possible numbers of edges, so each term is an
      edge density and SM lies in [-1, 1]. SM is undefined for M = 1.
IFN = (1/M) * sum_i ifn_i, where ifn_i is the number of classes of service i that are
      called by at least one class of another service.
ICP = static calls between classes of different services / all static calls in the graph.
NED = 1 - n_ne / M, where n_ne is the number of services with 5 to 20 classes.

Computations use exact fractions and return floats.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from .graph import CallGraph
from .partition import Partition, canonical, sizes

NON_EXTREME_MIN = 5
NON_EXTREME_MAX = 20


@dataclass(frozen=True)
class Metrics:
    k: int
    sm: float
    ifn: float
    icp: float
    ned: float


def _canonical(graph: CallGraph, partition: Partition) -> Partition:
    if set(partition) != set(graph.classes):
        missing = sorted(set(graph.classes) - set(partition))
        extra = sorted(set(partition) - set(graph.classes))
        raise ValueError(f"Partition does not cover the graph classes (missing {missing}, extra {extra})")
    return canonical(partition, graph.classes)


def sm_terms(graph: CallGraph, partition: Partition) -> tuple[list[int], list[int], dict[tuple[int, int], int]]:
    """Return m_i, mu_i and gamma_ij (ordered pairs) for a canonical partition."""
    p = _canonical(graph, partition)
    m = sizes(p)
    mu = [0] * len(m)
    gamma: dict[tuple[int, int], int] = defaultdict(int)
    for a, b in graph.edges:
        i, j = p[a], p[b]
        if i == j:
            mu[i] += 1
        else:
            gamma[(i, j)] += 1
    return m, mu, dict(gamma)


def structural_modularity_exact(graph: CallGraph, partition: Partition) -> Fraction | None:
    m, mu, gamma = sm_terms(graph, partition)
    big_m = len(m)
    if big_m < 2:
        return None
    cohesion = sum((Fraction(mu[i], m[i] ** 2) for i in range(big_m)), Fraction(0)) / big_m
    coupling = sum((Fraction(g, 2 * m[i] * m[j]) for (i, j), g in gamma.items()), Fraction(0))
    coupling /= Fraction(big_m * (big_m - 1), 2)
    return cohesion - coupling


def structural_modularity(graph: CallGraph, partition: Partition) -> float:
    value = structural_modularity_exact(graph, partition)
    return math.nan if value is None else float(value)


def interface_classes(graph: CallGraph, partition: Partition) -> set[str]:
    """Classes called by at least one class of another service."""
    p = _canonical(graph, partition)
    return {b for a, b in graph.edges if p[a] != p[b]}


def interface_number(graph: CallGraph, partition: Partition) -> float:
    p = _canonical(graph, partition)
    # sum_i ifn_i is the number of interface classes, since each class is in one service.
    return float(Fraction(len(interface_classes(graph, p)), len(set(p.values()))))


def inter_partition_communication(graph: CallGraph, partition: Partition) -> float:
    p = _canonical(graph, partition)
    total = graph.total_calls
    if total == 0:
        return math.nan
    cross = sum(n for (a, b), n in graph.calls.items() if p[a] != p[b])
    return float(Fraction(cross, total))


def non_extreme_distribution(
    partition: Partition, low: int = NON_EXTREME_MIN, high: int = NON_EXTREME_MAX
) -> float:
    service_sizes = sizes(canonical(partition, sorted(partition)))
    non_extreme = sum(1 for s in service_sizes if low <= s <= high)
    return float(1 - Fraction(non_extreme, len(service_sizes)))


def compute(graph: CallGraph, partition: Partition) -> Metrics:
    p = _canonical(graph, partition)
    return Metrics(
        k=len(set(p.values())),
        sm=structural_modularity(graph, p),
        ifn=interface_number(graph, p),
        icp=inter_partition_communication(graph, p),
        ned=non_extreme_distribution(p),
    )
