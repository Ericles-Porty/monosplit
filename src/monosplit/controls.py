"""Control decompositions.

- AH: agglomerative hierarchical clustering (scikit-learn) on a distance between
  classes, with the dendrogram cut into exactly K clusters.
- Random: a partition drawn uniformly from all partitions of the classes into exactly
  K non-empty services.
- HDBSCAN: descriptive reference only. It chooses the number of clusters itself, so it
  stays outside the pairing by K.

Distances between classes a and b (a != b):
- calls:     1 / (1 + w(a,b) + w(b,a)), where w counts static call sites. Classes with
             no calls between them are at distance 1.
- neighbors: Jaccard distance between the closed neighbourhoods N[a] and N[b], where
             N[x] is x plus every class that calls x or is called by x.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import HDBSCAN, AgglomerativeClustering

from .graph import CallGraph
from .partition import Partition, canonical

DISTANCES = ("calls", "neighbors")
LINKAGES = ("average", "complete", "single")


@dataclass(frozen=True)
class AHVariant:
    distance: str
    linkage: str

    def __post_init__(self) -> None:
        if self.distance not in DISTANCES:
            raise ValueError(f"Unknown distance '{self.distance}'; use one of {DISTANCES}")
        if self.linkage not in LINKAGES:
            raise ValueError(f"Unknown linkage '{self.linkage}'; use one of {LINKAGES}")

    @property
    def name(self) -> str:
        return f"{self.distance}:{self.linkage}"

    @classmethod
    def parse(cls, text: str) -> AHVariant:
        distance, _, linkage = text.partition(":")
        return cls(distance, linkage)


ALL_AH_VARIANTS = tuple(AHVariant(d, l) for d in DISTANCES for l in LINKAGES)


def distance_matrix(graph: CallGraph, kind: str) -> np.ndarray:
    n = graph.n_classes
    index = {c: i for i, c in enumerate(graph.classes)}
    if kind == "calls":
        weights = np.zeros((n, n))
        for (a, b), count in graph.calls.items():
            weights[index[a], index[b]] += count
            weights[index[b], index[a]] += count
        dist = 1.0 / (1.0 + weights)
    elif kind == "neighbors":
        neighbors = graph.undirected_neighbors()
        closed = [neighbors[c] | {c} for c in graph.classes]
        dist = np.ones((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                jaccard = len(closed[i] & closed[j]) / len(closed[i] | closed[j])
                dist[i, j] = dist[j, i] = 1.0 - jaccard
    else:
        raise ValueError(f"Unknown distance '{kind}'; use one of {DISTANCES}")
    np.fill_diagonal(dist, 0.0)
    return dist


def agglomerative(graph: CallGraph, k: int, variant: AHVariant) -> Partition:
    """AH partition with exactly k services. Deterministic for a given graph."""
    n = graph.n_classes
    if not 1 <= k <= n:
        raise ValueError(f"k must be between 1 and {n}, got {k}")
    if k == n:
        return {c: i for i, c in enumerate(graph.classes)}
    if k == 1:
        return {c: 0 for c in graph.classes}
    model = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage=variant.linkage)
    labels = model.fit_predict(distance_matrix(graph, variant.distance))
    return canonical(dict(zip(graph.classes, labels.tolist())), graph.classes)


def _stirling2_rows(n: int, k: int) -> list[list[int]]:
    """S[i][j] = Stirling number of the second kind, for 0 <= i <= n, 0 <= j <= k."""
    s = [[0] * (k + 1) for _ in range(n + 1)]
    s[0][0] = 1
    for i in range(1, n + 1):
        for j in range(1, min(i, k) + 1):
            s[i][j] = j * s[i - 1][j] + s[i - 1][j - 1]
    return s


def random_partition(classes: Sequence[str], k: int, seed: int) -> Partition:
    """Uniform random partition of `classes` into exactly k non-empty services.

    Uses the recurrence S(i, j) = j S(i-1, j) + S(i-1, j-1): element i opens a new
    service with probability S(i-1, j-1) / S(i, j) and otherwise joins one of the j
    services of the first i-1 elements, chosen uniformly. Every partition into k
    services has the same probability. Python's `random` is used because the counts
    need arbitrary-precision integers.
    """
    classes = list(classes)
    n = len(classes)
    if not 1 <= k <= n:
        raise ValueError(f"k must be between 1 and {n}, got {k}")
    s = _stirling2_rows(n, k)
    rng = random.Random(seed)

    opens_service = [False] * n
    j = k
    for i in range(n, 0, -1):
        if rng.randrange(s[i][j]) < s[i - 1][j - 1]:
            opens_service[i - 1] = True
            j -= 1
    assert j == 0

    labels: list[int] = []
    opened = 0
    for i in range(n):
        if opens_service[i]:
            labels.append(opened)
            opened += 1
        else:
            labels.append(rng.randrange(opened))
    return canonical(dict(zip(classes, labels)), classes)


def hdbscan_partition(graph: CallGraph, distance: str, min_cluster_size: int = 2) -> tuple[Partition, int]:
    """HDBSCAN partition; each noise point becomes a service of its own.

    Returns the partition and the number of noise points.
    """
    labels = HDBSCAN(min_cluster_size=min_cluster_size, metric="precomputed", copy=True).fit_predict(
        distance_matrix(graph, distance)
    )
    raw: dict[str, object] = {}
    noise = 0
    for name, label in zip(graph.classes, labels.tolist()):
        if label == -1:
            raw[name] = ("noise", name)
            noise += 1
        else:
            raw[name] = label
    return canonical(raw, graph.classes), noise
