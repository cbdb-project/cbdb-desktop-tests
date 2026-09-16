"""A lexer for one question: does a shipped page's JavaScript still parse?

Why this exists, and why it is not a general JavaScript parser.  A form
page here is one HTML file with a single inline ``<script>`` holding the
whole of its behaviour.  A syntax error anywhere in that block is not a
local problem: the browser abandons the entire script, so *every*
function the page declares is undefined, every control is inert, and the
page still returns HTTP 200 with a complete-looking DOM.  Nothing that
talks HTTP can see it.

``test_ui_pages.py`` does see it -- a real Chromium logs the parse error
on load -- and that test stays.  This module is the second check in the
second place (AGENTS.md, operating principle 9): it needs no browser, so
it runs in a checkout with no Chromium, it runs in a tenth of a second,
and it answers with ``file:line`` rather than with the browser's
position-free ``missing ) after argument list``.  A defect report that
says where the fix goes is worth more than one that says a page is
broken.

**Scope, stated honestly.**  This finds exactly one species of syntax
error: a quoted string literal that its line never closes.  That is a
real class, not a curiosity -- an ordinary JavaScript string may not
span a line break, so an unclosed ``'`` or ``"`` is always a syntax
error, whatever follows it -- and it is the species a careless
search-and-replace across a template produces.  It is not a claim that a
page whose every string closes parses; that claim belongs to the browser
test, which makes it properly.

The lexer therefore tracks only as much as it takes to know whether a
quote is a quote: line and block comments, the three string forms, and
regular-expression literals (``/'/`` is a slash, an apostrophe and a
slash, and reading it as the start of a string would report every later
line of the file).  Template literals *may* span lines and are followed
across them; ``${...}`` inside one is read as code, because it is.

**Known imprecision, so nobody re-derives it.**  A ``/`` immediately
after a comment is read as opening a regular expression, because closing
a comment clears the "a value just ended" state rather than restoring
what preceded it.  So ``a /* note */ / 2`` is mis-lexed.  It is left
alone deliberately: the alternative reading mis-lexes the commoner
``foo() // note`` newline ``/re/.test(x)``, neither shape occurs in any
shipped template, and the version here is the one checked script by
script against ``node --check`` across five builds.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: ``<script>`` blocks that carry their own source.  A non-greedy match
#: means a literal ``</script>`` inside a JavaScript string ends the
#: body early -- which is not a bug to fix: a real HTML parser ends the
#: element there too, which is why such a string has to be written
#: ``<\/script>``.  Matching the browser is the point.  One with a ``src``
#: attribute is a reference to a file, not a body to read, and none of
#: these pages has one -- but the build could grow one, and reading its
#: empty body as "no JavaScript here" would silently stop checking a
#: page.  ``inline_scripts`` returns the bodies; ``external_scripts``
#: counts what it declined to read, so a caller can assert on it.
_SCRIPT = re.compile(r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>",
                     re.IGNORECASE | re.DOTALL)
#: ``src`` on a ``<script>``, quoted **or not**: HTML allows
#: ``<script src=main.js>``, and a pattern that insisted on a quote
#: would read such a tag as an empty inline body -- counting zero
#: external scripts while the page's real JavaScript went unscanned.
_SRC_ATTR = re.compile(r"""\bsrc\s*=""", re.IGNORECASE)

#: The character before a ``/`` that means the ``/`` divides rather than
#: opens a regular expression.  After a value -- an identifier, a
#: number, a closing bracket, a string -- a slash is division; after an
#: operator, a comma, or the start of a statement, it opens a literal.
#: ``)`` is deliberately on the division side even though
#: ``if (x) /re/.test(y)`` exists, because no page here writes that and
#: the other reading would mis-lex every ``(a + b) / 2``.
#:
#: The quote characters are here because a closing quote is the end of a
#: value: ``"12" / 2`` is division.  Without them the ``/`` opened a
#: "regex" that ran to the next ``/`` -- commonly one inside a later
#: string -- and left that string's tail looking unterminated.  ``}`` is
#: here for the same reason, for ``{a: 1} / 2``; it makes the other
#: reading of ``if (x) {} /re/.test(y)`` wrong, which is the same trade
#: already made for ``)`` and for the same reason.
_VALUE_END = re.compile(r"""[A-Za-z0-9_$)\]}'"`]""")

#: ...and these two-character operators also end a value, although
#: neither of their characters does on its own: ``n++ / 2`` is division.
_VALUE_END_PAIRS = ("++", "--")

