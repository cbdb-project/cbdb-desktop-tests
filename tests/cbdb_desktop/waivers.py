"""Outcomes the maintainer has agreed to tolerate, keyed by the program.

Some findings are negotiated away rather than fixed: "yes, that is
wrong; for our readers it does not matter this year".  Left as ordinary
failures they train everyone to read a red run as normal, which is the
one thing this suite cannot afford.  Left as ``xfail`` markers in the
test files they become invisible policy, edited by whoever is closest to
the code and never re-negotiated.

So they live in one optional table outside the suite, and **the key is
the program's own name for the test**:

.. code-block:: toml

    # waivers.toml
    # The key is a test function's own name.  Quote it when it carries
    # a module ("test_exports.py::test_x"), or TOML reads the dot as a
    # path and makes a sub-table of it.
    [test_an_export_produces_a_well_formed_file]
    params    = ["entry:kml", "places:kml"]
    reason    = "Agreed 2026-09-10: the KML preamble is cosmetic for us."
    reason_zh = "2026-09-10 協商：KML 檔頭對我們的使用者只是外觀問題。"
    agreed_by = "maintainer"
    agreed_on = 2026-09-10
    expires   = 2026-12-01

Why the function name and not an identifier of our own: **there is no
identifier of our own that survives a stateless round.**  A defect id is
assigned while writing one report and is gone by the next, so a table
keyed by ``W-001``, or by one of the defect numbers a round assigns,
would point at nothing the second time it was read -- worse, it would
point at whatever the *next* round happened to give that number to.  A test function's name is part of the program, it is
the same on every run, and if it is renamed or deleted the table stops
matching and says so -- which is exactly the failure mode a waiver list
must have.  ``params`` narrows a waiver to particular parametrisations,
using the ids pytest already prints in ``test_x[entry:kml]``, so the
address of a waived outcome is "function name, plus the variables it ran
with" and nothing else.

Two modes, and the default is the one that keeps working:

``tolerate`` (default)
    The test still runs.  A failure becomes a **strict** xfail, so the
    waived thing going away is reported as an unexpected pass and the
    waiver gets retired.  A waiver is not a way to stop measuring.

``skip``
    The test does not run.  For the destructive or the very slow only.
    Note what it costs: a skipped test issues no requests, so it stops
    contributing to the endpoint-coverage record and
    ``test_zz_controls.py`` may fail *because* of the waiver.  That is
    correct -- coverage is measured, not assumed -- and it is why
    ``tolerate`` is the default.

Enabled by pointing ``CBDB_WAIVERS`` at the file.  ``.env.example``
points it at this repo's own ``waivers.toml``, so a fresh checkout
judges the build the way the maintainer does; comment that line out and
nothing is tolerated at all, which is the right way to see what a build
really does.  Unset means no waivers exist and the suite behaves exactly
as if this module were not here.  Set but unreadable, malformed, or
missing a required field is a **hard error**: a waiver table that
silently fails to load would quietly re-expose everything in it, and the
run would look normal.

The table is data, not code, and nothing in it can invent a tolerated
outcome by itself: every entry has to match a test the program actually
collected, and ``tests/test_waivers.py`` fails the run when one does
not.
"""
from __future__ import annotations

import datetime as _dt
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

#: What a waiver may say.  Anything else is a typo and refused, because
#: a misspelled ``reason`` would otherwise waive a test with no reason
#: recorded anywhere.
_FIELDS = frozenset({"params", "mode", "reason", "reason_zh", "raises",
                     "agreed_by", "agreed_on", "expires", "note"})
_REQUIRED = ("reason", "reason_zh", "agreed_by", "agreed_on")
_MODES = ("tolerate", "skip")

#: The only exception a waiver may narrow itself to.  A waiver that
#: tolerated ``Exception`` would swallow an unrelated crash of the same
#: test, which is the mistake AGENTS.md § "How a defect is recorded"
#: exists to prevent.
_RAISES = ("KnownShippedDefect",)


class WaiverError(RuntimeError):
    """The waiver table cannot be used as written."""


@dataclass(frozen=True)
class Waiver:
    """One agreed-tolerated outcome, addressed the way the program is."""

    #: The test function's own name, or ``module.py::function`` when the
    #: same function name exists in more than one module.
    test: str
    reason: str
    reason_zh: str
    agreed_by: str
    agreed_on: _dt.date
    mode: str = "tolerate"
    #: pytest parametrisation ids this applies to; empty means all of
    #: them, including an unparametrised test.
    params: tuple[str, ...] = ()
    raises: str | None = None
    expires: _dt.date | None = None
    note: str = ""

    @property
    def function(self) -> str:
        return self.test.split("::")[-1]

    @property
    def module(self) -> str | None:
        return self.test.split("::")[0] if "::" in self.test else None

    def expired(self, today: _dt.date | None = None) -> bool:
        if self.expires is None:
            return False
        return self.expires < (today or _dt.date.today())

    def describes(self, *, module: str, function: str,
                  param: str | None) -> bool:
        """Does this waiver address that collected test?"""
        if function != self.function:
            return False
        if self.module is not None and module != self.module:
            return False
        if not self.params:
            return True
        return param is not None and param in self.params

    def as_json(self) -> dict:
        """The shape written to ``artifacts/waivers_applied.json``."""
        return {
            "test": self.test,
            "params": list(self.params),
            "mode": self.mode,
            "raises": self.raises,
            "reason": self.reason,
            "reason_zh": self.reason_zh,
            "agreed_by": self.agreed_by,
            "agreed_on": self.agreed_on.isoformat(),
            "expires": self.expires.isoformat() if self.expires else None,
            "note": self.note,
        }


