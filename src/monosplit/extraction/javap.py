"""Run `javap -v -p` and parse its output into class records.

Each record holds the class's superclass, interfaces, declared methods and every
method invocation found in its bytecode:

- invokevirtual, invokespecial, invokestatic and invokeinterface instructions;
- invokedynamic instructions whose bootstrap arguments contain a method handle
  (method references and lambda bodies). A string concatenation has none.

javap omits the owner of a member that belongs to the class being printed
("// Method getUsername:()Ljava/lang/String;"); the parser fills it in.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

INVOKE_OPCODES = ("invokevirtual", "invokespecial", "invokestatic", "invokeinterface", "invokedynamic")
# Method-handle kinds that call code. REF_getField and similar only read or write fields.
INVOKING_HANDLE_KINDS = (
    "REF_invokeVirtual",
    "REF_invokeStatic",
    "REF_invokeSpecial",
    "REF_newInvokeSpecial",
    "REF_invokeInterface",
)

_INSTRUCTION = re.compile(
    r"^\s+(?P<offset>\d+): (?P<opcode>invoke\w+)\s+#\d+(?:,\s+\d+)?\s+"
    r"// (?P<kind>Method|InterfaceMethod|InvokeDynamic) (?P<ref>\S+)$"
)
_MEMBER_REF = re.compile(r'^(?:(?P<owner>"[^"]+"|[^".:\s]+)\.)?(?P<name>"[^"]+"|[^".:\s]+):(?P<desc>\S+)$')
_INDY_REF = re.compile(r"^#(?P<bsm>\d+):")
_LINE_ENTRY = re.compile(r"^\s+line (?P<line>\d+): (?P<pc>\d+)$")
_BSM_ENTRY = re.compile(r"^\s{2}(?P<index>\d+): #\d+ ")
_BSM_ARGUMENT = re.compile(r"^\s{6}#\d+ (?P<value>.+)$")
_HANDLE = re.compile(r"^(?P<kind>REF_\w+) (?P<ref>\S+)$")


@dataclass
class Invocation:
    method: str  # calling method: name + descriptor
    opcode: str  # invokevirtual ... or "invokedynamic/REF_invokeVirtual"
    owner: str  # internal name of the referenced class, e.g. org/x/Foo
    name: str
    desc: str
    offset: int
    line: int | None = None


@dataclass
class ClassRecord:
    name: str  # internal name, e.g. org/mybatis/jpetstore/domain/Cart
    declaration: str
    super_name: str | None
    interfaces: list[str]
    source_file: str | None = None
    methods: set[tuple[str, str]] = field(default_factory=set)
    invocations: list[Invocation] = field(default_factory=list)

    @property
    def kind(self) -> str:
        words = _strip_generics(self.declaration).split()
        for kind in ("interface", "enum", "record"):
            if kind in words:
                return "annotation" if kind == "interface" and "@interface" in self.declaration else kind
        return "abstract class" if "abstract" in words else "class"


def _strip_generics(text: str) -> str:
    previous = None
    while previous != text:
        previous, text = text, re.sub(r"<[^<>]*>", "", text)
    return text


def _internal(dotted: str) -> str:
    return dotted.strip().replace(".", "/")


def _parse_declaration(declaration: str) -> list[str]:
    """Interfaces implemented by a class, or extended by an interface."""
    text = _strip_generics(declaration)
    if " implements " in text:
        names = text.split(" implements ", 1)[1]
    elif " interface " in f" {text} " and " extends " in text:
        names = text.split(" extends ", 1)[1]
    else:
        return []
    return [_internal(n) for n in names.split(",") if n.strip()]


def _member_name(header: str, class_name: str) -> str:
    """Method name from a javap member header such as 'public void addItem(...)'."""
    if header.strip() == "static {};":
        return "<clinit>"
    name = header.split("(", 1)[0].split()[-1]
    return "<init>" if name == class_name.replace("/", ".") else name


def _unquote(text: str | None) -> str | None:
    return text[1:-1] if text and text.startswith('"') and text.endswith('"') else text


def _split_member(ref: str, current: str) -> tuple[str, str, str]:
    match = _MEMBER_REF.match(ref)
    if not match:
        raise ValueError(f"Unrecognised member reference: {ref}")
    owner = _unquote(match["owner"]) or current
    return owner, _unquote(match["name"]), match["desc"]


def _line_for(offset: int, table: list[tuple[int, int]]) -> int | None:
    """Source line of a bytecode offset, from (start_pc, line) entries."""
    line = None
    for start_pc, number in sorted(table):
        if start_pc > offset:
            break
        line = number
    return line


def parse_class(text: str) -> ClassRecord:
    """Parse the javap output of one class file."""
    lines = text.splitlines()
    declaration = next(
        line for line in lines[1:] if line and not line[0].isspace() and line != "Constant pool:"
    )
    this_match = next(re.search(r"this_class: #\d+\s+// (\S+)", l) for l in lines if "this_class:" in l)
    name = this_match.group(1)
    super_line = next((l for l in lines if "super_class:" in l), "")
    super_match = re.search(r"// (\S+)", super_line)
    record = ClassRecord(
        name=name,
        declaration=declaration,
        super_name=super_match.group(1) if super_match else None,
        interfaces=_parse_declaration(declaration),
    )

    pending_indy: list[tuple[str, int, int]] = []  # (method, offset, bootstrap index)
    method_lines: dict[str, list[tuple[int, int]]] = {}
    bootstrap: dict[int, list[tuple[str, str]]] = {}

    in_members = False
    method: str | None = None
    header: str | None = None
    reading_lines = False
    bsm_index: int | None = None
    in_bootstrap = False

    for line in lines:
        if not in_members:
            if line == "{":
                in_members = True
            elif line.startswith("SourceFile:"):
                record.source_file = line.split('"')[1]
            elif line == "BootstrapMethods:":
                in_bootstrap = True
            elif in_bootstrap:
                if line and not line[0].isspace():
                    in_bootstrap = False
                    continue
                entry = _BSM_ENTRY.match(line)
                if entry:
                    bsm_index = int(entry["index"])
                    bootstrap[bsm_index] = []
                    continue
                argument = _BSM_ARGUMENT.match(line)
                if argument and bsm_index is not None:
                    handle = _HANDLE.match(argument["value"])
                    if handle and handle["kind"] in INVOKING_HANDLE_KINDS:
                        bootstrap[bsm_index].append((handle["kind"], handle["ref"]))
            continue

        if line == "}":
            in_members = False
            method = None
            continue
        if line.startswith("  ") and not line.startswith("   ") and line.endswith(";"):
            header = line.strip()
            method = None
            reading_lines = False
            continue
        if line.startswith("    descriptor: ") and header is not None:
            if "(" in header or header == "static {};":
                desc = line.split("descriptor: ", 1)[1].strip()
                method_name = _member_name(header, name)
                record.methods.add((method_name, desc))
                method = f"{method_name}{desc}"
                method_lines[method] = []
            header = None
            continue
        if method is None:
            continue
        stripped = line.strip()
        if stripped == "LineNumberTable:":
            reading_lines = True
            continue
        if reading_lines:
            entry = _LINE_ENTRY.match(line)
            if entry:
                method_lines[method].append((int(entry["pc"]), int(entry["line"])))
                continue
            reading_lines = False
        instruction = _INSTRUCTION.match(line)
        if instruction:
            offset = int(instruction["offset"])
            if instruction["kind"] == "InvokeDynamic":
                pending_indy.append((method, offset, int(_INDY_REF.match(instruction["ref"])["bsm"])))
            else:
                owner, member, desc = _split_member(instruction["ref"], name)
                record.invocations.append(Invocation(method, instruction["opcode"], owner, member, desc, offset))

    for caller, offset, index in pending_indy:
        for kind, ref in bootstrap.get(index, []):
            owner, member, desc = _split_member(ref, name)
            record.invocations.append(Invocation(caller, f"invokedynamic/{kind}", owner, member, desc, offset))

    for invocation in record.invocations:
        invocation.line = _line_for(invocation.offset, method_lines.get(invocation.method, []))
    record.invocations.sort(key=lambda i: (i.method, i.offset, i.opcode))
    return record


def parse_output(text: str) -> list[ClassRecord]:
    """Parse javap output covering one or more class files."""
    blocks = re.split(r"(?m)^(?=Classfile )", text)
    return [parse_class(block) for block in blocks if block.startswith("Classfile ")]


def javap_command(jdk_home: Path) -> list[str]:
    exe = jdk_home / "bin" / ("javap.exe" if (jdk_home / "bin" / "javap.exe").exists() else "javap")
    return [str(exe), "-J-Dstdout.encoding=UTF-8", "-J-Duser.language=en", "-v", "-p"]


def run_javap(jdk_home: Path, class_dir: Path, class_files: list[Path], chunk: int = 60) -> str:
    """javap output for `class_files` (paths relative to `class_dir`)."""
    outputs = []
    for start in range(0, len(class_files), chunk):
        part = [str(p) for p in class_files[start:start + chunk]]
        result = subprocess.run(
            javap_command(jdk_home) + part, cwd=class_dir, capture_output=True, check=True
        )
        outputs.append(result.stdout.decode("utf-8"))
    return "".join(outputs)


def javap_version(jdk_home: Path) -> str:
    result = subprocess.run(javap_command(jdk_home)[:1] + ["-version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()