#: ...except after one of these words, where the previous character is
#: the last letter of a keyword rather than the end of a value, and the
#: slash opens a regular expression after all.  ``return /['"]/.test(x)``
#: is ordinary JavaScript, and reading its regex as division lexes the
#: quotes inside it as code and reports a string that is not there.
_REGEX_KEYWORDS = frozenset({
    "return", "typeof", "case", "else", "in", "of", "delete", "void",
    "throw", "do", "await", "instanceof", "new", "yield",
})

_IDENT = re.compile(r"[A-Za-z0-9_$]")

#: JavaScript ends a line on four characters, not one, and a string may
#: not span any of them.  A lone carriage return and the two Unicode
#: separators are as much a syntax error inside a quote as ``\n`` is, and
#: reading them as ordinary text would miss a broken line entirely.  A
#: ``\r`` that is part of a ``\r\n`` pair is skipped rather than counted,
#: so a CRLF file is not read as twice as many lines as it has.
_LINE_TERMINATORS = "\n\r  "


@dataclass(frozen=True)
class Unterminated:
    """One string literal that its own line never closes."""

    line: int                # 1-based, within the whole HTML file
    quote: str               # the quote character that was left open
    column: int              # 1-based, where the literal starts
    text: str                # the offending source line, stripped

    def __str__(self) -> str:  # pragma: no cover - used only in messages
        return f"line {self.line}: unterminated {self.quote}: {self.text}"


def inline_scripts(html: str) -> list[tuple[int, str]]:
    """``[(first line number, body)]`` for each inline ``<script>``."""
    out = []
    for match in _SCRIPT.finditer(html):
        if _SRC_ATTR.search(match.group("attrs") or ""):
            continue
        line = html.count("\n", 0, match.start("body")) + 1
        out.append((line, match.group("body")))
    return out


def external_scripts(html: str) -> int:
    """How many ``<script src=...>`` tags this page has, and so how much
    of its JavaScript ``inline_scripts`` did not look at."""
    return sum(1 for match in _SCRIPT.finditer(html)
               if _SRC_ATTR.search(match.group("attrs") or ""))


def unterminated_strings(source: str, first_line: int = 1) -> list[Unterminated]:
    """Every string literal in ``source`` that its own line leaves open.

    Recovery is per line and deliberate: on reaching the end of a line
    inside a ``'`` or ``"`` literal, the finding is recorded and the
    lexer resumes in code state on the next line.  Carrying the state
    forward instead would report every subsequent line of the file,
    which turns nine real findings into two thousand and hides where
    they are.
    """
    findings: list[Unterminated] = []
    line = first_line
    column = 1
    index = 0
    end = len(source)

    # Where the literal currently being read started, for the message.
    open_line = open_column = 0
    # "code" | "line_comment" | "block_comment" | "'" | '"' | "`"
    state = "code"
    # The last non-space character seen in code state, to tell a regex
    # literal from a division.
    previous = ""
    # Depth of ``${ ... }`` interpolations, with the template quote to
    # return to when each closes.
    template_stack: list[str] = []
    brace_depth: list[int] = []

    def advance(count: int = 1) -> None:
        nonlocal index, column
        index += count
        column += count

    while index < end:
        char = source[index]

        if char in _LINE_TERMINATORS:
            if state in ("'", '"'):
                findings.append(Unterminated(
                    line=open_line, quote=state, column=open_column,
                    text=_line_text(source, index)))
                state = "code"
                previous = ""
            elif state == "line_comment":
                state = "code"
                previous = ""
            index += 1
            # The \n of a \r\n pair is the same line ending, counted once.
            if char == "\r" and source.startswith("\n", index):
                index += 1
            line += 1
            column = 1
            continue

        if state == "line_comment":
            advance()
            continue

        if state == "block_comment":
            if source.startswith("*/", index):
                state = "code"
                previous = ""
                advance(2)
            else:
                advance()
            continue

        if state in ("'", '"', "`"):
            if char == "\\":
                # A backslash before a line ending is a legal line
                # continuation, and stepping over both characters
                # without counting the line shifts every line number
                # reported after it.
                if index + 1 < end and source[index + 1] in _LINE_TERMINATORS:
                    index += 2
                    if (source[index - 1] == "\r"
                            and source.startswith("\n", index)):
                        index += 1
                    line += 1
                    column = 1
                    continue
                advance(2)
                continue
            if state == "`" and source.startswith("${", index):
                # Interpolated code: lex it as code, and remember the
                # template to come back to when its brace closes.
                template_stack.append(state)
                brace_depth.append(0)
                state = "code"
                previous = ""
                advance(2)
                continue
            if char == state:
                state = "code"
                previous = char
                advance()
                continue
            advance()
            continue

        # --- code -----------------------------------------------------
        if source.startswith("//", index):
            state = "line_comment"
            advance(2)
            continue
        if source.startswith("/*", index):
            state = "block_comment"
            advance(2)
            continue
        if char in "'\"`":
            state = char
            open_line, open_column = line, column
            advance()
            continue
        if char == "/" and (not _ends_a_value(source, index, previous)
                            or _preceding_word(source, index) in _REGEX_KEYWORDS):
            index, line, column = _skip_regex(source, index, line, column)
            previous = "/"
            continue
        if char == "{" and brace_depth:
            brace_depth[-1] += 1
        elif char == "}" and brace_depth:
            if brace_depth[-1] == 0:
                state = template_stack.pop()
                brace_depth.pop()
                advance()
                continue
            brace_depth[-1] -= 1
        if not char.isspace():
            previous = char
        advance()

    # A template literal may legally span lines, so an unclosed backtick
    # can only be recognised here, at the end of the source -- but it
    # must be recognised.  Without this, one stray backtick swallows
    # every line after it and the page reports clean, which is the
    # gate quietly narrowing itself to nothing.  The line reported is
    # where the literal *opened*, since that is where the fix goes.
    if state in ("'", '"', "`"):
        findings.append(Unterminated(
            line=open_line, quote=state, column=open_column,
            text=_line_text(source, min(end, len(source) - 1))))
    return findings


