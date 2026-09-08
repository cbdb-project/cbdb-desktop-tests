"""Read the application's routing table out of its own Go source.

The shipped distribution includes ``Code/*.go``, so the set of routes the
binary serves is knowable without guessing and without maintaining a
duplicate list that drifts.  This module treats that source strictly as
**data**: it extracts route registrations and the navigation page map,
and interprets nothing about what a handler then does.

That distinction is the whole design rule of this suite.  Reading "the
app registers POST /api/entry/query" out of the source and then checking
the running binary answers it is a cross-check between two artefacts of
the same build.  Reading the SQL out of a handler and re-running it in
Python would be a transcription, and would only ever test the copy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .staging import AppLayout

_HANDLE_FUNC_START = re.compile(r"\br\.HandleFunc\(\s*\"(?P<path>[^\"]+)\"\s*,")
_METHODS_START = re.compile(r"\A\s*\.Methods\(")

# Anything that is not code: line and block comments, and string, raw
# string and rune literals.  Blanked (length-preserving) before scanning
# so that offsets still line up with the original file.
_NON_CODE = re.compile(
    r"//[^\n]*"           # line comment
    r"|/\*.*?\*/"         # block comment
    r"|`[^`]*`"           # raw string
    r"|\"(?:\\.|[^\"\\])*\""   # interpreted string
    r"|'(?:\\.|[^'\\])*'",     # rune
    re.DOTALL,
)


def _blank_non_code(source: str, *, keep_strings: bool = True) -> str:
    """Replace comments (and optionally strings) with spaces of equal length.

    Offsets are preserved, so a match found in the blanked text points at
    the same place in the original.  ``keep_strings=True`` blanks only
    comments, which is what route scanning needs: the route path is
    itself a string literal.
    """
    def blank(match: re.Match[str]) -> str:
        text = match.group(0)
        if keep_strings and not text.startswith(("//", "/*")):
            return text
        return "".join(" " if ch != "\n" else "\n" for ch in text)

    return _NON_CODE.sub(blank, source)

_PATH_PREFIX_RE = re.compile(r"""\br\.PathPrefix\(\s*"(?P<prefix>[^"]+)"\s*\)""")

_METHOD_RE = re.compile(r'"([A-Z]+)"')

# The navigation wildcard's page map, e.g.  "entry": "LookAtEntry",
_PAGE_MAP_RE = re.compile(r'^\s*"(?P<key>[a-z_]+)"\s*:\s*"(?P<target>\w+)"\s*,',
                          re.MULTILINE)

# serveStaticFile(pickersDir, "entry_picker.html")
_PICKER_RE = re.compile(r'serveStaticFile\(\s*\w+\s*,\s*"(?P<file>[^"]+)"\s*\)')


@dataclass(frozen=True)
class Route:
    """One route the application registers."""

    path: str
    methods: tuple[str, ...]
    handler: str
    source: str  # "file:line", for failure messages that point at the code

    @property
    def is_page(self) -> bool:
        """A route that renders HTML rather than serving JSON."""
        return not self.path.startswith("/api/")

    @property
    def is_wildcard(self) -> bool:
        return "{" in self.path

    @property
    def form(self) -> str:
        """Which form a route belongs to, by source file."""
        name = self.source.split(":", 1)[0]
        return name.removesuffix("_form_backend.go").removesuffix(".go")


def _close_paren(source: str, open_index: int) -> int:
    """Index of the ``)`` matching the ``(`` at ``open_index``.

    A regex cannot do this: several handlers are themselves calls --
    ``serveStaticFile(pickersDir, "entry_picker.html")``,
    ``qbePageHandler(tmplFile)`` -- so a non-greedy match to the first
    ``)`` silently drops those routes.  Missing routes in a route-drift
    check is the one failure mode that would make the check worthless,
    so the nesting is tracked properly: interpreted and raw strings,
    runes, and both comment forms are skipped rather than counted.
    """
    depth = 0
    index = open_index
    length = len(source)
    while index < length:
        char = source[index]
        pair = source[index:index + 2]
        if pair == "//":
            newline = source.find("\n", index)
            index = length if newline < 0 else newline + 1
            continue
        if pair == "/*":
            end = source.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        if char == "`":  # raw string: no escapes, runs to the next backtick
            end = source.find("`", index + 1)
            index = length if end < 0 else end + 1
            continue
        if char in ('"', "'"):
            quote = char
            index += 1
            while index < length and source[index] != quote:
                index += 2 if source[index] == "\\" else 1
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"unbalanced parentheses from offset {open_index}")


class ParseError(RuntimeError):
    """A route registration could not be read out of the Go source."""


