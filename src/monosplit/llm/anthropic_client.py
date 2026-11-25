"""Claude models through the Anthropic Messages API (official `anthropic` SDK).

Notes for the experiment configuration:
- anthropic >= 2.0 sends API version 2026-10-21, which rejects `temperature`, `top_p` and
  `top_k` on every model, even at their default values. Claude samples with the API
  defaults (temperature 1.0), so leave `temperature` unset; the adapter refuses it.
- Current models think adaptively and do not accept disabled thinking. Thinking depth is
  set with the effort level, e.g. options = {output_config = {effort = "high"}}. Claude
  Opus 5.5 defaults to "medium" and Claude Sonnet 5.5 to "high", so set it explicitly.
- Requests are streamed and collected with `get_final_message()`, so a large
  `max_output_tokens` does not hit HTTP timeouts. Thinking tokens count against it.
- Credentials: without `api_key_env`, the SDK resolves ANTHROPIC_API_KEY,
  ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile.
- The server-side refusal fallback is not enabled: it would answer with another model,
  and the model is a controlled variable of the experiment. A refusal is logged as an
  invalid attempt with reason "refusal".
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

from .base import ClientField, LLMClient, LLMConfigurationError, LLMRequest, LLMResponse, register
from .env import env_value, has_env

_SAMPLING_FIELDS = ("temperature", "top_p", "top_k")


@register("anthropic")
class AnthropicClient(LLMClient):
    default_key_env = "ANTHROPIC_API_KEY"
    client_fields = (ClientField("api_key_env", "text", None), ClientField("timeout_s", "number", 900))
    accepts_temperature = False
    request_example = {"output_config": {"effort": "high"}}
    pricing_url = "https://platform.claude.com/docs/en/about-claude/pricing"

    @classmethod
    def key_present(cls, options: Mapping[str, Any]) -> bool | None:
        name = options.get("api_key_env")
        if name:
            return has_env(name)
        return has_env("ANTHROPIC_API_KEY") or has_env("ANTHROPIC_AUTH_TOKEN")

    def __init__(
        self,
        api_key_env: str | None = None,
        timeout_s: float = 900.0,
        sdk_max_retries: int = 4,
        default_max_output_tokens: int = 32000,
    ) -> None:
        import anthropic

        kwargs: dict = {"timeout": timeout_s, "max_retries": sdk_max_retries}
        if api_key_env:
            api_key = env_value(api_key_env)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable {api_key_env} is not set")
            kwargs["api_key"] = api_key
        elif "ANTHROPIC_API_KEY" not in os.environ and env_value("ANTHROPIC_API_KEY"):
            # Saved for the user after this process started (see env.py).
            kwargs["api_key"] = env_value("ANTHROPIC_API_KEY")
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(**kwargs)
        self._default_max_output_tokens = default_max_output_tokens

    def sdk_version(self) -> str | None:
        return f"anthropic {self._anthropic.__version__}"

    def list_models(self) -> list[str]:
        return sorted(model.id for model in self._client.models.list())

    def validate_request(self, request: LLMRequest) -> None:
        if request.temperature is not None or any(f in request.options for f in _SAMPLING_FIELDS):
            raise LLMConfigurationError(
                "The Anthropic API version sent by anthropic>=2.0 (2026-10-21) rejects temperature, "
                "top_p and top_k on every model. Remove them; Claude samples at the default temperature 1.0."
            )
        if request.seed is not None:
            raise LLMConfigurationError("The Anthropic Messages API has no seed parameter")

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.validate_request(request)
        params = {
            "model": request.model,
            "max_tokens": request.max_output_tokens or self._default_max_output_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
            **request.options,
        }
        start = time.perf_counter()
        with self._client.messages.stream(**params) as stream:
            message = stream.get_final_message()
        latency = time.perf_counter() - start

        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            reasoning_tokens=None,
            finish_reason=message.stop_reason,
            refused=message.stop_reason == "refusal",
            truncated=message.stop_reason == "max_tokens",
            response_id=message.id,
            latency_s=latency,
            raw=message.to_dict(),
        )
