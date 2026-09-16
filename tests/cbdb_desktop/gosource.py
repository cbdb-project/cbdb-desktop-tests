"""Reading the shipped Go sources as text.

The build ships its own source, and several gates read it to find out
what the application is made of -- which tables a form writes, which
file a declaration sits in.  That is source read as *data*, which
AGENTS.md permits; none of it re-implements what the code does.

Two small readers live here rather than in one of the test files that
uses them.  ``test_scratch_tables.py`` had them first; when
``test_cross_form_channel.py`` needed the same two questions answered,
the copy written for it was weaker -- it stripped only
``_form_backend.go`` and had no notion of a shared file -- and review
caught the divergence before either version was committed.  Rather
than reconcile two copies, there is one.

Note what ``form_of`` cannot tell you: a handler that belongs to a
form but lives in one of ``SHARED_FILES`` is reported as ``<shared>``,
and a caller that discards ``<shared>`` therefore discards it too.
That is the right answer for schema and helpers, which is all those
files hold in this build, and the wrong one the day a form's handler
moves into ``main.go``.  Callers that subtract ``SHARED`` are relying
on that and should say so.
"""
from __future__ import annotations

import re

#: Sources that belong to no single form: the schema, the helpers and
#: the navigation shell.  Naming them is the only way to tell "shared"
#: from "a form whose file happens not to end in _form_backend.go".
SHARED_FILES = {"main.go", "cbdb_shared_utils.go",
                "cbdb_navigation_backend.go"}

#: What ``form_of`` answers for a file in ``SHARED_FILES``.
SHARED = "<shared>"


def form_of(filename: str) -> str:
    """``networks_form_backend.go`` -> ``networks``; a shared file -> ``<shared>``.

    Both halves of a form map to the same name: a form's backend and
    its query file are one form, and a caller asking "which forms name
    this table" wants them counted once.
    """
    if filename in SHARED_FILES:
        return SHARED
    return (filename.removesuffix("_form_backend.go")
            .removesuffix("_form_query.go")
            .removesuffix(".go"))


def strip_comments(source: str) -> str:
    """Go source with ``//`` and ``/* */`` blanked.

    So that a table or a function named in prose -- a TODO, a comment
    explaining what a handler used to do -- is not read as a use of it.
    Offsets are not preserved; nothing here needs them.
    """
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", source)


def struct_body(source: str, struct_name: str) -> str | None:
    """The field block of one Go struct declaration, or ``None``.

    Matched to a closing brace in column zero rather than by a
    non-greedy run to the next ``}``, which would stop at the first
    brace inside a field's tag or a comment and report the struct's
    fields as absent -- a gate reading nothing and finding nothing
    wrong with it.
    """
    found = re.search(
        r"^type\s+" + re.escape(struct_name) + r"\s+struct\s*\{(.*?)^\}",
        source, re.DOTALL | re.MULTILINE)
    return found.group(1) if found else None


#: Three ``chk*`` fields on ``NetworkQuery`` that are not association
#: categories: all three are address controls read by
#: ``populateScratchAddr``.  ``chkXYRef`` in particular was counted as a
#: category until the source was asked which flags ``makeAssocFilter``
#: gives a selector to -- it is the historical-XY bounding-box switch,
#: and counting it made the sweep claim thirty categories where the form
#: offers twenty-nine.
_NOT_CATEGORIES = frozenset({"chkSubUnits", "chkPlaceLimit", "chkXYRef"})


#: ``{(path, size, mtime): flags}``.  These readers are called once per
#: network request -- hundreds of times in a run -- and each call
#: re-read and re-parsed a 3,000-line Go file.
#:
#: The path alone is not enough for a key, and the difference matters
#: for exactly one caller: ``stage(..., force=True)`` replaces the tree
#: *at the same path*, so a forced restage inside one process would be
#: served the previous build's answer.  Size and mtime move when the
#: file does, which is the cheap version of the content-addressing
#: ``staging.py`` does properly.
_CATEGORY_CACHE: dict[tuple[str, int, int], list[str]] = {}


def association_category_flags(layout) -> list[str]:
    """The ``chk*`` association categories ``NetworkQuery`` declares.

    Read off the request struct rather than listed, for the reason
    AGENTS.md section *Coverage is the program's job* gives: a category
    the build gains should widen every sweep over them by itself.

    Shared, because since the 2026-09-15 build this list is needed for
    more than sweeping.  That build made an empty category selection
    mean "no association ties" rather than "no filter" -- correctly, and
    it is the fix to a real defect -- so a request that ticks nothing no
    longer means what the suite's network request bodies assumed it
    meant.  Anything that wants "an ordinary unfiltered network" now has
    to say so by ticking all of them, which is what ``all_categories_on``
    below is for.
    """
    source = layout.code_dir / "networks_form_backend.go"
    stat = source.stat()
    key = (str(source), stat.st_size, stat.st_mtime_ns)
    if key not in _CATEGORY_CACHE:
        text = source.read_text(encoding="utf-8", errors="replace")
        body = struct_body(text, "NetworkQuery")
        assert body, "networks_form_backend.go no longer declares NetworkQuery"
        flags = re.findall(r'`json:"(chk[A-Za-z]+)"`', body)
        _CATEGORY_CACHE[key] = sorted(set(flags) - _NOT_CATEGORIES)
    return list(_CATEGORY_CACHE[key])


def all_categories_on(layout) -> dict[str, bool]:
    """Every association category ticked, as request fields.

    Selecting all of them is the one selection the handler treats as no
    filter at all (``totalCount == categoryMax`` skips the filter table),
    so this is how a test asks for a network with the association side
    left alone.  Ticking none is a different request with a different
    meaning, and asking for it by accident is what this exists to stop.
    """
    return {flag: True for flag in association_category_flags(layout)}