def parse_routes(source: str, filename: str) -> list[Route]:
    """Every ``r.HandleFunc(...).Methods(...)`` in one Go file.

    A registration this cannot read raises rather than being skipped: a
    silently dropped route would weaken the very check the caller is
    running, and "the parser broke" must never look like "the route was
    removed".
    """
    # Comments are blanked first (string literals are kept, since the
    # route path is one).  Without this a registration inside a commented
    # -out block would be counted as live, and a ")" inside a comment
    # would end the scan early.
    source = _blank_non_code(source)

    out: list[Route] = []
    for match in _HANDLE_FUNC_START.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        open_index = source.index("(", match.start())
        try:
            close_index = _close_paren(source, open_index)
        except ValueError as exc:
            raise ParseError(f"{filename}:{line}: {exc}") from exc

        tail = source[close_index + 1:]
        if not _METHODS_START.match(tail):
            raise ParseError(
                f"{filename}:{line}: route {match.group('path')!r} is registered "
                "without a .Methods() clause, which this parser does not model")
        methods_open = tail.index("(")
        methods_close = _close_paren(tail, methods_open)
        methods = tuple(_METHOD_RE.findall(tail[methods_open:methods_close]))
        if not methods:
            raise ParseError(f"{filename}:{line}: no methods parsed from "
                             f"{tail[methods_open:methods_close + 1]!r}")

        out.append(Route(
            path=match.group("path"),
            methods=methods,
            handler=source[match.end():close_index].strip(),
            source=f"{filename}:{line}",
        ))

    # A registration the scanner walked past entirely would be invisible
    # above, so the count is checked against the raw occurrences in the
    # same (comment-free) text.
    raw = source.count("HandleFunc(")
    if raw != len(out):
        raise ParseError(f"{filename}: parsed {len(out)} routes but the file "
                         f"mentions HandleFunc( {raw} times.  A registration "
                         "written in a shape this parser does not model would "
                         "otherwise be silently missing from the route surface.")
    return out


def parse_path_prefixes(source: str) -> list[str]:
    return [m.group("prefix") for m in _PATH_PREFIX_RE.finditer(source)]


def all_routes(layout: AppLayout) -> list[Route]:
    """Every route the shipped binary registers, sorted by path."""
    out: list[Route] = []
    for path in layout.go_sources():
        out.extend(parse_routes(path.read_text(encoding="utf-8", errors="replace"),
                                path.name))
    return sorted(out, key=lambda r: (r.path, r.methods))


def page_map(layout: AppLayout) -> dict[str, str]:
    """The ``/{page}`` navigation map: shortcut name -> target page.

    Read from HandlePageNavigation in the navigation backend, which is
    the only place the mapping exists.
    """
    raw = (layout.code_dir / "cbdb_navigation_backend.go").read_text(
        encoding="utf-8", errors="replace")
    start = raw.find("pageMap := map[string]string{")
    if start < 0:
        raise ParseError("HandlePageNavigation no longer declares a pageMap")

    # Brace-balance over a copy with comments *and* strings blanked, so a
    # "}" inside either cannot end the literal early -- a short map reads
    # exactly like a build that dropped a form.  Offsets are preserved,
    # so the span is then read back out of the original text.
    scan = _blank_non_code(raw, keep_strings=False)
    depth = 0
    end = -1
    for index in range(scan.index("{", start), len(scan)):
        if scan[index] == "{":
            depth += 1
        elif scan[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end < 0:
        raise ParseError("the pageMap literal is not closed")

    body = raw[start:end]
    mapping = {m.group("key"): m.group("target")
               for m in _PAGE_MAP_RE.finditer(body)}
    if not mapping:
        raise ParseError("the pageMap literal parsed to nothing")

    # Every "key": "value" line in the literal must have been understood.
    # A key the pattern does not match (an upper-case or hyphenated page
    # name, say) would otherwise vanish from the map, and the navigation
    # test would simply never check that shortcut.
    pairs = len(re.findall(r'"[^"]*"\s*:\s*"[^"]*"', body))
    if pairs != len(mapping):
        raise ParseError(f"the pageMap literal has {pairs} entries but only "
                         f"{len(mapping)} were understood")
    return mapping


def picker_files(layout: AppLayout) -> list[str]:
    """The picker HTML files main.go serves, in registration order."""
    source = (layout.code_dir / "main.go").read_text(encoding="utf-8",
                                                     errors="replace")
    return [m.group("file") for m in _PICKER_RE.finditer(source)]


def concrete_get_pages(routes: list[Route]) -> list[Route]:
    """GET routes that render a page and take no path variables."""
    return [r for r in routes
            if "GET" in r.methods and r.is_page and not r.is_wildcard]


def probe_path(route: Route, *, person_id: int = 1) -> str:
    """A requestable path for a route, filling in any path variables.

    Only ``{id}`` appears in this build (the browser's per-person
    sub-resources); anything else is reported rather than guessed at.
    """
    if not route.is_wildcard:
        return route.path
    filled = route.path.replace("{id}", str(person_id))
    if "{" in filled:
        raise ValueError(f"no probe value for the variables in {route.path}")
    return filled
