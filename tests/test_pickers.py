"""What the Entry and Status pickers' type trees leave unreachable.

These two pickers show a tree of types and then the codes under the
type a user picks, so a code is reachable only through the type it
hangs from.  Two ways that can go wrong are checked here, and both
are about the tree rather than about the codes.

Most of what a first draft of this file tested was already tested,
and better, in ``test_lookups.py``: that every type the relation
names is one the picker offers (`:86`, `:100`), and that the
codes-for-type endpoints agree with the relation (`:559`-`:668`).
Those duplicates are gone.  One of them was also wrong -- it
asserted that the codes for a type *equal* the relation's exact
rows, while the endpoint matches by prefix so that choosing a parent
returns its descendants.  It passed only because the type it picked,
the one with the most exact rows, happens to be a leaf; three of the
twenty-nine entry types would have made it raise a finding against
correct behaviour.  ``test_lookups.py`` had already learned that and
asserts containment.

What is left is the gap those tests leave: they pin the parent trees
of the Office, Associations and Texts pickers, and not these two.
"""
from __future__ import annotations

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect

pytestmark = pytest.mark.app

#: ``picker -> the endpoints and field names its tree is built from``.
#:
#: ``root`` is how each answer spells "this type has no parent", and
#: the two differ: Entry's ``ParentID`` is a plain string filled by
#: ``COALESCE(..., '')`` and carries ``"0"``, while Status's
#: ``ParentCode`` is a ``*string`` and marshals as JSON ``null``.  A
#: check that knew only one of those would report all nineteen Entry
#: roots as dangling, which is what the first probe of this did.
#:
#: ``roots`` is pinned exactly, for the reason ``test_lookups.py``
#: gives where it pins the other three trees: without it, a tree
#: whose parents had all become null would read as a valid forest of
#: roots and the dangling check below would compare nothing.
_PICKERS = {
    "entry": {
        "types": "/api/entry-types",
        "relation": "/api/entry-code-type-rel",
        "rel_type": "entryType",
        "parent": "parentId",
        "root": "0",
        "roots": 19,
    },
    "status": {
        "types": "/api/status-types",
        "relation": "/api/status-code-type-rel",
        "rel_type": "statusTypeCode",
        "parent": "parentCode",
        "root": None,
        "roots": 13,
    },
}


def _types(app: CbdbApp, picker: dict) -> list[dict]:
    rows = app.json("GET", picker["types"])
    assert isinstance(rows, list) and rows, (
        f"{picker['types']} answered {rows!r}; the picker's first "
        "control is built from this list, so an empty answer means "
        "the picker opens onto nothing")
    return rows


@pytest.mark.parametrize("name", sorted(_PICKERS))
def test_every_type_the_picker_offers_has_codes_under_it(
        app: CbdbApp, name: str):
    """A type that opens onto nothing is a dead branch of the control.

    Judged against the relation endpoint rather than against the
    database: the application's own statement of which codes belong
    to which type is what the picker will use, so a type absent from
    it opens empty however many rows the database holds.

    Prefix matching is why this is asked of the relation and not of
    ``codes-for-type``.  Choosing a parent type returns its
    descendants' codes, so a parent with no codes of its own is not
    a dead branch; a type that appears nowhere in the relation, at
    any depth, is.
    """
    picker = _PICKERS[name]
    offered = {str(row.get("code")): row for row in _types(app, picker)}

    relation = app.json("GET", picker["relation"])
    assert isinstance(relation, list) and relation, (
        f"{picker['relation']} answered {relation!r}, so no code can "
        "be attributed to any type and this test judges nothing")

    populated = {str(row.get(picker["rel_type"])) for row in relation}
    # A parent counts as populated when a descendant is, because the
    # endpoint the picker calls matches by prefix.
    reachable = {
        code for code in offered
        if any(kind == code or kind.startswith(code) for kind in populated)
    }

    empty = sorted(set(offered) - reachable)
    if empty:
        described = {code: offered[code].get("desc") for code in empty[:8]}
        raise KnownShippedDefect(
            f"the {name} picker offers {len(empty)} of its "
            f"{len(offered)} types with no code anywhere beneath "
            f"them: {described}.  Choosing one shows an empty second "
            f"list, with nothing on the page to say why.  "
            f"({len(populated)} distinct types carry codes in "
            f"{picker['relation']}.)")


@pytest.mark.parametrize("name", sorted(_PICKERS))
def test_every_parent_a_type_names_is_a_type_that_exists(
        app: CbdbApp, name: str):
    """The type tree must hang together.

    Both pickers build a tree from this one answer and render any
    type whose parent is not in it at the top level.  So a dangling
    parent does not disappear -- it is shown as a root, at the wrong
    level, and the codes under it are found by a user looking in the
    wrong place, which is worse than an empty branch because nothing
    looks wrong.

    The root count is pinned as well as the dangling set.  Without
    it a build that nulled every parent would present a flat list of
    roots, no reference would dangle, and this test would pass
    having compared nothing -- which is live here, because thirteen
    of Status's fourteen types are already roots and exactly one row
    reaches the check below.
    """
    picker = _PICKERS[name]
    rows = _types(app, picker)

    assert any(picker["parent"] in row for row in rows), (
        f"no row from {picker['types']} carries {picker['parent']!r} "
        "any more, so either the field was renamed or the hierarchy "
        "is gone; this test checks nothing until it is updated")

    codes = {str(row.get("code")) for row in rows}
    roots, dangling, spellings = 0, {}, {}
    for row in rows:
        parent = row.get(picker["parent"])
        if parent == picker["root"]:
            roots += 1
            continue
        spellings[repr(parent)] = spellings.get(repr(parent), 0) + 1
        if str(parent) not in codes:
            dangling.setdefault(str(parent), []).append(str(row.get("code")))

    # The sentinel is compared before ``str()``, and to one value, not
    # to a set of plausible ones.  A set of {"0", "", None} would let
    # every Entry root become "" or null without anything noticing --
    # a floor where an exact pin is available, which is operating
    # principle 5.  It also matters which: the two pickers spell it
    # differently, and a reader who checks the wrong one sees
    # nineteen dangling parents that are not there.
    other_roots = {text: n for text, n in spellings.items()
                   if text in ("''", "None", "'0'")}
    assert not other_roots, (
        f"{picker['types']} spells 'no parent' as "
        f"{picker['root']!r}, and {other_roots} row(s) carry a "
        "different empty-looking value.  One of the two is now "
        "wrong; read which before adjusting either, because the "
        "dangling check below treats an unrecognised sentinel as a "
        "broken reference and the count above treats it as a child.")

    assert roots == picker["roots"], (
        f"{picker['types']} now has {roots} type(s) with no parent, "
        f"not {picker['roots']}.  The shape of the tree moved: read "
        f"it before changing the number, because a tree that has "
        f"become all roots would make the dangling check below "
        f"vacuous.  ({len(rows)} types in all; "
        f"{picker['parent']}={picker['root']!r} means no parent.)")

    if dangling:
        raise KnownShippedDefect(
            f"{len(dangling)} parent reference(s) in "
            f"{picker['types']} name no type in the same answer: "
            f"{dict(sorted(dangling.items())[:6])} as "
            f"{picker['parent']} -> the types claiming it.  Each is "
            f"rendered at the top level instead of under its parent, "
            f"so the codes beneath it are shown somewhere the user "
            f"would not look for them.  ({len(rows)} types, {roots} "
            f"of them roots.)")
