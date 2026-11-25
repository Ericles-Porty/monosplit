"""Partitions of the graph classes into services.

A partition maps each class to a service index 0..K-1. Indices are canonical: services
are numbered by the first class, in graph order, that belongs to them, so two equal
partitions have equal mappings.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence

Partition = dict[str, int]


def canonical(labels: Mapping[str, Hashable], order: Sequence[str]) -> Partition:
    if set(labels) != set(order):
        raise ValueError("Labels must cover exactly the classes in `order`")
    index: dict[Hashable, int] = {}
    result: Partition = {}
    for name in order:
        label = labels[name]
        if label not in index:
            index[label] = len(index)
        result[name] = index[label]
    return result


def n_services(partition: Partition) -> int:
    return len(set(partition.values()))


def services(partition: Partition) -> list[list[str]]:
    """Classes of each service, by service index; classes sorted inside each service."""
    k = n_services(partition)
    if sorted(set(partition.values())) != list(range(k)):
        raise ValueError("Service indices must be 0..K-1")
    groups: list[list[str]] = [[] for _ in range(k)]
    for name, service in partition.items():
        groups[service].append(name)
    return [sorted(g) for g in groups]


def sizes(partition: Partition) -> list[int]:
    return [len(g) for g in services(partition)]
