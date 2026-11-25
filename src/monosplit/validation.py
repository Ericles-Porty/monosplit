"""Acceptance rule for an LLM output.

An output is accepted when all of the following hold:
1. it contains a JSON object (bare, inside a ``` code fence, or surrounded by text);
2. the object has the requested format: {"microservices": [{"name": str, "classes": [str, ...]}, ...]};
3. every class name is one of the classes sent in the prompt;
4. no class appears more than once;
5. every class sent in the prompt appears;
6. there are at least two non-empty services.

Services with an empty class list are dropped and counted; they do not reject the
output. Checks run in this order, and the first failing check is the rejection reason.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from .partition import Partition

REASONS = (
    "invalid_json",
    "invalid_schema",
    "unknown_class",
    "duplicate_class",
    "missing_class",
    "too_few_services",
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class ValidationResult:
    accepted: bool
    reason: str | None = None
    detail: str = ""
    json_location: str | None = None  # bare | fence | embedded
    partition: Partition | None = None  # class -> service index, in prompt names
    service_names: list[str] | None = None
    k: int | None = None
    empty_services_dropped: int = 0
    problems: dict[str, list[str]] = field(default_factory=dict)


def extract_json(text: str) -> tuple[object, str] | None:
    """Return the first JSON object found in `text` and where it was found."""
    stripped = text.strip()
    try:
        return json.loads(stripped), "bare"
    except json.JSONDecodeError:
        pass
    for block in _FENCE.findall(text):
        try:
            return json.loads(block.strip()), "fence"
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _end = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value, "embedded"
    return None


def validate_output(text: str, expected_classes: Sequence[str], min_services: int = 2) -> ValidationResult:
    found = extract_json(text)
    if found is None:
        return ValidationResult(False, "invalid_json", "No JSON object in the output")
    data, location = found

    services = data.get("microservices") if isinstance(data, dict) else None
    if not isinstance(services, list) or not services:
        return ValidationResult(False, "invalid_schema", "Missing non-empty list 'microservices'", location)
    names: list[str] = []
    groups: list[list[str]] = []
    dropped = 0
    for position, service in enumerate(services):
        if not isinstance(service, dict) or not isinstance(service.get("classes"), list):
            return ValidationResult(
                False, "invalid_schema", f"Service {position} is not an object with a 'classes' list", location
            )
        classes = service["classes"]
        if not all(isinstance(c, str) for c in classes):
            return ValidationResult(False, "invalid_schema", f"Service {position} has non-string classes", location)
        if not classes:
            dropped += 1
            continue
        name = service.get("name")
        names.append(name.strip() if isinstance(name, str) and name.strip() else f"service_{position + 1}")
        groups.append([c.strip() for c in classes])

    expected = set(expected_classes)
    listed = [c for group in groups for c in group]
    problems = {
        "unknown_class": sorted(set(listed) - expected),
        "duplicate_class": sorted(c for c, n in Counter(listed).items() if n > 1),
        "missing_class": sorted(expected - set(listed)),
    }
    problems = {k: v for k, v in problems.items() if v}
    for reason in ("unknown_class", "duplicate_class", "missing_class"):
        if reason in problems:
            detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in problems.items())
            return ValidationResult(
                False, reason, detail, location, empty_services_dropped=dropped, problems=problems
            )

    if len(groups) < min_services:
        return ValidationResult(
            False,
            "too_few_services",
            f"{len(groups)} non-empty service(s); at least {min_services} required",
            location,
            k=len(groups),
            empty_services_dropped=dropped,
        )

    partition = {c: index for index, group in enumerate(groups) for c in group}
    return ValidationResult(
        True,
        json_location=location,
        partition=partition,
        service_names=names,
        k=len(groups),
        empty_services_dropped=dropped,
    )
