"""Hand-calculation check of the metric code, shown in the pilot report.

The graph and the two partitions are the ones in docs/metrics_worked_example.md, where
each value is derived by hand. tests/test_metrics.py runs the same check.
"""

from __future__ import annotations

from fractions import Fraction

from .graph import CallGraph
from .metrics import inter_partition_communication, interface_number, non_extreme_distribution, structural_modularity_exact

WORKED_GRAPH = CallGraph.build(
    "ABCDEF",
    {("A", "B"): 3, ("B", "A"): 1, ("A", "C"): 2, ("C", "D"): 1, ("D", "E"): 4, ("E", "F"): 2, ("F", "D"): 1, ("B", "E"): 1},
)
P1 = {"A": 0, "B": 0, "C": 0, "D": 1, "E": 1, "F": 2}
P2 = {"A": 0, "B": 0, "C": 1, "D": 1, "E": 1, "F": 1}

EXPECTED = [
    ("P1", "SM", Fraction(-1, 36)),
    ("P1", "IFN", Fraction(1)),
    ("P1", "ICP", Fraction(1, 3)),
    ("P1", "NED", Fraction(1)),
    ("P2", "SM", Fraction(1, 4)),
    ("P2", "IFN", Fraction(1)),
    ("P2", "ICP", Fraction(1, 5)),
    ("P2", "NED", Fraction(1)),
]


def metrics_hand_check() -> list[dict]:
    partitions = {"P1": P1, "P2": P2}
    rows = []
    for name, metric, expected in EXPECTED:
        p = partitions[name]
        if metric == "SM":
            computed = float(structural_modularity_exact(WORKED_GRAPH, p))
        elif metric == "IFN":
            computed = interface_number(WORKED_GRAPH, p)
        elif metric == "ICP":
            computed = inter_partition_communication(WORKED_GRAPH, p)
        else:
            computed = non_extreme_distribution(p)
        rows.append(
            {"partition": name, "metric": metric, "hand": str(expected), "computed": computed,
             "match": abs(computed - float(expected)) < 1e-12}
        )
    return rows
