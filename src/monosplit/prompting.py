"""Prompt template, rendering and the obfuscated variant.

Variants:
- original: class names as in the code (package and class).
- obfuscated: every class renamed to C01, C02, ... in a seeded random order, so the
  aliases do not follow the packages. Edges and call counts are unchanged.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

from .graph import CallGraph

VARIANTS = ("original", "obfuscated")
_SECTION = re.compile(r"^### (system|user)[ \t]*$", re.MULTILINE)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system: str
    user: str
    sha256: str  # of the whole template text, as stored

    @classmethod
    def parse(cls, name: str, text: str) -> PromptTemplate:
        parts = _SECTION.split(text)
        sections = dict(zip(parts[1::2], (p.strip() for p in parts[2::2])))
        if set(sections) != {"system", "user"}:
            raise ValueError(f"Prompt {name} must have one '### system' and one '### user' section")
        return cls(name=name, system=sections["system"], user=sections["user"], sha256=sha256_text(text))

    @classmethod
    def load(cls, path: Path) -> PromptTemplate:
        """A template from a text file (the earlier layout, prompts/<name>.txt)."""
        return cls.parse(path.stem, path.read_text(encoding="utf-8"))

    def render(self, graph: CallGraph) -> tuple[str, str]:
        values = {
            "class_count": graph.n_classes,
            "class_list": "\n".join(f"- {c}" for c in graph.classes),
            "edge_count": graph.n_edges,
            "call_count": graph.total_calls,
            "edge_list": "\n".join(f"{a} -> {b}: {n}" for (a, b), n in sorted(graph.calls.items())),
        }
        return Template(self.system).substitute(values), Template(self.user).substitute(values)


def load_prompt(name: str) -> PromptTemplate:
    """A prompt version stored in the database (collection `prompts`)."""
    from .store import open_store

    doc = open_store().config_doc("prompts", name)
    if doc is None:
        raise ValueError(f"No prompt version {name!r} in the database")
    return PromptTemplate.parse(name, doc["text"])


def obfuscation_map(classes: list[str] | tuple[str, ...], seed: int) -> dict[str, str]:
    """class name -> alias (C01, C02, ...), assigned in a seeded random order."""
    width = max(2, len(str(len(classes))))
    shuffled = list(classes)
    random.Random(seed).shuffle(shuffled)
    return {name: f"C{i + 1:0{width}d}" for i, name in enumerate(shuffled)}


def variant_graph(graph: CallGraph, variant: str, seed: int) -> tuple[CallGraph, dict[str, str]]:
    """The graph as sent to the LLM, and the mapping prompt name -> class name."""
    if variant == "original":
        return graph, {c: c for c in graph.classes}
    if variant == "obfuscated":
        mapping = obfuscation_map(graph.classes, seed)
        return graph.rename(mapping), {alias: name for name, alias in mapping.items()}
    raise ValueError(f"Unknown variant '{variant}'; use one of {VARIANTS}")
