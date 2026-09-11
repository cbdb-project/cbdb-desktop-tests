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
