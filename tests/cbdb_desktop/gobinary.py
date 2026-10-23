"""Does the shipped Go source build the shipped binary?

The distribution carries ``Code/*.go`` beside ``cbdb.exe``, and this
suite reads that source **as data** in a dozen places -- the routing
table, the scratch-table ownership map, the citations in every defect it
files.  All of that is only true of the program users run if the source
is the program's source.  The 20261021 archive is the first where it is
not: the binary was rebuilt and all but one ``.go`` file is
byte-identical to the previous archive's.

The check compares **names**, because names are what both sides carry.
A Go binary keeps the name of every function it contains, stripped or
not -- the runtime needs them for stack traces, and inlined functions
keep theirs for the same reason -- in a table of NUL-terminated strings
(the ``pclntab``'s function-name table).  The ``main`` package's entries
are read straight out of the executable's bytes; the source declares the
same names with ``func``.  A function present in one and absent from the
other is code that was added, renamed or removed after the published
source was taken.

Two asymmetries keep that honest, both stated so nobody re-derives them:

* **A source function the binary lacks counts only if something calls
  it.**  The linker drops a function nothing references, so an unused
  helper is legitimately absent.  "Referenced" means its name occurs in
  the source outside comments and outside its own ``func`` line --
  read, not run, so a reference from code that is itself dead still
  counts, which errs towards reporting.
* **A binary name the source lacks counts only if the source does not
  declare it as something else.**  Package-level ``var`` and ``const``
  names sit in the same table (``main.kinshipMu``), as can types; the
  source's ``type``/``var``/``const`` declarations are subtracted.

What a name scan cannot see: a change *inside* a function that keeps
its name.  This finds a stale source when the edits added, renamed or
removed a function -- the common case, and the 20261021 one -- and is
silent about a build whose every change was to a body.

**Normalising the binary's names** (pinned on a fixture whose answer is
written down, in ``test_build_provenance.py``):

* ``main.(*T).m`` and ``main.T.m`` are the method ``T.m``; ``main.f`` is
  the function ``f``;
* compiler-made wrappers keep their parent's name with a suffix --
  ``-fm`` (a method value), ``.funcN`` (a closure), ``.deferwrapN``,
  ``.gowrapN``, ``-rangeN`` -- and count as the parent;
* generic instantiations ``f[...]`` count as ``f``;
* what the compiler writes for every program -- ``init``, ``init.N``,
  ``inittasks``, ``main``, the ``glob.`` initialisers, the type-equality
  helpers (``..eq.``) -- is nothing anyone declared, and is dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .gosource import strip_comments

#: A NUL-terminated ``main.`` name, as the function-name table stores
#: them.  The framing matters: unframed, the scan also reads type names
#: from reflection data (``*main.addrInfo``), file paths (``main.go``)
#: and fragments of longer strings.
_SYMBOL = re.compile(rb"(?<=\x00)main\.[A-Za-z0-9_.()*\[\]-]+(?=\x00)")

_WRAPPER = re.compile(
    r"(?:-fm|-range\d+|\.func\d+(?:\.\d+)*|\.deferwrap\d+|\.gowrap\d+)+$")

#: Functions every Go program's ``main`` package has whether or not the
#: source declares them -- the compiler writes them.
_COMPILER_MADE = frozenset({"init", "inittasks", "main", "glob"})


def normalise(symbol: str) -> str | None:
    """A binary symbol as the declared name it belongs to, or ``None``."""
    if not symbol.startswith("main.") or "..eq." in symbol:
        return None
    name = symbol[len("main."):]
    if not name or name.startswith("."):
        return None
    name = re.sub(r"\[[^\]]*\]", "", name)          # generic instantiation
    while True:
        stripped = _WRAPPER.sub("", name)
        if stripped == name:
            break
        name = stripped
    name = re.sub(r"(?:\.\d+)+$", "", name)         # init.0, init.1
    name = name.rstrip(".")
    if name.startswith("glob."):
        return None
    method = re.fullmatch(r"\(\*?([A-Za-z_]\w*)\)\.([A-Za-z_]\w*)", name)
    if method:
        return f"{method.group(1)}.{method.group(2)}"
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?", name):
        return None
    if name.split(".")[0] in _COMPILER_MADE and "." not in name:
        return None
    if name in _COMPILER_MADE:
        return None
    return name


def binary_names(data: bytes) -> set[str]:
    """Every declared ``main`` name in a Go executable's bytes."""
    out = set()
    for match in _SYMBOL.finditer(data):
        name = normalise(match.group().decode("ascii", "replace"))
        if name:
            out.add(name)
    return out


