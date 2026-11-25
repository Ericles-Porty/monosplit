"""Controls and metrics for every accepted LLM run.

For each accepted run with K services: the LLM partition, one AH partition per AH
variant cut at K, and one random partition into K services (seed derived from the
master seed and the run), all measured with SM, IFN, ICP and NED on the same graph.
HDBSCAN is computed once per distance, outside the pairing by K.

AH selection rule, fixed before the pilot runs (ah_primary = "auto"): the AH variant
with the highest median SM over all accepted runs becomes the AH control; ties go to
the variant listed first. This picks the strongest AH on the primary metric.

Stored in the database as the current evaluation of the study (store.py):
    metrics                 one row per (variant, run, method)
    evaluations.partitions  every partition measured
    evaluations.ah_selection        median SM of each AH variant and the selected one
    evaluations.paired_differences  LLM minus control, per run, for the AH control and the random partition

A new evaluation replaces the previous one atomically.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from .config import ExperimentConfig
from .controls import DISTANCES, AHVariant, agglomerative, hdbscan_partition, random_partition
from .metrics import compute
from .partition import canonical
from .seeds import derive_seed
from .store import clean_row, pairs

METRICS = ("sm", "ifn", "icp", "ned")


def load_accepted(config: ExperimentConfig, profile: str, variant: str) -> list[dict]:
    return config.store().accepted_runs(config.key(profile, variant))


def random_seed(config: ExperimentConfig, profile: str, variant: str, run: int) -> int:
    return derive_seed(config.seed, config.app, profile, variant, run, "random")


def select_ah(rows: list[dict], config: ExperimentConfig) -> tuple[AHVariant, list[dict]]:
    table = []
    for variant in config.ah_variants:
        values = [r["sm"] for r in rows if r["method"] == f"ah:{variant.name}"]
        table.append({"ah_variant": variant.name, "runs": len(values), "median_sm": statistics.median(values) if values else None})
    if config.ah_primary != "auto":
        chosen = AHVariant.parse(config.ah_primary)
    else:
        candidates = [t for t in table if t["median_sm"] is not None]
        if not candidates:
            raise RuntimeError("No accepted runs to select the AH variant")
        best = max(t["median_sm"] for t in candidates)
        chosen = AHVariant.parse(next(t["ah_variant"] for t in candidates if t["median_sm"] == best))
    for t in table:
        t["selected"] = t["ah_variant"] == chosen.name
        t["rule"] = "highest median SM" if config.ah_primary == "auto" else "fixed in config"
    return chosen, table


def evaluate(config: ExperimentConfig, profile: str) -> str:
    """Compute the controls and metrics and store them as the current evaluation; returns its id."""
    graph = config.graph()
    rows: list[dict] = []
    partitions: list[dict] = []

    def measure(variant: str, run: int | str, method: str, partition: dict, seed: int | None = None, **extra) -> None:
        values = compute(graph, partition)
        rows.append(
            {"variant": variant, "run": run, "method": method, "k": values.k,
             **{m: getattr(values, m) for m in METRICS}, "seed": seed, **extra}
        )
        partitions.append(
            {"variant": variant, "run": run, "method": method, "seed": seed,
             "partition": canonical(partition, graph.classes)}
        )

    for variant in config.variants:
        for run in load_accepted(config, profile, variant):
            if set(run["partition"]) != set(graph.classes):
                raise RuntimeError(f"{variant} run {run['run']}: partition does not cover the graph")
            k = run["k"]
            measure(variant, run["run"], "llm", run["partition"])
            for ah in config.ah_variants:
                measure(variant, run["run"], f"ah:{ah.name}", agglomerative(graph, k, ah))
            seed = random_seed(config, profile, variant, run["run"])
            measure(variant, run["run"], "random", random_partition(graph.classes, k, seed), seed)
    if not rows:
        raise RuntimeError(f"No accepted runs for {config.name}/{config.app}/{profile} in database {config.database}")

    for distance in DISTANCES:
        partition, noise = hdbscan_partition(graph, distance, config.hdbscan_min_cluster_size)
        measure("", None, f"hdbscan:{distance}", partition, noise_points=noise)

    chosen, selection = select_ah(rows, config)
    paired = []
    for variant in config.variants:
        llm_rows = [r for r in rows if r["variant"] == variant and r["method"] == "llm"]
        for llm in llm_rows:
            for control in (f"ah:{chosen.name}", "random"):
                other = next(r for r in rows if r["variant"] == variant and r["run"] == llm["run"] and r["method"] == control)
                paired.append(
                    {"variant": variant, "run": llm["run"], "control": "ah" if control != "random" else "random",
                     "control_method": control, "k": llm["k"], **{f"d_{m}": llm[m] - other[m] for m in METRICS}}
                )

    from .runner import graph_fingerprint

    doc = {
        "graph_sha256": graph_fingerprint(graph),
        "evaluated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "ah_selection": [clean_row(r) for r in selection],
        "paired_differences": [clean_row(r) for r in paired],
        "partitions": [{**item, "partition": pairs(item["partition"])} for item in partitions],
    }
    return config.store().save_evaluation(config.key(profile), doc, rows)