@dataclass
class WaiverTable:
    """The parsed table, plus what it turned out to match this run."""

    path: Path | None = None
    waivers: tuple[Waiver, ...] = ()
    #: waiver.test -> the ids of the tests it was applied to, filled in
    #: during collection.  A waiver that ends up with none is a waiver
    #: addressed at nothing, which ``test_waivers.py`` fails on.
    applied: dict[str, list[str]] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def matching(self, *, module: str, function: str,
                 param: str | None) -> Waiver | None:
        """The waiver for one collected test, or None.

        A more specific waiver wins: one that names parametrisations is
        preferred over a blanket one for the same function, so a table
        can waive two ids of a matrix and still judge the rest.
        """
        found = [w for w in self.waivers
                 if w.describes(module=module, function=function, param=param)]
        if not found:
            return None
        found.sort(key=lambda w: (bool(w.params), w.module is not None),
                   reverse=True)
        return found[0]

    def record(self, waiver: Waiver, test_id: str) -> None:
        self.applied.setdefault(waiver.test, []).append(test_id)

    def unmatched(self) -> list[Waiver]:
        return [w for w in self.waivers if not self.applied.get(w.test)]

    def expired(self, today: _dt.date | None = None) -> list[Waiver]:
        return [w for w in self.waivers if w.expired(today)]


def parse(text: str, *, path: Path | None = None) -> tuple[Waiver, ...]:
    """Parse a waiver table, refusing anything it cannot fully honour.

    Every failure here is a hard one.  The alternative -- skipping an
    entry we do not understand -- silently un-waives it, and the run
    then fails for a reason nobody connects to this file.
    """
    where = f" in {path}" if path else ""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise WaiverError(
            f"the waiver table is not valid TOML{where}: {exc}.  A key that "
            "carries a module has to be quoted -- "
            '["test_exports.py::test_something"] -- because a bare TOML key '
            "may hold neither a dot nor a colon.") from exc

    out: list[Waiver] = []
    for key, body in raw.items():
        at = f"[{key}]{where}"
        if not isinstance(body, dict):
            raise WaiverError(
                f"{at} must be a table of fields, not {type(body).__name__}.  "
                "The key is the test function's own name: "
                "[test_an_export_produces_a_well_formed_file]")
        if key.split("::")[-1].startswith("test_") is False:
            raise WaiverError(
                f"{at} is not the name of a test.  A waiver is keyed by the "
                "program's own name for what it waives -- the test "
                "function, optionally as module.py::function -- because no "
                "id of our own survives a stateless round.")
        nested = sorted(k for k, v in body.items() if isinstance(v, dict))
        if nested:
            raise WaiverError(
                f"{at} contains sub-tables {nested}.  A key holding a dot or "
                "a colon has to be quoted in TOML, or it is read as a path: "
                'write ["test_exports.py::test_something"], with the quotes.')
        unknown = sorted(set(body) - _FIELDS)
        if unknown:
            raise WaiverError(
                f"{at} has fields this suite does not know: {unknown}.  "
                f"Allowed: {sorted(_FIELDS)}")
        missing = [f for f in _REQUIRED if not body.get(f)]
        if missing:
            raise WaiverError(
                f"{at} is missing {missing}.  A waiver has to say what was "
                "agreed, in both languages, and who agreed to it -- the "
                "report prints all of it.")

        mode = body.get("mode", "tolerate")
        if mode not in _MODES:
            raise WaiverError(f"{at} has mode {mode!r}, not one of {list(_MODES)}")

        raises = body.get("raises")
        if raises is not None and raises not in _RAISES:
            raise WaiverError(
                f"{at} narrows to {raises!r}; only {list(_RAISES)} may be "
                "named.  A waiver that tolerated any exception would "
                "swallow an unrelated failure of the same test.")

        params = body.get("params", ())
        if isinstance(params, str) or not all(
                isinstance(p, str) for p in params):
            raise WaiverError(
                f"{at} params must be a list of pytest parametrisation ids, "
                "as printed in test_x[entry:kml]")

        for name in ("agreed_on", "expires"):
            value = body.get(name)
            if value is not None and not isinstance(value, _dt.date):
                raise WaiverError(
                    f"{at} {name} must be a TOML date (2026-09-10), "
                    f"got {value!r}")

        out.append(Waiver(
            test=key,
            reason=str(body["reason"]).strip(),
            reason_zh=str(body["reason_zh"]).strip(),
            agreed_by=str(body["agreed_by"]).strip(),
            agreed_on=body["agreed_on"],
            mode=mode,
            params=tuple(params),
            raises=raises,
            expires=body.get("expires"),
            note=str(body.get("note", "")).strip(),
        ))

    return tuple(out)


def load(path: Path | None) -> WaiverTable:
    """Read the configured table, or return an empty one.

    ``None`` is the default and means "no waivers".  A path that is set
    and cannot be read is an error, never an empty table: the whole
    point of the file is that what it holds is visible.
    """
    if path is None:
        return WaiverTable()
    if not path.is_file():
        raise WaiverError(
            f"CBDB_WAIVERS points at {path}, which does not exist.  Unset it "
            "to run with no waivers, or create the table.")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise WaiverError(f"cannot read the waiver table {path}: {exc}") from exc
    return WaiverTable(path=path, waivers=parse(text, path=path))
