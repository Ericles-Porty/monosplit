from __future__ import annotations

from monosplit.llm.fake_client import classes_in_prompt
from helpers import PROMPT_FILE
from monosplit.prompting import PromptTemplate, obfuscation_map, variant_graph


def test_template_renders_every_class_and_edge(toy_graph):
    template = PromptTemplate.load(PROMPT_FILE)
    system, user = template.render(toy_graph)
    assert "software architect" in system
    assert "$" not in user
    assert classes_in_prompt(user) == list(toy_graph.classes)
    for (a, b), n in toy_graph.calls.items():
        assert f"{a} -> {b}: {n}" in user
    assert f"Classes ({toy_graph.n_classes})" in user
    assert f"Call graph ({toy_graph.n_edges} edges, {toy_graph.total_calls} calls)" in user
    assert '{"microservices": [' in user


def test_template_comments_are_not_sent():
    template = PromptTemplate.load(PROMPT_FILE)
    assert "Placeholders" not in template.system + template.user


def test_obfuscation_keeps_edges_and_hides_names(toy_graph):
    graph, alias_to_class = variant_graph(toy_graph, "obfuscated", seed=42)
    assert set(graph.classes) == {f"C{i:02d}" for i in range(1, 7)}
    assert set(alias_to_class.values()) == set(toy_graph.classes)
    restored = {(alias_to_class[a], alias_to_class[b]): n for (a, b), n in graph.calls.items()}
    assert restored == toy_graph.calls


def test_obfuscation_is_seeded():
    classes = [f"org.x.K{i}" for i in range(30)]
    assert obfuscation_map(classes, 1) == obfuscation_map(classes, 1)
    assert obfuscation_map(classes, 1) != obfuscation_map(classes, 2)
    assert sorted(obfuscation_map(classes, 1).values())[0] == "C01"


def test_original_variant_is_unchanged(toy_graph):
    graph, alias_to_class = variant_graph(toy_graph, "original", seed=42)
    assert graph is toy_graph
    assert alias_to_class == {c: c for c in toy_graph.classes}
