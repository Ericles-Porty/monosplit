"""LLM runs: acceptance rule, retries and a complete log.

Procedure for one variant (original or obfuscated names):
- The prompt is rendered once, and every attempt sends the same prompt.
- A run ends at its first accepted output. An invalid output is re-sent, without
  feedback, up to `max_retries` times; if every attempt is invalid, the run fails.
- Runs repeat until `accepted_runs` runs are accepted, or stop after `max_failed_runs`
  failed runs.
- An API error (network, rate limit after the SDK's own retries, server error) is
  logged and stops the command. Running the command again resumes where it stopped.
- Providers with `per_attempt_seed` (local models, where the same seed and prompt can give
  the same answer every time) get a seed per attempt, derived from the master seed
  (`attempt_seed`) and recorded with it, so the runs differ. Other providers get the
  profile's seed.
- A configuration error found by the first call of a new variant (for example a prompt
  longer than the context window of a local model) stops the command and removes the
  variant document, which has no attempt yet, so the profile can still be corrected.

Stored in the database (store.py):
    variants    the configuration of the variant (meta; resuming under another one is
                refused), the prompt exactly as sent and the prompt name -> class name map
    attempts    one document per attempt: the log record, the full API response and,
                when accepted, the partition in class names
"""

from __future__ import annotations

import json
import platform
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .config import ExperimentConfig, LLMProfile
from .graph import CallGraph
from .llm import LLMClient, LLMConfigurationError
from .prompting import load_prompt, sha256_text, variant_graph
from .store import Store
from .seeds import derive_seed
from .validation import validate_output


class RunStopped(RuntimeError):
    """The runs of a variant stopped before reaching the target; rerun to resume."""


@dataclass
class RunState:
    accepted: int = 0
    failed_runs: int = 0
    attempts: int = 0
    run: int = 1  # current run number
    tries: int = 0  # invalid attempts in the current run


def replay(records: list[dict], max_retries: int) -> RunState:
    """Rebuild the loop state from the attempt log."""
    state = RunState()
    for record in records:
        state.attempts = max(state.attempts, record["attempt"])
        if record["status"] == "accepted":
            state.accepted += 1
            state.run = record["run"] + 1
            state.tries = 0
        elif record["status"] == "invalid":
            state.tries += 1
            if state.tries > max_retries:
                state.failed_runs += 1
                state.run = record["run"] + 1
                state.tries = 0
    return state


