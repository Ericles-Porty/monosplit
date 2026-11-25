"""Registry and adapters. SDK clients are replaced by stubs; no request leaves the machine."""

from __future__ import annotations

import httpx
import pytest

from monosplit.llm import LLMConfigurationError, LLMRequest, create_client, provider_info, providers
from monosplit.llm.anthropic_client import AnthropicClient
from monosplit.llm.gemini_client import GeminiClient
from monosplit.llm.ollama_client import OllamaClient, OllamaServerError
from monosplit.llm.openai_client import OpenAIChatClient

REQUEST = LLMRequest(system="sys", user="- A\n- B", model="m", max_output_tokens=100)


def test_registry_lists_every_adapter():
    assert providers() == ["anthropic", "fake", "gemini", "ollama", "openai", "openai_compatible"]
    with pytest.raises(LLMConfigurationError):
        create_client("unknown")
    info = {p["provider"]: p for p in provider_info()}
    assert [name for name, p in info.items() if not p["paid"]] == ["fake", "ollama"]
    assert [name for name, p in info.items() if p["per_attempt_seed"]] == ["ollama"]


def test_missing_api_key_is_a_configuration_error(monkeypatch):
    monkeypatch.delenv("MONOSPLIT_TEST_KEY", raising=False)
    with pytest.raises(LLMConfigurationError):
        create_client("openai", api_key_env="MONOSPLIT_TEST_KEY")


def test_anthropic_rejects_sampling_parameters(monkeypatch):
    monkeypatch.setenv("MONOSPLIT_TEST_KEY", "test")
    client = AnthropicClient(api_key_env="MONOSPLIT_TEST_KEY")
    with pytest.raises(LLMConfigurationError, match="temperature"):
        client.validate_request(LLMRequest(system="s", user="u", model="m", temperature=1.0))
    with pytest.raises(LLMConfigurationError):
        client.validate_request(LLMRequest(system="s", user="u", model="m", options={"top_p": 0.9}))
    with pytest.raises(LLMConfigurationError):
        client.validate_request(LLMRequest(system="s", user="u", model="m", seed=1))
    client.validate_request(REQUEST)


def test_anthropic_response_mapping(monkeypatch):
    from anthropic.types import Message

    monkeypatch.setenv("MONOSPLIT_TEST_KEY", "test")
    client = AnthropicClient(api_key_env="MONOSPLIT_TEST_KEY")
    message = Message.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": "{}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
    )
    sent = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return message

    def stream(**params):
        sent.update(params)
        return Stream()

    monkeypatch.setattr(client._client.messages, "stream", stream)
    response = client.generate(
        LLMRequest(system="sys", user="u", model="claude-opus-5-5", options={"output_config": {"effort": "high"}})
    )
    assert sent["system"] == "sys" and sent["max_tokens"] == 32000 and sent["output_config"] == {"effort": "high"}
    assert "temperature" not in sent
    assert (response.text, response.model, response.input_tokens, response.output_tokens) == ("{}", "claude-opus-5-5", 10, 20)
    assert not response.refused and not response.truncated
    assert response.raw["id"] == "msg_1"


def test_openai_response_mapping(monkeypatch):
    from openai.types.chat import ChatCompletion

    monkeypatch.setenv("MONOSPLIT_TEST_KEY", "test")
    client = OpenAIChatClient(api_key_env="MONOSPLIT_TEST_KEY")
    completion = ChatCompletion.model_validate(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-test-2026-01-01",
            "choices": [{"index": 0, "finish_reason": "length",
                         "message": {"role": "assistant", "content": "{", "refusal": None}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12,
                      "completion_tokens_details": {"reasoning_tokens": 3}},
        }
    )
    sent = {}

    def create(**params):
        sent.update(params)
        return completion

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    response = client.generate(LLMRequest(system="s", user="u", model="gpt-test", temperature=1.0, max_output_tokens=50))
    assert sent["temperature"] == 1.0 and sent["max_completion_tokens"] == 50
    assert sent["messages"][0] == {"role": "system", "content": "s"}
    assert (response.output_tokens, response.reasoning_tokens, response.truncated) == (7, 3, True)
    assert response.model == "gpt-test-2026-01-01"


def test_openai_compatible_needs_no_key_and_uses_max_tokens(monkeypatch):
    client = create_client("openai_compatible", base_url="http://localhost:11434/v1")
    sent = {}

    def create(**params):
        sent.update(params)
        raise RuntimeError("stop before parsing")

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    with pytest.raises(RuntimeError):
        client.generate(REQUEST)
    assert sent["max_tokens"] == 100 and "max_completion_tokens" not in sent


