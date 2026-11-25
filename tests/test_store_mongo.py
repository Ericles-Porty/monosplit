"""Integration tests against the MongoDB server of compose.yaml (skipped when it does not answer).

Each test works in a database of its own, monosplit_test_<random>, dropped at the end; the
main-database names (configuration, graphs) point to it too, so the study database is never
touched. These tests check what mongomock cannot vouch for: the unique indexes of the real
server, the atomic switch of evaluations and a byte-identical dump after restore.
"""

from __future__ import annotations

import uuid

import pytest

from helpers import fake_profile, make_config
from monosplit import dbtools, store
from monosplit.evaluate import evaluate
from monosplit.llm import create_client
from monosplit.runner import run_variant

pytestmark = pytest.mark.mongo


def _main(monkeypatch, name: str) -> None:
    for constant in ("DEFAULT_DATABASE", "GRAPH_DATABASE", "CONFIG_DATABASE"):
        monkeypatch.setattr(store, constant, name)


@pytest.fixture
def real(monkeypatch):
    try:
        connection = store._connect()
    except store.StoreUnavailable as error:
        pytest.skip(str(error))
    store.set_client(connection)
    name = f"monosplit_test_{uuid.uuid4().hex[:8]}"
    _main(monkeypatch, name)
    yield name
    connection.drop_database(name)
    connection.drop_database(f"{name}_copy")
    connection.close()


def _config(tmp_path, toy_graph, name, **changes):
    return make_config(tmp_path, toy_graph, database=name, graph_database=name, **changes)


def test_duplicate_attempt_is_refused_by_the_server(real, tmp_path, toy_graph):
    config = _config(tmp_path, toy_graph, real, accepted_runs=2)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    key = config.key("fake", "original")
    first = config.store().attempts(key)[0]
    with pytest.raises(store.DuplicateAttempt):
        config.store().append_attempt(key, first)
    assert [r["attempt"] for r in config.store().attempts(key)] == [1, 2]


def test_a_new_evaluation_replaces_the_old_rows(real, tmp_path, toy_graph):
    config = _config(tmp_path, toy_graph, real)
    run_variant(create_client("fake", seed=3), fake_profile(), config, "original", toy_graph)
    db = config.store().db
    first = evaluate(config, "fake")
    rows = db.metrics.count_documents({})
    second = evaluate(config, "fake")
    assert first != second
    assert db.metrics.count_documents({}) == rows
    assert db.metrics.count_documents({"evaluation_id": first}) == 0
    assert db.evaluations.find_one({})["evaluation_id"] == second


def test_dump_restore_dump_is_identical(real, tmp_path, toy_graph, monkeypatch):
    config = _config(tmp_path, toy_graph, real)
    for variant in config.variants:
        run_variant(create_client("fake", seed=3), fake_profile(), config, variant, toy_graph)
    evaluate(config, "fake")
    config.store().set_note(config.key("fake"), "checked by hand")
    counts = dbtools.dump(config.store(), tmp_path / "a")
    assert counts["prompts"] == 1 and counts["notes"] == 1 and counts["audit"] >= 2

    _main(monkeypatch, f"{real}_copy")
    copy = store.open_store(f"{real}_copy", f"{real}_copy")
    assert dbtools.restore(copy, tmp_path / "a" / real) == counts
    with pytest.raises(RuntimeError, match="not empty"):
        dbtools.restore(copy, tmp_path / "a" / real)
    dbtools.dump(copy, tmp_path / "b")
    for name in counts:
        first = (tmp_path / "a" / real / f"{name}.jsonl").read_bytes()
        assert first == (tmp_path / "b" / f"{real}_copy" / f"{name}.jsonl").read_bytes(), name
