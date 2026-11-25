"""End-to-end check with the fake client: runs, controls, metrics and the report."""

from __future__ import annotations

from helpers import fake_profile, make_config
from monosplit import report as report_module
from monosplit.evaluate import evaluate
from monosplit.llm import create_client
from monosplit.report import write_report
from monosplit.runner import run_variant


def test_pipeline_end_to_end(tmp_path, toy_graph, monkeypatch):
    monkeypatch.setattr(report_module, "WORK_DIR", tmp_path / "work")
    config = make_config(tmp_path, toy_graph)
    for variant in config.variants:
        run_variant(create_client("fake", seed=3), fake_profile(), config, variant, toy_graph)

    store, key = config.store(), config.key("fake")
    first_id = evaluate(config, "fake")
    metrics = store.metrics(key)
    per_run = 1 + len(config.ah_variants) + 1  # LLM, every AH variant, random
    assert len(metrics) == 2 * 3 * per_run + 2  # two variants, three runs, two HDBSCAN rows
    for variant in config.variants:
        for run in {r["run"] for r in metrics if r["variant"] == variant}:
            ks = {r["k"] for r in metrics if r["variant"] == variant and r["run"] == run}
            assert len(ks) == 1, "every method of a run must have the LLM's K"

    evaluation = store.evaluation(key)
    assert sum(r["selected"] is True for r in evaluation["ah_selection"]) == 1
    paired = evaluation["paired_differences"]
    assert len(paired) == 2 * 3 * 2
    assert {r["control"] for r in paired} == {"ah", "random"}

    second_id = evaluate(config, "fake")
    assert second_id != first_id
    assert store.metrics(key) == metrics, "controls must be reproducible"
    # The new evaluation replaced the old one: no metric row of the first is left.
    assert store.db.metrics.count_documents({"evaluation_id": first_id}) == 0

    copy = write_report(config, "fake").read_text(encoding="utf-8")
    assert "## Paired differences (LLM - control)" in copy
    assert "no hypothesis test" in copy
    stored = store.evaluation(key)
    assert stored["report_md"] == copy
    assert {s["variant"] for s in stored["attempts_summary"]} == {"original", "obfuscated"}