def read_jsonl(path: Path) -> list[dict]:
    """Lines of a JSONL file (used to import the file layout of earlier versions)."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def obfuscation_seed(config: ExperimentConfig) -> int:
    return derive_seed(config.seed, config.app, "obfuscation")


# Recorded in the variant meta; part of the fingerprint, so a change of rule cannot mix seeds.
ATTEMPT_SEED_RULE = "sha256(master seed/experiment/app/profile/variant/attempt/<n>) mod 2^31"


def attempt_seed(config: ExperimentConfig, profile: str, variant: str, attempt: int) -> int:
    """Seed of one attempt, for providers with per-attempt seeds. The experiment name is part
    of it, so two experiments with the same master seed (a pilot and the full experiment)
    do not draw the same samples. 31 bits: every server accepts it."""
    return derive_seed(config.seed, config.name, config.app, profile, variant, "attempt", attempt) % 2**31


def graph_fingerprint(graph: CallGraph) -> str:
    lines = [*graph.classes, *(f"{a}>{b}:{n}" for (a, b), n in sorted(graph.calls.items()))]
    return sha256_text("\n".join(lines))


def _fingerprint(meta: dict) -> dict:
    """Fields that must match to resume: anything that changes what the model receives."""
    llm = meta["llm"]
    return {
        "app": meta["app"],
        "variant": meta["variant"],
        "graph_sha256": meta["graph_sha256"],
        "prompt_sha256": meta["prompt_sha256"],
        "provider": llm["provider"],
        "model": llm["model"],
        "temperature": llm["temperature"],
        "max_output_tokens": llm["max_output_tokens"],
        "seed": llm["seed"],
        "request_options": llm["request_options"],
        "max_retries": meta["max_retries"],
        # Local models: the weights behind the tag, and the rule of the seeds.
        "model_digest": (meta.get("model_identity") or {}).get("digest"),
        "attempt_seeds": meta.get("attempt_seeds"),
    }


def _ensure_meta(store: Store, key: dict, meta: dict, system: str, user: str, alias_map: dict) -> bool:
    """Store the variant on its first run (True); on a resume, refuse another configuration."""
    if store.insert_variant(key, meta, system + "\n", user + "\n", alias_map):
        return True
    stored = store.variant(key)["meta"]
    old, new = _fingerprint(stored), _fingerprint(meta)
    changed = sorted(k for k in new if old.get(k) != new[k])
    if changed:
        raise RunStopped(
            f"{'/'.join(key.values())} was produced with another configuration (differs in: {', '.join(changed)}). "
            "Use another experiment name or LLM profile."
        )
    return False


def run_variant(
    client: LLMClient,
    profile: LLMProfile,
    config: ExperimentConfig,
    variant: str,
    graph: CallGraph,
    progress: Callable[[dict], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    """Run one variant until its target. `progress` receives a dict after every attempt;
    `cancel`, when set, stops the loop before the next attempt (an attempt in flight finishes)."""
    store = config.store()
    key = config.key(profile.name, variant)
    prompt_graph, alias_to_class = variant_graph(graph, variant, obfuscation_seed(config))
    template = load_prompt(config.prompt_template)
    system, user = template.render(prompt_graph)
    request = profile.request(system, user)
    client.validate_request(request)
    per_attempt = type(client).per_attempt_seed
    if per_attempt and profile.seed is not None:
        raise LLMConfigurationError(
            f"{profile.provider} gets a seed derived for each attempt; remove the seed from profile {profile.name}", "seed"
        )
    # Before the variant is stored: a server that is down or a model that is missing stores nothing.
    try:
        identity = client.model_identity(request.model)
    except LLMConfigurationError:
        raise
    except Exception as error:
        raise RunStopped(f"{variant}: the model server did not answer ({type(error).__name__}: {error}). Rerun to resume.") from error

    meta = {
        "experiment": config.name,
        "app": config.app,
        "variant": variant,
        "graph_sha256": graph_fingerprint(graph),
        "prompt_template": template.name,
        "prompt_template_sha256": template.sha256,
        "prompt_sha256": sha256_text(system + "\n\n" + user),
        "obfuscation_seed": obfuscation_seed(config) if variant == "obfuscated" else None,
        "max_retries": config.max_retries,
        "llm": profile.describe(),
        "sdk": client.sdk_version(),
        "monosplit": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "created_utc": _now(),
    }
    if identity:
        meta["model_identity"] = identity
    if per_attempt:
        meta["attempt_seeds"] = ATTEMPT_SEED_RULE
    created = _ensure_meta(store, key, meta, system, user, alias_to_class)

    state = replay(store.attempts(key), config.max_retries)
    expected = list(prompt_graph.classes)

    def report(event: str, record: dict | None = None) -> None:
        if progress is not None:
            progress({"event": event, "variant": variant, "target": config.accepted_runs, **asdict(state), "record": record})

    report("start")
    while state.accepted < config.accepted_runs:
        if cancel is not None and cancel.is_set():
            raise RunStopped(f"{variant}: cancelled")
        if state.failed_runs >= config.max_failed_runs:
            raise RunStopped(f"{variant}: {state.failed_runs} failed runs reached the limit max_failed_runs")
        attempt = state.attempts + 1
        record = {"attempt": attempt, "run": state.run, "try": state.tries + 1, "timestamp_utc": _now()}
        sent = replace(request, seed=attempt_seed(config, profile.name, variant, attempt)) if per_attempt else request
        if sent.seed is not None:
            record["seed"] = sent.seed
        try:
            response = client.generate(sent)
        except LLMConfigurationError:
            # Nothing of this variant is stored yet: drop it, so the profile stays editable.
            if created and not store.attempts(key):
                store.discard_variant(key)
            raise
        except Exception as error:  # SDK errors of any provider
            record.update(status="api_error", error=f"{type(error).__name__}: {error}")
            store.append_attempt(key, record)
            report("api_error", record)
            raise RunStopped(f"{variant}: API error on attempt {attempt} ({error}). Rerun to resume.") from error

        result = validate_output(response.text, expected)
        reason = None if result.accepted else ("refusal" if response.refused else result.reason)
        raw = {"attempt": attempt, **asdict(response)}
        record.update(
            status="accepted" if result.accepted else "invalid",
            reason=reason,
            detail=result.detail,
            k=result.k,
            json_location=result.json_location,
            empty_services_dropped=result.empty_services_dropped,
            model_returned=response.model,
            finish_reason=response.finish_reason,
            refused=response.refused,
            truncated=response.truncated,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            reasoning_tokens=response.reasoning_tokens,
            latency_s=round(response.latency_s, 3),
            cost_usd=profile.pricing.cost(response.input_tokens, response.output_tokens),
            response_id=response.response_id,
        )
        accepted = None
        if result.accepted:
            partition = {alias_to_class[a]: s for a, s in result.partition.items()}
            services = [
                {
                    "name": name,
                    "classes": sorted(c for c, s in partition.items() if s == index),
                    "prompt_names": sorted(a for a, s in result.partition.items() if s == index),
                }
                for index, name in enumerate(result.service_names)
            ]
            accepted = {"run": state.run, "k": result.k, "services": services, "partition": partition}
        # One insert per attempt: the record, the raw response and the accepted partition.
        store.append_attempt(key, record, raw, accepted)
        state.attempts = attempt

        if result.accepted:
            state.accepted += 1
            state.run += 1
            state.tries = 0
        else:
            state.tries += 1
            if state.tries > config.max_retries:
                state.failed_runs += 1
                state.run += 1
                state.tries = 0
        report("attempt", record)

    return {"variant": variant, "accepted": state.accepted, "failed_runs": state.failed_runs, "attempts": state.attempts}
