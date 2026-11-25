"""Defaults of the tool: created in an empty database, never overwritten, never deletable."""

from __future__ import annotations

import monosplit.configstore as configstore
from monosplit.config import load_config, load_profile
from monosplit.defaults import default_documents, ensure_defaults
from monosplit.prompting import load_prompt
from monosplit.store import open_store


def test_defaults_fill_an_empty_database():
    store = open_store()
    created = ensure_defaults(store)
    assert "experiments/dry_run" in created and "prompts/decomposition_base" in created and "profiles/fake" in created
    config = load_config("dry_run")
    assert (config.prompt_template, config.llm_profile, config.database) == ("decomposition_base", "fake", "monosplit_dry_run")
    assert load_profile("fake").provider == "fake"
    load_prompt("decomposition_base")
    assert ensure_defaults(store) == []


def test_defaults_keep_edits():
    store = open_store()
    ensure_defaults(store)
    doc = store.config_doc("experiments", "dry_run")
    store.put_config("experiments", "dry_run", {**doc, "accepted_runs": 2}, create=False, source="test")
    ensure_defaults(store)
    assert store.config_doc("experiments", "dry_run")["accepted_runs"] == 2


def test_every_default_is_protected():
    for collection, docs in default_documents().items():
        for doc in docs:
            name = doc.get("id") or doc["name"]
            assert configstore.is_protected(collection, name), (collection, name)
