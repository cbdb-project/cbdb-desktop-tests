"""Does each shipped page's JavaScript still parse?

A form here keeps the whole of its behaviour in one inline ``<script>``.
That makes a syntax error in it total rather than local: the browser
discards the entire block, so every function the page declares is
undefined, every button is wired to nothing, and the page still answers
HTTP 200 with a DOM that looks complete.  No request-level test can see
that, and neither can a reader skimming the file -- the broken line
looks like the fifteen working ones around it.

``test_ui_pages.py::test_every_page_the_build_serves_loads_without_
throwing`` sees it, because a real Chromium logs the parse error, and it
stays.  This module is the second check in the second place (AGENTS.md,
operating principle 9: "two checks in two places beat one", and
principle 8: "prefer the check that needs no query").  It reads the
shipped templates, so it needs no browser and no running application; it
runs whether or not Playwright has downloaded a Chromium; and it answers
with the page and the line number, where the browser can only say
``missing ) after argument list`` with no position at all.  A defect
report that names the line is a different quality of bug report from one
that names the page.

**What it checks, exactly.**  One species of syntax error: a quoted
string literal that its own line never closes.  An ordinary JavaScript
string may not contain a raw line break, so an unclosed ``'`` or ``"``
is always a syntax error -- and it is precisely what a careless
search-and-replace across a template leaves behind.  It is *not* a claim
that a page whose every string closes therefore parses.  That claim is
the browser's to make, and it makes it.

The narrowness cuts both ways, and this is the part to read before
trusting a green run here.  A syntax error of any other species -- an
unbalanced paren, a stray ``}``, a top-level throw -- is invisible to
this module, and the browser test that would catch it **skips itself
when Chromium is absent**.  So in a fresh checkout with no Playwright
browser, this module is the only thing looking, and it is looking for
one shape.  "The scripts parse" is not what a pass here means.

The pages come from ``controls.pages``, the same inventory the button
and endpoint gates are built from, so a page the build adds is scanned
without anyone remembering to add it.
"""
from __future__ import annotations

import pytest

from cbdb_desktop import controls, jsscan
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.staging import AppLayout

#: How many broken lines this build ships, per page.  Recognising the
#: exact shape is what lets an *unrelated* new breakage arrive as a plain
#: assertion failure instead of wearing this one's name -- see AGENTS.md
#: § "How a defect is recorded".
#:
#: Keyed on the broken lines' **text**, deliberately not on their line
#: numbers.  Nothing about this defect depends on a line number: an
#: unrelated edit anywhere above line 923 in any of the three templates
#: would shift all nine, the signature would stop matching, and the very
#: same defect would report as an unrecognised failure and land in the
#: report's *unclassified* table.  That is brittle in the direction the
#: project cares about, and simultaneously loose in the other -- line
#: numbers would equally match nine *different* breakages that happened
#: to fall on those lines.  The text is exact, and it moves with the
#: defect rather than with the file.  The line numbers still appear in
#: the message, where they are what a reader needs and cost nothing if
#: they move.
_SHIPPED_BREAKAGE: dict[str, tuple[str, ...]] = {
    "association_pairs": (
        "showSuccess('Export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
        "showSuccess('GIS export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
        "showSuccess('Neo4j export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
        "' export: ' + (j.files || []).length +  file(s) offered for "
        "download — check each Save dialog.'\");",
    ),
    "entry": (
        "showSuccess('Neo4j export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
        "showSuccess('Query results export: ' + (j.files || []).length +  "
        "file(s) offered for download — check each Save dialog.'\");",
    ),
    "group_data": (
        "showSuccess('Query results export: ' + (j.files || []).length +  "
        "file(s) offered for download — check each Save dialog.'\");",
        "showSuccess('GIS export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
        "showSuccess('Neo4j export: ' + (j.files || []).length +  file(s) "
        "offered for download — check each Save dialog.'\");",
    ),
}


