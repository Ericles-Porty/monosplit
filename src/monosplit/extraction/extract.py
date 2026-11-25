"""Build the class-level static call graph of an application from its bytecode.

Counting rules:
- Nodes: top-level classes compiled from the application's main sources (interfaces,
  enums and abstract classes included). Nested, inner, local and anonymous classes are
  merged into their top-level class.
- One call = one invocation instruction (or one method handle of an invokedynamic
  instruction, as in method references) whose target is a method or constructor of
  another top-level class of the application.
- The target is the class that declares the invoked member. javac records the static
  type of the receiver, so `setMessage(...)` inside AccountActionBean is recorded
  against AccountActionBean even though AbstractActionBean declares it; the extractor
  walks the superclasses and interfaces of the application to find the declaring class.
  Members declared only in library types (Object.toString, a Stripes interface) are
  library calls and stay out of the graph.
- Calls inside the same top-level class are not edges.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from ..graph import CallGraph
from .javap import ClassRecord, parse_output, run_javap

SKIPPED_CLASS_FILES = ("module-info.class", "package-info.class")


@dataclass
class CallSite:
    caller: str  # top-level class, dotted name
    caller_class_file: str  # class file holding the call, e.g. org.x.Outer$1
    caller_method: str
    target: str  # member as referenced in the bytecode: owner.name:desc
    callee: str  # top-level class that declares the member; empty for library members
    opcode: str
    source: str  # source file relative to the source root
    line: int | None
    status: str  # edge | self | library


@dataclass
class Extraction:
    graph: CallGraph
    sites: list[CallSite]
    class_rows: list[dict]
    stats: dict


def _dotted(internal: str) -> str:
    return internal.replace("/", ".")


def collect_class_files(class_dir: Path) -> list[Path]:
    return sorted(
        p.relative_to(class_dir)
        for p in class_dir.rglob("*.class")
        if p.name not in SKIPPED_CLASS_FILES
    )


def build_extraction(records: list[ClassRecord]) -> Extraction:
    by_name = {r.name: r for r in records}
    if len(by_name) != len(records):
        raise ValueError("The same class file appears twice")

    def top_level(internal: str) -> str:
        outer = internal.split("$", 1)[0]
        return outer if outer in by_name else internal

    def declaring_class(owner: str, name: str, desc: str) -> str | None:
        queue, seen = [owner], set()
        while queue:
            current = queue.pop(0)
            if current in seen or current not in by_name:
                continue
            seen.add(current)
            record = by_name[current]
            if (name, desc) in record.methods:
                return current
            if record.super_name:
                queue.append(record.super_name)
            queue.extend(record.interfaces)
        return None

    tops = sorted({top_level(r.name) for r in records})
    sites: list[CallSite] = []
    counts: Counter[tuple[str, str]] = Counter()
    for record in records:
        caller = top_level(record.name)
        package = record.name.rsplit("/", 1)[0] if "/" in record.name else ""
        source = f"{package}/{record.source_file}" if record.source_file else ""
        for inv in record.invocations:
            declaring = declaring_class(inv.owner, inv.name, inv.desc)
            if declaring is None:
                callee, status = "", "library"
            else:
                callee = _dotted(top_level(declaring))
                status = "self" if top_level(declaring) == caller else "edge"
            if status == "edge":
                counts[(_dotted(caller), callee)] += 1
            sites.append(
                CallSite(
                    caller=_dotted(caller),
                    caller_class_file=_dotted(record.name),
                    caller_method=inv.method,
                    target=f"{inv.owner}.{inv.name}:{inv.desc}",
                    callee=callee,
                    opcode=inv.opcode,
                    source=source,
                    line=inv.line,
                    status=status,
                )
            )

    graph = CallGraph.build((_dotted(t) for t in tops), dict(counts))
    class_rows = []
    for top in tops:
        name = _dotted(top)
        record = by_name[top]
        package = top.rsplit("/", 1)[0] if "/" in top else ""
        class_rows.append(
            {
                "class": name,
                "package": _dotted(package),
                "simple_name": top.rsplit("/", 1)[-1],
                "kind": record.kind,
                "source": f"{package}/{record.source_file}" if record.source_file else "",
                "class_files": sum(1 for r in records if top_level(r.name) == top),
                "out_edges": sum(1 for (a, _b) in graph.calls if a == name),
                "in_edges": sum(1 for (_a, b) in graph.calls if b == name),
                "out_calls": sum(n for (a, _b), n in graph.calls.items() if a == name),
                "in_calls": sum(n for (_a, b), n in graph.calls.items() if b == name),
            }
        )
    status_counts = Counter(s.status for s in sites)
    stats = {
        "class_files": len(records),
        "classes": graph.n_classes,
        "edges": graph.n_edges,
        "calls_in_graph": graph.total_calls,
        "isolated_classes": sum(1 for row in class_rows if row["out_edges"] == 0 and row["in_edges"] == 0),
        "invocations_total": len(sites),
        "invocations_edge": status_counts["edge"],
        "invocations_self": status_counts["self"],
        "invocations_library": status_counts["library"],
        "method_handle_invocations_edge": sum(
            1 for s in sites if s.status == "edge" and s.opcode.startswith("invokedynamic/")
        ),
    }
    return Extraction(graph=graph, sites=sites, class_rows=class_rows, stats=stats)


def extract(jdk_home: Path, class_dirs: list[Path]) -> Extraction:
    records: list[ClassRecord] = []
    for class_dir in class_dirs:
        files = collect_class_files(class_dir)
        if not files:
            raise RuntimeError(f"No class files under {class_dir}")
        records.extend(parse_output(run_javap(jdk_home, class_dir, files)))
    return build_extraction(records)


def store_extraction(store, app_id: str, extraction: Extraction, meta: dict, source: str = "cli") -> None:
    """Store the class rows, edges, call sites and metadata of `app_id` in the graphs collection."""
    store.put_graph(
        app_id,
        extraction.class_rows,
        [{"caller": a, "callee": b, "calls": n} for (a, b), n in sorted(extraction.graph.calls.items())],
        [asdict(site) for site in extraction.sites],
        {**meta, "stats": extraction.stats},
        source=source,
    )


_CLASS_INTS = ("class_files", "out_edges", "in_edges", "out_calls", "in_calls")


def read_graph_folder(folder: Path) -> dict:
    """classes.csv, edges.csv, call_sites.csv and graph.json of the earlier file layout,
    with numbers converted, as the arguments of Store.put_graph."""
    with (folder / "classes.csv").open(newline="", encoding="utf-8") as f:
        classes = [{k: (int(v) if k in _CLASS_INTS and v != "" else v) for k, v in row.items()} for row in csv.DictReader(f)]
    with (folder / "edges.csv").open(newline="", encoding="utf-8") as f:
        edges = [{"caller": r["caller"], "callee": r["callee"], "calls": int(r["calls"])} for r in csv.DictReader(f)]
    sites = []
    if (folder / "call_sites.csv").exists():
        sites = [asdict(site) for site in read_call_sites(folder / "call_sites.csv")]
    meta = json.loads((folder / "graph.json").read_text(encoding="utf-8")) if (folder / "graph.json").exists() else {}
    return {"classes": classes, "edges": edges, "call_sites": sites, "meta": meta}


def read_call_sites(path: Path) -> list[CallSite]:
    with path.open(newline="", encoding="utf-8") as f:
        return [
            CallSite(**{**row, "line": int(row["line"]) if row["line"] else None})
            for row in csv.DictReader(f)
        ]


def describe_site(site: CallSite, source_root: str) -> str:
    """'src/main/java/x/Cart.java:70 addItem -> CartItem.<init>' for a person reading the code."""
    caller_method = site.caller_method.split("(", 1)[0]
    referenced_owner, member = site.target.split(":", 1)[0].rsplit(".", 1)
    declaring = site.callee.rsplit(".", 1)[-1]
    text = f"{source_root}/{site.source}:{site.line} {caller_method} -> {declaring}.{member}"
    referenced = referenced_owner.rsplit("/", 1)[-1]
    if referenced.split("$", 1)[0] != declaring:
        text += f" (called on {referenced}, declared in {declaring})"
    if site.opcode.startswith("invokedynamic/"):
        text += " (method reference)"
    return text


EDGE_CHECK_FIELDS = ("caller", "callee", "calls", "call_sites", "confirmed", "notes")


def source_root_finder(checkout: Path, source_roots: list[str] | tuple[str, ...]) -> Callable[[str], str]:
    """For a source file relative to a source root (app/Cart.java), the source root of the
    checkout that holds it; the first root when no checkout holds the file. Applications with
    several modules have one source root per module."""
    def find(source: str) -> str:
        for root in source_roots:
            if (checkout / root / source).is_file():
                return root
        return source_roots[0]

    return find


def edge_sample(graph: CallGraph, sites: list[dict], n: int, seed: int,
                source_root: str | Callable[[str], str]) -> list[dict]:
    """Sample `n` edges for manual checking against the source code.

    Each row lists up to three call sites (file:line, relative to the application
    checkout) and leaves the columns `confirmed` (yes/no) and `notes` for the person
    checking. An edge is confirmed when the listed lines contain the calls. `source_root`
    is the source folder, or a function that finds it for each file (source_root_finder).
    """
    root_of = source_root if callable(source_root) else (lambda _source: source_root)
    edge_sites = [CallSite(**s) for s in sites if s["status"] == "edge"]
    edges = graph.edges
    sample = sorted(random.Random(seed).sample(edges, min(n, len(edges))))
    rows = []
    for caller, callee in sample:
        matching = [s for s in edge_sites if s.caller == caller and s.callee == callee]
        examples = "; ".join(describe_site(s, root_of(s.source)) for s in matching[:3])
        rows.append({"caller": caller, "callee": callee, "calls": graph.calls[(caller, callee)],
                     "call_sites": examples, "confirmed": "", "notes": ""})
    return rows


def write_edge_check(rows: list[dict], path: Path) -> Path:
    """The edge check as a CSV file (the layout of earlier versions)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(EDGE_CHECK_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_edge_check(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [{**row, "calls": int(row["calls"]) if row.get("calls") else None} for row in csv.DictReader(f)]
