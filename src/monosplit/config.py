"""Experiment configurations and LLM profiles, stored in MongoDB (collections `experiments`
and `profiles` of the main database; see store.py).

An experiment configuration fixes the application, the number of runs, the variants, the
seeds, the prompt version, the controls and the analysis: descriptive or with the hypothesis
tests of the full experiment (`inferential`). An LLM profile fixes the provider, the model
and its parameters. Runs are stored in the database named by the experiment (`database`),
keyed by experiment name, application, profile name and variant.

The command line and the jobs name them: `--experiment pilot --llm gpt-5.6-luna`. Paths of
the earlier file layout (config/pilot.toml, config/llm/<profile>.toml) are accepted and
reduced to the name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from .controls import AHVariant
from .graph import CallGraph
from .llm import LLMRequest
from .prompting import VARIANTS
from .store import DEFAULT_DATABASE, GRAPH_DATABASE, Store, open_store, study_key

_DATABASE = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


def name_of(value: str) -> str:
    """'config/llm/gpt.toml' -> 'gpt', 'prompts/decomposition_v1.txt' -> 'decomposition_v1', 'pilot' -> 'pilot'."""
    value = (value or "").strip()
    if value.endswith((".toml", ".txt")) or "/" in value or "\\" in value:
        return PurePath(value.replace("\\", "/")).stem
    return value


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    source: str = ""
    accessed: str = ""

    def cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if self.input_per_mtok is None or self.output_per_mtok is None:
            return None
        if input_tokens is None or output_tokens is None:
            return None
        return (input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok) / 1_000_000


@dataclass(frozen=True)
class LLMProfile:
    name: str
    provider: str
    model: str
    temperature: float | None
    max_output_tokens: int | None
    seed: int | None
    client_options: dict[str, Any] = field(default_factory=dict)
    request_options: dict[str, Any] = field(default_factory=dict)
    pricing: Pricing = field(default_factory=Pricing)

    def request(self, system: str, user: str) -> LLMRequest:
        return LLMRequest(
            system=system,
            user=user,
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            seed=self.seed,
            options=dict(self.request_options),
        )

    def describe(self) -> dict[str, Any]:
        """Recorded with every run; contains no secrets (keys come from the environment)."""
        return {
            "profile": self.name,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "seed": self.seed,
            "client_options": self.client_options,
            "request_options": self.request_options,
            "pricing": self.pricing.__dict__,
        }


def profile_from_doc(doc: dict) -> LLMProfile:
    """The profile the runner uses, from a document of the `profiles` collection."""
    name, provider, model = doc.get("name", ""), doc.get("provider", ""), doc.get("model", "")
    if doc.get("template") or name.startswith("_"):
        raise ValueError(f"{name} is a template; create a profile from it")
    if not provider or not model or "CHANGE-ME" in (provider, model):
        raise ValueError(f"profile {name}: set the provider and the model")
    pricing = {k: v for k, v in (doc.get("pricing") or {}).items() if v is not None}
    temperature = doc.get("temperature")
    return LLMProfile(
        name=name,
        provider=provider,
        model=model,
        temperature=float(temperature) if temperature is not None else None,
        max_output_tokens=doc.get("max_output_tokens"),
        seed=doc.get("seed"),
        client_options=dict(doc.get("client") or {}),
        request_options=dict(doc.get("request") or {}),
        pricing=Pricing(**pricing),
    )


def load_profile(name: str) -> LLMProfile:
    name = name_of(name)
    doc = open_store().config_doc("profiles", name)
    if doc is None:
        raise ValueError(f"No LLM profile {name!r} in the database (Configuration page, or `monosplit db import-config`)")
    return profile_from_doc(doc)


@dataclass(frozen=True)
class ExperimentConfig:
    id: str
    name: str
    app: str
    seed: int
    accepted_runs: int
    max_retries: int
    max_failed_runs: int
    variants: tuple[str, ...]
    database: str
    prompt_template: str
    llm_profile: str | None
    ah_variants: tuple[AHVariant, ...]
    ah_primary: str
    hdbscan_min_cluster_size: int
    inferential: bool = False
    graph_database: str = GRAPH_DATABASE

    def store(self) -> Store:
        return open_store(self.database, self.graph_database)

    def key(self, profile: str, variant: str | None = None) -> dict:
        """Key of a study (or of one of its variants) in the database."""
        return study_key(self.name, self.app, profile, variant)

    def graph(self) -> CallGraph:
        graph = self.store().graph(self.app)
        if graph is None:
            raise RuntimeError(f"No graph for {self.app} in the database; run `monosplit extract {self.app}`")
        return graph


def config_from_doc(doc: dict) -> ExperimentConfig:
    """The configuration the runner uses, from a document of the `experiments` collection."""
    label = doc.get("id", "?")
    variants = tuple(doc.get("variants") or ["original"])
    unknown = set(variants) - set(VARIANTS)
    if unknown:
        raise ValueError(f"{label}: unknown variants {sorted(unknown)}")
    ah_variants = tuple(AHVariant.parse(v) for v in doc.get("ah_variants") or ["calls:average"])
    ah_primary = doc.get("ah_primary") or "auto"
    if ah_primary != "auto" and AHVariant.parse(ah_primary) not in ah_variants:
        raise ValueError(f"{label}: ah_primary {ah_primary} is not among ah_variants")
    database = doc.get("database") or DEFAULT_DATABASE
    if not isinstance(database, str) or not _DATABASE.match(database):
        raise ValueError(f"{label}: database must have 1 to 60 letters, digits, _ or -")
    inferential = doc.get("inferential", False)
    if not isinstance(inferential, bool):
        raise ValueError(f"{label}: inferential must be true or false")
    for required in ("name", "app", "seed", "accepted_runs", "prompt_template"):
        if doc.get(required) in (None, ""):
            raise ValueError(f"{label}: {required} is missing")
    return ExperimentConfig(
        id=label,
        name=doc["name"],
        app=doc["app"],
        seed=int(doc["seed"]),
        accepted_runs=int(doc["accepted_runs"]),
        max_retries=int(doc.get("max_retries", 3)),
        max_failed_runs=int(doc.get("max_failed_runs") or doc["accepted_runs"]),
        variants=variants,
        database=database,
        prompt_template=doc["prompt_template"],
        llm_profile=doc.get("llm") or None,
        ah_variants=ah_variants,
        ah_primary=ah_primary,
        hdbscan_min_cluster_size=int(doc.get("hdbscan_min_cluster_size", 2)),
        inferential=inferential,
    )


def load_config(experiment: str) -> ExperimentConfig:
    experiment = name_of(experiment)
    doc = open_store().config_doc("experiments", experiment)
    if doc is None:
        raise ValueError(
            f"No experiment configuration {experiment!r} in the database (Configuration page, or `monosplit db import-config`)"
        )
    return config_from_doc(doc)