_FUNC = re.compile(
    r"^func\s+(?:\(\s*(?:[A-Za-z_]\w*\s+)?\*?\s*(?P<recv>[A-Za-z_]\w*)"
    r"(?:\[[^\]]*\])?\s*\)\s*)?(?P<name>[A-Za-z_]\w*)\s*[\[(]", re.MULTILINE)
_ONE = re.compile(r"^\s*(?:type|var|const)\s+(?P<name>[A-Za-z_]\w*)\b",
                  re.MULTILINE)
_BLOCK = re.compile(r"^\s*(?:type|var|const)\s*\((?P<body>.*?)^\s*\)",
                    re.MULTILINE | re.DOTALL)
_BLOCK_ENTRY = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\b", re.MULTILINE)


@dataclass
class Declarations:
    #: ``{function or Type.method: file name}``
    functions: dict[str, str]
    #: type, var and const names -- anything that is not a function
    others: set[str]
    #: functions whose name occurs in code other than their own ``func``
    referenced: set[str]


def source_declarations(sources: dict[str, str]) -> Declarations:
    """What ``{file name: Go source}`` declares, and which of it is used."""
    functions: dict[str, str] = {}
    others: set[str] = set()
    code = {name: strip_comments(text) for name, text in sources.items()}
    for file_name, text in sorted(code.items()):
        for m in _FUNC.finditer(text):
            name = (f"{m.group('recv')}.{m.group('name')}" if m.group("recv")
                    else m.group("name"))
            if m.group("name") in ("init", "main") and not m.group("recv"):
                continue
            functions.setdefault(name, file_name)
        others |= {m.group("name") for m in _ONE.finditer(text)}
        for block in _BLOCK.finditer(text):
            others |= {m.group("name")
                       for m in _BLOCK_ENTRY.finditer(block.group("body"))}
    joined = "\n".join(code[f] for f in sorted(code))
    referenced = set()
    for name in functions:
        bare = name.rsplit(".", 1)[-1]
        uses = len(re.findall(r"(?<![\w])" + re.escape(bare) + r"\b", joined))
        declared = len(re.findall(
            r"^func\s+(?:\([^)]*\)\s*)?" + re.escape(bare) + r"\b",
            joined, re.MULTILINE))
        if uses > declared:
            referenced.add(name)
    return Declarations(functions, others - set(functions), referenced)


@dataclass
class Comparison:
    #: names the binary has that the source does not declare
    only_in_binary: list[str]
    #: ``{name: file}`` the source declares *and calls* that the binary lacks
    only_in_source: dict[str, str]
    #: source functions nothing calls, absent from the binary as expected
    dropped_as_unused: list[str]
    #: how many names were compared, so an empty scan is not read as a match
    compared: int


def compare(exe_bytes: bytes, sources: dict[str, str]) -> Comparison:
    decl = source_declarations(sources)
    in_binary = binary_names(exe_bytes) - decl.others
    missing = sorted(set(decl.functions) - in_binary)
    return Comparison(
        only_in_binary=sorted(in_binary - set(decl.functions)),
        only_in_source={n: decl.functions[n] for n in missing
                        if n in decl.referenced},
        dropped_as_unused=[n for n in missing if n not in decl.referenced],
        compared=len(in_binary & set(decl.functions)))


def compare_files(exe: Path, go_files: list[Path]) -> Comparison:
    return compare(exe.read_bytes(),
                   {p.name: p.read_text(encoding="utf-8", errors="replace")
                    for p in go_files})
