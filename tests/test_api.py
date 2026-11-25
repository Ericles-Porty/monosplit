"""Payloads, HTTP API and static export, on a data folder produced with the fake client."""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from helpers import fake_profile, make_config
from monosplit.api import payloads
from monosplit.api.export import MARKER, STATIC_FLAG, export_site
from monosplit.api.layout import force_layout
from monosplit.api.server import create_app
from monosplit.evaluate import evaluate
from monosplit.llm import create_client
from monosplit.metrics import interface_classes
from monosplit.runner import run_variant
from monosplit.store import study_key

STUDY = ("test", "toy", "fake")


@pytest.fixture
def data_dir(tmp_path, toy_graph):
    """The test database with two variants of three runs, evaluated (name kept from the file layout)."""
    config = make_config(tmp_path, toy_graph)
    for variant in config.variants:
        run_variant(create_client("fake", seed=3), fake_profile(), config, variant, toy_graph)
    evaluate(config, "fake")
    return config.store()


def test_layout_is_deterministic(toy_graph):
    first = force_layout(toy_graph, seed=1)
    assert first == force_layout(toy_graph, seed=1)
    assert set(first) == set(toy_graph.classes)
    assert all(x >= 0 and y >= 0 for x, y in first.values())


def test_isolated_classes_go_below_the_drawing():
    from monosplit.graph import CallGraph

    graph = CallGraph.build("ABCDZ", {("A", "B"): 2, ("B", "C"): 1, ("C", "D"): 1})
    positions = force_layout(graph, seed=1)
    lowest_connected = max(positions[c][1] for c in "ABCD")
    assert positions["Z"][1] > lowest_connected
    # The connected part spans 90 * sqrt(n) pixels along its longer side.
    span = max(max(positions[c][0], positions[c][1]) for c in "ABCD")
    assert span == pytest.approx(90 * 5**0.5, rel=0.01)


def test_index_lists_the_study(data_dir):
    index = payloads.index_payload(data_dir)
    study = next(s for s in index["studies"] if s["id"] == "test/toy/fake")
    assert study["evaluated"] and study["has_graph"]
    assert [v["variant"] for v in study["variants"]] == ["original", "obfuscated"]
    assert all(len(v["runs"]) == 3 for v in study["variants"])
    assert next(a for a in index["apps"] if a["id"] == "toy")["graph"]["classes"] == 6


def test_graph_payload(data_dir, toy_graph):
    graph = payloads.graph_payload(data_dir, "toy")
    assert [c["id"] for c in graph["classes"]] == list(toy_graph.classes)
    assert {(e["source"], e["target"]): e["calls"] for e in graph["edges"]} == toy_graph.calls
    assert set(graph["layout"]["positions"]) == set(toy_graph.classes)


def test_run_payload_agrees_with_the_metric_files(data_dir, toy_graph):
    run = payloads.run_payload(data_dir, *STUDY, "original", 1)
    rows = data_dir.metrics(study_key(*STUDY))
    recorded = {r["method"]: r for r in rows if r["variant"] == "original" and r["run"] == 1}
    assert {d["method"] for d in run["decompositions"]} == set(recorded)
    for item in run["decompositions"]:
        row = recorded[item["method"]]
        for metric in ("sm", "ifn", "icp", "ned"):
            assert item["metrics"][metric] == pytest.approx(float(row[metric]))
        assert item["k"] == int(row["k"]) == len(item["services"])
        assert sorted(c for s in item["services"] for c in s["classes"]) == sorted(toy_graph.classes)
        assert set(item["interfaces"]) == interface_classes(toy_graph, item["assignment"])
        assert sum(e["calls"] for e in item["service_edges"]) == item["cross_calls"]
    assert run["decompositions"][0]["method"] == "llm"
    assert all(s["name"] for s in run["decompositions"][0]["services"])


def test_obfuscated_run_lists_the_names_the_model_saw(data_dir, toy_graph):
    run = payloads.run_payload(data_dir, *STUDY, "obfuscated", 1)
    assert set(run["prompt_names"]) == set(toy_graph.classes)
    assert all(alias.startswith("C") for alias in run["prompt_names"].values())


def test_study_payload_stability(data_dir):
    study = payloads.study_payload(data_dir, *STUDY)
    stability = study["variants"][0]["stability"]
    assert stability["runs"] == [1, 2, 3]
    assert [stability["ari"][i][i] for i in range(3)] == [1.0, 1.0, 1.0]
    assert set(stability["moved"]["1"]) == {"2", "3"}
    assert {r["method"] for r in study["references"]} == {"hdbscan:calls", "hdbscan:neighbors"}
    assert sum(r["selected"] for r in study["ah_selection"]) == 1


