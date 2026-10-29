"""Is the Go source in the archive the source of the binary in it?

The suite reads ``Code/*.go`` as data -- ``routes.py`` builds the route
inventory from it, ``test_scratch_tables.py`` the table-ownership map,
every defect cites ``file:line`` in it -- on the premise that it is the
source of the ``cbdb.exe`` beside it.  When it is not, every one of those
readings describes some other program, and nothing else in the suite
would say so: they would all agree with each other, about the wrong
build.  So the premise is checked, once, here, with no application and
no query (AGENTS.md operating principle 8): the names of the functions
the binary contains against the functions the source declares.  See
``cbdb_desktop/gobinary.py`` for why names, what is normalised, and what
a name scan cannot see.

Checked against two builds before it was trusted: on 20260925 it finds
no difference at all; on 20261021 it finds the four functions the
developers' revision notes describe adding (QBE-3's display SQL, PLC-4's
index addresses, ASP-6's distance) and the Rerun handler NET-4 says was
removed -- in the binary, not in the source shipped beside it.
"""
from __future__ import annotations

import pytest

from cbdb_desktop import gobinary
from cbdb_desktop.staging import AppLayout

def test_the_shipped_source_is_the_source_of_the_shipped_binary(
        layout: AppLayout):
    """Every function the binary has, the source declares, and back.

    A failure here is a packaging problem (origin ``release``), not a
    code defect: the program may be fine, but the source published as
    its source is not, and every test that reads that source as data is
    reading another build.
    """
    result = gobinary.compare_files(layout.exe, layout.go_sources())

    # The instrument first: a scan that read nothing would "match".
    declared = result.compared + len(result.only_in_source) \
        + len(result.dropped_as_unused)
    assert result.compared >= 0.9 * declared, (
        f"only {result.compared} of the {declared} functions Code/*.go "
        "declares were found by name in cbdb.exe -- the binary's "
        "function-name table is no longer being read (a new Go version's "
        "layout?), so this comparison cannot judge the build")

    assert not result.only_in_binary and not result.only_in_source, (
        "the Go source shipped in Code/ is not the source of cbdb.exe: "
        f"functions only in the binary {result.only_in_binary}; functions "
        f"the source declares and uses that the binary lacks "
        f"{result.only_in_source}.  (Ignored as legitimately absent, "
        f"because nothing calls them: {result.dropped_as_unused}.)")


# ---------------------------------------------------------------------------
# the instrument, against answers written down
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("symbol,expected", [
    ("main.fmtOptFloat", "fmtOptFloat"),
    ("main.(*PlaceHandler).fillIndexAddresses", "PlaceHandler.fillIndexAddresses"),
    ("main.(*PlaceHandler).handleQuery-fm", "PlaceHandler.handleQuery"),
    ("main.(*PlaceHandler).handleQuery.func2", "PlaceHandler.handleQuery"),
    ("main.(*PlaceHandler).handleQuery.func2.1", "PlaceHandler.handleQuery"),
    ("main.(*Exec).run.deferwrap1", "Exec.run"),
    ("main.Record.String", "Record.String"),
    ("main.ptr[go.shape.int]", "ptr"),
    ("main.init", None),
    ("main.init.0", None),
    ("main.inittasks", None),
    ("main.main", None),
    ("main.main.func1", None),
    ("main.glob..func1", None),
    ("type:.eq.main.Record", None),
    ("main..eq.Record", None),
])
def test_a_binary_symbol_is_read_as_the_name_it_was_declared_with(symbol,
                                                                   expected):
    assert gobinary.normalise(symbol) == expected


_FIXTURE_SOURCE = {
    "a.go": """package main

// helper is mentioned here, in a comment, which is not a use.
type Record struct{ ID int }
type (
    alias = int
    other struct{}
)
var registryMu sync.Mutex
const (
    limit = 10
)

func (r *Record) Used() int { return helper(r.ID) }
func (r Record) Unused() {}
func helper(n int) int { return n }
func orphan() {}
func main() { _ = (&Record{}).Used() }
""",
}


def test_the_source_reader_tells_functions_from_everything_else():
    decl = gobinary.source_declarations(_FIXTURE_SOURCE)
    assert decl.functions == {"Record.Used": "a.go", "Record.Unused": "a.go",
                              "helper": "a.go", "orphan": "a.go"}
    assert decl.others == {"Record", "alias", "other", "registryMu", "limit"}
    # helper is called; Used is called; orphan and Unused are named only
    # on their own func line (and helper's comment mention does not count).
    assert decl.referenced == {"helper", "Record.Used"}


def test_the_comparison_reports_both_directions_and_spares_dead_code():
    binary = (b"\x00main.helper\x00main.(*Record).Used\x00main.registryMu\x00"
              b"main.added\x00main.main\x00main.inittasks\x00")
    result = gobinary.compare(binary, _FIXTURE_SOURCE)
    assert result.only_in_binary == ["added"]          # registryMu is a var
    assert result.only_in_source == {}
    assert result.dropped_as_unused == ["Record.Unused", "orphan"]
    assert result.compared == 2

    # Remove a called function from the binary: that is a finding.
    stale = binary.replace(b"main.helper\x00", b"")
    assert gobinary.compare(stale, _FIXTURE_SOURCE).only_in_source == {
        "helper": "a.go"}
