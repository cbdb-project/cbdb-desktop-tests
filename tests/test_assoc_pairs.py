"""Association Pairs: every intermediary it reports lies between the seeds.

The form takes two people (or an imported list) and reports who connects
them: a **1-node** intermediary X is associated with both seeds, and a
**2-node** intermediary lies on a path ``Seed1 - X - Y - Seed2`` in which
neither X nor Y is a seed and X is not Y.  That definition is the user's
guide's, and it is the whole oracle here.

Why this file exists.  Up to 20260925 the pair-mode SQL in
``assocLink2nd`` excluded the wrong two cases: ``X <> Seed1`` and
``Y <> Seed2``, which can only happen through a self-association, instead
of ``X <> Seed2`` and ``Y <> Seed1``.  So whenever the two seeds were
directly associated, ``Seed1 - X - Seed1 - Seed2`` and
``Seed1 - Seed2 - Y - Seed2`` were accepted as 2-node paths, and the
result was padded with people associated with only one of the seeds.
Every HTTP test passed: the reply was well formed, every person in it was
real, every edge in it was in ``ASSOC_DATA``.  It was found by a person
reading the Gephi graph while writing the user's guide (ASP-9 in the
developers' notes of 2026-10-13), not by this suite -- which is the
reason for this file.  On the 20260925 binary the first seed pair below
returned 5 such people among its 20 distance-2 intermediaries, and with
kinship included 14 of 29; on 20261021, none.

What the test asserts is an internal invariant of one response, read off
the reply's own ``network`` edge list: each person at ``nodeDist`` 2 has
a neighbour Y, not a seed and not itself, such that the two of them
reach one seed each.  It predicts no count and runs none of the
handler's joins, so it holds whatever CBDB contains and would hold for a
handler rewritten from scratch.  It can fail: the swapped exclusions
fail it on every seed pair that is directly associated.

The inputs are chosen from the data, as the rule requires: seed pairs
that are directly associated (the only case the defect needs) and small
enough that a 2-node query stays cheap.  Choosing them predicts nothing.

The edges are read as undirected.  ``ASSOC_DATA`` mostly stores both
directions, and the query walks it in one; reading both directions can
only *admit* a path, so this test never reports a correct handler wrong,
at the price of not checking direction.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect

#: How many seed pairs to drive, and the associate-count band that keeps
#: a 2-node query on each of them small.
_SEED_PAIRS = 4
_DEGREE = (8, 25)

_MODES = {
    "pair": {"useList": False, "includeKinship": False},
    "pair+kin": {"useList": False, "includeKinship": True},
    "list": {"useList": True, "includeKinship": False},
    "list+kin": {"useList": True, "includeKinship": True},
}


@pytest.fixture(scope="module")
def seed_pairs(sqlite_conn) -> list[tuple[int, int]]:
    """Directly associated pairs of people with modest association counts."""
    low, high = _DEGREE
    rows = sqlite_conn.execute(
        """
        WITH deg AS (SELECT c_personid AS p, COUNT(DISTINCT c_assoc_id) AS d
                     FROM ASSOC_DATA GROUP BY c_personid)
        SELECT a.c_personid, a.c_assoc_id
        FROM ASSOC_DATA a
        JOIN deg d1 ON d1.p = a.c_personid
        JOIN deg d2 ON d2.p = a.c_assoc_id
        WHERE a.c_personid > 0 AND a.c_personid < a.c_assoc_id
          AND d1.d BETWEEN ? AND ? AND d2.d BETWEEN ? AND ?
        GROUP BY a.c_personid, a.c_assoc_id
        ORDER BY a.c_personid, a.c_assoc_id
        LIMIT ?""",
        (low, high, low, high, _SEED_PAIRS)).fetchall()
    assert len(rows) == _SEED_PAIRS, \
        f"only {len(rows)} directly associated seed pairs in the band {_DEGREE}"
    return [(int(a), int(b)) for a, b in rows]


def _query(app: CbdbApp, seed1: int, seed2: int, mode: str) -> dict:
    body = {"personId1": seed1, "personId2": seed2, "use2ndOrder": True,
            "yearFilterType": "none", **_MODES[mode]}
    if body["useList"]:
        imported = app.post("/api/assocpairs/import-list",
                            json={"personIds": [seed1, seed2]})
        assert imported.status_code == 200, imported.text[:200]
        body["personId1"] = body["personId2"] = 0
    reply = app.post("/api/assocpairs/query", json=body)
    assert reply.status_code == 200, f"{mode} {seed1},{seed2}: {reply.text[:200]}"
    return reply.json()


def _off_path(payload: dict, seed1: int, seed2: int):
    """The reported intermediaries no path in the reply's own edges explains.

    Returns ``(distance_1, distance_2, unexplained_1, unexplained_2)``.
    """
    seeds = {seed1, seed2}
    neighbours: dict[int, set[int]] = defaultdict(set)
    for edge in payload["network"]:
        a, b = edge["personId1"], edge["personId2"]
        if a != b:
            neighbours[a].add(b)
            neighbours[b].add(a)

    def reaches(person: int, seed: int) -> bool:
        return seed in neighbours[person]

    dist = {p["personId"]: p["nodeDist"] for p in payload["people"]}
    first = [p for p, d in dist.items() if d == 1]
    second = [p for p, d in dist.items() if d == 2]
    bad_first = [x for x in first
                 if not (reaches(x, seed1) and reaches(x, seed2))]
    bad_second = [
        x for x in second
        if not any(y not in seeds and y != x
                   and ((reaches(x, seed1) and reaches(y, seed2))
                        or (reaches(x, seed2) and reaches(y, seed1)))
                   for y in neighbours[x])]
    return first, second, bad_first, bad_second, neighbours


@pytest.mark.parametrize("mode", list(_MODES))
def test_every_intermediary_lies_on_a_path_between_the_seeds(
        app: CbdbApp, seed_pairs, mode):
    """A 2-node query reports only people on a Seed1 - X - Y - Seed2 path.

    And every 1-node intermediary is associated with both seeds.  Driven
    in all four shapes of the query, because the fix had to reach every
    call of ``assocLink2nd``: with and without kinship, from two seeds
    and from an imported list of the same two people.
    """
    seen_second = 0
    findings, failures = [], []
    try:
        for seed1, seed2 in seed_pairs:
            payload = _query(app, seed1, seed2, mode)
            _first, second, bad_first, bad_second, neighbours = \
                _off_path(payload, seed1, seed2)
            seen_second += len(second)
            if bad_first:
                failures.append(
                    f"seeds {seed1},{seed2}: {len(bad_first)} 1-node "
                    f"intermediaries not associated with both seeds, "
                    f"e.g. {bad_first[:5]}")
            if bad_second:
                # The recognised signature of the swapped seed exclusions:
                # each such person touches one seed and nothing that
                # reaches the other.
                touched = {x: sorted(neighbours[x] & {seed1, seed2})
                           for x in bad_second[:5]}
                findings.append(
                    f"seeds {seed1},{seed2} (directly associated): "
                    f"{len(bad_second)} of {len(second)} 2-node "
                    f"intermediaries lie on no Seed1-X-Y-Seed2 path with "
                    f"X, Y not seeds; e.g. person -> seeds it touches: "
                    f"{touched}")
    finally:
        if _MODES[mode]["useList"]:
            app.post("/api/assocpairs/clear-list", json={})

    assert not failures, f"{mode}: " + "; ".join(failures)
    if findings:
        raise KnownShippedDefect(
            f"Association Pairs {mode} 2-node query admits paths through a "
            f"seed (the X<>Seed2 / Y<>Seed1 exclusions are missing from "
            f"assocLink2nd): " + "; ".join(findings))
    assert seen_second, (
        f"{mode}: no seed pair produced a 2-node intermediary, so nothing "
        f"was checked -- choose seed pairs that have some: {seed_pairs}")
