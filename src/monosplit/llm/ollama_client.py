"""Local models served by Ollama, through its native REST API (POST /api/chat).

The OpenAI-compatible endpoint of Ollama (provider `openai_compatible`) is not used for the
study: it cannot set the context window per request, so the server default applies, which
depends on the GPU (4096 tokens with less than 24 GB of VRAM), and a longer prompt is cut
without warning. It also reports neither the model digest nor the server version.

What this adapter does:
- Sends the context window (`options.num_ctx`, required in the request options of the
  profile) and the output limit (`num_predict`, from max_output_tokens) with every request,
  with `truncate = false` and `shift = false`: the server refuses a prompt that does not fit
  instead of cutting it, and never drops tokens to keep generating.
- After each answer, checks that the prompt plus the output limit fit in the context the
  server allocated; otherwise the configuration is refused before the attempt is stored.
- Refuses Ollama cloud models, which run on ollama.com and not on this machine.
- Records with each variant the model digest (`ollama pull` can move a tag to other
  weights), the quantization, the Modelfile parameters and the server version; and with each
  attempt the server version, the digest, the context allocated and the share of the model
  in GPU memory. A digest change during a variant stops it.
- Receives a seed for each attempt from the runner (`per_attempt_seed`), so the runs differ
  and the seed of each attempt is recorded. Whether a seed gives the same answer again depends
  on the model (checked on 2026-11-06, Ollama 0.40.15, docs/decisions.md): qwen3.5:4b answered
  the same to the same seed, also in a new process, as the server took the same part of the
  prompt from its cache in every call; gpt-oss:20b did not, as for it that part shrinks by one
  token at every call.
- Tries a request again after a server failure (HTTP 5xx), which a crash of the model process
  causes (RETRY_WAITS).

Notes for the experiment configuration:
- Temperature empty: the model's own default applies (Modelfile parameters, recorded).
- Thinking: `think` in the request options, true or false, or "low" / "medium" / "high" for
  gpt-oss. The thinking text stays in the raw response; only the answer is validated.
- Other model options (top_p, top_k, ...) go under "options" in the request options.
- No call is billed, so runs start without the cost confirmation.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Mapping
from typing import Any

from .base import ClientField, LLMClient, LLMConfigurationError, LLMRequest, LLMResponse, register

DEFAULT_URL = "http://127.0.0.1:11434"
# Set by the adapter on every request; a profile cannot change them.
FIXED_FIELDS = {"stream": False, "truncate": False, "shift": False}
_RESERVED_TOP = ("model", "messages", *FIXED_FIELDS)
_RESERVED_OPTIONS = {
    "num_predict": "the output limit of the profile",
    "seed": "the seed of each attempt",
    "temperature": "the temperature of the profile",
}
# Waits before trying again a request the server failed with HTTP 5xx: the model process of
# Ollama can crash and is started again by the next request (twice on 2026-11-06, when
# gpt-oss:20b was loaded again right after being unloaded). No answer was produced, so a new
# try is not a new sample. A timeout or a server that is not running is not retried.
RETRY_WAITS = (10.0, 30.0)
# Prompts of this study have fewer characters per token in every tokenizer measured
# (DayTrader: 3.5 with Qwen 3.5, 3.8 with OpenAI's o200k). Used only to refuse, before any
# call, a context that cannot hold the prompt; the exact check uses the server's count.
_MAX_CHARS_PER_TOKEN = 5


class OllamaServerError(RuntimeError):
    """The server failed to answer (not a configuration problem): an API error."""


class OllamaUnreachable(OllamaServerError):
    """Nothing answers at the server address: Ollama is not running. Not retried."""


def _short(digest: str | None) -> str:
    return (digest or "none")[:12]


def check_request_options(max_output_tokens: int | None, request_options: Mapping[str, Any]) -> int:
    """Check the parts of a profile this adapter relies on; returns num_ctx."""
    for key in _RESERVED_TOP:
        if key in request_options:
            raise LLMConfigurationError(f"'{key}' is set by the adapter; remove it from the request options", "request")
    model_options = request_options.get("options", {})
    if not isinstance(model_options, Mapping):
        raise LLMConfigurationError("'options' in the request options must be a JSON object", "request")
    for key, source in _RESERVED_OPTIONS.items():
        if key in model_options:
            raise LLMConfigurationError(f"options.{key} comes from {source}; remove it from the request options", "request")
    num_ctx = model_options.get("num_ctx")
    if not isinstance(num_ctx, int) or isinstance(num_ctx, bool) or num_ctx <= 0:
        raise LLMConfigurationError(
            'Set the context window in the request options, for example {"options": {"num_ctx": 49152}}. '
            "The server default depends on the GPU (4096 tokens with less than 24 GB of VRAM) and cuts longer prompts.",
            "request",
        )
    if max_output_tokens is None:
        raise LLMConfigurationError("Set the output limit; it is sent as num_predict", "max_output_tokens")
    if max_output_tokens >= num_ctx:
        raise LLMConfigurationError(
            f"The output limit ({max_output_tokens}) must be smaller than the context window (num_ctx {num_ctx})",
            "max_output_tokens",
        )
    return num_ctx


@register("ollama")
class OllamaClient(LLMClient):
    default_key_env = None
    client_fields = (
        ClientField("base_url", "text", DEFAULT_URL, required=True),
        ClientField("timeout_s", "number", 3600),
    )
    accepts_temperature = True
    request_example = {"options": {"num_ctx": 49152}}
    pricing_url = None
    paid = False
    per_attempt_seed = True

    def __init__(self, base_url: str = DEFAULT_URL, timeout_s: float = 3600.0, transport: Any = None,
                 retry_waits: tuple[float, ...] = RETRY_WAITS) -> None:
        import httpx

        base = base_url.strip().rstrip("/")
        if base.endswith("/v1"):
            raise LLMConfigurationError(
                "base_url is the address of the Ollama server, without /v1 (that is the OpenAI-compatible endpoint)", "client"
            )
        self._httpx = httpx
        self._base = base
        # The read timeout covers a whole answer: the response comes in one piece.
        self._client = httpx.Client(base_url=base, timeout=httpx.Timeout(timeout_s, connect=10.0), transport=transport)
        self._retry_waits = tuple(retry_waits)
        self._identities: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------ HTTP

    def _send(self, method: str, path: str, body: dict | None = None) -> dict:
        for wait in (*self._retry_waits, None):
            try:
                return self._send_once(method, path, body)
            except OllamaUnreachable:
                raise
            except OllamaServerError:
                if wait is None:
                    raise
                time.sleep(wait)
        raise AssertionError("unreachable")

    def _send_once(self, method: str, path: str, body: dict | None) -> dict:
        try:
            response = self._client.request(method, path, json=body)
        except self._httpx.ConnectError as error:
            raise OllamaUnreachable(
                f"Ollama is not answering at {self._base} ({error}); start the Ollama app or `ollama serve`"
            ) from error
        if response.status_code < 400:
            return response.json()
        try:
            message = str(response.json().get("error") or response.text)
        except ValueError:
            message = response.text
        if response.status_code == 404 and "model" in message and "not found" in message:
            raise LLMConfigurationError(f"Ollama: {message}. Download it with `ollama pull <model>`", "model")
        if response.status_code == 400:
            if "context" in message:
                raise LLMConfigurationError(
                    f"Ollama: {message}. Raise num_ctx in the request options: the prompt and the output limit must fit in it",
                    "request",
                )
            raise LLMConfigurationError(f"Ollama refused the request: {message}", "request")
        raise OllamaServerError(f"Ollama answered HTTP {response.status_code}: {message}")

    def _listed(self, model: str) -> dict | None:
        """The entry of `model` among the models stored by the server (it has the digest)."""
        wanted = {model, model if ":" in model else f"{model}:latest"}
        for entry in self._send("GET", "/api/tags").get("models", []):
            if entry.get("name") in wanted or entry.get("model") in wanted:
                return entry
        return None

    def _loaded(self, model: str) -> dict | None:
        """The entry of `model` among the models loaded in memory (context, GPU share)."""
        wanted = {model, model if ":" in model else f"{model}:latest"}
        for entry in self._send("GET", "/api/ps").get("models", []):
            if entry.get("name") in wanted or entry.get("model") in wanted:
                return entry
        return None

    # ------------------------------------------------------------ LLMClient

    def sdk_version(self) -> str | None:
        versions = {identity.get("server_version") for identity in self._identities.values()} - {None}
        server = versions.pop() if len(versions) == 1 else self._send("GET", "/api/version").get("version")
        return f"ollama {server}; httpx {self._httpx.__version__}"

    def list_models(self) -> list[str]:
        models = self._send("GET", "/api/tags").get("models", [])
        return sorted(m["name"] for m in models if m.get("name") and not m.get("remote_host"))

    @classmethod
    def validate_profile(cls, temperature, max_output_tokens, seed, request_options) -> None:
        check_request_options(max_output_tokens, request_options)

    def validate_request(self, request: LLMRequest) -> None:
        num_ctx = check_request_options(request.max_output_tokens, request.options)
        characters = len(request.system) + len(request.user)
        fewest = math.ceil(characters / _MAX_CHARS_PER_TOKEN)
        if fewest + request.max_output_tokens > num_ctx:
            raise LLMConfigurationError(
                f"The prompt has {characters} characters, at least {fewest} tokens; with the output limit of "
                f"{request.max_output_tokens} it cannot fit in num_ctx {num_ctx}. Raise num_ctx or lower the output limit.",
                "request",
            )

    def model_identity(self, model: str) -> dict[str, Any]:
        version = self._send("GET", "/api/version").get("version")
        show = self._send("POST", "/api/show", {"model": model})
        if show.get("remote_host") or show.get("remote_model"):
            raise LLMConfigurationError(
                f"{model} is an Ollama cloud model, served by {show.get('remote_host') or 'ollama.com'}, not by this machine",
                "model",
            )
        listed = self._listed(model)
        if listed is None:
            raise LLMConfigurationError(f"{model} is not among the models of this Ollama server; run `ollama pull {model}`", "model")
        details = show.get("details") or {}
        info = show.get("model_info") or {}
        architecture = info.get("general.architecture")
        template = show.get("template")
        identity = {
            "server": "ollama",
            "server_version": version,
            "model": listed.get("name"),
            "digest": listed.get("digest"),
            "size_bytes": listed.get("size"),
            "format": details.get("format"),
            "family": details.get("family"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            "runner": details.get("runner"),
            "architecture": architecture,
            "parameter_count": info.get("general.parameter_count"),
            "trained_context_length": info.get(f"{architecture}.context_length") if architecture else None,
            "modelfile_parameters": [" ".join(line.split()) for line in (show.get("parameters") or "").splitlines() if line.strip()],
            "capabilities": show.get("capabilities") or [],
            "thinking": show.get("thinking"),
            "template_source": show.get("template_source"),
            "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest() if template else None,
            "renderer": show.get("renderer"),
            "parser": show.get("parser"),
            "modified_at": show.get("modified_at"),
            "fixed_request_fields": dict(FIXED_FIELDS),
        }
        self._identities[model] = identity
        return identity

    def _body(self, request: LLMRequest) -> dict[str, Any]:
        options = dict(request.options.get("options") or {})
        options["num_predict"] = request.max_output_tokens
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.seed is not None:
            options["seed"] = request.seed
        return {
            "model": request.model,
            "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.user}],
            **FIXED_FIELDS,
            **{k: v for k, v in request.options.items() if k != "options"},
            "options": options,
        }

    def generate(self, request: LLMRequest) -> LLMResponse:
        num_ctx = check_request_options(request.max_output_tokens, request.options)
        identity = self._identities.get(request.model) or self.model_identity(request.model)
        listed = self._listed(request.model)
        digest = listed.get("digest") if listed else None
        if digest != identity.get("digest"):
            raise LLMConfigurationError(
                f"{request.model} now has digest {_short(digest)} instead of {_short(identity.get('digest'))}: "
                "the tag points to other weights. Pull the original back or use another profile.",
                "model",
            )
        version = self._send("GET", "/api/version").get("version")

        start = time.perf_counter()
        reply = self._send("POST", "/api/chat", self._body(request))
        latency = time.perf_counter() - start

        loaded = self._loaded(request.model) or {}
        context = loaded.get("context_length")
        prompt_tokens = reply.get("prompt_eval_count")
        room = context or num_ctx
        if prompt_tokens is not None and prompt_tokens + request.max_output_tokens > room:
            raise LLMConfigurationError(
                f"The prompt has {prompt_tokens} tokens for {request.model}; with the output limit of "
                f"{request.max_output_tokens} it needs {prompt_tokens + request.max_output_tokens} tokens of context, and "
                f"the server allocated {room} (num_ctx {num_ctx}). Raise num_ctx or lower the output limit.",
                "request",
            )
        message = reply.get("message") or {}
        done_reason = reply.get("done_reason")
        return LLMResponse(
            text=message.get("content") or "",
            model=reply.get("model"),
            input_tokens=prompt_tokens,
            output_tokens=reply.get("eval_count"),  # thinking included
            reasoning_tokens=None,  # not reported apart
            finish_reason=done_reason,
            refused=False,  # a local model has no refusal signal; a refusal in words fails validation
            truncated=done_reason == "length",
            response_id=None,
            latency_s=latency,
            raw=reply,
            runtime={
                "server_version": version,
                "digest": digest,
                "context_length": context,
                "size_bytes": loaded.get("size"),
                "size_vram_bytes": loaded.get("size_vram"),
            },
        )