def test_moved_classes_matches_services_by_overlap():
    a = [["A", "B", "C"], ["D", "E"]]
    b = [["D", "E", "C"], ["A", "B"]]
    assert payloads.moved_classes(a, b) == ["C"]
    assert payloads.moved_classes(a, a) == []


def test_http_api(data_dir, tmp_path):
    client = TestClient(create_app(data_dir.database, web_dist=tmp_path / "missing"), base_url="http://127.0.0.1:8765")
    assert client.get("/api/index").status_code == 200
    assert client.get("/api/graph/toy").json()["app"] == "toy"
    assert client.get("/api/study/test/toy/fake").status_code == 200
    assert client.get("/api/run/test/toy/fake/obfuscated/2").json()["run"] == 2
    assert client.get("/api/run/test/toy/fake/original/99").status_code == 404
    assert client.get("/api/study/test/toy/other").status_code == 404
    assert client.get("/api/graph/..%2F..%2Fsecret").status_code == 404
    assert client.get("/api/results/test/fake").json()["id"] == "test/fake"
    assert client.get("/api/results/test/other").status_code == 404
    assert "npm run build" in client.get("/").text


def test_results_payload_is_descriptive_without_the_analysis_flag(data_dir):
    results = payloads.results_payload(data_dir, "test", "fake")
    assert results["analysis"]["inferential"] is False and results["tests"] is None
    assert results["scopes"] == ["all"] and [a["app"] for a in results["apps"]] == ["toy"]
    app = results["apps"][0]
    assert app["checks"]["coverage"] == {"covering": 6, "accepted": 6, "classes": 6}
    assert [v["accepted"] for v in app["variants"]] == [3, 3]
    # 3 runs x 2 controls x 2 variants, one summary per metric for each (variant, control).
    assert len(results["differences"]) == 12
    assert {(s["variant"], s["control"]) for s in results["difference_summaries"]} == {
        (v, c) for v in ("original", "obfuscated") for c in ("ah", "random")
    }
    # Summaries are the report's: numpy's linear quartiles over the runs.
    llm_sm = [r["sm"] for r in results["metrics"] if r["method"] == "llm" and r["variant"] == "original"]
    summary = next(s for s in results["metric_summaries"]
                   if (s["variant"], s["method"], s["metric"]) == ("original", "llm", "sm"))
    assert summary["median"] == pytest.approx(float(np.median(llm_sm)))
    assert summary["q1"] == pytest.approx(float(np.percentile(llm_sm, 25)))


def test_results_payload_runs_the_planned_tests_when_enabled(data_dir):
    results = payloads.results_payload(data_dir, "test", "fake", inferential=True)
    assert [(t["scope"], t["variant"]) for t in results["tests"]] == [("all", "original"), ("all", "obfuscated")]
    comparisons = results["tests"][0]["comparisons"]
    assert [(c["control"], c["metric"]) for c in comparisons] == [
        (c, m) for c in ("ah", "random") for m in ("sm", "ifn", "icp", "ned")
    ]
    tested = [c for c in comparisons if c["p_value"] is not None]
    assert all(c["p_holm"] >= c["p_value"] for c in tested)
    assert set(results["tests"][0]["criterion"]) == {"ah", "random"}


def test_static_export(data_dir, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head><title>x</title></head><body></body></html>", encoding="utf-8")
    out = tmp_path / "site"
    counts = export_site(out, data_dir, web_dist=dist)
    assert counts == {"graphs": 1, "studies": 1, "runs": 6, "results": 1}
    assert STATIC_FLAG in (out / "index.html").read_text(encoding="utf-8")
    run = json.loads((out / "data" / "run" / "test" / "toy" / "fake" / "original" / "1.json").read_text(encoding="utf-8"))
    assert run["run"] == 1
    results = json.loads((out / "data" / "results" / "test" / "fake.json").read_text(encoding="utf-8"))
    assert results["id"] == "test/fake" and results["tests"] is None
    assert (out / MARKER).exists()
    export_site(out, data_dir, web_dist=dist)  # a previous export can be replaced

    other = tmp_path / "not-a-site"
    other.mkdir()
    (other / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(RuntimeError):
        export_site(other, data_dir, web_dist=dist)


def test_http_api_explains_a_stopped_database(tmp_path, monkeypatch):
    from monosplit import store

    def down():
        raise store.StoreUnavailable("MongoDB does not answer. Start it with `docker compose up -d`")

    store.set_client(None)
    monkeypatch.setattr(store, "_connect", down)
    client = TestClient(create_app("monosplit", web_dist=tmp_path / "missing"), base_url="http://127.0.0.1:8765")
    answer = client.get("/api/index")
    assert answer.status_code == 503 and "docker compose up -d" in answer.json()["detail"]
