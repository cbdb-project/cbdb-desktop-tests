"""The Group Data form's five section switches.

Group Data takes a list of people and answers with what is recorded
about them, under five independent switches: *Status*, *Office*,
*Entry*, *Text* and *Address*.  Each has its own list in the
response, so which list a record arrives in *is* its kind and a
switch can be judged without knowing anything about the data.

Two things this file deliberately does not test, both of which its
first draft did.

The five counts are not an oracle.  ``handleQuery`` assigns each one
from its own slice length in the same statement
(``resp.StatusCount = len(resp.StatusRecords)``), so ``count ==
len(records)`` is ``len(x) == len(x)`` round-tripped through JSON.
AGENTS.md names that shape as the first of its three worked examples
of a test that cannot fail, and ``test_stateful_forms.py`` had
already written the same conclusion down in prose.  Five such tests
were written here anyway and are gone.

And the sections' independence -- that two switches together give
what each gives alone -- is a property of a rewrite but not of this
build, where the five sub-queries are five independent SELECTs with
nothing shared between them.  It cannot fail here, so it is not
here.

What is left is the part that can fail: a section answered when
nobody asked for it, and the all-off case.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.subjects import SUBJECT

# Marked per test rather than for the module.  The sweep gate below
# reads only the shipped Go, and a module-wide marker meant that
# ``run_tests.ps1 -Fast`` deselected it along with the tests it
# guards -- so the check that stops the sweep reporting success over
# a subset was the first thing dropped whenever the app was not
# running.  A gate you can skip is the failure mode AGENTS.md's fifth
# coverage property is about.

#: ``switch in the request`` -> ``the list it fills in the response``.
#: The names travel together so they cannot drift apart.  ``queryAddr``
#: fills ``placeRecords``, which is the one pair that is not the same
#: word twice.
_SECTIONS = {
    "queryStatus": "statusRecords",
    "queryOffice": "officeRecords",
    "queryEntry": "entryRecords",
    "queryText": "textRecords",
    "queryAddr": "placeRecords",
}

#: Two genuinely different people, both with records in all five
#: sections.  ``SUBJECT`` is 1762, whose Entry section is a single
#: row -- thin enough that a data refresh removing it would turn the
#: liveness guards below into failures pointing at the build.  7055
#: has 5 / 30 / 4 / 116 / 54 across the five, so the pair does not
#: rest on one row anywhere.
#:
#: The first draft wrote ``[SUBJECT, 1762]`` and a comment about
#: needing a second person.  They are the same person.
_SUBJECTS = [SUBJECT, 7055]

#: The five count fields, named only so that the all-off test can
#: check the response is the declared shape.  Nothing asserts a count
#: against its list: the handler assigns each from that list's own
#: length, so the comparison cannot fail -- AGENTS.md's first worked
#: example of exactly that.
_COUNTS = ("statusCount", "officeCount", "entryCount", "textCount",
           "placeCount")


def _switches_the_build_declares(layout) -> set[str]:
    """The ``query*`` flags ``GroupDataQueryRequest`` declares.

    Read from the struct for the reason § *Coverage is the program's
    job* gives: a sixth switch would otherwise sit undriven while
    this file reported that every switch behaves.
    """
    text = (layout.code_dir / "groupdata_form_backend.go").read_text(
        encoding="utf-8", errors="replace")
    body = re.search(r"^type\s+GroupDataQueryRequest\s+struct\s*\{(.*?)^\}",
                     text, re.DOTALL | re.MULTILINE)
    assert body, (
        "groupdata_form_backend.go no longer declares "
        "GroupDataQueryRequest, so the switches cannot be read from it")
    return set(re.findall(r'`json:"(query[A-Za-z]+)"`', body.group(1)))


def _query(app: CbdbApp, **switches) -> dict:
    body = {"personIds": _SUBJECTS}
    body.update({name: False for name in _SECTIONS})
    body.update(switches)
    answer = app.json("POST", "/api/groupdata/query", json=body)
    assert isinstance(answer, dict), answer
    return answer


def test_the_sweep_drives_every_switch_the_build_declares(layout):
    """The denominator, before anything is swept.

    Without this the tests below report that every switch behaves
    over whatever subset this file happens to name -- the failure
    that let the Use XY switches and the Networks categories go
    unsent for the life of the suite.
    """
    declared = _switches_the_build_declares(layout)
    assert declared == set(_SECTIONS), (
        f"GroupDataQueryRequest declares {sorted(declared)} and this "
        f"file drives {sorted(_SECTIONS)}.  Declared and never sent: "
        f"{sorted(declared - set(_SECTIONS))}.  Sent and no longer "
        f"declared: {sorted(set(_SECTIONS) - declared)}.")


@pytest.mark.app
@pytest.mark.parametrize("switch", sorted(_SECTIONS))
def test_a_section_is_empty_unless_its_switch_is_on(
        app: CbdbApp, switch: str):
    """Ask for one section and the other four must stay empty.

    No oracle: which list a record arrives in is what makes it a
    Status record or an Office record, so a record in a list nobody
    asked for answers for itself.

    Driven one switch at a time rather than by dropping one from a
    full set, which is what ``test_stateful_forms.py`` does.  A
    handler that reads one flag for all five sections passes the
    drop-one form on four of five cases and fails this one on four
    of five.
    """
    answer = _query(app, **{switch: True})
    mine = _SECTIONS[switch]

    intruders = {
        records: len(answer.get(records) or [])
        for other, records in _SECTIONS.items()
        if other != switch and (answer.get(records) or [])
    }
    assert not intruders, (
        f"asking for {switch} alone filled {sorted(intruders)} as "
        f"well: {intruders}.  A section the user did not ask for may "
        f"not be answered; the people asked about were {_SUBJECTS}.")

    # Liveness, so the four assertions above cannot pass because the
    # form answered nothing at all.  Both subjects were chosen to
    # have records in every section, so an empty answer here is the
    # build or the data moving, not a thin subject.
    assert answer.get(mine), (
        f"asking for {switch} returned no {mine} for either of "
        f"{_SUBJECTS}, so the emptiness of the other four proves "
        "nothing.  Both were chosen because they have records in all "
        "five sections; check that before reading this as a defect.")


@pytest.mark.app
def test_asking_for_nothing_answers_with_nothing(app: CbdbApp):
    """Every switch off: there is no sixth thing to return.

    The third form to be asked this question, and the reason to keep
    asking: the Places page answers an empty category selection with
    the Biography rows, and the Networks page answers an empty
    category selection with every association there is.  Both
    substitute a default for "the user chose nothing", and both do
    it silently.

    Group Data does not, and that is worth a test rather than a
    note.  It is what bounds those two findings to two forms, and a
    build that grew the same fallback here would otherwise look like
    a third instance nobody had checked for.
    """
    answer = _query(app)

    # The response has to be the response, not an error envelope that
    # happens to carry no record lists.  Without this, a handler that
    # answered ``{"error": "..."}`` with HTTP 200 would read as
    # "correctly returned nothing".
    missing = [key for key in
               list(_SECTIONS.values()) + sorted(_COUNTS)
               if key not in answer]
    assert not missing, (
        f"the all-off answer is missing {missing} from the ten keys "
        f"GroupDataQueryResponse declares; it carried {sorted(answer)}. "
        "An answer that is not the declared shape says nothing about "
        "whether the sections were suppressed or the request failed.")

    filled = {
        records: len(answer.get(records) or [])
        for records in _SECTIONS.values()
        if answer.get(records)
    }
    if filled:
        raise KnownShippedDefect(
            f"with all {len(_SECTIONS)} sections unticked the form "
            f"answered with {filled}, for people {_SUBJECTS}.  Every "
            "kind of record the form offers was excluded, so there is "
            "nothing left for it to answer with; returning something "
            "means the selection is being substituted rather than "
            "applied, as it is on the Places and Networks pages.")

    # And the answer is a real one, not an error envelope that
    # happens to carry no lists: with one switch on, rows come back.
    live = _query(app, **{sorted(_SECTIONS)[0]: True})
    assert live.get(_SECTIONS[sorted(_SECTIONS)[0]]), (
        "the endpoint returned nothing with a section ticked either, "
        "so the empty answer above says nothing about the all-off "
        f"case -- it is what this endpoint returns for {_SUBJECTS} "
        "whatever is asked.")
