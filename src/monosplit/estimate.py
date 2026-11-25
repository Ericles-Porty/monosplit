"""Cost estimate of the LLM runs still missing in a study, shown before a paid run starts.

Per variant:
- input tokens per attempt: the mean observed in earlier attempts of the same variant, or
  the prompt length in characters / 4 (an approximation; tokenizers differ);
- output tokens per attempt: the observed mean, or DEFAULT_OUTPUT_TOKENS;
- expected attempts: missing runs x observed attempts per accepted run (default 1.25);
- maximum attempts: (missing runs + failed runs still allowed) x (1 + max_retries), each
  at the output-token limit of the profile. This bounds the spending of the job;
- time: expected attempts x the mean time of the earlier answered attempts; unknown before
  the first attempt. For local models, where nothing is billed, time is the cost that matters.

The confirmation token changes when the configuration, the profile, the prompt or the stored
runs change, so a run can only start against the estimate the user saw. Providers that bill
nothing (`paid = False`) start without it; for them the estimate also checks that the model
can be served (local server running, model downloaded) and reports the problem if not.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from statistics import mean

from .config import ExperimentConfig, LLMProfile
from .llm import create_client, provider_class
from .prompting import load_prompt, variant_graph
from .runner import obfuscation_seed, replay

DEFAULT_OUTPUT_TOKENS = 3000
DEFAULT_ATTEMPTS_PER_RUN = 1.25
DEFAULT_OUTPUT_CAP = 32000


def _cost(tokens_in: float, tokens_out: float, profile: LLMProfile) -> float | None:
    p = profile.pricing
    if p.input_per_mtok is None or p.output_per_mtok is None:
        return None
    return (tokens_in * p.input_per_mtok + tokens_out * p.output_per_mtok) / 1_000_000


def estimate(config: ExperimentConfig, profile: LLMProfile, variants: list[str]) -> dict:
    graph = config.graph()
    store = config.store()
    template = load_prompt(config.prompt_template)
    cap = profile.max_output_tokens or DEFAULT_OUTPUT_CAP
    rows = []
    for variant in variants:
        prompt_graph, _ = variant_graph(graph, variant, obfuscation_seed(config))
        system, user = template.render(prompt_graph)
        records = store.attempts(config.key(profile.name, variant))
        state = replay(records, config.max_retries)
        answered = [r for r in records if r.get("status") != "api_error"]
        with_tokens = [r for r in answered if r.get("input_tokens") is not None and r.get("output_tokens") is not None]
        observed = bool(with_tokens)
        tokens_in = mean(r["input_tokens"] for r in with_tokens) if observed else math.ceil((len(system) + len(user)) / 4)
        tokens_out = mean(r["output_tokens"] for r in with_tokens) if observed else DEFAULT_OUTPUT_TOKENS
        timed = [r["latency_s"] for r in answered if r.get("latency_s") is not None]
        seconds = mean(timed) if timed else None
        per_run = len(answered) / state.accepted if state.accepted else DEFAULT_ATTEMPTS_PER_RUN
        missing = max(0, config.accepted_runs - state.accepted)
        failures_left = max(0, config.max_failed_runs - state.failed_runs)
        expected_attempts = missing * max(1.0, per_run)
        max_attempts = (missing + failures_left) * (1 + config.max_retries) if missing else 0
        expected = _cost(expected_attempts * tokens_in, expected_attempts * tokens_out, profile)
        maximum = _cost(max_attempts * tokens_in, max_attempts * cap, profile)
        rows.append(
            {
                "variant": variant,
                "accepted": state.accepted,
                "target": config.accepted_runs,
                "missing": missing,
                "attempts_so_far": len(answered),
                "failed_runs": state.failed_runs,
                "observed": observed,
                "input_tokens_per_attempt": round(tokens_in),
                "output_tokens_per_attempt": round(tokens_out),
                "output_cap": cap,
                "expected_attempts": round(expected_attempts, 1),
                "max_attempts": max_attempts,
                "expected_cost_usd": expected,
                "max_cost_usd": maximum,
                "seconds_per_attempt": round(seconds, 1) if seconds is not None else None,
                "expected_seconds": round(expected_attempts * seconds) if seconds is not None else (0 if not missing else None),
            }
        )
    priced = profile.pricing.input_per_mtok is not None and profile.pricing.output_per_mtok is not None
    fingerprint = json.dumps(
        {
            "config": asdict(config),
            "profile": profile.describe(),
            "prompt": template.sha256,
            "variants": variants,
            "rows": [(r["variant"], r["accepted"], r["attempts_so_far"]) for r in rows],
        },
        sort_keys=True,
        default=str,
    )
    try:
        key_present = provider_class(profile.provider).key_present(profile.client_options)
    except Exception:
        key_present = None
    paid = provider_class(profile.provider).paid
    problem = None
    if not paid and any(r["missing"] for r in rows):
        try:
            create_client(profile.provider, **profile.client_options).model_identity(profile.model)
        except Exception as error:  # server down, model not downloaded, cloud model
            problem = str(error)
    times = [r["expected_seconds"] for r in rows]
    return {
        "experiment": config.name,
        "app": config.app,
        "profile": profile.name,
        "provider": profile.provider,
        "model": profile.model,
        "paid": paid,
        "problem": problem,
        "priced": priced,
        "key_present": key_present,
        "variants": rows,
        "missing_runs": sum(r["missing"] for r in rows),
        "expected_cost_usd": sum(r["expected_cost_usd"] for r in rows) if priced else None,
        "max_cost_usd": sum(r["max_cost_usd"] for r in rows) if priced else None,
        "expected_seconds": sum(times) if None not in times else None,
        "defaults": {"output_tokens": DEFAULT_OUTPUT_TOKENS, "attempts_per_run": DEFAULT_ATTEMPTS_PER_RUN},
        "token": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16],
    }
