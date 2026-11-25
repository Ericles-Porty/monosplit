from __future__ import annotations

import json

import pytest

from monosplit.validation import extract_json, validate_output

CLASSES = ["A", "B", "C", "D"]


def answer(*groups, names=None) -> str:
    services = [{"name": (names or [f"s{i}" for i in range(len(groups))])[i], "classes": list(g)}
                for i, g in enumerate(groups)]
    return json.dumps({"microservices": services})


def test_accepts_a_complete_partition():
    result = validate_output(answer("AB", "CD"), CLASSES)
    assert result.accepted
    assert result.k == 2
    assert result.partition == {"A": 0, "B": 0, "C": 1, "D": 1}
    assert result.json_location == "bare"


@pytest.mark.parametrize(
    "text, location",
    [
        ("```json\n" + answer("AB", "CD") + "\n```", "fence"),
        ("Here it is:\n" + answer("AB", "CD") + "\nThanks.", "embedded"),
    ],
)
def test_finds_json_in_fences_and_text(text, location):
    result = validate_output(text, CLASSES)
    assert result.accepted and result.json_location == location


@pytest.mark.parametrize(
    "text, reason",
    [
        ("no json here", "invalid_json"),
        ('{"services": []}', "invalid_schema"),
        ('{"microservices": [{"name": "x"}]}', "invalid_schema"),
        (answer("AB", "CDE"), "unknown_class"),
        (answer("AB", "BCD"), "duplicate_class"),
        (answer("AB", "C"), "missing_class"),
        (answer("ABCD"), "too_few_services"),
    ],
)
def test_rejection_reasons(text, reason):
    result = validate_output(text, CLASSES)
    assert not result.accepted
    assert result.reason == reason


def test_empty_services_are_dropped_not_rejected():
    result = validate_output(answer("AB", "", "CD"), CLASSES)
    assert result.accepted
    assert result.k == 2
    assert result.empty_services_dropped == 1


def test_one_service_plus_empty_ones_is_too_few():
    result = validate_output(answer("ABCD", ""), CLASSES)
    assert result.reason == "too_few_services"


def test_names_are_matched_exactly_after_trimming():
    text = json.dumps({"microservices": [{"name": "x", "classes": [" A", "B "]}, {"name": "y", "classes": ["c", "D"]}]})
    result = validate_output(text, CLASSES)
    assert result.reason == "unknown_class"
    assert result.problems["unknown_class"] == ["c"]
    assert result.problems["missing_class"] == ["C"]


def test_missing_service_name_gets_a_default():
    text = json.dumps({"microservices": [{"classes": ["A", "B"]}, {"name": " ", "classes": ["C", "D"]}]})
    result = validate_output(text, CLASSES)
    assert result.service_names == ["service_1", "service_2"]


def test_extract_json_returns_none_without_object():
    assert extract_json("[1, 2, 3] and {broken") is None
