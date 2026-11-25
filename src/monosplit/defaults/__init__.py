"""Defaults of the tool, kept in the package so they do not depend on the database or the dump.

They are the entries that cannot be deleted (configstore.PROTECTED): the experiment
`dry_run`, the application `jpetstore` it reads, the profile `fake`, the profile templates
and the prompt `decomposition_base`. The graph of `jpetstore` is not a default: extract it.
`ensure_defaults` creates each one that is missing and never touches one that exists, so
edits made on the Configuration page stay.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..prompting import sha256_text

HERE = Path(__file__).parent
PROMPTS = {"decomposition_base": HERE / "decomposition_base.txt"}


def default_documents() -> dict[str, list[dict]]:
    """Configuration documents by collection, as stored."""
    docs = {name: json.loads((HERE / f"{name}.json").read_text(encoding="utf-8")) for name in ("apps", "profiles", "experiments")}
    docs["prompts"] = []
    for name, path in PROMPTS.items():
        text = path.read_text(encoding="utf-8")
        docs["prompts"].append({"name": name, "text": text, "sha256": sha256_text(text)})
    return docs


def ensure_defaults(store, source: str = "defaults") -> list[str]:
    """Create the missing defaults in the configuration database; returns what was created.
    The dry run comes last, because it names its prompt, profile and application."""
    from ..store import CONFIG

    created = []
    docs = default_documents()
    for collection in ("apps", "prompts", "profiles", "experiments"):
        for doc in docs[collection]:
            name = doc[CONFIG[collection]]
            if store.config_doc(collection, name) is None:
                store.put_config(collection, name, doc, create=True, source=source)
                created.append(f"{collection}/{name}")
    return created
