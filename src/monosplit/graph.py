"""Class-level static call graph shared by the three decomposition methods.

Nodes are the top-level classes of the application. An edge (a, b) exists when code
of class a invokes a method or constructor of class b; its weight is the number of
static call sites. Calls inside a class are not edges, and calls to library classes
are not part of the graph.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CallGraph:
    classes: tuple[str, ...]
    calls: dict[tuple[str, str], int]

    def __post_init__(self) -> None:
        names = set(self.classes)
        if len(names) != len(self.classes):
            raise ValueError("Duplicate class names in the graph")
        if list(self.classes) != sorted(self.classes):
            raise ValueError("Classes must be sorted")
        for (caller, callee), count in self.calls.items():
            if caller not in names or callee not in names:
                raise ValueError(f"Edge {caller} -> {callee} uses a class outside the graph")
            if caller == callee:
                raise ValueError(f"Self-call on {caller}: calls inside a class are not edges")
            if not isinstance(count, int) or count <= 0:
                raise ValueError(f"Edge {caller} -> {callee} must have a positive integer count")

    @classmethod
    def build(cls, classes, calls: dict[tuple[str, str], int]) -> CallGraph:
        return cls(tuple(sorted(classes)), dict(sorted(calls.items())))

    @property
    def n_classes(self) -> int:
        return len(self.classes)

    @property
    def edges(self) -> list[tuple[str, str]]:
        """Distinct directed class pairs with at least one call, sorted."""
        return sorted(self.calls)

    @property
    def n_edges(self) -> int:
        return len(self.calls)

    @property
    def total_calls(self) -> int:
        return sum(self.calls.values())

    def symmetric_calls(self, a: str, b: str) -> int:
        return self.calls.get((a, b), 0) + self.calls.get((b, a), 0)

    def undirected_neighbors(self) -> dict[str, set[str]]:
        neighbors: dict[str, set[str]] = {c: set() for c in self.classes}
        for a, b in self.calls:
            neighbors[a].add(b)
            neighbors[b].add(a)
        return neighbors

    def rename(self, mapping: dict[str, str]) -> CallGraph:
        """Same edges and counts under new class names (used for obfuscation)."""
        if set(mapping) != set(self.classes) or len(set(mapping.values())) != len(mapping):
            raise ValueError("Mapping must be a bijection over the graph classes")
        return CallGraph.build(
            (mapping[c] for c in self.classes),
            {(mapping[a], mapping[b]): n for (a, b), n in self.calls.items()},
        )