def test_gemini_response_mapping(monkeypatch):
    from google.genai import types

    monkeypatch.setenv("MONOSPLIT_TEST_KEY", "test")
    client = GeminiClient(api_key_env="MONOSPLIT_TEST_KEY")
    reply = types.GenerateContentResponse.model_validate(
        {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "{}"}]}, "finish_reason": "STOP"}],
            "usage_metadata": {"prompt_token_count": 4, "candidates_token_count": 6, "thoughts_token_count": 9},
            "model_version": "gemini-test-001",
            "response_id": "r1",
        }
    )
    sent = {}

    def generate_content(**params):
        sent.update(params)
        return reply

    monkeypatch.setattr(client._client.models, "generate_content", generate_content)
    response = client.generate(LLMRequest(system="s", user="u", model="gemini-test", max_output_tokens=10))
    assert sent["config"].system_instruction == "s" and sent["config"].max_output_tokens == 10
    assert (response.text, response.output_tokens, response.reasoning_tokens) == ("{}", 15, 9)
    assert response.finish_reason == "STOP" and not response.refused


def test_fake_client_groups_by_package():
    client = create_client("fake")
    response = client.generate(LLMRequest(system="", user="- a.X\n- a.Y\n- b.Z", model="fake"))
    assert '"classes": ["a.X", "a.Y"]' in response.text


# ---------------------------------------------------------------- Ollama (a fake server behind httpx.MockTransport)

DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
OLLAMA_REQUEST = LLMRequest(system="sys", user="- A\n- B", model="m:4b", max_output_tokens=100, seed=11,
                            options={"think": True, "options": {"num_ctx": 4096, "top_k": 20}})


class FakeOllama:
    """Answers the routes the adapter uses, like Ollama 0.40.15; `sent` keeps the chat bodies."""

    def __init__(self, digest=DIGEST, show=None, chat_status=200, chat_reply=None, context=4096):
        self.digest, self.context, self.sent = digest, context, []
        self.show = show if show is not None else {
            "details": {"format": "gguf", "family": "qwen35", "parameter_size": "4.2B", "quantization_level": "Q4_K_M",
                        "runner": "llamacpp"},
            "model_info": {"general.architecture": "qwen35", "qwen35.context_length": 262144,
                           "general.parameter_count": 4_200_000_000},
            "parameters": "temperature                    1\ntop_k                          20",
            "capabilities": ["completion", "thinking"],
            "template": "{{ .Prompt }}",
        }
        self.chat_status = chat_status
        self.chat_reply = chat_reply if chat_reply is not None else {
            "model": "m:4b", "message": {"role": "assistant", "content": '{"microservices": []}', "thinking": "long thoughts"},
            "done": True, "done_reason": "stop", "prompt_eval_count": 30, "prompt_eval_cached_count": 0, "eval_count": 50,
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json

        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.15"})
        if path == "/api/show":
            if self.show == "missing":
                return httpx.Response(404, json={"error": "model 'm:4b' not found"})
            return httpx.Response(200, json=self.show)
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": "m:4b", "model": "m:4b", "digest": self.digest, "size": 3_000_000_000},
                {"name": "big:120b-cloud", "remote_host": "https://ollama.com:443"},
            ]})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": [
                {"name": "m:4b", "size": 3_000_000_000, "size_vram": 1_500_000_000, "context_length": self.context},
            ]})
        if path == "/api/chat":
            self.sent.append(json.loads(request.content))
            if self.chat_status != 200:
                return httpx.Response(self.chat_status, json={"error": self.chat_reply})
            return httpx.Response(200, json=self.chat_reply)
        return httpx.Response(404, text="404 page not found")


def ollama(server: FakeOllama) -> OllamaClient:
    return OllamaClient(transport=httpx.MockTransport(server), retry_waits=())


def test_ollama_request_and_response_mapping():
    server = FakeOllama()
    client = ollama(server)
    identity = client.model_identity("m:4b")
    assert (identity["digest"], identity["quantization_level"], identity["trained_context_length"]) == (DIGEST, "Q4_K_M", 262144)
    assert identity["modelfile_parameters"] == ["temperature 1", "top_k 20"] and identity["server_version"] == "0.40.15"
    response = client.generate(OLLAMA_REQUEST)
    body = server.sent[0]
    assert (body["stream"], body["truncate"], body["shift"], body["think"]) == (False, False, False, True)
    assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "- A\n- B"}]
    assert body["options"] == {"num_ctx": 4096, "top_k": 20, "num_predict": 100, "seed": 11}  # no temperature: the model default
    assert response.text == '{"microservices": []}'  # the thinking stays in the raw response
    assert (response.input_tokens, response.output_tokens, response.truncated, response.refused) == (30, 50, False, False)
    assert response.raw["message"]["thinking"] == "long thoughts"
    assert response.runtime == {"server_version": "0.40.15", "digest": DIGEST, "context_length": 4096,
                                "size_bytes": 3_000_000_000, "size_vram_bytes": 1_500_000_000}
    assert client.sdk_version().startswith("ollama 0.40.15")
    assert client.list_models() == ["m:4b"]  # cloud models left out


