"""The Networks form's filters: who is in the network, and by what tie.

The Networks page is the application's social-network tool, and almost
all of it is filters.  Two checkboxes decide whether kin or non-kin
ties are followed, two more decide which sexes appear, four numbers cap
how far a kinship walk goes, and **twenty-nine** checkboxes select the
categories of association to include -- politics, scholarship, writing,
military, religion, finance, family, medicine, each with its own sub-
kinds.  A researcher uses them to ask a specific question: *the
scholarly ties only*, *no kin*, *women only*.

The suite drove none of the twenty-nine, and never varied the sex or
kin switches at all -- every network query it sent omitted the flags
entirely, which left ``totalCount`` at zero and skipped the category
filter altogether.  Worth stating rather than glossing: the one code
path the suite exercised was the one where the filter does not run,
which is how three of the findings below sat in a shipped build
unnoticed.  This file drives them, and the oracle throughout
is the response itself.  Every edge the query returns says what kind of
tie it is -- ``linkType`` is ``K`` for kinship, ``linkCode`` names the
association -- and every node says its sex.  So a filter can be checked
against the rows it produced without knowing anything about the data:
if the user unticked kinship, no returned edge may be a kinship edge.

That is the strongest oracle available here and it needs saying why.  A
network query has no fixed right answer to compare against: it is a
graph walk whose size depends on the person, the depth and the data.
What it does have is a promise about *what may appear*, and that is
what these tests hold it to.  Nothing below predicts how large a
network should be, and nothing reproduces the traversal.

One thing this file deliberately does not do: it does not decide for
itself which association code belongs to which category.  Nothing here
works out that a *Preface of book by* tie is a writing tie rather than
a scholarly one -- re-deriving that in Python would be exactly the
transcription AGENTS.md prohibits.

It tried that route first and withdrew it, which is worth recording
because the attempt looks legitimate. The idea was to read the clause
``makeAssocFilter`` inserts for a checkbox --

    if q.ChkFamily {
        if err := exec("SUBSTR(c_assoc_type_code,1,2)='09'"); ...

-- resolve it against ``ASSOC_CODE_TYPE_REL``, and check the returned
codes against the result. Both halves are shipped artefacts and
neither reproduces the traversal, so it reads as build-as-data. But
the handler computes its own filter with *that clause against that
table*, so a build that mapped Family to the wrong type code would
have had its mistake copied into the expectation and passed. Against
the deciding question -- would this still mean something if the
handler were rewritten to the same specification? -- the answer is
no, and that settles it.

What the file does instead needs no mapping at all. Every association
code carries exactly one type, so the categories partition the codes;
two single-category answers that share a code are therefore two of
the application's own answers contradicting each other. The partition
is asserted from the data rather than assumed, and the clause is
still read -- but only to decide which checkboxes can be driven,
which is an input.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.forms import STORE_RESET, WORKING_LIST_RESETS
from cbdb_desktop.subjects import SUBJECT

pytestmark = pytest.mark.app

#: The smallest query that still returns a network worth filtering.
#: Depth one on both walks: these are graph traversals with no
#: server-side cap, and this file runs many of them.
_BASE = {
    "usePersonID": True, "useKin": True, "useNonKin": True,
    "useMale": True, "useFemale": True, "maxLoop": 1, "maxNodeDist": 1,
    "kinParam": True, "maxUp": 1, "maxDwn": 1, "maxCol": 1, "maxMar": 1,
}

#: How many association-category checkboxes ``NetworkQuery``
#: declares, after the three ``chk*`` fields that are not categories
#: are set aside.  Pinned
#: exactly: this is the denominator of the sweep below, and a build
#: that gains a category should be read rather than silently covered
#: one short.
EXPECTED_CATEGORY_FLAGS = 29


@pytest.fixture
def ego(app: CbdbApp):
    """A person with a network big enough to filter, list cleared after."""
    def reset():
        for path, body in WORKING_LIST_RESETS:
            app.post(path, json=body)
        app.post(STORE_RESET[0], json=STORE_RESET[1])

    reset()
    app.post("/api/networks/set-person", json={"personId": SUBJECT})
    yield SUBJECT
    reset()


def _query(app: CbdbApp, **extra) -> dict:
    answer = app.json("POST", "/api/networks/query", json=dict(_BASE, **extra))
    assert {"edgeRecords", "nodeRecords"} <= set(answer), sorted(answer)
    return answer


def _edges(answer: dict) -> list[dict]:
    return answer["edgeRecords"]


def _nodes(answer: dict) -> list[dict]:
    return answer["nodeRecords"]


# ---------------------------------------------------------------------------
# the two switches that decide which ties are followed
# ---------------------------------------------------------------------------

def test_turning_kinship_off_returns_no_kinship_ties(app: CbdbApp, ego):
    """Untick Kinship and no edge may come back marked as kinship.

    Every edge says what it is: ``linkType`` is ``K`` for a kinship
    tie.  So this needs no knowledge of the data at all -- it is the
    response judged against the box the user unticked.

    Both directions are driven.  A switch that is ignored returns the
    kinship edges anyway, which this catches; a switch that is wired
    to the wrong branch returns *nothing*, which the liveness check
    catches.
    """
    both = _query(app, useKin=True, useNonKin=True)
    kin_edges = [e for e in _edges(both) if e.get("linkType") == "K"]
    assert kin_edges, (
        f"person {ego} has no kinship edges even with Kinship ticked, so "
        "unticking it cannot be judged on this subject")

    without = _query(app, useKin=False, useNonKin=True)
    leaked = [e for e in _edges(without) if e.get("linkType") == "K"]
    assert not leaked, (
        f"{len(leaked)} kinship edge(s) came back with Kinship unticked, "
        f"for example {leaked[:2]}")
    assert _edges(without), (
        "unticking Kinship removed every edge, including the non-kin "
        "ones the other box is still asking for")


def test_turning_non_kinship_off_returns_only_kinship_ties(
        app: CbdbApp, ego):
    """The other half, which is not the same test.

    A handler that ignored ``useNonKin`` would pass the kinship test
    above perfectly.  This is the mirror: with only Kinship ticked,
    every edge must be a kinship edge.
    """
    only_kin = _query(app, useKin=True, useNonKin=False)
    assert _edges(only_kin), (
        "asking for kinship ties alone returned no edges at all")

    others = [e for e in _edges(only_kin) if e.get("linkType") != "K"]
    assert not others, (
        f"{len(others)} non-kinship edge(s) came back with Non-Kinship "
        f"unticked: {[e.get('linkType') for e in others[:6]]}")


def test_unticking_both_tie_kinds_returns_no_edges(app: CbdbApp, ego):
    """Neither kin nor non-kin: there is no third kind.

    The degenerate case, and worth holding: a form that substitutes a
    default when the user has selected nothing is a real shape in this
    build -- the Places page does it with its categories -- and it
    turns "I asked for nothing" into "here is everything".
    """
    neither = _query(app, useKin=False, useNonKin=False)
    edges = _edges(neither)
    if edges:
        raise KnownShippedDefect(
            f"for person {ego}, unticking both Kinship and Non-Kinship "
            f"returned {len(edges)} edge(s), of kinds "
            f"{sorted({e.get('linkType') for e in edges})}.  There is no "
            "third kind of tie, so a network with neither selected has "
            "no edges to draw; returning some means the selection is "
            "being substituted rather than applied")


# ---------------------------------------------------------------------------
# the sex filter
# ---------------------------------------------------------------------------

def _raw_query(app: CbdbApp, **extra):
    """The query endpoint without raising on a non-200.

    ``app.json`` turns an HTTP 500 into an ``AppError``, which is the
    right default and the wrong one here: a 500 *is* the finding, and
    a test that dies on it reports an error with the diagnosis
    nowhere.
    """
    return app.post("/api/networks/query", json=dict(_BASE, **extra))


@pytest.mark.parametrize("excluded,switch", [("F", "useFemale"),
                                             ("M", "useMale")])
def test_the_sex_filter_removes_the_sex_it_was_told_to(
        app: CbdbApp, ego, excluded: str, switch: str):
    """Untick one sex and nobody of that sex may be in the network.

    Each node carries ``sex``, so this is the response against the
    box.  Both are driven because they are separate fields in the
    request and a handler can easily read one twice.

    The subject is exempt: the person the network is *of* is its
    centre, and a filter that dropped them would leave a network with
    no ego.  Whether that is right is a question for the developers;
    what is checked here is everybody else.
    """
    both = _query(app)
    present = {node["personId"] for node in _nodes(both)
               if node.get("sex") == excluded}
    assert present, (
        f"person {ego}'s network contains nobody of sex {excluded} even "
        "with both boxes ticked, so removing them cannot be judged on "
        "this subject.  Pick another ego rather than skipping: a sex "
        "filter nothing can judge is a sex filter nothing covers.")

    response = _raw_query(app, **{switch: False})
    if response.status_code != 200:
        # The same query with a dynasty filter added, because the
        # source says that is what decides it -- and a filter that
        # works only when an unrelated filter is also on is a
        # different report from a filter that never works.
        with_dynasty = _raw_query(app, **{switch: False,
                                          "useDynasties": True,
                                          "fromDynasty": 15})
        raise KnownShippedDefect(
            f"unticking {switch} answers HTTP {response.status_code}: "
            f"{response.text.strip()[:120]}.  The sex condition is "
            "written against the alias BIOG_MAIN_1 and appended to "
            "both the kin and the non-kin WHERE strings, but of the "
            "kinship FROM clauses only fromKinDynasty and fromKinAddr "
            "define that alias -- the plain fromKin, which is the one "
            "chosen when neither a dynasty nor an address filter is "
            "set, does not.  Adding a dynasty filter to the same "
            f"request answers HTTP {with_dynasty.status_code}, which "
            "is the shape of it: the sex filter is reachable only by "
            "a user who happens to be filtering by dynasty or address "
            "as well.")

    filtered = response.json()
    remaining = [node for node in _nodes(filtered)
                 if node.get("sex") == excluded and node["personId"] != ego]

    assert _nodes(filtered), (
        f"unticking {switch} emptied the network entirely")
    assert not remaining, (
        f"{len(remaining)} person(s) of sex {excluded} are still in the "
        f"network with {switch} unticked, for example "
        f"{[n.get('name') for n in remaining[:4]]}")


def test_the_sex_filter_stops_erroring_when_a_dynasty_filter_is_on(
        app: CbdbApp, ego):
    """The other half of the diagnosis above, driven rather than read.

    Named for what it proves and no more.  It asserts that the same
    request stops answering HTTP 500, not that the sex filter then
    works: a handler that accepted the request and ignored the switch
    would pass this, and checking the filtering as well is the job of
    the test above once the 500 is gone.

    That is enough for what it is here to establish.  If this passes
    while the test above raises, the fault is not the sex filter as
    such but the alias it names: the kinship FROM that a dynasty
    filter selects defines ``BIOG_MAIN_1`` and the plain one does
    not.  That is a more useful thing to hand a maintainer than "sex
    filtering is broken", and it is the difference between a one-line
    fix and a hunt.

    If both fail, the diagnosis is wrong and the entry needs
    rewriting -- which is the point of driving it.
    """
    response = _raw_query(app, useFemale=True, useMale=False,
                          useDynasties=True, fromDynasty=15)
    assert response.status_code == 200, (
        "the sex filter answers HTTP "
        f"{response.status_code} even with a dynasty filter set: "
        f"{response.text.strip()[:160]}.  The entry on the sex filter "
        "says a dynasty filter is what makes it reachable, and this "
        "says otherwise -- re-read the FROM selection in "
        "networks_form_query.go before trusting that entry.")


# ---------------------------------------------------------------------------
# the twenty-nine category checkboxes
# ---------------------------------------------------------------------------

def _category_flags(layout) -> list[str]:
    """The ``chk*`` association categories ``NetworkQuery`` declares.

    Read off the request struct rather than listed here, for the
    reason § *Coverage is the program's job* gives: a category the
    build gains should widen this sweep by itself.

    ``chkSubUnits``, ``chkPlaceLimit`` and ``chkXYRef`` are excluded:
    all three are address controls read by ``populateScratchAddr``,
    not association categories.  ``chkXYRef`` was counted as a
    category until the source was asked which flags
    ``makeAssocFilter`` gives a selector to -- it is the historical-XY
    bounding-box switch, and counting it made this sweep claim thirty
    categories where the form offers twenty-nine.

    ``chkKin`` was in the exclusion set too and is not a field on
    ``NetworkQuery`` at all; kinship is ``useKin``.  Excluding a name
    that matches nothing costs nothing today and would have silently
    swallowed a real category if the build ever added one under that
    name, so it is gone.
    """
    text = (layout.code_dir / "networks_form_backend.go").read_text(
        encoding="utf-8", errors="replace")
    body = re.search(r"^type\s+NetworkQuery\s+struct\s*\{(.*?)^\}",
                     text, re.DOTALL | re.MULTILINE)
    assert body, "networks_form_backend.go no longer declares NetworkQuery"
    flags = re.findall(r'`json:"(chk[A-Za-z]+)"`', body.group(1))
    return sorted(set(flags) - {"chkSubUnits", "chkPlaceLimit",
                                "chkXYRef"})



def test_the_category_sweep_covers_every_category_the_build_declares(layout):
    """The denominator, pinned, before anything is swept.

    Without this the sweep below reports "every category behaves" over
    whatever subset happened to be found, which is the failure mode
    that let seven Use XY switches go unsent for the life of the
    suite.
    """
    flags = _category_flags(layout)
    assert len(flags) == EXPECTED_CATEGORY_FLAGS, (
        f"NetworkQuery declares {len(flags)} association categories, not "
        f"{EXPECTED_CATEGORY_FLAGS}: {flags}.  Update the number in the "
        "same commit as the reason")


def test_no_category_switch_removes_an_edge_that_was_already_there(
        app: CbdbApp, ego, layout):
    """Each category can only add people, and some must actually add.

    Twenty-nine checkboxes, of which the rest of the suite sends
    none.  The property is the one ``test_query_matrix.py``'s sweep
    uses for the read-only forms -- widening a selection may not
    narrow an answer -- but it has to be stated on the right thing
    here, and the first version stated it on the wrong one.

    It asserted that no ``(personId, nodeId, linkCode)`` triple may
    disappear.  A correct build can break that.
    ``sqlPruneAssocInverse2`` marks a row deleted once the inverse of
    its association code appears in the same batch for the same two
    people with the larger ``c_personid``, so a wider selection can
    bring in the other orientation and legitimately drop this one.
    The tie is not lost; it is reported the other way round.  What
    survives that pruning is the **unordered pair**, exactly one
    orientation of which is kept, so a pair is what a category may
    not take away.

    The effect half is aggregate rather than per-category, because
    which categories a single person's network can demonstrate is a
    fact about that person: this subject has political and scholarly
    ties and no medical ones.  Demanding that *every* category change
    the answer would fail on a correct build.  Demanding that none of
    the twenty-nine does is the claim that catches a sweep wired to
    nothing -- and it is checked before the narrowing half, so that a
    build which narrows still has its liveness read.  In the first
    version the order was the other way round and the liveness
    assertion had never once executed.
    """
    flags = _category_flags(layout)
    none_on = {flag: False for flag in flags}

    # The baseline is *one* category on, not none.  All-off cannot be
    # the control here: this build treats an empty selection as no
    # filter and answers with everything, which is its own finding
    # below -- measuring "does adding a category add edges" against
    # that baseline would report every category as *removing* edges,
    # which is what the first version of this test did.
    anchor = flags[0]

    def pairs_and_edges(**extra):
        answer = _query(app, **dict(none_on, **extra))
        rows = _edges(answer)
        return ({frozenset((e["personId"], e["nodeId"])) for e in rows},
                {(e["personId"], e["nodeId"], e["linkCode"]) for e in rows})

    base_pairs, base_edges = pairs_and_edges(**{anchor: True})

    changed, shrank = [], {}
    for flag in flags[1:]:
        pairs, edges = pairs_and_edges(**{anchor: True, flag: True})
        lost = base_pairs - pairs
        if lost:
            shrank[flag] = sorted(tuple(sorted(pair)) for pair in lost)[:4]
        if edges != base_edges:
            changed.append(flag)

    # Liveness first, so that a build which also narrows still has
    # this half read.  The other order left it unreachable.
    assert changed, (
        f"adding any of the other {len(flags) - 1} categories to "
        f"{anchor} changed nothing in person {ego}'s network.  Either "
        "the subject has ties of one category only -- in which case "
        "this test needs a different one -- or the category checkboxes "
        "are not reaching the query")

    assert not shrank, (
        f"adding a category to {anchor} removed {len(shrank)} "
        f"person-pair(s) that were connected without it, which no "
        f"category switch may do: {shrank}.  Pairs rather than edges, "
        "because the inverse-pruning passes legitimately drop one "
        "orientation of a tie once the other enters the batch -- but "
        "they keep the pair.  A pair that vanishes entirely is a "
        f"connection the wider selection lost.  Driven on person "
        f"{ego}.")


def test_turning_every_category_off_leaves_no_association_ties(
        app: CbdbApp, ego, layout):
    """No category selected, and Kinship off: nothing should come back.

    The counterpart to the sweep, and the one that catches a
    substituted default.  With kinship excluded as well, every edge
    that could still appear would have to belong to a category the
    user turned off.
    """
    flags = _category_flags(layout)
    answer = _query(app, useKin=False, useNonKin=True,
                    **{flag: False for flag in flags})

    edges = _edges(answer)
    if edges:
        raise KnownShippedDefect(
            f"for person {ego}, with Kinship unticked and all "
            f"{len(flags)} association categories unticked, the query "
            f"returned {len(edges)} "
            f"edge(s) of link types "
            f"{sorted({e.get('linkType') for e in edges})} and codes "
            f"{sorted({e.get('linkCode') for e in edges})[:8]}.  Every "
            "kind of tie the form offers has been excluded, so an edge "
            "that still appears belongs to a category the user turned "
            "off")


def _category_selectors(layout) -> dict[str, str]:
    """``chk*`` -> the WHERE clause ``makeAssocFilter`` inserts for it.

    The build's own statement of what each checkbox selects, taken
    from the source rather than written out here.  Each branch reads

        if q.ChkFamily {
            if err := exec("SUBSTR(c_assoc_type_code,1,2)='09'"); ...

    and the clause is what goes into ``ZZ_SCRATCH_ASSOC_FILTER``.
    """
    text = (layout.code_dir / "networks_form_backend.go").read_text(
        encoding="utf-8", errors="replace")
    region = re.search(
        r"func \(h \*NetworkHandler\) makeAssocFilter.*?\n\}\n",
        text, re.DOTALL)
    assert region, "networks_form_backend.go no longer defines makeAssocFilter"
    found = re.findall(
        r"if q\.(Chk\w+)\s*\{[^{}]*?exec\(\"([^\"]+)\"\)",
        region.group(0), re.DOTALL)
    return {flag[0].lower() + flag[1:]: clause for flag, clause in found}


def test_every_category_the_form_offers_selects_something(layout):
    """A checkbox that inserts no codes cannot filter anything.

    ``makeAssocFilter`` is where a ticked category becomes a set of
    association codes.  A category with no branch there is a control
    the user can tick that changes nothing about which ties come
    back -- and the count it contributes still moves the all-on
    threshold, so it is not even inert.
    """
    flags = _category_flags(layout)
    selectors = _category_selectors(layout)
    without = sorted(set(flags) - set(selectors))

    if without:
        text = (layout.code_dir / "networks_form_backend.go").read_text(
            encoding="utf-8", errors="replace")
        region = re.search(
            r"func \(h \*NetworkHandler\) makeAssocFilter.*?\n\}\n",
            text, re.DOTALL).group(0)
        prefixes = sorted(set(re.findall(
            r"exec\(\"SUBSTR\(c_assoc_type_code,1,2\)='(\d\d)'\"\)",
            region)))
        raise KnownShippedDefect(
            f"{len(without)} of the {len(flags)} association categories "
            f"the Networks form offers select no association codes at "
            f"all: {without}.  makeAssocFilter gives every other "
            f"category a branch that inserts into "
            f"ZZ_SCRATCH_ASSOC_FILTER, and the query INNER JOINs that "
            f"table, so a category with no branch cannot add a tie.  "
            f"The prefixes any branch there can insert are {prefixes}, "
            f"and the function's own comment names '06' as Military -- "
            f"'06' is not among them.  The two military counters are "
            f"kept up to date (militaryCount against militaryMax) and "
            f"nothing ever reads them, so ticking a Military box only "
            f"moves the total that decides whether any filter is "
            f"applied at all")


def test_no_two_categories_return_the_same_association(
        app: CbdbApp, ego, layout, sqlite_conn):
    """Two categories that select different ties may not return one.

    The oracle here is the application disagreeing with itself, and
    it is worth saying why it had to be built this way.

    The obvious test -- read the clause ``makeAssocFilter`` inserts
    for a checkbox, resolve it against ``ASSOC_CODE_TYPE_REL``, and
    check the returned codes against that set -- computes its
    expected answer with the same clause against the same table the
    handler uses.  A build that mapped *Teacher* to the wrong type
    code would have the mistake copied into the expectation and pass.
    Against AGENTS.md's deciding question, would it still mean
    something if the handler were rewritten to the same
    specification, the answer is no, so it is not the test to write.

    This one needs no mapping.  Every association code carries
    exactly one type -- asserted below from the data, not assumed --
    so the categories partition the codes and no code belongs to two
    of them.  Two single-category answers that share a code are
    therefore two of the application's own answers contradicting each
    other, and at least one of them contains a tie its category does
    not select.  Which one, this test does not say; that it happened
    is what it is for.

    It catches something the version it replaced could not: a
    category wired to the wrong type code shows up as an overlap with
    the category that owns that code -- invisible to a test whose
    expectation was computed from the same wrong clause.

    Not strictly more, though, and the gap is worth naming.  This
    sees a leak only when the code it leaks also reaches some *other*
    category's answer.  A code that arrives in exactly one
    single-category answer -- because the category that owns it has
    no ties on this subject, or because it has no
    ``ASSOC_CODE_TYPE_REL`` row and so belongs to no category at all
    -- overlaps with nothing and passes.  So a green result here
    means no two categories contradicted each other, which is weaker
    than "no category leaked".  Widening the subject list would
    narrow that gap; nothing in the response can close it.
    """
    partitioned = sqlite_conn.execute(
        "SELECT COUNT(*) FROM (SELECT c_assoc_code "
        "FROM ASSOC_CODE_TYPE_REL GROUP BY c_assoc_code "
        "HAVING COUNT(DISTINCT c_assoc_type_code) > 1)").fetchone()[0]
    assert partitioned == 0, (
        f"{partitioned} association code(s) now carry more than one "
        "type, so the categories no longer partition the codes and a "
        "code shared between two answers would be legitimate.  This "
        "test rests on that partition and has to be rewritten.")

    # Which checkboxes can be driven is an input, and the build says
    # it: a category with no branch in makeAssocFilter selects
    # nothing and is reported separately.
    drivable = sorted(_category_selectors(layout))
    assert drivable, "no category has a selector, so none can be driven"

    flags = _category_flags(layout)
    off = {flag: False for flag in flags}

    returned: dict[str, set[int]] = {}
    for flag in drivable:
        answer = _query(app, useKin=False, useNonKin=True,
                        **dict(off, **{flag: True}))
        returned[flag] = {e["linkCode"] for e in _edges(answer)}

    live = [flag for flag, codes in returned.items() if codes]
    assert len(live) > 1, (
        f"only {len(live)} of the {len(drivable)} categories returned "
        f"any tie for person {ego}, so no two answers can be compared "
        "and this test would pass without checking anything.  Pick a "
        "subject with a wider range of ties.")

    overlaps = {}
    for i, first in enumerate(live):
        for second in live[i + 1:]:
            shared = returned[first] & returned[second]
            if shared:
                overlaps[f"{first} & {second}"] = sorted(shared)[:6]

    if overlaps:
        worst = sorted(overlaps.items(), key=lambda kv: -len(kv[1]))[:5]
        raise KnownShippedDefect(
            f"{len(overlaps)} pair(s) of association categories "
            f"returned the same tie for person {ego}, though every "
            "association code carries exactly one type and the "
            "categories therefore select disjoint sets of codes.  "
            f"Worst: {dict(worst)}.  At least one answer in each pair "
            "contains a tie its own category does not select.  The "
            "recruiting loops honour the category filter and the "
            "closure pass does not -- no last-loop FROM joins "
            "ZZ_SCRATCH_ASSOC_FILTER -- so once a person is on the "
            "list every tie they have is drawn, whatever the user "
            f"ticked.  {len(live)} of {len(drivable)} categories "
            "returned anything at all on this subject.")
