"""The handful of inputs this suite fixes instead of discovering.

Almost every input here is chosen from the shipped data at run time
(``discovery.py``), for the reason that module gives: a hand-picked
parameter lands on sparse data about half the time, and a query test
whose result set is empty asserts nothing while looking exactly like a
passing test.

Three inputs are deliberately **not** discovered.  They drive the
browser tests, and a browser test that also has to choose its own input
is two experiments in one: when it fails you cannot tell whether the
page is broken or the input was wrong.  So they are fixed, and the cost
of fixing them is recorded here rather than paid silently -- a data
refresh can retire any of them, and for ``ASSOC_CODE`` in particular
only its *presence* matters to the control it enables, so the
precondition that uses it would go on passing while the claim beside it
had quietly become false.

Hence the table below, and the test that reads it.  Adding a fixed input
means adding a row, and the row is what gets checked.
"""
from __future__ import annotations

from dataclasses import dataclass

#: A person with a small, non-empty network.  The same subject
#: ``test_stateful_forms.py`` uses, for the same reason.
SUBJECT = 1762

#: One entry code that returns a result, for the export accounting.
#: Small on purpose: the first version of that test used a code with
#: 92,572 rows, whose export takes long enough that the page's own
#: three-second success message had come and gone before it was read.
ENTRY_CODE = 36

#: One association code that ``ASSOC_DATA`` has a row for, so that
#: ticking it is the same act a user performs.
ASSOC_CODE = 349


@dataclass(frozen=True)
class FixedInput:
    """One hand-picked input, and where the shipped data must have it."""

    name: str
    value: int
    table: str
    column: str
    #: True when exactly one row must match -- an id in a code or person
    #: table.  False when one or more will do: a data row.
    unique: bool
    why: str


FIXED_INPUTS: tuple[FixedInput, ...] = (
    FixedInput("SUBJECT", SUBJECT, "BIOG_MAIN", "c_personid", True,
               "the person every browser and stateful-form test queries"),
    FixedInput("ENTRY_CODE", ENTRY_CODE, "ENTRY_DATA", "c_entry_code", False,
               "the entry code the export-accounting test queries"),
    FixedInput("ASSOC_CODE", ASSOC_CODE, "ASSOC_CODES", "c_assoc_code", True,
               "the association code the Associations precondition ticks; "
               "the picker could not offer it if the code table lacked it"),
    FixedInput("ASSOC_CODE", ASSOC_CODE, "ASSOC_DATA", "c_assoc_code", False,
               "and it has to name something: a code that exists but "
               "covers no rows is not the input its comment claims"),
)
