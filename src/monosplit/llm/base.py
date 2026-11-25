"""Common interface of the LLM clients.

Design: Strategy + Adapter + Registry.
- `LLMClient` is the strategy interface. The runner, the prompt and the logs only use it.
- Each provider has one adapter class (openai_client.py, anthropic_client.py, ...) that
  translates an `LLMRequest` into its SDK call and the SDK response into an `LLMResponse`.
- `register` puts each adapter in a registry under a provider name, and `create_client`
  builds the adapter named in the experiment configuration.

To test another model, write the experiment config with another provider/model. To add a
provider, write one adapter class decorated with `@register("name")` and import its module
in `monosplit/llm/__init__.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .env import has_env


class LLMConfigurationError(ValueError):
    """The configuration asks for something the provider does not accept. `field` names the
    profile field to fix (temperature, seed, request, ...), when there is one."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    model: str
    temperature: float | None = None  # None: not sent, the provider default applies
    max_output_tokens: int | None = None
    seed: int | None = None
    options: Mapping[str, Any] = field(default_factory=dict)  # provider-specific request fields, sent as given


@dataclass
class LLMResponse:
    text: str
    model: str | None  # model reported by the API
    input_tokens: int | None
    output_tokens: int | None  # billed output tokens, reasoning tokens included
    reasoning_tokens: int | None  # part of output_tokens, when the API reports it
    finish_reason: str | None
    refused: bool  # the provider declined to answer
    truncated: bool  # generation stopped at the output-token limit
    response_id: str | None
    latency_s: float
    raw: dict[str, Any]  # the full API response, JSON-compatible
    # What served this attempt, when the server reports it (local servers: version and model digest).
    runtime: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClientField:
    """A constructor option of an adapter, described for the configuration interface."""

    key: str
    kind: str  # "text" | "number"
    default: Any = None
    required: bool = False


class LLMClient(ABC):
    provider: ClassVar[str] = ""
    # Metadata shown by the configuration interface.
    default_key_env: ClassVar[str | None] = None
    client_fields: ClassVar[tuple[ClientField, ...]] = ()
    accepts_temperature: ClassVar[bool | None] = None  # None: depends on the model
    request_example: ClassVar[dict[str, Any]] = {}
    pricing_url: ClassVar[str | None] = None
    # False when no call is billed (offline or local models): runs start without the cost confirmation.
    paid: ClassVar[bool] = True
    # True when the runner sends a seed derived for each attempt (runner.attempt_seed) instead
    # of the profile's seed: needed where the same seed and prompt give the same answer.
    per_attempt_seed: ClassVar[bool] = False

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send one request and return the normalised response."""

    def validate_request(self, request: LLMRequest) -> None:
        """Raise LLMConfigurationError before any call if the provider rejects the request."""

    @classmethod
    def validate_profile(cls, temperature: float | None, max_output_tokens: int | None, seed: int | None,
                         request_options: Mapping[str, Any]) -> None:
        """Raise LLMConfigurationError (with `field`) when a profile cannot work with this
        provider. Called when a profile is saved, before any prompt exists."""

    def model_identity(self, model: str) -> dict[str, Any]:
        """What identifies the served model beyond its name (digest, quantization, server
        version), recorded with each variant; the digest must match to resume. Empty when the
        provider does not report it. Raises when the model cannot be served."""
        return {}

    def sdk_version(self) -> str | None:
        return None

    def list_models(self) -> list[str]:
        """Model identifiers available to the configured account, when the API lists them."""
        return []

    @classmethod
    def key_present(cls, options: Mapping[str, Any]) -> bool | None:
        """Whether the API key this adapter would use is set; None when no key is needed."""
        name = options.get("api_key_env", cls.default_key_env)
        return has_env(name) if name else None


_REGISTRY: dict[str, type[LLMClient]] = {}


def register(name: str):
    def decorator(cls: type[LLMClient]) -> type[LLMClient]:
        if name in _REGISTRY:
            raise ValueError(f"Provider '{name}' is already registered")
        cls.provider = name
        _REGISTRY[name] = cls
        return cls

    return decorator


def providers() -> list[str]:
    return sorted(_REGISTRY)


def provider_class(provider: str) -> type[LLMClient]:
    if provider not in _REGISTRY:
        raise LLMConfigurationError(f"Unknown provider '{provider}'. Registered: {', '.join(providers())}")
    return _REGISTRY[provider]


def create_client(provider: str, **options: Any) -> LLMClient:
    """Instantiate the adapter registered as `provider` with its constructor options."""
    return provider_class(provider)(**options)


def provider_info() -> list[dict[str, Any]]:
    """Metadata of every registered adapter, for the configuration interface."""
    return [
        {
            "provider": name,
            "default_key_env": cls.default_key_env,
            "client_fields": [f.__dict__ for f in cls.client_fields],
            "accepts_temperature": cls.accepts_temperature,
            "request_example": cls.request_example,
            "pricing_url": cls.pricing_url,
            "paid": cls.paid,
            "per_attempt_seed": cls.per_attempt_seed,
        }
        for name, cls in sorted(_REGISTRY.items())
    ]
