"""Call-graph extraction checked on the Java fixture in tests/fixtures/java.

Expected graph (derived by hand from the fixture sources):
- Controller -> Service: 3 (constructor, get, toString declared in Service);
  service.hashCode() is declared only in Object, a library call.
- Service -> Base: 2 (super constructor; log(...), recorded against Service in the
  bytecode and resolved to Base, which declares it).
- Service -> Repo: 4 (Repo.create(), find in get, the method reference repo::lookup,
  and find inside the anonymous class Service$1, merged into Service).
- Lonely has no edges.

tests/fixtures/javap_app.txt is the javap output of the compiled fixture (JDK 21), so the
parser is tested without a JDK. The second test compiles the fixture again when a JDK is
installed and checks that the live output gives the same graph.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from monosplit.extraction.extract import build_extraction, collect_class_files, extract
from monosplit.extraction.javap import parse_output
from monosplit.extraction.jdk import find_jdk

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_CALLS = {
    ("app.Controller", "app.Service"): 3,
    ("app.Service", "app.Base"): 2,
    ("app.Service", "app.Repo"): 4,
}


def _check(extraction) -> None:
    graph = extraction.graph
    assert graph.classes == ("app.Base", "app.Controller", "app.Lonely", "app.Repo", "app.Service")
    assert graph.calls == EXPECTED_CALLS
    assert extraction.stats["class_files"] == 6
    assert extraction.stats["isolated_classes"] == 1
    assert extraction.stats["method_handle_invocations_edge"] == 1


def test_parse_saved_javap_output():
    records = parse_output((FIXTURES / "javap_app.txt").read_text(encoding="utf-8"))
    extraction = build_extraction(records)
    _check(extraction)

    service = next(r for r in records if r.name == "app/Service")
    assert service.super_name == "app/Base"
    assert ("log", "(Ljava/lang/String;)V") not in service.methods
    assert ("<init>", "()V") in service.methods
    base = next(r for r in records if r.name == "app/Base")
    assert base.kind == "abstract class"


def test_call_sites_have_lines_and_resolved_targets():
    extraction = build_extraction(parse_output((FIXTURES / "javap_app.txt").read_text(encoding="utf-8")))
    log_call = next(s for s in extraction.sites if s.target.startswith("app/Service.log:"))
    assert (log_call.callee, log_call.status, log_call.source, log_call.line) == ("app.Base", "edge", "app/Service.java", 9)
    anonymous = next(s for s in extraction.sites if s.caller_class_file == "app.Service$1" and s.status == "edge")
    assert (anonymous.caller, anonymous.callee, anonymous.line) == ("app.Service", "app.Repo", 21)
    hash_call = next(s for s in extraction.sites if "hashCode" in s.target)
    assert hash_call.status == "library"


@pytest.mark.skipif(find_jdk() is None, reason="no JDK installed (uv run monosplit jdk install)")
def test_live_javac_and_javap(tmp_path):
    jdk = find_jdk()
    javac = jdk / "bin" / ("javac.exe" if (jdk / "bin" / "javac.exe").exists() else "javac")
    sources = sorted(str(p) for p in (FIXTURES / "java").rglob("*.java"))
    classes = tmp_path / "classes"
    subprocess.run([str(javac), "-g", "--release", "21", "-d", str(classes), *sources], check=True)
    assert len(collect_class_files(classes)) == 6
    _check(extract(jdk, [classes]))


def test_edge_sample_finds_the_module_of_each_file(tmp_path):
    from monosplit.extraction.extract import edge_sample, source_root_finder
    from monosplit.graph import CallGraph

    for root, source in (("core/src", "app/Cart.java"), ("web/src", "app/web/Shop.java")):
        (tmp_path / root / source).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / root / source).write_text("class X {}", encoding="utf-8")
    graph = CallGraph.build(["app.Cart", "app.Item", "app.web.Shop"], {("app.Cart", "app.Item"): 1, ("app.web.Shop", "app.Cart"): 1})

    def site(caller, callee, source, line):
        return {"caller": caller, "caller_class_file": caller, "caller_method": "run()V", "target": f"{callee.replace('.', '/')}.go:()V",
                "callee": callee, "opcode": "invokevirtual", "source": source, "line": line, "status": "edge"}

    sites = [site("app.Cart", "app.Item", "app/Cart.java", 3), site("app.web.Shop", "app.Cart", "app/web/Shop.java", 7)]
    rows = edge_sample(graph, sites, 2, 1, source_root_finder(tmp_path, ["core/src", "web/src"]))
    paths = {row["caller"]: row["call_sites"].split(" ", 1)[0] for row in rows}
    assert paths == {"app.Cart": "core/src/app/Cart.java:3", "app.web.Shop": "web/src/app/web/Shop.java:7"}
