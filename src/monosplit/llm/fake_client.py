"""Offline client for tests and dry runs of the pipeline.

It reads the class list from the prompt (lines starting with "- ") and answers without
calling any API: classes are grouped by package when names have packages, otherwise
spread over services in a seeded random order. Its outputs are not experimental data;
the dry-run configuration writes them under work/.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict

from .base import ClientField, LLMClient, LLMRequest, LLMResponse, register


def classes_in_prompt(user_prompt: str) -> list[str]:
    return [line[2:].strip() for line in user_prompt.splitlines() if line.startswith("- ")]


@register("fake")
class FakeClient(LLMClient):
    client_fields = (ClientField("seed", "number", 0), ClientField("invalid_first", "number", 0))
    accepts_temperature = True
    paid = False

    def __init__(self, invalid_first: int = 0, seed: int = 0, refuse: bool = False) -> None:
        self._invalid_first = invalid_first
        self._seed = seed
        self._refuse = refuse
        self.calls = 0

    def sdk_version(self) -> str | None:
        return "fake"

    def list_models(self) -> list[str]:
        return ["fake"]

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        classes = classes_in_prompt(request.user)
        if self._refuse:
            return self._response(request, "", "refusal", refused=True)
        if self.calls <= self._invalid_first:
            return self._response(request, "Here is the decomposition: {not valid json", "stop")

        groups: dict[str, list[str]] = defaultdict(list)
        if all("." in c for c in classes):
            for name in classes:
                groups[name.rsplit(".", 1)[0]].append(name)
        else:
            rng = random.Random(self._seed * 1000 + self.calls)
            shuffled = classes[:]
            rng.shuffle(shuffled)
            k = max(2, round(len(classes) / 6))
            for position, name in enumerate(shuffled):
                groups[f"group{position % k}"].append(name)
        payload = {
            "microservices": [
                {"name": f"service-{i + 1}", "classes": members}
                for i, (_key, members) in enumerate(sorted(groups.items()))
            ]
        }
        return self._response(request, json.dumps(payload), "stop")

    def _response(self, request: LLMRequest, text: str, finish: str, refused: bool = False) -> LLMResponse:
        return LLMResponse(
            text=text,
            model="fake",
            input_tokens=len(request.system + request.user) // 4,
            output_tokens=len(text) // 4,
            reasoning_tokens=None,
            finish_reason=finish,
            refused=refused,
            truncated=False,
            response_id=f"fake-{self.calls}",
            latency_s=0.0,
            raw={"fake": True, "text": text},
        )
