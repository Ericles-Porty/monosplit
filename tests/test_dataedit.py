"""The Data page: read-only browsing of the stored runs, the edge check, study notes, study
deletion with a backup, and the audit of every change."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from helpers import DATABASE, PROMPT, fake_profile, make_config
from monosplit import dataedit
from monosplit.api.data import attempt_payload, attempts_payload, studies_payload
from monosplit.api.jobs import JobManager
from monosplit.api.server import create_app
from monosplit.configstore import ConfigError
from monosplit.evaluate import evaluate
from monosplit.llm import create_client
from monosplit.runner import run_variant
from monosplit.store import open_store, study_key

HEADERS = {"X-MonoSplit-Request": "1"}
ROWS = [
    {"caller": "A", "callee": "B", "calls": 3, "call_sites": "A.java:3", "confirmed": "", "notes": ""},
    {"caller": "D", "callee": "E", "calls": 4, "call_sites": "D.java:9", "confirmed": "", "notes": ""},
]


@pytest.fixture
def study(tmp_path, toy_graph):
    """Experiment test, application toy, profile fake: both variants run and evaluated."""
    config = make_config(tmp_path, toy_graph, accepted_runs=2)
    open_store().put_config("experiments", "test-config", {
        "name": "test", "app": "toy", "seed": 7, "accepted_runs": 2, "database": DATABASE, "prompt_template": PROMPT,
    }, create=True, source="test")
    for variant in config.variants:
        run_variant(create_client("fake", seed=3), fake_profile(), config, variant, toy_graph)
    evaluate(config, "fake")
    open_store().put_graph("toy", [{"class": c} for c in toy_graph.classes],
                           [{"caller": a, "callee": b, "calls": n} for (a, b), n in toy_graph.calls.items()], [], {})
    open_store().set_edge_check("toy", ROWS, {"n": 2, "seed": 1})
    return config


def test_unknown_databases_are_refused(study):
    with pytest.raises(ConfigError):
        dataedit.data_store("nowhere")
    assert dataedit.data_store(DATABASE).database == DATABASE


def test_browse_studies_and_attempts(study):
    store = open_store(DATABASE)
    studies = studies_payload(store)["studies"]
    assert [s["id"] for s in studies] == ["test/toy/fake"]
    row = studies[0]
    assert {v["variant"]: v["accepted"] for v in row["variants"]} == {"original": 2, "obfuscated": 2}
    assert row["configs"] == ["test-config"] and row["evaluated_utc"]

    page = attempts_payload(store, {"variant": "obfuscated", "status": "accepted"}, 0, 1)
    assert page["total"] == 2 and len(page["rows"]) == 1
    first = page["rows"][0]
    assert "raw" not in first and "accepted" not in first
    detail = attempt_payload(store, study_key("test", "toy", "fake", "obfuscated"), first["attempt"])
    assert detail["raw"]["text"] and detail["accepted"]["partition"][0].keys() == {"class", "service"}


def test_edge_check_edits_are_checked_and_audited(study):
    result = dataedit.update_edge_check("toy", [{"row": 2, "caller": "D", "callee": "E", "confirmed": "yes", "notes": " line 9 "}])
    assert result["summary"] == {"yes": 1, "no": 0, "unchecked": 1}
    assert result["rows"][1]["notes"] == "line 9"
    rows, _ = open_store().audit_entries(collection="graphs")
    update = next(r for r in rows if r["action"] == "update")
    assert update["target"] == "toy/edge_check"
    assert update["before"][0]["confirmed"] == "" and update["after"][0] == {"row": 2, **result["rows"][1]}
    with pytest.raises(ConfigError) as info:
        dataedit.update_edge_check("toy", [{"row": 1, "caller": "D", "callee": "E", "confirmed": "no"}])
    assert info.value.conflict
    for bad in ({"row": 3, "caller": "A", "callee": "B"}, {"row": 1, "caller": "A", "callee": "B", "confirmed": "maybe"}):
        with pytest.raises(ConfigError):
            dataedit.update_edge_check("toy", [bad])


def test_study_note(study):
    key = study_key("test", "toy", "fake")
    assert dataedit.set_note(DATABASE, key, "  re-run after the prompt fix  ")["text"] == "re-run after the prompt fix"
    assert studies_payload(open_store(DATABASE))["studies"][0]["note"] == "re-run after the prompt fix"
    dataedit.set_note(DATABASE, key, "")
    assert open_store(DATABASE).note(key) is None
    actions = [r["action"] for r in open_store(DATABASE).audit_entries(collection="notes")[0]]
    assert actions == ["update", "create"]
    with pytest.raises(ConfigError):
        dataedit.set_note(DATABASE, study_key("other", "toy", "fake"), "x")


def test_delete_study_keeps_a_backup(study, tmp_path):
    key = study_key("test", "toy", "fake")
    with pytest.raises(ConfigError) as info:
        dataedit.delete_study(DATABASE, key, "test/toy", backup_root=tmp_path / "backups")
    assert info.value.field == "confirm"
    result = dataedit.delete_study(DATABASE, key, "test/toy/fake", backup_root=tmp_path / "backups")
    assert result["deleted"]["attempts"] > 0 and result["deleted"]["variants"] == 2
    store = open_store(DATABASE)
    assert store.study_counts(key) == {name: 0 for name in store.study_counts(key)}
    manifest = json.loads((tmp_path / "backups").glob("*/test/manifest.json").__next__().read_text(encoding="utf-8"))
    assert manifest["counts"]["variants"] == 2
    entry = store.audit_entries(collection="study")[0][0]
    assert entry["action"] == "delete" and entry["target"] == "test/toy/fake" and result["backup"] in entry["detail"]


def test_data_routes(study, tmp_path, monkeypatch):
    monkeypatch.setattr(dataedit, "WORK_DIR", tmp_path / "work")
    client = TestClient(create_app("monosplit", web_dist=tmp_path / "nodist", jobs=JobManager(log_dir=tmp_path / "jobs")),
                        base_url="http://127.0.0.1:8765")
    names = [d["name"] for d in client.get("/api/data/databases").json()["databases"]]
    assert {"monosplit", DATABASE} <= set(names)
    assert client.get("/api/data/nowhere/studies").status_code == 400
    assert client.get(f"/api/data/{DATABASE}/studies").json()["studies"][0]["id"] == "test/toy/fake"
    page = client.get(f"/api/data/{DATABASE}/attempts", params={"app_id": "toy", "variant": "original", "limit": 10}).json()
    assert page["total"] >= 2 and {r["variant"] for r in page["rows"]} == {"original"}
    first = page["rows"][0]["attempt"]
    assert client.get(f"/api/data/{DATABASE}/attempt/test/toy/fake/original/{first}").json()["attempt"] == first
    assert client.get(f"/api/data/{DATABASE}/attempt/test/toy/fake/original/999").status_code == 404
    edits = {"edits": [{"row": 1, "caller": "A", "callee": "B", "confirmed": "no"}]}
    assert client.put("/api/data/edge-check/toy", json=edits).status_code == 403  # write guard
    assert client.put("/api/data/edge-check/toy", json=edits, headers=HEADERS).json()["summary"]["no"] == 1
    note = client.put(f"/api/data/{DATABASE}/notes/test/toy/fake", json={"text": "ok"}, headers=HEADERS)
    assert note.json()["text"] == "ok"
    assert client.get(f"/api/data/{DATABASE}/audit").json()["rows"][0]["collection"] == "notes"
    body = {"experiment": "test", "app": "toy", "profile": "fake", "confirm": "test/toy/fake"}
    deleted = client.post(f"/api/data/{DATABASE}/studies/delete", json=body, headers=HEADERS).json()
    assert deleted["deleted"]["variants"] == 2
    assert client.get(f"/api/data/{DATABASE}/studies").json()["studies"] == []