#: The sentence the nine broken lines were trying to write.  Counting
#: where it *did* come out right is what turns "three pages are broken"
#: into "a search-and-replace went wrong on three of ten", which is a
#: different and more actionable sentence for a maintainer -- and it is
#: counted rather than stated, because a hand-written count in a failure
#: message is the one number nothing checks.
_REPLACED_SENTENCE = "file(s) offered for download"


def _intact_siblings(layout: AppLayout) -> list[tuple[str, int]]:
    """``[(page, line)]`` where the same sentence is written correctly."""
    out = []
    for page, path in sorted(controls.pages(layout).items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        broken = {f.line for f in jsscan.scan_page(text)}
        for number, line in enumerate(text.splitlines(), start=1):
            if _REPLACED_SENTENCE in line and number not in broken:
                out.append((page, number))
    return out


def _scan(layout: AppLayout) -> dict[str, list[jsscan.Unterminated]]:
    """``{page: findings}``, for every page the build serves."""
    out = {}
    for page, path in sorted(controls.pages(layout).items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        findings = jsscan.scan_page(html)
        if findings:
            out[page] = findings
    return out


def test_every_page_script_closes_every_string_it_opens(layout: AppLayout):
    """A page whose JavaScript does not parse is a page with no behaviour.

    The failure message carries the page, the line, and the line's text,
    because the reader of it has no registry and no report -- the fix is
    one character per line and it has to be findable from this sentence
    alone.
    """
    found = _scan(layout)

    detail = "; ".join(
        f"{page} {[f.line for f in findings]}"
        for page, findings in sorted(found.items()))
    signature = {page: tuple(f.text for f in findings)
                 for page, findings in found.items()}

    if signature == _SHIPPED_BREAKAGE:
        example = found["association_pairs"][0]
        broken = sum(len(lines) for lines in found.values())
        intact = _intact_siblings(layout)
        raise KnownShippedDefect(
            f"{broken} unterminated string literals across {len(found)} of "
            f"{len(controls.pages(layout))} shipped pages: {detail}.  "
            "Each page keeps all its behaviour in one inline <script>, so "
            "the syntax error discards the whole block and every function "
            "on the page with it -- the page still answers HTTP 200, and "
            "every button on it fires an onclick that calls a function "
            "which no longer exists.  The shape is the same in all "
            f"{broken}: {example.text}  -- the opening quote of the "
            "' file(s) offered for download' fragment is missing and a "
            f"stray '\" was left at the end.  The same sentence is written "
            f"correctly {len(intact)} times across "
            f"{len({page for page, _ in intact})} other pages, so this is "
            "a botched search-and-replace rather than a change anyone "
            "chose.")

    assert not found, (
        "these pages open a JavaScript string their line never closes, "
        "which discards the whole inline <script> and leaves every "
        f"control on the page inert: {detail}")


def test_no_page_hides_its_javascript_where_this_check_cannot_read_it(
        layout: AppLayout):
    """Every page's JavaScript is inline, which is what makes the scan total.

    ``jsscan`` reads ``<script>`` bodies and skips ``<script src=...>``,
    which is correct -- there is no body to read -- but it means a build
    that moved a page's code into a file would be scanned clean while
    checking nothing.  Pin the count at zero so that move fails here
    rather than quietly narrowing the gate.
    """
    external = {}
    for page, path in sorted(controls.pages(layout).items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        count = jsscan.external_scripts(html)
        if count:
            external[page] = count
    assert not external, (
        "these pages load JavaScript from a file, which this scan does "
        f"not read: {external}.  Point it at the file, or say here why "
        "the file needs no checking")


#: Every page in this build keeps its behaviour in exactly one inline
#: ``<script>``.  Pinned as an exact count per page rather than as "at
#: least one", because a floor is what lets a page acquire a second,
#: real script block that the scan then only partly reads -- and because
#: operating principle 5 is that a legitimate change should fail a test
#: and be read, not pass quietly.
_EXPECTED_INLINE_SCRIPTS = 1


def test_every_page_the_build_serves_carries_a_script_to_check(
        layout: AppLayout):
    """An empty scan is a failure, not a pass.

    If ``_SCRIPT`` ever stopped matching -- a build that writes
    ``<script type="module">`` differently, say -- every page would scan
    clean with nothing read, and the gate above would certify a build it
    never looked at.  So the number of blocks is pinned exactly and
    their size is sanity-checked: a count alone is satisfied by one
    empty block, and a size alone by one tiny block beside a real one.
    """
    wrong = {}
    for page, path in sorted(controls.pages(layout).items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        scripts = jsscan.inline_scripts(html)
        body = sum(len(src) for _line, src in scripts)
        if len(scripts) != _EXPECTED_INLINE_SCRIPTS or body < 200:
            wrong[page] = (len(scripts), body)
    assert not wrong, (
        "these pages do not carry exactly "
        f"{_EXPECTED_INLINE_SCRIPTS} inline <script> of a plausible size, "
        "so the syntax gate above is reading something other than what "
        f"it thinks -- {{page: (blocks, bytes)}}: {wrong}")


# ---------------------------------------------------------------------------
# The scanner's own tests.
#
# A gate that decides what counts as broken needs its own check of that
# decision (AGENTS.md § "Coverage is the program's job", rule 5).  Both
# directions matter and the false-positive direction matters more: a
# scanner that flags an apostrophe inside a double-quoted string, or the
# quotes inside a regular expression, would report every page in the
# build and be switched off within a round.
# ---------------------------------------------------------------------------

_MUST_NOT_FLAG = [
    ("an apostrophe inside a double-quoted string",
     """var a = "it's fine";"""),
    ("quotes inside a regular expression",
     """var r = /['"]/g; var b = 1;"""),
    # Note the string: a case with no quote in it at all cannot fail,
    # whatever the lexer does, and this one was exactly that until a
    # mutation run caught it.  With `"x/y"` present, reading the first
    # `/` as a regex ends it at the slash inside that string and leaves
    # `y";` open -- so the case now kills the mutant it names.
    ("division, which is the same character as a regex",
     '''var x = a / 2, s = "x/y";'''),
    ("division after a string, which is also the end of a value",
     '''var n = "12" / 2, s = "a/b";'''),
    ("division after an object literal's closing brace",
     '''var n = {a: 1} / 2, s = "a/b";'''),
    ("division after an increment, where neither character ends a value",
     '''var n = 1; n++ / 2; var s = "a/b";'''),
    ("a regular expression after a keyword, not a division",
     """function f(x){ return /['"]/.test(x); }"""),
    ("an apostrophe in a block comment below its opening line",
     "/*\n   don't worry\n*/\nvar a = 1;\n"),
    ("a template nested inside an interpolation",
     "var t = `a${ `b${c}'d` }e`; var s = 1;\n"),
    ("a template literal spanning lines, with interpolation",
     "var t = `line one\n  ${a + 'x'} line two`;\nvar z = 1;"),
    ("an escaped quote inside its own quote",
     r"var s = 'don\'t';"),
    ("an apostrophe in a line comment",
     "// it's a comment\nvar a = 1;"),
    ("an apostrophe in a block comment",
     "/* don't\n   worry */\nvar a = 1;"),
    ("both quote styles inside one interpolation",
     "var t = `a${ b ? 'y' : \"n\" }c`;\n"),
]

_MUST_FLAG = [
    ("a single-quoted string with no closing quote",
     "var s = 'oops;\nvar t = 1;"),
    ("a double-quoted string with no closing quote",
     'var s = "oops;\nvar t = 1;'),
    ("the shape this build ships",
     """showSuccess('X: ' + n +  file(s) offered.'");\n"""),
    ("an unterminated string inside an interpolation",
     "var t = `a${ 'oops };\nvar z = 1;\n"),
    ("a broken line after a slash that opened nothing",
     "var r = /abc;\nvar s = 'oops;\nvar z = 1;\n"),
    ("an unterminated string at the end of the source, with no newline",
     "var s = 'oops;"),
    # The one species that cannot be seen line by line: a template
    # literal may legally span lines, so an unclosed backtick is only
    # recognisable at the end of the source -- and until it was, one
    # stray backtick made the scanner report the whole page clean.
    ("an unterminated template literal, which swallows the rest",
     "var t = `oops;\nvar s = 'really broken;\nvar z = 1;\n"),
]


@pytest.mark.parametrize("description,source",
                         _MUST_NOT_FLAG, ids=[d for d, _ in _MUST_NOT_FLAG])
def test_the_scanner_does_not_flag_valid_javascript(description, source):
    assert jsscan.unterminated_strings(source) == [], description


@pytest.mark.parametrize("description,source",
                         _MUST_FLAG, ids=[d for d, _ in _MUST_FLAG])
def test_the_scanner_flags_an_unterminated_string(description, source):
    assert len(jsscan.unterminated_strings(source)) == 1, description


def test_the_scanner_recovers_at_the_end_of_a_broken_line():
    """One broken line is one finding, not one per line after it.

    Carrying the open-string state past the newline would report the
    whole rest of the file, which is the difference between a report
    that says where the fix goes and a report nobody reads.
    """
    source = "var a = 'broken;\nvar b = 'also broken;\nvar c = 1;\n"
    found = jsscan.unterminated_strings(source)
    assert [f.line for f in found] == [1, 2]


def test_a_finding_says_where_on_the_line_the_string_opened():
    """``column`` is reported, so it has to be right.

    Nothing else asserts it and nothing prints it, which is how a field
    that always reads 1 would survive -- and a position that is quietly
    wrong is worse in a bug report than no position at all.
    """
    found = jsscan.unterminated_strings("  var s = 'oops;\n")
    assert [(f.line, f.column) for f in found] == [(1, 11)]


def test_a_line_continuation_does_not_lose_a_line():
    """``\\`` before a newline is legal, and still a line.

    Stepping over the backslash and the newline together -- the obvious
    way to handle an escape -- reports every later finding one line
    early, which points a reader at the wrong line of a file they have
    been told to trust.
    """
    source = "var s = 'abc\\\n def';\nvar t = 'oops;\n"
    found = jsscan.unterminated_strings(source)
    assert [f.line for f in found] == [3]


def test_a_carriage_return_ends_a_line_the_way_a_newline_does():
    """JavaScript ends a line on four characters, not one.

    A lone ``\\r`` and the two Unicode separators are as much a syntax
    error inside a quote as ``\\n``, and a scanner that reads them as
    ordinary text walks straight past a broken line.  The ``\\r\\n``
    pair is one ending, not two, or every line number in a CRLF file is
    doubled -- and these templates ship CRLF.
    """
    assert [f.line for f in jsscan.unterminated_strings("var s = 'a\rb';")] \
        == [f.line for f in jsscan.unterminated_strings("var s = 'a\nb';")]
    assert [f.line for f in jsscan.unterminated_strings("var s = 'a b';")] \
        == [1, 2]
    crlf = "var a = 1;\r\nvar s = 'oops;\r\nvar t = 2;\r\n"
    assert [f.line for f in jsscan.unterminated_strings(crlf)] == [2]


def test_a_script_tag_with_an_unquoted_src_is_still_an_external_script():
    """``<script src=main.js>`` is legal HTML and has no body to read.

    Requiring a quote read such a tag as an empty inline script, so the
    "nothing is hidden from this scan" gate counted zero external
    scripts while a page's real JavaScript went unread.
    """
    page = '<script src=main.js></script><script>var a = 1;</script>'
    assert jsscan.external_scripts(page) == 1
    assert len(jsscan.inline_scripts(page)) == 1


def test_a_line_continuation_inside_a_slash_does_not_lose_a_line_either():
    """The same escape, on the regular-expression path.

    Two code paths step over a backslash, and pinning one of them left
    the other free to drop a line -- which a mutation run duly showed.
    """
    source = "var r = /ab\\\n cd/;\nvar s = 'oops;\n"
    found = jsscan.unterminated_strings(source)
    assert [f.line for f in found] == [3]
