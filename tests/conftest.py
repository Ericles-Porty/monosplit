from __future__ import annotations

import pytest

from monosplit import store
from monosplit.graph import CallGraph


def pytest_configure(config):
    config.addinivalue_line("markers", "mongo: needs the MongoDB server of compose.yaml (skipped when it does not answer)")


@pytest.fixture(autouse=True)
def database():
    """Every test gets an empty in-memory MongoDB (mongomock); tests marked `mongo` replace it."""
    import mongomock

    store.set_client(mongomock.MongoClient())
    yield
    store.set_client(None)


@pytest.fixture
def toy_graph() -> CallGraph:
    """Six classes; the hand calculation is in docs/metrics_worked_example.md."""
    return CallGraph.build(
        "ABCDEF",
        {
            ("A", "B"): 3,
            ("B", "A"): 1,
            ("A", "C"): 2,
            ("C", "D"): 1,
            ("D", "E"): 4,
            ("E", "F"): 2,
            ("F", "D"): 1,
            ("B", "E"): 1,
        },
    )


@pytest.fixture
def partition_p1() -> dict[str, int]:
    """S1 = {A, B, C}, S2 = {D, E}, S3 = {F}."""
    return {"A": 0, "B": 0, "C": 0, "D": 1, "E": 1, "F": 2}


@pytest.fixture
def partition_p2() -> dict[str, int]:
    """S1 = {A, B}, S2 = {C, D, E, F}."""
    return {"A": 0, "B": 0, "C": 1, "D": 1, "E": 1, "F": 1}
