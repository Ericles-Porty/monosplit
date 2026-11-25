"""Configuration store, import of the earlier files, cost estimate, jobs and the write guard
of the API.

The configuration lives in the in-memory MongoDB of the tests (mongomock); no test calls a
paid model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import monosplit.apps as apps_module
import monosplit.configstore as configstore
import monosplit.report as report_module
from helpers import PROMPT, PROMPT_FILE, put_graph, seed_prompt
from monosplit import dbtools
from monosplit.api.jobs import JobManager
from monosplit.api.server import create_app
from monosplit.config import load_config, load_profile
from monosplit.configstore import ConfigError
from monosplit.estimate import estimate
from monosplit.store import open_store, study_key

COMMIT = "a" * 40
FAKE = {"provider": "fake", "model": "fake", "client": {"seed": 1}}
PRICED = {
    "provider": "openai",
    "model": "gpt-test",
    "max_output_tokens": 1000,
    "client": {"api_key_env": "MONOSPLIT_TEST_UNSET_KEY"},
    "request": {"reasoning_effort": "low"},
    "pricing": {"input_per_mtok": 1.0, "output_per_mtok": 10.0, "source": "test", "accessed": "2026-11-05"},
}
# A local model on a port where nothing answers: no test reaches a real Ollama server.
LOCAL = {
    "provider": "ollama",
    "model": "m:4b",
    "max_output_tokens": 1000,
    "client": {"base_url": "http://127.0.0.1:9", "timeout_s": 5},
    "request": {"think": True, "options": {"num_ctx": 8192}},
}
TOY = {"name": "Toy", "note": "", "repository": "https://example.org/toy.git", "tag": None, "commit": COMMIT,
       "build": "maven-wrapper", "build_args": [], "source_roots": ["src"], "class_dirs": ["classes"]}


def experiment(**changes) -> dict:
    data = {
        "name": "exp",
        "app": "toy",
        "seed": 7,
        "accepted_runs": 2,
        "max_retries": 1,
        "max_failed_runs": 2,
        "variants": ["original", "obfuscated"],
        "database": "monosplit",
        "llm": None,
        "prompt_template": PROMPT,
        "ah_variants": ["calls:average", "neighbors:complete"],
        "ah_primary": "auto",
        "hdbscan_min_cluster_size": 2,
    }
    data.update(changes)
    return data


@pytest.fixture
def sandbox(tmp_path, monkeypatch, toy_graph):
    root = tmp_path / "pkg"
    store = open_store()
    store.put_config("apps", "toy", TOY, create=True, source="test")
    seed_prompt(store)
    put_graph("toy", toy_graph, store)
    for module in (configstore, report_module, apps_module):
        monkeypatch.setattr(module, "WORK_DIR", root / "work")
    monkeypatch.delenv("MONOSPLIT_TEST_UNSET_KEY", raising=False)
    return root


def fake_run_meta(experiment="exp", app="toy", profile="p1", template=PROMPT):
    """A stored variant, as a first run leaves it (no attempt yet)."""
    key = study_key(experiment, app, profile, "original")
    open_store().insert_variant(key, {"prompt_template": template}, "", "", {})


def audit(collection: str) -> list[dict]:
    rows, _ = open_store().audit_entries(collection=collection)
    return rows


# ---------------------------------------------------------------- profiles

def test_profile_roundtrip(sandbox):
    saved = configstore.save_profile("p1", {**PRICED, "note": "  chosen for the test  "}, create=True)
    assert saved["valid"] and saved["key_present"] is False
    assert saved["data"]["note"] == "chosen for the test"
    profile = load_profile("p1")
    assert (profile.model, profile.request_options, profile.pricing.output_per_mtok) == ("gpt-test", {"reasoning_effort": "low"}, 10.0)
    assert load_profile("config/llm/p1.toml") == profile  # paths of the earlier layout name the profile
    with pytest.raises(ConfigError):
        configstore.save_profile("p1", PRICED, create=True)


@pytest.mark.parametrize(
    "data, field",
    [
        ({**PRICED, "provider": "nope"}, "provider"),
        ({**PRICED, "model": " "}, "model"),
        ({**PRICED, "provider": "anthropic", "temperature": 1.0, "client": {}}, "temperature"),
        ({**PRICED, "pricing": {"input_per_mtok": 1.0}}, "pricing"),
        ({**PRICED, "client": {"unknown": 1}}, "client"),
        ({**PRICED, "provider": "openai_compatible", "client": {}}, "client"),
        ({**PRICED, "note": 3}, "note"),
        ({**LOCAL, "seed": 3}, "seed"),  # each attempt gets its own seed
        ({**LOCAL, "request": {"think": True}}, "request"),  # no num_ctx
        ({**LOCAL, "max_output_tokens": 8192}, "max_output_tokens"),
        ({**LOCAL, "request": {"options": {"num_ctx": 8192, "seed": 1}}}, "request"),
    ],
)
def test_profile_validation(sandbox, data, field):
    with pytest.raises(ConfigError) as info:
        configstore.save_profile("bad", data, create=True)
    assert info.value.field == field
    assert open_store().config_doc("profiles", "bad") is None


def test_client_numbers(sandbox):
    configstore.save_profile("zero-seed", {**FAKE, "client": {"seed": 0, "invalid_first": 0}}, create=True)
    with pytest.raises(ConfigError) as info:
        configstore.save_profile("no-timeout", {**PRICED, "client": {"timeout_s": 0}}, create=True)
    assert info.value.field == "client"


def test_profile_with_runs_is_locked(sandbox):
    configstore.save_profile("p1", PRICED, create=True)
    fake_run_meta()
    with pytest.raises(ConfigError) as info:
        configstore.save_profile("p1", {**PRICED, "model": "other"}, create=False)
    assert info.value.conflict and info.value.field == "model"
    configstore.save_profile("p1", {**PRICED, "pricing": {**PRICED["pricing"], "input_per_mtok": 2.0}}, create=False)
    with pytest.raises(ConfigError):
        configstore.delete_profile("p1")


def test_templates_are_read_only(sandbox):
    open_store().put_config("profiles", "_openai", {"template": True, "provider": "openai", "model": "CHANGE-ME"},
                            create=True, source="test")
    entry = next(p for p in configstore.list_profiles() if p["name"] == "_openai")
    assert entry["template"] and entry["valid"]
    with pytest.raises(ConfigError):
        configstore.save_profile("_openai", PRICED, create=False)
    with pytest.raises(ValueError, match="template"):
        load_profile("_openai")


def test_changes_are_audited(sandbox):
    configstore.save_profile("p1", PRICED, create=True)
    configstore.save_profile("p1", PRICED, create=False)  # unchanged: not audited
    configstore.save_profile("p1", {**PRICED, "note": "new note"}, create=False)
    configstore.delete_profile("p1")
    rows = audit("profiles")
    assert [r["action"] for r in rows] == ["delete", "update", "create"]  # newest first
    update = rows[1]
    assert (update["before"]["note"], update["after"]["note"], update["source"]) == ("", "new note", "web")
    assert "updated_utc" not in update["after"]


def test_default_profile_cannot_be_deleted(sandbox):
    configstore.save_profile("p1", FAKE, create=True)
    configstore.save_experiment("exp", experiment(llm="p1"), create=True)
    with pytest.raises(ConfigError) as info:
        configstore.delete_profile("p1")
    assert info.value.conflict
    assert load_config("exp").llm_profile == "p1"


def test_defaults_of_the_tool_cannot_be_deleted(sandbox):
    configstore.save_profile("fake", FAKE, create=True)
    open_store().put_config("profiles", "_openai", {"template": True, "provider": "openai", "model": "CHANGE-ME"},
                            create=True, source="test")
    configstore.save_experiment("dry_run", experiment(llm="fake", database="test_dry_run"), create=True)
    for delete, name in ((configstore.delete_experiment, "dry_run"), (configstore.delete_profile, "fake"),
                         (configstore.delete_profile, "_openai"), (configstore.delete_prompt, PROMPT)):
        with pytest.raises(ConfigError, match="default of the tool") as info:
            delete(name)
        assert info.value.conflict
    assert {e["id"]: e["protected"] for e in configstore.list_experiments()} == {"dry_run": True}
    assert {p["name"]: p["protected"] for p in configstore.list_profiles()} == {"fake": True, "_openai": True}
    assert next(p for p in configstore.list_prompts() if p["name"] == PROMPT)["protected"]
    # The defaults can still be edited, and other entries can be deleted.
    configstore.save_experiment("dry_run", experiment(llm="fake", database="test_dry_run", accepted_runs=3), create=False)
    configstore.save_profile("other", FAKE, create=True)
    configstore.delete_profile("other")


# ---------------------------------------------------------------- experiments

def test_experiment_roundtrip_and_lock(sandbox):
    configstore.save_experiment("exp", experiment(note="first configuration"), create=True)
    config = load_config("exp")
    assert (config.id, config.name, config.accepted_runs, config.variants) == ("exp", "exp", 2, ("original", "obfuscated"))
    assert config.prompt_template == PROMPT
    fake_run_meta()
    with pytest.raises(ConfigError) as info:
        configstore.save_experiment("exp", experiment(seed=8), create=False)
    assert info.value.conflict and info.value.field == "seed"
    configstore.save_experiment("exp", experiment(accepted_runs=3), create=False)
    assert load_config("exp").accepted_runs == 3
    # The analysis is not locked: the same runs can be read descriptively or with the tests.
    configstore.save_experiment("exp", experiment(accepted_runs=3, inferential=True), create=False)
    assert load_config("config/exp.toml").inferential is True
    assert load_config("exp").seed == 7
    entry = next(e for e in configstore.list_experiments() if e["id"] == "exp")
    assert entry["valid"] and entry["studies"] == ["exp/toy/p1"]
    with pytest.raises(ConfigError):
        configstore.delete_experiment("exp")


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"app": "missing"}, "app"),
        ({"variants": []}, "variants"),
        ({"accepted_runs": 0}, "accepted_runs"),
        ({"prompt_template": "none"}, "prompt_template"),
        ({"llm": "missing"}, "llm"),
        ({"ah_primary": "calls:single"}, "ah_primary"),
        ({"database": "../outside"}, "database"),
        ({"inferential": "yes"}, "inferential"),
    ],
)
def test_experiment_validation(sandbox, changes, field):
    with pytest.raises(ConfigError) as info:
        configstore.save_experiment("exp", experiment(**changes), create=True)
    assert info.value.field == field


# ---------------------------------------------------------------- prompts

def test_prompt_versions(sandbox):
    base = PROMPT_FILE.read_text(encoding="utf-8")
    assert configstore.next_prompt_name("decomposition_v1") == "decomposition_v2"
    created = configstore.create_prompt("decomposition_v2", base.replace("software architect", "senior software architect"))
    assert created["valid"] and created["text"].endswith("\n")
    assert configstore.next_prompt_name("decomposition_v1") == "decomposition_v3"
    with pytest.raises(ConfigError) as info:
        configstore.create_prompt("decomposition_v2", base)
    assert info.value.conflict
    preview = configstore.preview_prompt(base, "toy", "obfuscated", 7)
    assert "- C01" in preview["user"]
    fake_run_meta(experiment="other", template=PROMPT)
    with pytest.raises(ConfigError):
        configstore.delete_prompt(PROMPT)
    configstore.save_experiment("exp", experiment(prompt_template="decomposition_v2"), create=True)
    with pytest.raises(ConfigError):
        configstore.delete_prompt("decomposition_v2")
    configstore.delete_experiment("exp")
    configstore.delete_prompt("decomposition_v2")


@pytest.mark.parametrize(
    "text",
    [
        "### system\nx\n### user\n$edge_list\n",
        "### system\nx\n### user\n$class_list $edge_list $price\n",
        "no sections at all",
    ],
)
def test_prompt_checks(sandbox, text):
    with pytest.raises(ConfigError):
        configstore.check_prompt(text)


# ---------------------------------------------------------------- applications

def test_app_save_and_lock(sandbox):
    data = {"name": "Shop", "repository": "https://example.org/shop.git", "tag": "v1", "commit": "b" * 40,
            "build": "maven", "build_args": ["-B", "compile"], "source_roots": ["src/main/java"], "class_dirs": ["target/classes"]}
    configstore.save_app("shop", data, create=True)
    assert {a["id"] for a in configstore.list_apps()} == {"toy", "shop"}
    with pytest.raises(ConfigError) as info:
        configstore.save_app("shop2", {**data, "commit": "abc"}, create=True)
    assert info.value.field == "commit"
    # toy has an extracted graph in the sandbox: its commit is locked, its name is not.
    toy = next(a for a in configstore.list_apps() if a["id"] == "toy")
    toy_data = {k: toy[k] for k in ("name", "repository", "tag", "commit", "build", "build_args", "source_roots", "class_dirs")}
    open_store().put_graph("toy", [{"class": c} for c in "ABCDEF"], [], [], {"stats": {"classes": 6}})
    with pytest.raises(ConfigError) as info:
        configstore.save_app("toy", {**toy_data, "commit": "c" * 40}, create=False)
    assert info.value.conflict
    configstore.save_app("toy", {**toy_data, "name": "Toy app"}, create=False)
    assert apps_module.load_apps()["toy"].name == "Toy app"
    with pytest.raises(ConfigError):
        configstore.delete_app("toy")
    configstore.save_experiment("exp", experiment(app="shop"), create=True)
    with pytest.raises(ConfigError):
        configstore.delete_app("shop")
    configstore.delete_experiment("exp")
    configstore.delete_app("shop")


# ---------------------------------------------------------------- import of the earlier files

def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_import_config_files(tmp_path):
    root = tmp_path / "old"
    _write(root / "config" / "apps.toml",
           f'# header\n[toy]\nname = "Toy"\nnote = "pinned"\nrepository = "https://example.org/toy.git"\ncommit = "{COMMIT}"\n'
           'build = "maven-wrapper"\nsource_roots = ["src"]\nclass_dirs = ["classes"]\n')
    _write(root / "config" / "llm" / "fake.toml",
           "# Offline client for tests.\n[llm]\nprovider = \"fake\"\nmodel = \"fake\"\n\n[client]\nseed = 1\n")
    _write(root / "config" / "llm" / "_openai.toml",
           "# Template.\n[llm]\nprovider = \"openai\"\nmodel = \"CHANGE-ME\"\n# temperature = 1.0\n")
    _write(root / "config" / "exp.toml",
           "# Experiment configuration exp, saved by the monosplit interface on 2026-11-05.\n"
           "# With stored runs, name, app, seed, max_retries, prompt and database cannot change.\n\n"
           "# Why this experiment exists.\n#\n#   uv run monosplit pilot --config config/exp.toml\n"
           '[experiment]\nname = "exp"\napp = "toy"\nseed = 7          # master seed\naccepted_runs = 2\n'
           '# llm = "config/llm/<profile>.toml"\nllm = "config/llm/fake.toml"\n\n'
           '[prompt]\ntemplate = "prompts/decomposition_v1.txt"\n')
    _write(root / "prompts" / "decomposition_v1.txt", PROMPT_FILE.read_text(encoding="utf-8"))

    store = open_store()
    counts = dbtools.import_config(store, root, log=lambda _m: None)
    assert {name: c["imported"] for name, c in counts.items()} == {"apps": 1, "profiles": 2, "prompts": 1, "experiments": 1}
    config = load_config("exp")
    assert (config.llm_profile, config.prompt_template, config.max_failed_runs) == ("fake", "decomposition_v1", 2)
    assert store.config_doc("experiments", "exp")["note"] == "Why this experiment exists."
    assert store.config_doc("profiles", "fake")["note"] == "Offline client for tests."
    assert store.config_doc("profiles", "_openai")["note"] == "Template.\n\ntemperature = 1.0"
    assert store.config_doc("prompts", "decomposition_v1")["text"] == PROMPT_FILE.read_text(encoding="utf-8")
    assert [a["action"] for a in store.audit_entries(collection="experiments")[0]] == ["import"]

    again = dbtools.import_config(store, root, log=lambda _m: None)
    assert all(c["imported"] == 0 and not c["different"] for c in again.values())
    _write(root / "config" / "llm" / "fake.toml", "[llm]\nprovider = \"fake\"\nmodel = \"other\"\n")
    changed = dbtools.import_config(store, root, log=lambda _m: None)
    assert changed["profiles"]["different"] == ["fake"]
    assert load_profile("fake").model == "fake"


def test_dump_holds_the_configuration(sandbox, tmp_path):
    configstore.save_profile("p1", FAKE, create=True)
    counts = dbtools.dump(open_store(), tmp_path / "dump")
    assert counts["apps"] == 1 and counts["profiles"] == 1 and counts["prompts"] == 1
    assert counts["audit"] >= 4
    other = open_store("monosplit_other")
    assert "profiles" not in dbtools.dump(other, tmp_path / "dump")


# ---------------------------------------------------------------- estimate and jobs

def test_estimate_before_and_after_runs(sandbox):
    configstore.save_profile("priced", PRICED, create=True)
    configstore.save_experiment("exp", experiment(), create=True)
    config = load_config("exp")
    profile = load_profile("priced")
    result = estimate(config, profile, ["original"])
    row = result["variants"][0]
    assert (row["missing"], row["observed"], row["max_attempts"]) == (2, False, (2 + 2) * 2)
    assert result["max_cost_usd"] == pytest.approx(row["max_attempts"] * (row["input_tokens_per_attempt"] * 1 + 1000 * 10) / 1e6)
    assert result["key_present"] is False
    assert estimate(config, profile, ["original"])["token"] == result["token"]
    configstore.save_profile("priced", {**PRICED, "pricing": {**PRICED["pricing"], "input_per_mtok": 3.0}}, create=False)
    assert estimate(config, load_profile("priced"), ["original"])["token"] != result["token"]


def test_paid_job_needs_the_estimate_token(sandbox):
    configstore.save_profile("priced", PRICED, create=True)
    configstore.save_experiment("exp", experiment(), create=True)
    manager = JobManager(log_dir=sandbox / "work" / "jobs")
    with pytest.raises(ConfigError) as info:
        manager.submit("full", {"config": "exp", "profile": "priced"})
    assert info.value.conflict and info.value.field == "confirm"
    with pytest.raises(ConfigError) as info:
        manager.submit("full", {"config": "nope", "profile": "priced"})
    assert info.value.field == "config"
    assert manager.list() == []


def test_local_model_needs_no_key_and_no_confirmation(sandbox):
    saved = configstore.save_profile("local", LOCAL, create=True)
    assert saved["valid"] and saved["key_present"] is None
    configstore.save_experiment("exp", experiment(), create=True)
    result = estimate(load_config("exp"), load_profile("local"), ["original"])
    assert (result["paid"], result["priced"], result["expected_seconds"]) == (False, False, None)
    assert "not answering" in result["problem"]  # nothing listens on port 9
    manager = JobManager(log_dir=sandbox / "work" / "jobs")
    job = manager.submit("llm", {"config": "exp", "profile": "local"})  # no estimate token needed
    manager.wait_idle(timeout=60)
    done = manager.get(job["id"])
    assert done["status"] == "failed" and "did not answer" in done["error"]
    assert open_store().variants() == []  # nothing stored, the profile stays editable
    configstore.save_profile("local", {**LOCAL, "model": "m:9b"}, create=False)


def test_free_job_runs_to_the_report(sandbox):
    configstore.save_profile("fake", FAKE, create=True)
    configstore.save_experiment("exp", experiment(), create=True)
    manager = JobManager(log_dir=sandbox / "work" / "jobs")
    job = manager.submit("full", {"config": "exp", "profile": "fake"})
    manager.wait_idle(timeout=120)
    done = manager.get(job["id"])
    assert done["status"] == "succeeded", done["error"]
    assert done["progress"]["original"]["accepted"] == 2
    assert done["progress"]["obfuscated"]["accepted"] == 2
    assert done["result"]["report"].endswith("report.md")
    assert (sandbox / "work" / "jobs" / f"{job['id']}.log").exists()


# ---------------------------------------------------------------- HTTP and the write guard

def test_write_guard(sandbox):
    app = create_app("monosplit", web_dist=sandbox / "nodist", jobs=JobManager(log_dir=sandbox / "work" / "jobs"))
    local = TestClient(app, base_url="http://127.0.0.1:8765")
    body = {"data": FAKE, "create": True}
    assert local.put("/api/config/profiles/fake", json=body).status_code == 403
    headers = {"X-MonoSplit-Request": "1"}
    assert local.put("/api/config/profiles/fake", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    assert local.put("/api/config/profiles/fake", json=body, headers=headers).status_code == 200
    assert local.put("/api/config/profiles/fake", json=body, headers=headers).status_code == 409
    assert local.get("/api/config").json()["profiles"][0]["name"] == "fake"
    assert TestClient(app, base_url="http://evil.example").get("/api/index").status_code == 403
    answer = local.post("/api/config/models", json={"provider": "fake", "client": {}}, headers=headers).json()
    assert answer["models"] == ["fake"]
