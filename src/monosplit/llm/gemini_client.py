"""Gemini models through the Google Gen AI SDK (`google-genai`).

Notes for the experiment configuration:
- Thinking depth goes in the request options, e.g. options = {thinking_config = {thinking_level = "high"}};
  options are passed to `GenerateContentConfig` as given.
- `output_tokens` is candidates_token_count + thoughts_token_count, since thinking
  tokens are billed as output.
"""

from __future__ import annotations

import time

from .base import ClientField, LLMClient, LLMConfigurationError, LLMRequest, LLMResponse, register
from .env import env_value

_REFUSAL_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}


@register("gemini")
class GeminiClient(LLMClient):
    default_key_env = "GEMINI_API_KEY"
    client_fields = (ClientField("api_key_env", "text", "GEMINI_API_KEY"), ClientField("timeout_s", "number", 900))
    accepts_temperature = True
    request_example = {"thinking_config": {"thinking_level": "high"}}
    pricing_url = "https://ai.google.dev/gemini-api/docs/pricing"

    def __init__(self, api_key_env: str = "GEMINI_API_KEY", timeout_s: float = 900.0) -> None:
        import google.genai as genai
        from google.genai import types

        api_key = env_value(api_key_env)
        if not api_key:
            raise LLMConfigurationError(f"Environment variable {api_key_env} is not set")
        self._genai = genai
        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    def sdk_version(self) -> str | None:
        return f"google-genai {self._genai.__version__}"

    def list_models(self) -> list[str]:
        names = []
        for model in self._client.models.list():
            actions = model.supported_actions or []
            if model.name and (not actions or "generateContent" in actions):
                names.append(model.name.removeprefix("models/"))
        return sorted(names)

    def generate(self, request: LLMRequest) -> LLMResponse:
        config: dict = {"system_instruction": request.system}
        if request.temperature is not None:
            config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            config["max_output_tokens"] = request.max_output_tokens
        if request.seed is not None:
            config["seed"] = request.seed
        config.update(request.options)

        start = time.perf_counter()
        response = self._client.models.generate_content(
            model=request.model,
            contents=request.user,
            config=self._types.GenerateContentConfig(**config),
        )
        latency = time.perf_counter() - start

        usage = response.usage_metadata
        candidates = usage.candidates_token_count if usage else None
        thoughts = usage.thoughts_token_count if usage else None
        output = None if candidates is None and thoughts is None else (candidates or 0) + (thoughts or 0)
        finish = response.candidates[0].finish_reason if response.candidates else None
        finish_name = finish.name if finish is not None else None
        blocked = bool(response.prompt_feedback and response.prompt_feedback.block_reason)
        return LLMResponse(
            text=response.text or "",
            model=response.model_version or request.model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=output,
            reasoning_tokens=thoughts,
            finish_reason=finish_name or ("BLOCKED" if blocked else None),
            refused=blocked or finish_name in _REFUSAL_REASONS,
            truncated=finish_name == "MAX_TOKENS",
            response_id=response.response_id,
            latency_s=latency,
            raw=response.model_dump(mode="json", exclude_none=True, exclude={"sdk_http_response"}),
        )
