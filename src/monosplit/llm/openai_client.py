"""OpenAI models through the Chat Completions API (official `openai` SDK).

The same adapter serves OpenAI-compatible servers (vLLM, LM Studio, OpenRouter, DeepSeek and
others) through `base_url`, registered as provider `openai_compatible`. For Ollama use the
provider `ollama` (ollama_client.py): through this endpoint the context window cannot be set
per request, and the server default cuts longer prompts without warning.

Notes for the experiment configuration:
- Reasoning models may reject `temperature`; leave it unset for them. Their reasoning
  depth goes in the request options, e.g. options = {reasoning_effort = "medium"}.
- `output_tokens` is `usage.completion_tokens`, which already includes reasoning tokens.
"""

from __future__ import annotations

import time

from .base import ClientField, LLMClient, LLMConfigurationError, LLMRequest, LLMResponse, register
from .env import env_value


@register("openai")
class OpenAIChatClient(LLMClient):
    default_key_env = "OPENAI_API_KEY"
    client_fields = (ClientField("api_key_env", "text", "OPENAI_API_KEY"), ClientField("timeout_s", "number", 900))
    accepts_temperature = None  # reasoning models accept only the default
    request_example = {"reasoning_effort": "medium"}
    pricing_url = "https://developers.openai.com/api/docs/pricing"

    def __init__(
        self,
        api_key_env: str | None = "OPENAI_API_KEY",
        base_url: str | None = None,
        timeout_s: float = 900.0,
        sdk_max_retries: int = 4,
        max_tokens_field: str = "max_completion_tokens",
    ) -> None:
        import openai

        api_key = None
        if api_key_env:
            api_key = env_value(api_key_env)
            if not api_key:
                raise LLMConfigurationError(f"Environment variable {api_key_env} is not set")
        self._openai = openai
        self._client = openai.OpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=timeout_s,
            max_retries=sdk_max_retries,
        )
        self._max_tokens_field = max_tokens_field

    def sdk_version(self) -> str | None:
        return f"openai {self._openai.__version__}"

    def list_models(self) -> list[str]:
        return sorted(model.id for model in self._client.models.list())

    def generate(self, request: LLMRequest) -> LLMResponse:
        params = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        }
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            params[self._max_tokens_field] = request.max_output_tokens
        if request.seed is not None:
            params["seed"] = request.seed
        params.update(request.options)

        start = time.perf_counter()
        completion = self._client.chat.completions.create(**params)
        latency = time.perf_counter() - start

        choice = completion.choices[0]
        usage = completion.usage
        details = usage.completion_tokens_details if usage else None
        return LLMResponse(
            text=choice.message.content or "",
            model=completion.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            reasoning_tokens=details.reasoning_tokens if details else None,
            finish_reason=choice.finish_reason,
            refused=bool(choice.message.refusal) or choice.finish_reason == "content_filter",
            truncated=choice.finish_reason == "length",
            response_id=completion.id,
            latency_s=latency,
            raw=completion.model_dump(mode="json"),
        )


@register("openai_compatible")
class OpenAICompatibleClient(OpenAIChatClient):
    """Any server that implements the Chat Completions API, e.g. vLLM at http://localhost:8000/v1.
    Ollama answers here too (http://localhost:11434/v1), but the provider `ollama` controls its context window."""

    default_key_env = None
    client_fields = (
        ClientField("base_url", "text", "http://localhost:11434/v1", required=True),
        ClientField("api_key_env", "text", None),
        ClientField("timeout_s", "number", 1800),
    )
    accepts_temperature = True
    request_example = {}
    pricing_url = None

    def __init__(
        self,
        base_url: str,
        api_key_env: str | None = None,
        timeout_s: float = 900.0,
        sdk_max_retries: int = 4,
        max_tokens_field: str = "max_tokens",
    ) -> None:
        super().__init__(
            api_key_env=api_key_env,
            base_url=base_url,
            timeout_s=timeout_s,
            sdk_max_retries=sdk_max_retries,
            max_tokens_field=max_tokens_field,
        )
