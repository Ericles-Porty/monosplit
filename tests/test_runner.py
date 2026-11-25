from __future__ import annotations

from dataclasses import replace

import pytest

from helpers import fake_profile, make_config
from monosplit.llm import LLMClient, LLMConfigurationError, create_client
from monosplit.llm.fake_client import FakeClient
from monosplit.runner import ATTEMPT_SEED_RULE, RunStopped, attempt_seed, run_variant
from monosplit.store import DuplicateAttempt


def attempts(config, variant="original"):
    return config.store().attempts(config.key("fake", variant))


def test_runs_until_target_accepted(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph)
    summary = run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    assert summary == {"variant": "original", "accepted": 3, "failed_runs": 0, "attempts": 3}
    store, key = config.store(), config.key("fake", "original")
    assert [r["run"] for r in store.accepted_runs(key)] == [1, 2, 3]
    assert all(store.raw(key, n)["text"] for n in (1, 2, 3))
    assert store.variant(key)["prompt_user"].count("\n- ") == toy_graph.n_classes


def test_an_attempt_is_stored_once(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    record = attempts(config)[0]
    with pytest.raises(DuplicateAttempt):
        config.store().append_attempt(config.key("fake", "original"), record)
    assert len(attempts(config)) == 1


def test_invalid_outputs_are_resent(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=2)
    run_variant(create_client("fake", invalid_first=2), fake_profile(), config, "original", toy_graph)
    log = attempts(config)
    assert [(r["run"], r["try"], r["status"]) for r in log] == [
        (1, 1, "invalid"), (1, 2, "invalid"), (1, 3, "accepted"), (2, 1, "accepted"),
    ]
    assert log[0]["reason"] == "invalid_json"


def test_failed_runs_stop_the_variant(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, max_retries=1, max_failed_runs=2)
    with pytest.raises(RunStopped, match="failed runs"):
        run_variant(create_client("fake", invalid_first=100), fake_profile(), config, "original", toy_graph)
    assert [(r["run"], r["try"]) for r in attempts(config)] == [(1, 1), (1, 2), (2, 1), (2, 2)]


def test_refusal_is_recorded(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, max_retries=0, max_failed_runs=1)
    with pytest.raises(RunStopped):
        run_variant(create_client("fake", refuse=True), fake_profile(), config, "original", toy_graph)
    assert attempts(config)[0]["reason"] == "refusal"


def test_resume_adds_only_missing_runs(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=2)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    summary = run_variant(create_client("fake"), fake_profile(), replace(config, accepted_runs=3), "original", toy_graph)
    assert summary["attempts"] == 3
    assert [r["run"] for r in attempts(config)] == [1, 2, 3]


class FailsOnce(LLMClient):
    def __init__(self):
        self.inner = create_client("fake")
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.calls == 2:
            raise ConnectionError("network down")
        return self.inner.generate(request)


def test_api_error_stops_and_resume_continues(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph)
    with pytest.raises(RunStopped, match="API error"):
        run_variant(FailsOnce(), fake_profile(), config, "original", toy_graph)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    log = attempts(config)
    assert [(r["attempt"], r["run"], r["try"], r["status"]) for r in log] == [
        (1, 1, 1, "accepted"), (2, 2, 1, "api_error"), (3, 2, 1, "accepted"), (4, 3, 1, "accepted"),
    ]


def test_resume_under_another_configuration_is_refused(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    changed = fake_profile(request_options={"effort": "high"})
    with pytest.raises(RunStopped, match="request_options"):
        run_variant(create_client("fake"), changed, replace(config, accepted_runs=2), "original", toy_graph)


class LocalFake(FakeClient):
    """The fake client behaving like a local model: per-attempt seeds and a model digest."""

    per_attempt_seed = True

    def __init__(self, digest="digest-a", fail_identity=False, config_error=False, **options):
        super().__init__(**options)
        self.digest, self.fail_identity, self.config_error, self.seeds = digest, fail_identity, config_error, []

    def model_identity(self, model):
        if self.fail_identity:
            raise ConnectionError("connection refused")
        return {"server": "test", "digest": self.digest}

    def generate(self, request):
        if self.config_error:
            raise LLMConfigurationError("the prompt does not fit in num_ctx", "request")
        self.seeds.append(request.seed)
        return super().generate(request)


def test_local_models_get_a_seed_per_attempt(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=2)
    client = LocalFake(invalid_first=1)
    run_variant(client, fake_profile(), config, "original", toy_graph)
    log = attempts(config)
    expected = [attempt_seed(config, "fake", "original", n) for n in (1, 2, 3)]
    assert [r["seed"] for r in log] == client.seeds == expected  # the re-sent invalid output gets a new seed too
    assert len(set(expected)) == 3 and all(0 <= s < 2**31 for s in expected)
    # Another experiment with the same master seed draws other samples.
    assert attempt_seed(replace(config, name="other"), "fake", "original", 1) != expected[0]
    meta = config.store().variant(config.key("fake", "original"))["meta"]
    assert meta["attempt_seeds"] == ATTEMPT_SEED_RULE and meta["model_identity"]["digest"] == "digest-a"
    # A resume goes on with the seeds of the next attempts.
    resumed = LocalFake()
    run_variant(resumed, fake_profile(), replace(config, accepted_runs=3), "original", toy_graph)
    assert resumed.seeds == [attempt_seed(config, "fake", "original", 4)]
    with pytest.raises(LLMConfigurationError, match="seed"):
        run_variant(LocalFake(), fake_profile(seed=5), replace(config, accepted_runs=4), "original", toy_graph)


def test_cloud_runs_record_no_seed_and_no_identity(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    run_variant(create_client("fake"), fake_profile(), config, "original", toy_graph)
    assert "seed" not in attempts(config)[0]
    meta = config.store().variant(config.key("fake", "original"))["meta"]
    assert "model_identity" not in meta and "attempt_seeds" not in meta


def test_resume_with_other_weights_is_refused(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    run_variant(LocalFake(digest="digest-a"), fake_profile(), config, "original", toy_graph)
    with pytest.raises(RunStopped, match="model_digest"):
        run_variant(LocalFake(digest="digest-b"), fake_profile(), replace(config, accepted_runs=2), "original", toy_graph)


def test_configuration_error_on_the_first_call_leaves_nothing(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    store, key = config.store(), config.key("fake", "original")
    with pytest.raises(LLMConfigurationError):
        run_variant(LocalFake(config_error=True), fake_profile(), config, "original", toy_graph)
    assert store.variant(key) is None and attempts(config) == []  # the profile stays editable
    with pytest.raises(RunStopped, match="did not answer"):
        run_variant(LocalFake(fail_identity=True), fake_profile(), config, "original", toy_graph)
    assert store.variant(key) is None
    # A variant that already has attempts is evidence and stays.
    run_variant(LocalFake(), fake_profile(), config, "original", toy_graph)
    with pytest.raises(LLMConfigurationError):
        run_variant(LocalFake(config_error=True), fake_profile(), replace(config, accepted_runs=2), "original", toy_graph)
    assert store.variant(key) is not None and len(attempts(config)) == 1


def test_obfuscated_runs_are_stored_in_class_names(tmp_path, toy_graph):
    config = make_config(tmp_path, toy_graph, accepted_runs=1)
    run_variant(create_client("fake"), fake_profile(), config, "obfuscated", toy_graph)
    store, key = config.store(), config.key("fake", "obfuscated")
    run = store.accepted_runs(key)[0]
    assert set(run["partition"]) == set(toy_graph.classes)
    assert all(name.startswith("C") for s in run["services"] for name in s["prompt_names"])
    assert set(store.alias_map(key).values()) == set(toy_graph.classes)
    prompt = store.variant(key)["prompt_user"]
    assert "- A\n" not in prompt and "- C01" in prompt