def _ends_a_value(source: str, index: int, previous: str) -> bool:
    """Does what precedes the ``/`` at ``index`` complete a value?

    ``previous`` answers this for a single character.  ``++`` and ``--``
    need the pair: neither ``+`` nor ``-`` ends a value alone, but
    ``n++ / 2`` is division.
    """
    stop = index - 1
    while stop >= 0 and source[stop].isspace():
        stop -= 1
    if stop >= 1 and source[stop - 1:stop + 1] in _VALUE_END_PAIRS:
        return True
    return bool(_VALUE_END.match(previous or " "))


def _preceding_word(source: str, index: int) -> str:
    """The identifier immediately before ``index``, ignoring spaces.

    Only ever consulted when the character before the slash already
    looked like the end of a value, so this is reading the word that
    character belongs to -- ``return`` rather than ``n``.
    """
    stop = index - 1
    while stop >= 0 and source[stop].isspace():
        stop -= 1
    start = stop
    while start >= 0 and _IDENT.match(source[start]):
        start -= 1
    return source[start + 1:stop + 1]


def _skip_regex(source: str, index: int, line: int, column: int) -> tuple[int, int, int]:
    """Step over a ``/.../`` literal, so the quotes inside it are text.

    A regular expression, like a plain string, cannot span a line: if the
    closing slash is not found before the newline, the ``/`` was division
    after all (or the line is broken in some other way) and lexing
    resumes at the newline rather than swallowing the rest of the file.
    """
    index += 1
    column += 1
    in_class = False
    while index < len(source):
        char = source[index]
        if char in _LINE_TERMINATORS:
            return index, line, column
        if char == "\\":
            if (index + 1 < len(source)
                    and source[index + 1] in _LINE_TERMINATORS):
                # As in a string: hand the line ending back to the main
                # loop to count, rather than stepping over it here and
                # reporting every later finding one line too early.
                return index + 1, line, column
            index += 2
            column += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return index + 1, line, column + 1
        index += 1
        column += 1
    return index, line, column


def _line_text(source: str, index: int) -> str:
    """The whole source line ``index`` falls on, stripped."""
    start = max(source.rfind(char, 0, index)
                for char in _LINE_TERMINATORS) + 1
    stops = [at for at in (source.find(char, index)
                           for char in _LINE_TERMINATORS) if at != -1]
    return source[start:min(stops) if stops else len(source)].strip()


def scan_page(html: str) -> list[Unterminated]:
    """Every unterminated string literal in one page's inline scripts."""
    findings: list[Unterminated] = []
    for first_line, body in inline_scripts(html):
        findings.extend(unterminated_strings(body, first_line))
    return findings
