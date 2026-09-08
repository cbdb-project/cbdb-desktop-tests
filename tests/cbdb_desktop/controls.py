"""Every button on every form, and what pressing it calls.

The question this module exists to answer is "which buttons has anything
ever pressed?", and the reason it is a program rather than a list is that
a list is wrong by the next build.  There are 157 buttons across fifteen
pages; an agent or a person reading the templates and writing down what
they see will miss some, and will not notice the three a build adds.

So the inventory is **extracted from the shipped templates**, the same
way ``routes.py`` extracts the routing table from the shipped Go: as
data, with no interpretation of what a handler then does.  What comes out
is, per page, every ``<button>``, the JavaScript function it is wired to,
and the set of API endpoints reachable from that function.

**How the wiring is read.**  The templates use two styles, and both had
to be handled because the forms are split between them:

* inline -- ``<button onclick="saveEntryCodes()">``, used by the six
  older form pages;
* bound -- ``getElementById('btn-pajek').addEventListener('click',
  exportPajek)``, used by kinship, networks, group data and association
  pairs, sometimes through an arrow wrapper
  (``('click', () => exportGIS('kml'))``).

From the handler name, ``endpoints_for`` walks the page's own call graph
-- function bodies matched by brace balance, ``fetch('/api/...')`` calls
collected, called function names followed -- and returns every endpoint
the press can reach.  Depth-limited and cycle-safe, because a page's
functions do call each other in loops.

**What this is not.**  It is not a claim that pressing the button in a
browser does what the extracted graph says: JavaScript can compute an
endpoint name, and one page does (the QBE grid).  The extraction is
therefore checked in two directions by ``test_controls.py`` -- every
endpoint found here must be a route the build registers, and every
endpoint a form's page contains must be reachable from some button --
so a page the parser reads badly fails a test rather than quietly
reporting good coverage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .staging import AppLayout

_BUTTON = re.compile(r"<button\b(?P<attrs>[^>]*)>(?P<label>.*?)</button>",
                     re.IGNORECASE | re.DOTALL)
_ATTR = re.compile(r"""(?P<name>[a-zA-Z-]+)\s*=\s*(?P<quote>["'])(?P<value>.*?)(?P=quote)""",
                   re.DOTALL)

#: ``getElementById('btn-x')`` ... ``addEventListener('click',``.  The
#: handler argument is *not* matched by this pattern: it is read off by
#: paren balance in ``_listeners`` below, because the commonest handler
#: on the newer pages is a multi-statement inline arrow function and any
#: regex for that either stops at the first ``;`` -- silently reporting
#: the button as unwired -- or runs to the end of the file.
_LISTENER = re.compile(
    r"""getElementById\(\s*['"](?P<id>[^'"]+)['"]\s*\)"""
    r"""[^;{}]*?addEventListener\(\s*['"]click['"]\s*,\s*""",
    re.DOTALL)

#: ``function name(...)`` / ``async function name(...)`` /
#: ``const name = (async )?(...) =>``
_FUNCTION = re.compile(
    r"(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(",
)
_ARROW_FUNCTION = re.compile(
    r"(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?\([^)]*\)\s*=>\s*\{",
)

_FETCH = re.compile(r"""fetch\(\s*(?P<quote>['"`])(?P<path>/[^'"`]*)(?P=quote)""")
_TEMPLATE_FETCH = re.compile(r"""fetch\(\s*`(?P<path>/[^`$]*)\$""")
_CALL = re.compile(r"\b(?P<name>[A-Za-z_$][\w$]*)\s*\(")

#: Names that look like calls and are not this page's functions.  Kept
#: short on purpose: an unknown name simply contributes no endpoints, so
#: the cost of missing one from this list is nothing, while a name
#: wrongly *in* it would hide a real handler.
_NOT_FUNCTIONS = frozenset({
    "if", "for", "while", "switch", "catch", "return", "typeof", "function",
    "fetch", "JSON", "Object", "Array", "String", "Number", "Boolean", "Math",
    "parseInt", "parseFloat", "encodeURIComponent", "decodeURIComponent",
    "setTimeout", "setInterval", "alert", "confirm", "console", "querySelector",
    "getElementById", "addEventListener", "map", "filter", "forEach", "join",
    "split", "push", "concat", "slice", "sort", "keys", "values", "entries",
})


@dataclass(frozen=True)
class Button:
    """One ``<button>`` on one page."""

    page: str
    #: The element's id, or "" when it has none (the older pages wire
    #: their buttons inline and do not name them).
    element_id: str
    #: The visible label, where the markup has one.  Most buttons are
    #: labelled at runtime from a translation table, so this is often
    #: empty -- it is for reading failures, never for matching.
    label: str
    #: Handler expression: a function name, or the raw onclick text.
    handler: str
    #: How the handler is attached: "onclick" or "listener".
    wiring: str
    #: True when the markup ships the button disabled -- the export
    #: buttons do, until a query has run.
    disabled: bool = False

    @property
    def key(self) -> str:
        return f"{self.page}:{self.element_id or self.handler}"


@dataclass
class PageScript:
    """One page's JavaScript, indexed for call-graph walking."""

    page: str
    functions: dict[str, str] = field(default_factory=dict)

    def endpoints(self, expression: str, *, depth: int = 6) -> set[str]:
        """Every API path reachable from a handler expression."""
        seen: set[str] = set()
        out: set[str] = set()

        def walk(name: str, level: int) -> None:
            if level <= 0 or name in seen:
                return
            seen.add(name)
            body = self.functions.get(name)
            if body is None:
                return
            out.update(normalise(m.group("path"))
                       for m in _FETCH.finditer(body))
            out.update(normalise(m.group("path"))
                       for m in _TEMPLATE_FETCH.finditer(body))
            for call in _CALL.finditer(body):
                called = call.group("name")
                if called not in _NOT_FUNCTIONS:
                    walk(called, level - 1)

        # The expression itself may contain the fetch (an inline arrow
        # handler) as well as naming functions to follow.
        out.update(normalise(m.group("path"))
                   for m in _FETCH.finditer(expression))
        for call in _CALL.finditer(expression):
            if call.group("name") not in _NOT_FUNCTIONS:
                walk(call.group("name"), depth)
        # A bare handler name, with no call syntax.
        bare = expression.strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", bare):
            walk(bare, depth)
        return {path for path in out if path.startswith("/api/")}


def _brace_body(text: str, open_index: int) -> str:
    """The ``{...}`` block starting at or after ``open_index``."""
    start = text.find("{", open_index)
    if start < 0:
        return ""
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char in "\"'`":
            quote = char
            index += 1
            while index < len(text) and text[index] != quote:
                index += 2 if text[index] == "\\" else 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    return text[start:]


def _listeners(html: str) -> dict[str, str]:
    """``{element id: handler source}`` for every click listener bound.

    The handler is taken by paren balance from just after the comma, so
    a multi-statement inline arrow function is captured whole.  Getting
    this wrong is not a loud failure -- the button reads as wired to
    nothing, which looks like a dead button rather than a parser bug --
    which is why ``test_controls.py`` asserts the *count* of unwired
    buttons rather than trusting that zero means zero.
    """
    out: dict[str, str] = {}
    for match in _LISTENER.finditer(html):
        index = match.end()
        depth = 1          # we are already inside addEventListener(
        while index < len(html) and depth:
            char = html[index]
            if char in "\"'`":
                quote = char
                index += 1
                while index < len(html) and html[index] != quote:
                    index += 2 if html[index] == "\\" else 1
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        out[match.group("id")] = html[match.end():index].strip()
    return out


def parse_page(page: str, html: str) -> tuple[list[Button], PageScript]:
    """Every button on one page, and its script indexed for walking."""
    script = PageScript(page=page)
    for match in _FUNCTION.finditer(html):
        script.functions[match.group("name")] = _brace_body(html, match.end())
    for match in _ARROW_FUNCTION.finditer(html):
        script.functions.setdefault(match.group("name"),
                                    _brace_body(html, match.end() - 1))

    listeners = _listeners(html)

    buttons: list[Button] = []
    for match in _BUTTON.finditer(html):
        attrs = {a.group("name").lower(): a.group("value")
                 for a in _ATTR.finditer(match.group("attrs"))}
        element_id = attrs.get("id", "")
        onclick = attrs.get("onclick", "").strip()
        if onclick:
            handler, wiring = onclick, "onclick"
        elif element_id in listeners:
            handler, wiring = listeners[element_id], "listener"
        else:
            handler, wiring = "", "none"
        buttons.append(Button(
            page=page,
            element_id=element_id,
            label=re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "",
                                             match.group("label"))).strip(),
            handler=handler,
            wiring=wiring,
            disabled="disabled" in match.group("attrs").lower(),
        ))
    return buttons, script