def test_ollama_temperature_and_length_stop():
    server = FakeOllama(chat_reply={"model": "m:4b", "message": {"content": "{"}, "done_reason": "length",
                                    "prompt_eval_count": 30, "eval_count": 100})
    request = LLMRequest(system="s", user="u", model="m:4b", temperature=0.7, max_output_tokens=100,
                         options={"options": {"num_ctx": 4096}})
    response = ollama(server).generate(request)
    assert server.sent[0]["options"]["temperature"] == 0.7 and "seed" not in server.sent[0]["options"]
    assert response.truncated and response.finish_reason == "length"


@pytest.mark.parametrize(
    "max_tokens, options, field",
    [
        (100, {}, "request"),  # no num_ctx: the server default (4096 below 24 GB of VRAM) would cut prompts
        (100, {"options": {"num_ctx": "32k"}}, "request"),
        (None, {"options": {"num_ctx": 4096}}, "max_output_tokens"),
        (4096, {"options": {"num_ctx": 4096}}, "max_output_tokens"),
        (100, {"options": {"num_ctx": 4096, "seed": 1}}, "request"),
        (100, {"options": {"num_ctx": 4096, "num_predict": 9}}, "request"),
        (100, {"options": {"num_ctx": 4096, "temperature": 0.5}}, "request"),
        (100, {"truncate": True, "options": {"num_ctx": 4096}}, "request"),
        (100, {"options": [1]}, "request"),
    ],
)
def test_ollama_profile_checks(max_tokens, options, field):
    with pytest.raises(LLMConfigurationError) as info:
        OllamaClient.validate_profile(None, max_tokens, None, options)
    assert info.value.field == field


def test_ollama_refuses_a_prompt_that_cannot_fit_before_any_call():
    server = FakeOllama()
    client = ollama(server)
    long_prompt = LLMRequest(system="s", user="x" * 20_000, model="m:4b", max_output_tokens=1000,
                             options={"options": {"num_ctx": 4096}})
    with pytest.raises(LLMConfigurationError, match="cannot fit"):
        client.validate_request(long_prompt)
    client.validate_request(OLLAMA_REQUEST)
    assert server.sent == []


def test_ollama_context_overflow_is_a_configuration_error():
    # The server refuses a prompt longer than num_ctx (truncate = false) ...
    refused = FakeOllama(chat_status=400,
                         chat_reply="request (10141 tokens) exceeds the available context size (2048 tokens), try increasing it")
    with pytest.raises(LLMConfigurationError, match="Raise num_ctx") as info:
        ollama(refused).generate(OLLAMA_REQUEST)
    assert info.value.field == "request"
    # ... and the adapter refuses a prompt that leaves less room than the output limit.
    tight = FakeOllama(chat_reply={"model": "m:4b", "message": {"content": "{}"}, "done_reason": "stop",
                                   "prompt_eval_count": 4000, "eval_count": 10})
    with pytest.raises(LLMConfigurationError, match="needs 4100 tokens"):
        ollama(tight).generate(OLLAMA_REQUEST)


def test_ollama_model_problems():
    with pytest.raises(LLMConfigurationError, match="ollama pull") as info:
        ollama(FakeOllama(show="missing")).model_identity("m:4b")
    assert info.value.field == "model"
    cloud = FakeOllama(show={"remote_host": "https://ollama.com:443", "remote_model": "gpt-oss:120b"})
    with pytest.raises(LLMConfigurationError, match="cloud model"):
        ollama(cloud).model_identity("m:4b")
    server = FakeOllama()
    client = ollama(server)
    client.model_identity("m:4b")
    server.digest = "f" * 64  # `ollama pull` moved the tag to other weights
    with pytest.raises(LLMConfigurationError, match="other weights"):
        client.generate(OLLAMA_REQUEST)
    assert server.sent == []


def test_ollama_server_errors_are_api_errors():
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(OllamaServerError, match="not answering"):
        OllamaClient(transport=httpx.MockTransport(down), retry_waits=()).model_identity("m:4b")
    with pytest.raises(OllamaServerError, match="HTTP 500"):
        ollama(FakeOllama(chat_status=500, chat_reply="model requires more system memory")).generate(OLLAMA_REQUEST)
    with pytest.raises(LLMConfigurationError, match="without /v1"):
        OllamaClient(base_url="http://127.0.0.1:11434/v1")


def test_ollama_tries_again_after_a_server_crash():
    server = FakeOllama()
    crashes = iter([True, False])

    def flaky(request):
        if request.url.path == "/api/chat" and next(crashes):
            server.sent.append("crash")
            return httpx.Response(500, json={"error": "llama-server process has terminated: CUDA error"})
        return server(request)

    client = OllamaClient(transport=httpx.MockTransport(flaky), retry_waits=(0.0,))
    response = client.generate(OLLAMA_REQUEST)
    assert server.sent[0] == "crash" and server.sent[1]["options"]["seed"] == 11  # the same request, sent again
    assert response.text == '{"microservices": []}'
