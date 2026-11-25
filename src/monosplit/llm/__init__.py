"""LLM clients behind one interface. Importing this package registers every adapter.

Adapters import their SDK only when instantiated, so a missing SDK affects only its provider.
"""

from . import anthropic_client, fake_client, gemini_client, ollama_client, openai_client  # noqa: F401  (registration)
from .base import (
    LLMClient,
    LLMConfigurationError,
    LLMRequest,
    LLMResponse,
    create_client,
    provider_class,
    provider_info,
    providers,
    register,
)

__all__ = [
    "LLMClient",
    "LLMConfigurationError",
    "LLMRequest",
    "LLMResponse",
    "create_client",
    "provider_class",
    "provider_info",
    "providers",
    "register",
]