def _pages(layout: AppLayout) -> dict[str, Path]:
    """Every page with buttons: the form pages, plus the pickers and QBE."""
    pages = dict(layout.form_templates())
    pickers = layout.templates_dir / "pickers"
    for path in sorted(pickers.glob("*.html")):
        pages[f"pickers/{path.stem}"] = path
    qbe = layout.templates_dir / "qbe" / "qbe.html"
    if qbe.is_file():
        pages["qbe"] = qbe
    return pages


def inventory(layout: AppLayout) -> dict[str, tuple[list[Button], PageScript]]:
    """``{page: (buttons, script)}`` for every page in the build."""
    out = {}
    for page, path in sorted(_pages(layout).items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        out[page] = parse_page(page, html)
    assert out, "no page templates found in the staged build"
    return out


def buttons(layout: AppLayout) -> list[Button]:
    return [button for page_buttons, _ in inventory(layout).values()
            for button in page_buttons]


def endpoints_by_button(layout: AppLayout) -> dict[str, set[str]]:
    """``{button key: endpoints the press can reach}``."""
    out: dict[str, set[str]] = {}
    for _page, (page_buttons, script) in inventory(layout).items():
        for button in page_buttons:
            out[button.key] = (script.endpoints(button.handler)
                               if button.handler else set())
    return out


def normalise(path: str) -> str:
    """A fetched path in the shape the routing table declares it.

    The pages build three kinds of URL that a route never spells that
    way: a template literal with an interpolated id
    (``/api/browser/person/${_selectedId}/kinship``), a path with the
    query string cut off mid-write (``/api/browser/people?``), and a
    prefix that is completed by concatenation
    (``/api/browser/person/`` + id).  All three become the mux
    wildcard, ``{id}``, so that "the page calls this" and "the build
    registers this" can be compared at all.
    """
    path = re.sub(r"\$\{[^}]*\}", "{id}", path)
    path = path.split("?", 1)[0].rstrip("&")
    if path.endswith("/"):
        path += "{id}"
    return path


def endpoints_in_page(html: str) -> set[str]:
    """Every API endpoint the page's script mentions at all."""
    found = ({m.group("path") for m in _FETCH.finditer(html)}
             | {m.group("path") for m in _TEMPLATE_FETCH.finditer(html)})
    return {normalise(path) for path in found if path.startswith("/api/")}
