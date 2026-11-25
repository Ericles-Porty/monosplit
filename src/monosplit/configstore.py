"""Read, validate and write the configuration edited by the web interface. The documents
live in the main MongoDB database (collections apps, profiles, prompts and experiments;
see store.py), and every change is written to the audit collection.

Rules that keep runs reproducible:
- A profile that already has runs keeps its provider, model and request parameters; to
  change them, create another profile. Pricing, timeouts, the key variable and the note
  can change. Profiles whose name starts with "_" are read-only templates.
- An experiment with runs keeps its name, application, seed, retries, prompt and database.
- A prompt version is never overwritten; edits create a new version. A version used by a
  run or named by an experiment cannot be deleted.
- An application with an extracted graph or runs keeps its repository, commit and paths.

Every write is checked by building the object the runner uses from the new document.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from string import Template
from typing import Any

from .apps import BUILD_TYPES, app_from_doc, load_apps
from .config import config_from_doc, profile_from_doc
from .controls import ALL_AH_VARIANTS, AHVariant
from .llm import LLMConfigurationError, provider_class, providers
from .paths import WORK_DIR
from .prompting import VARIANTS, PromptTemplate, sha256_text, variant_graph
from .seeds import derive_seed
from .store import DEFAULT_DATABASE, DocumentExists, open_store, study_key

PLACEHOLDERS = {"class_count", "class_list", "edge_count", "call_count", "edge_list"}
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_APP_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REPOSITORY = re.compile(r"^(https://|git@|ssh://)\S+$")
_NOTE_LIMIT = 20_000


class ConfigError(ValueError):
    def __init__(self, message: str, field: str | None = None, conflict: bool = False) -> None:
        super().__init__(message)
        self.field = field
        self.conflict = conflict

    def payload(self) -> dict:
        return {"message": str(self), "field": self.field}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _check_name(value: str, field: str, pattern: re.Pattern = _NAME) -> str:
    if not isinstance(value, str) or not pattern.match(value) or ".." in value:
        raise ConfigError(f"Invalid name: {value!r}", field)
    return value


def _safe_relative(value: str, field: str) -> str:
    from pathlib import Path

    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value.strip():
        raise ConfigError(f"Use a relative path inside the application: {value!r}", field)
    return path.as_posix()


def _note(data: dict) -> str:
    note = data.get("note") or ""
    if not isinstance(note, str):
        raise ConfigError("The note must be text", "note")
    note = note.strip()
    if len(note) > _NOTE_LIMIT:
        raise ConfigError(f"The note is longer than {_NOTE_LIMIT} characters", "note")
    return note


# Defaults of the tool (src/monosplit/defaults): the dry run, its application, its offline
# profile, the base prompt and the profile templates. They can be
# edited (a prompt never is) but not deleted; every other entry can be deleted once nothing
# uses it.
PROTECTED = {"experiments": ("dry_run",), "apps": ("jpetstore",), "profiles": ("fake",), "prompts": ("decomposition_base",)}


def is_protected(collection: str, name: str) -> bool:
    """The defaults above and the profile templates (names starting with _)."""
    return name in PROTECTED.get(collection, ()) or (collection == "profiles" and name.startswith("_"))


def _check_deletable(collection: str, name: str, field: str) -> None:
    if is_protected(collection, name):
        raise ConfigError(f"{name} is a default of the tool and cannot be deleted", field, conflict=True)


def _put(collection: str, name: str, doc: dict, create: bool, source: str) -> dict:
    try:
        return open_store().put_config(collection, name, doc, create=create, source=source)
    except DocumentExists as error:
        raise ConfigError(str(error), "name", conflict=True) from None
    except LookupError as error:
        raise ConfigError(str(error), "name") from None


# ---------------------------------------------------------------- stored runs

def _databases() -> list[str]:
    names = {DEFAULT_DATABASE}
    for doc in open_store().config_docs("experiments"):
        database = doc.get("database")
        if isinstance(database, str) and database:
            names.add(database)
    return sorted(names)


def run_metas() -> list[dict]:
    """Every stored variant, in every database used by a configuration."""
    found = []
    for database in _databases():
        store = open_store(database)
        for doc in store.variants():
            key = study_key(doc["experiment"], doc["app"], doc["profile"], doc["variant"])
            found.append(
                {
                    "database": database,
                    **key,
                    "prompt_template": (doc.get("meta") or {}).get("prompt_template"),
                    "accepted": store.accepted_count(key),
                }
            )
    return found


def _studies(rows: list[dict]) -> list[str]:
    return sorted({f"{r['experiment']}/{r['app']}/{r['profile']}" for r in rows})


# ---------------------------------------------------------------- LLM profiles

_PROFILE_LOCKED = ("provider", "model", "temperature", "max_output_tokens", "seed", "request")


def _profile_data(doc: dict) -> dict:
    pricing = doc.get("pricing") or {}
    return {
        "provider": doc.get("provider", ""),
        "model": doc.get("model", ""),
        "temperature": doc.get("temperature"),
        "max_output_tokens": doc.get("max_output_tokens"),
        "seed": doc.get("seed"),
        "client": dict(doc.get("client") or {}),
        "request": dict(doc.get("request") or {}),
        "pricing": {
            "input_per_mtok": pricing.get("input_per_mtok"),
            "output_per_mtok": pricing.get("output_per_mtok"),
            "source": pricing.get("source", ""),
            "accessed": pricing.get("accessed", ""),
        },
        "note": doc.get("note") or "",
    }


def list_profiles() -> list[dict]:
    metas = run_metas()
    experiments = open_store().config_docs("experiments")
    rows = []
    for doc in open_store().config_docs("profiles"):
        name = doc["name"]
        template = bool(doc.get("template")) or name.startswith("_")
        entry: dict[str, Any] = {"name": name, "template": template, "data": _profile_data(doc),
                                 "updated_utc": doc.get("updated_utc"), "protected": is_protected("profiles", name)}
        if template:
            entry.update(valid=True, error=None)
        else:
            try:
                profile_from_doc(doc)
                entry.update(valid=True, error=None)
            except Exception as error:
                entry.update(valid=False, error=str(error))
        provider = entry["data"]["provider"]
        try:
            entry["key_present"] = provider_class(provider).key_present(entry["data"]["client"]) if provider else None
        except Exception:
            entry["key_present"] = None
        entry["used_by"] = _studies([m for m in metas if m["profile"] == name])
        entry["default_of"] = sorted(e["id"] for e in experiments if e.get("llm") == name)
        rows.append(entry)
    return rows


def _validate_profile(data: dict) -> dict:
    provider = data.get("provider")
    if provider not in providers():
        raise ConfigError(f"Unknown provider {provider!r}", "provider")
    cls = provider_class(provider)
    model = (data.get("model") or "").strip()
    if not model or model == "CHANGE-ME":
        raise ConfigError("Set the model", "model")

    temperature = data.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
            raise ConfigError("Temperature must be between 0 and 2, or empty for the API default", "temperature")
        if cls.accepts_temperature is False:
            raise ConfigError(f"The {provider} API does not accept a temperature; leave it empty", "temperature")
        temperature = float(temperature)
    max_tokens = data.get("max_output_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int) or not 1 <= max_tokens <= 1_000_000):
        raise ConfigError("Maximum output tokens must be an integer from 1 to 1,000,000", "max_output_tokens")
    seed = data.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise ConfigError("The seed must be an integer", "seed")
    if seed is not None and provider == "anthropic":
        raise ConfigError("The Anthropic API has no seed parameter", "seed")
    if seed is not None and cls.per_attempt_seed:
        raise ConfigError(
            f"{provider} gets a seed for each attempt, derived from the master seed of the experiment; leave the seed empty",
            "seed",
        )

    fields = {f.key: f for f in cls.client_fields}
    client = {}
    for key, value in (data.get("client") or {}).items():
        if key not in fields:
            raise ConfigError(f"Unknown client option {key!r} for {provider}", "client")
        if value in (None, ""):
            continue
        if fields[key].kind == "number":
            # Timeouts must be positive; other numbers (seeds, counters) may be zero.
            minimum_ok = value > 0 if key.endswith("timeout_s") else value >= 0
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not minimum_ok:
                raise ConfigError(f"{key} must be a {'positive' if key.endswith('timeout_s') else 'non-negative'} number", "client")
        elif not isinstance(value, str):
            raise ConfigError(f"{key} must be text", "client")
        client[key] = value
    for key, field in fields.items():
        if field.required and key not in client:
            raise ConfigError(f"{key} is required for {provider}", "client")

    request = data.get("request") or {}
    if not isinstance(request, dict):
        raise ConfigError("Request options must be a JSON object", "request")
    if provider == "anthropic" and any(k in request for k in ("temperature", "top_p", "top_k")):
        raise ConfigError("The Anthropic API rejects temperature, top_p and top_k", "request")
    try:
        json.dumps(request, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"Request options must be plain JSON values: {error}", "request") from None
    try:
        cls.validate_profile(temperature, max_tokens, seed, request)
    except LLMConfigurationError as error:
        raise ConfigError(str(error), error.field or "request") from None

    pricing = data.get("pricing") or {}
    clean_pricing: dict[str, Any] = {}
    for key in ("input_per_mtok", "output_per_mtok"):
        value = pricing.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, (int, float)) or value < 0:
            raise ConfigError(f"{key} must be a number of dollars per million tokens", "pricing")
        clean_pricing[key] = float(value)
    if bool(clean_pricing.get("input_per_mtok") is None) != bool(clean_pricing.get("output_per_mtok") is None):
        raise ConfigError("Fill both input and output prices, or neither", "pricing")
    if pricing.get("source"):
        clean_pricing["source"] = str(pricing["source"]).strip()
    if pricing.get("accessed"):
        if not _DATE.match(str(pricing["accessed"])):
            raise ConfigError("Access date must be YYYY-MM-DD", "pricing")
        clean_pricing["accessed"] = str(pricing["accessed"])
    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "seed": seed,
        "client": client,
        "request": request,
        "pricing": clean_pricing,
        "note": _note(data),
    }


def save_profile(name: str, data: dict, create: bool, source: str = "web") -> dict:
    _check_name(name, "name")
    old = open_store().config_doc("profiles", name)
    if create and old is not None:
        raise ConfigError(f"Profile {name} already exists", "name", conflict=True)
    if not create and old is None:
        raise ConfigError(f"No profile {name}", "name")
    clean = _validate_profile(data)
    if old is not None:
        used = _studies([m for m in run_metas() if m["profile"] == name])
        if used:
            before = _profile_data(old)
            if before["temperature"] is not None:
                before["temperature"] = float(before["temperature"])
            changed = [k for k in _PROFILE_LOCKED if before[k] != clean[k]]
            if changed:
                raise ConfigError(
                    f"Profile {name} already has runs ({', '.join(used)}); {', '.join(changed)} cannot change. "
                    "Create a new profile instead.",
                    changed[0],
                    conflict=True,
                )
    doc = {"name": name, "template": False, **clean}
    try:
        profile_from_doc(doc)
    except Exception as error:
        raise ConfigError(f"The profile does not load: {error}") from error
    _put("profiles", name, doc, create, source)
    return next(p for p in list_profiles() if p["name"] == name)


def delete_profile(name: str, source: str = "web") -> None:
    _check_deletable("profiles", name, "name")
    _check_name(name, "name")
    if open_store().config_doc("profiles", name) is None:
        raise ConfigError(f"No profile {name}", "name")
    used = _studies([m for m in run_metas() if m["profile"] == name])
    if used:
        raise ConfigError(f"Profile {name} has runs ({', '.join(used)}) and cannot be deleted", "name", conflict=True)
    defaults = sorted(e["id"] for e in open_store().config_docs("experiments") if e.get("llm") == name)
    if defaults:
        raise ConfigError(f"Profile {name} is the default of {', '.join(defaults)}", "name", conflict=True)
    open_store().delete_config("profiles", name, source=source)


# ---------------------------------------------------------------- experiments

_EXPERIMENT_LOCKED = ("name", "app", "seed", "max_retries", "prompt_template", "database")
_DATABASE = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


def _experiment_data(doc: dict) -> dict:
    return {
        "name": doc.get("name", ""),
        "app": doc.get("app", ""),
        "seed": doc.get("seed"),
        "accepted_runs": doc.get("accepted_runs"),
        "max_retries": doc.get("max_retries", 3),
        "max_failed_runs": doc.get("max_failed_runs"),
        "variants": list(doc.get("variants") or ["original"]),
        "database": doc.get("database") or DEFAULT_DATABASE,
        "llm": doc.get("llm"),
        "prompt_template": doc.get("prompt_template", ""),
        "ah_variants": list(doc.get("ah_variants") or ["calls:average"]),
        "ah_primary": doc.get("ah_primary", "auto"),
        "hdbscan_min_cluster_size": doc.get("hdbscan_min_cluster_size", 2),
        "inferential": doc.get("inferential", False),
        "note": doc.get("note") or "",
    }


def _experiment_runs(data: dict, metas: list[dict]) -> list[dict]:
    database = data.get("database") or DEFAULT_DATABASE
    return [m for m in metas if m["experiment"] == data.get("name") and m["database"] == database]


def list_experiments() -> list[dict]:
    metas = run_metas()
    rows = []
    for doc in open_store().config_docs("experiments"):
        entry: dict[str, Any] = {"id": doc["id"], "updated_utc": doc.get("updated_utc"),
                                 "protected": is_protected("experiments", doc["id"])}
        data = _experiment_data(doc)
        try:
            config_from_doc(doc)
            entry.update(valid=True, error=None)
        except Exception as error:
            entry.update(valid=False, error=str(error))
        runs = _experiment_runs(data, metas)
        entry.update(data=data, runs=runs, studies=_studies(runs))
        rows.append(entry)
    return rows


def _validate_experiment(data: dict) -> dict:
    store = open_store()
    name = _check_name(data.get("name", ""), "name")
    app = data.get("app", "")
    if app not in load_apps() and not (isinstance(app, str) and store.has_graph(app)):
        raise ConfigError(f"Unknown application {app!r}", "app")

    def integer(key: str, low: int, high: int) -> int:
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ConfigError(f"{key} must be an integer from {low} to {high}", key)
        return value

    seed = integer("seed", 0, 2**63 - 1)
    accepted = integer("accepted_runs", 1, 1000)
    retries = integer("max_retries", 0, 10)
    failed = integer("max_failed_runs", 1, 1000)
    variants = data.get("variants") or []
    if not variants or any(v not in VARIANTS for v in variants) or len(set(variants)) != len(variants):
        raise ConfigError(f"Variants must be a non-empty subset of {VARIANTS}", "variants")
    variants = [v for v in VARIANTS if v in variants]
    database = data.get("database") or DEFAULT_DATABASE
    if not isinstance(database, str) or not _DATABASE.match(database):
        raise ConfigError("The database name must have 1 to 60 letters, digits, _ or -", "database")
    llm = data.get("llm") or None
    if llm:
        profile = store.config_doc("profiles", llm) if isinstance(llm, str) else None
        if profile is None or profile.get("template") or llm.startswith("_"):
            raise ConfigError(f"Profile {llm} does not exist or is a template", "llm")
    template = data.get("prompt_template") or ""
    if not isinstance(template, str) or store.config_doc("prompts", template) is None:
        raise ConfigError(f"Prompt version {template!r} does not exist", "prompt_template")
    ah = data.get("ah_variants") or []
    try:
        parsed = [AHVariant.parse(v) for v in ah]
    except ValueError as error:
        raise ConfigError(str(error), "ah_variants") from error
    if not parsed:
        raise ConfigError("Choose at least one AH variant", "ah_variants")
    order = [v.name for v in ALL_AH_VARIANTS]
    ah = sorted({v.name for v in parsed}, key=order.index)
    primary = data.get("ah_primary") or "auto"
    if primary != "auto" and primary not in ah:
        raise ConfigError("The AH control must be 'auto' or one of the chosen variants", "ah_primary")
    hdbscan = integer("hdbscan_min_cluster_size", 2, 100)
    inferential = data.get("inferential", False)
    if not isinstance(inferential, bool):
        raise ConfigError("inferential must be true or false", "inferential")
    return {
        "name": name,
        "app": app,
        "seed": seed,
        "accepted_runs": accepted,
        "max_retries": retries,
        "max_failed_runs": failed,
        "variants": variants,
        "database": database,
        "llm": llm,
        "prompt_template": template,
        "ah_variants": ah,
        "ah_primary": primary,
        "hdbscan_min_cluster_size": hdbscan,
        "inferential": inferential,
        "note": _note(data),
    }


def save_experiment(experiment_id: str, data: dict, create: bool, source: str = "web") -> dict:
    _check_name(experiment_id, "id")
    old = open_store().config_doc("experiments", experiment_id)
    if create and old is not None:
        raise ConfigError(f"Configuration {experiment_id} already exists", "id", conflict=True)
    if not create and old is None:
        raise ConfigError(f"No configuration {experiment_id}", "id")
    clean = _validate_experiment(data)
    if old is not None:
        before = _experiment_data(old)
        if _experiment_runs(before, run_metas()):
            changed = [k for k in _EXPERIMENT_LOCKED if (before.get(k) or None) != (clean.get(k) or None)]
            if changed:
                raise ConfigError(
                    f"{experiment_id} already has runs; {', '.join(changed)} cannot change. Create a new configuration instead.",
                    changed[0],
                    conflict=True,
                )
    doc = {"id": experiment_id, **clean}
    try:
        config_from_doc(doc)
    except Exception as error:
        raise ConfigError(f"The configuration does not load: {error}") from error
    _put("experiments", experiment_id, doc, create, source)
    return next(e for e in list_experiments() if e["id"] == experiment_id)


def delete_experiment(experiment_id: str, source: str = "web") -> None:
    _check_name(experiment_id, "id")
    old = open_store().config_doc("experiments", experiment_id)
    if old is None:
        raise ConfigError(f"No configuration {experiment_id}", "id")
    _check_deletable("experiments", experiment_id, "id")
    if _experiment_runs(_experiment_data(old), run_metas()):
        raise ConfigError(f"{experiment_id} has runs and cannot be deleted", "id", conflict=True)
    open_store().delete_config("experiments", experiment_id, source=source)


# ---------------------------------------------------------------- prompts

def check_prompt(text: str) -> PromptTemplate:
    if not isinstance(text, str) or not text.strip():
        raise ConfigError("The prompt is empty", "text")
    try:
        template = PromptTemplate.parse("draft", text)
    except ValueError as error:
        raise ConfigError(str(error), "text") from error
    used = set()
    for part in (template.system, template.user):
        if not Template(part).is_valid():
            raise ConfigError("Invalid placeholder; write $$ for a literal dollar sign", "text")
        used |= set(Template(part).get_identifiers())
    unknown = sorted(used - PLACEHOLDERS)
    if unknown:
        raise ConfigError(f"Unknown placeholders: {', '.join('$' + u for u in unknown)}", "text")
    missing = [p for p in ("class_list", "edge_list") if p not in set(Template(template.user).get_identifiers())]
    if missing:
        raise ConfigError(f"The user section must contain {', '.join('$' + m for m in missing)}", "text")
    return template


def list_prompts() -> list[dict]:
    metas = run_metas()
    experiments = open_store().config_docs("experiments")
    rows = []
    for doc in open_store().config_docs("prompts"):
        name, text = doc["name"], doc["text"]
        entry = {"name": name, "text": text, "sha256": sha256_text(text), "created_utc": doc.get("created_utc"),
                 "protected": is_protected("prompts", name)}
        try:
            check_prompt(text)
            entry.update(valid=True, error=None)
        except ConfigError as error:
            entry.update(valid=False, error=str(error))
        entry["used_by"] = _studies([m for m in metas if m["prompt_template"] == name])
        entry["set_in"] = sorted(e["id"] for e in experiments if e.get("prompt_template") == name)
        rows.append(entry)
    return rows


def next_prompt_name(base: str) -> str:
    stem = re.sub(r"_v\d+$", "", base)
    existing = set(open_store().config_names("prompts"))
    version = 2
    while f"{stem}_v{version}" in existing:
        version += 1
    return f"{stem}_v{version}"


def create_prompt(name: str, text: str, source: str = "web") -> dict:
    _check_name(name, "name")
    if open_store().config_doc("prompts", name) is not None:
        raise ConfigError(f"Prompt {name} exists; prompt versions are never overwritten", "name", conflict=True)
    check_prompt(text)
    text = text if text.endswith("\n") else text + "\n"
    _put("prompts", name, {"name": name, "text": text, "sha256": sha256_text(text)}, True, source)
    return next(p for p in list_prompts() if p["name"] == name)


def delete_prompt(name: str, source: str = "web") -> None:
    _check_name(name, "name")
    if open_store().config_doc("prompts", name) is None:
        raise ConfigError(f"No prompt {name}", "name")
    _check_deletable("prompts", name, "name")
    used = _studies([m for m in run_metas() if m["prompt_template"] == name])
    if used:
        raise ConfigError(f"Prompt {name} was used by {', '.join(used)} and cannot be deleted", "name", conflict=True)
    if any(e.get("prompt_template") == name for e in open_store().config_docs("experiments")):
        raise ConfigError(f"Prompt {name} is set in an experiment configuration", "name", conflict=True)
    open_store().delete_config("prompts", name, source=source)


def preview_prompt(text: str, app: str, variant: str, seed: int) -> dict:
    template = check_prompt(text)
    stored = open_store().graph(_check_name(app, "app", _APP_ID))
    if stored is None:
        raise ConfigError(f"No extracted graph for {app}", "app")
    if variant not in VARIANTS:
        raise ConfigError(f"Unknown variant {variant}", "variant")
    graph, _ = variant_graph(stored, variant, derive_seed(seed, app, "obfuscation"))
    system, user = template.render(graph)
    return {"system": system, "user": user, "characters": len(system) + len(user)}


# ---------------------------------------------------------------- applications

_APP_LOCKED = ("repository", "commit", "source_roots", "class_dirs")


def _app_status(app_id: str) -> dict:
    checkout = WORK_DIR / "apps" / app_id
    doc = open_store().graph_doc(app_id, {"meta": 1, "edge_check": 1}) or {}
    return {
        "fetched": (checkout / ".git").is_dir(),
        "build_log": (WORK_DIR / "apps" / f"{app_id}-build.log").exists(),
        "graph": (doc.get("meta") or {}).get("stats"),
        "edge_check": doc.get("edge_check") is not None,
    }


def list_apps() -> list[dict]:
    metas = run_metas()
    experiments = open_store().config_docs("experiments")
    rows = []
    for doc in open_store().config_docs("apps"):
        app = app_from_doc(doc)
        runs = [m for m in metas if m["app"] == app.id]
        rows.append(
            {
                "id": app.id,
                "protected": is_protected("apps", app.id),
                "name": app.name,
                "note": app.note,
                "repository": app.repository,
                "tag": app.tag,
                "commit": app.commit,
                "build": app.build,
                "build_args": list(app.build_args),
                "source_roots": list(app.source_roots),
                "class_dirs": list(app.class_dirs),
                "status": _app_status(app.id),
                "studies": _studies(runs),
                "experiments": sorted(e["id"] for e in experiments if e.get("app") == app.id),
                "updated_utc": doc.get("updated_utc"),
            }
        )
    return rows


def _validate_app(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ConfigError("Set the name", "name")
    repository = (data.get("repository") or "").strip()
    if not _REPOSITORY.match(repository):
        raise ConfigError("The repository must be an https:// or git@ URL", "repository")
    commit = (data.get("commit") or "").strip().lower()
    if not _COMMIT.match(commit):
        raise ConfigError("The commit must be a full 40-character hash", "commit")
    build = data.get("build")
    if build not in BUILD_TYPES:
        raise ConfigError(f"Build must be one of {BUILD_TYPES}", "build")

    def strings(key: str, required: bool) -> list[str]:
        values = [str(v).strip() for v in (data.get(key) or []) if str(v).strip()]
        if required and not values:
            raise ConfigError(f"{key} needs at least one entry", key)
        return values

    return {
        "name": name,
        "note": _note(data),
        "repository": repository,
        "tag": (data.get("tag") or "").strip() or None,
        "commit": commit,
        "build": build,
        "build_args": strings("build_args", False),
        "source_roots": [_safe_relative(v, "source_roots") for v in strings("source_roots", True)],
        "class_dirs": [_safe_relative(v, "class_dirs") for v in strings("class_dirs", True)],
    }


def save_app(app_id: str, data: dict, create: bool, source: str = "web") -> dict:
    _check_name(app_id, "id", _APP_ID)
    current = {a["id"]: a for a in list_apps()}
    if create and app_id in current:
        raise ConfigError(f"Application {app_id} already exists", "id", conflict=True)
    if not create and app_id not in current:
        raise ConfigError(f"No application {app_id}", "id")
    clean = _validate_app(data)
    if app_id in current:
        old = current[app_id]
        if old["status"]["graph"] or old["studies"]:
            changed = [k for k in _APP_LOCKED if old[k] != clean[k]]
            if changed:
                raise ConfigError(
                    f"{app_id} already has an extracted graph or runs; {', '.join(changed)} cannot change. "
                    "Register it under a new id instead.",
                    changed[0],
                    conflict=True,
                )
    doc = {"id": app_id, **clean}
    app_from_doc(doc)
    _put("apps", app_id, doc, create, source)
    return next(a for a in list_apps() if a["id"] == app_id)


def delete_app(app_id: str, source: str = "web") -> None:
    current = {a["id"]: a for a in list_apps()}
    if app_id not in current:
        raise ConfigError(f"No application {app_id}", "id")
    _check_deletable("apps", app_id, "id")
    if current[app_id]["status"]["graph"] or current[app_id]["studies"]:
        raise ConfigError(f"{app_id} has an extracted graph or runs and cannot be deleted", "id", conflict=True)
    if current[app_id]["experiments"]:
        raise ConfigError(f"{app_id} is used by {', '.join(current[app_id]['experiments'])}", "id", conflict=True)
    open_store().delete_config("apps", app_id, source=source)


def resolve_tag(repository: str, tag: str) -> str:
    """Commit hash of a tag in a remote repository (annotated tags are peeled)."""
    if not _REPOSITORY.match(repository or ""):
        raise ConfigError("The repository must be an https:// or git@ URL", "repository")
    if not tag or not re.fullmatch(r"[A-Za-z0-9._/-]+", tag):
        raise ConfigError("Invalid tag", "tag")
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", repository, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ConfigError(f"git ls-remote failed: {getattr(error, 'stderr', '') or error}", "repository") from error
    refs = dict(reversed(line.split("\t")) for line in result.stdout.splitlines() if "\t" in line)
    commit = refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")
    if not commit:
        raise ConfigError(f"Tag {tag} not found in {repository}", "tag")
    return commit


def summary() -> dict:
    """Everything the configuration page needs in one response."""
    from .llm import provider_info

    return {
        "providers": provider_info(),
        "variants": list(VARIANTS),
        "ah_variants": [v.name for v in ALL_AH_VARIANTS],
        "build_types": list(BUILD_TYPES),
        "placeholders": sorted(PLACEHOLDERS),
        "profiles": list_profiles(),
        "experiments": list_experiments(),
        "prompts": list_prompts(),
        "apps": list_apps(),
        "databases": _databases(),
        "generated_utc": _now(),
    }
