from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from monosplit.config import ExperimentConfig, LLMProfile
from monosplit.controls import ALL_AH_VARIANTS
from monosplit.graph import CallGraph
from monosplit.prompting import sha256_text
from monosplit.store import Store, open_store

DATABASE = "test"
# Copy of the prompt version decomposition_base of the tool (versions are never changed).
PROMPT_FILE = Path(__file__).parent / "fixtures" / "prompts" / "decomposition_base.txt"
PROMPT = "decomposition_base"


def seed_prompt(store: Store | None = None) -> None:
    """Store the prompt version decomposition_base in the configuration, once."""
    store = store or open_store()
    if store.config_doc("prompts", PROMPT) is None:
        text = PROMPT_FILE.read_text(encoding="utf-8")
        store.put_config("prompts", PROMPT, {"text": text, "sha256": sha256_text(text)}, create=True, source="test")


def put_graph(app: str, graph: CallGraph, store: Store | None = None) -> None:
    """Store `graph` as the extracted graph of `app` (no call sites, no metadata)."""
    store = store or open_store(DATABASE)
    store.put_graph(app, [{"class": c} for c in graph.classes],
                    [{"caller": a, "callee": b, "calls": n} for (a, b), n in graph.calls.items()], [], {})


def make_config(tmp_path: Path, graph: CallGraph, **changes) -> ExperimentConfig:
    """Experiment `test` on application `toy`, stored in the test database (mongomock)."""
    config = ExperimentConfig(
        id="test",
        name="test",
        app="toy",
        seed=7,
        accepted_runs=3,
        max_retries=3,
        max_failed_runs=3,
        variants=("original", "obfuscated"),
        database=DATABASE,
        prompt_template=PROMPT,
        llm_profile=None,
        ah_variants=ALL_AH_VARIANTS,
        ah_primary="auto",
        hdbscan_min_cluster_size=2,
    )
    config = replace(config, **changes)
    seed_prompt()
    put_graph(config.app, graph, config.store())
    return config


def fake_profile(**changes) -> LLMProfile:
    profile = LLMProfile(
        name="fake",
        provider="fake",
        model="fake",
        temperature=None,
        max_output_tokens=None,
        seed=None,
    )
    return replace(profile, **changes)
