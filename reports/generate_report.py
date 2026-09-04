#!/usr/bin/env python
"""Turn one test run into the issues report.

Two inputs, and neither of them is written by hand:

* ``tests/cbdb_desktop/defects.py`` -- the registry of what has been
  found, which the tests themselves quote in their xfail reasons; and
* the JSON report of an actual run, which says whether each of those
  tests still demonstrates its defect.

So the report cannot claim a defect the tests do not still show, nor go
stale about one that has been fixed: a fixed defect turns its strict
xfail into an unexpected pass, which shows up here as APPARENTLY FIXED.

    python reports/generate_report.py [--json reports/pytest_report.json]

Writes reports/CBDB_Desktop_Issues.md and prints its path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from cbdb_desktop.defects import DEFECTS, Defect  # noqa: E402

DEFAULT_JSON = ROOT / "reports" / "pytest_report.json"
OUTPUT = ROOT / "reports" / "CBDB_Desktop_Issues.md"

_STATUS_ORDER = {"CONFIRMED": 0, "INCONCLUSIVE": 1,
                 "APPARENTLY FIXED": 2, "NOT EXERCISED": 3}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def load_run(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"no test run to report on: {path} does not exist.\n"
            "Run:  python -m pytest tests --json-report "
            f"--json-report-file={path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def outcomes_for(run: dict, defect: Defect) -> dict[str, list[str]]:
    """Group the run's outcomes for the tests that demonstrate a defect.

    Tests are named file-qualified ("test_lookups.py::test_x").  Matching
    on the bare function name would let a same-named test in another file
    confirm -- or silently "fix" -- the wrong defect.
    """
    grouped: dict[str, list[str]] = {}
    for test in run["tests"]:
        node = test["nodeid"]
        stem = node.split("[", 1)[0]
        if any(stem.endswith(name) for name in defect.tests):
            grouped.setdefault(test["outcome"], []).append(node)
    return grouped


def status_of(grouped: dict[str, list[str]]) -> str:
    if not grouped:
        return "NOT EXERCISED"
    if grouped.get("xfailed"):
        # Any test still demonstrating the defect means it is still there.
        return "CONFIRMED"
    if grouped.get("failed") or grouped.get("error"):
        # The test ran and neither confirmed the defect nor passed: it
        # broke on something else.  Saying "not exercised" would be a
        # lie, and "apparently fixed" would be a worse one.
        return "INCONCLUSIVE"
    if grouped.get("xpassed") or grouped.get("passed"):
        return "APPARENTLY FIXED"
    return "NOT EXERCISED"


def _environment(run: dict) -> list[str]:
    env = run.get("environment", {})
    lines = []
    for label, key in (("Python", "Python"), ("Platform", "Platform")):
        if env.get(key):
            lines.append(f"- {label}: {env[key]}")
    return lines


def render(run: dict, zip_name: str | None) -> str:
    summary = run["summary"]
    created = datetime.fromtimestamp(run["created"], tz=timezone.utc)

    out: list[str] = []
    out.append("# CBDB-Desktop — issues found by the test suite")
    out.append("")
    out.append(f"Generated {created:%Y-%m-%d %H:%M UTC} from a run of "
               f"{summary.get('total', 0)} tests "
               f"({run['duration']:.0f}s).")
    out.append("")
    if zip_name:
        out.append(f"Build under test: `{zip_name}`")
        out.append("")
    out.append("| outcome | count |")
    out.append("|---|---|")
    for key in ("passed", "failed", "error", "xfailed", "xpassed", "skipped"):
        if summary.get(key):
            out.append(f"| {key} | {summary[key]} |")
    out.append("")
    out.append("Every issue below was found by driving the shipped "
               "`Bin/cbdb.exe` over HTTP against the shipped database, and "
               "each one is demonstrated by a named test that fails (as a "
               "strict xfail) for as long as the defect is present.")
    out.append("")

    ranked = sorted(
        DEFECTS.values(),
        key=lambda d: (_STATUS_ORDER[status_of(outcomes_for(run, d))],
                       _SEVERITY_ORDER.get(d.severity, 9), d.key))

    out.append("## Summary")
    out.append("")
    out.append("| id | severity | status | issue |")
    out.append("|---|---|---|---|")
    for defect in ranked:
        status = status_of(outcomes_for(run, defect))
        out.append(f"| {defect.key} | {defect.severity} | {status} | "
                   f"{defect.title} |")
    out.append("")

    for defect in ranked:
        grouped = outcomes_for(run, defect)
        status = status_of(grouped)

        out.append(f"## {defect.key} — {defect.title}")
        out.append("")
        out.append(f"**Severity:** {defect.severity} &nbsp;&nbsp; "
                   f"**Area:** {defect.area} &nbsp;&nbsp; "
                   f"**Status in this run:** {status}")
        out.append("")
        if status == "APPARENTLY FIXED":
            out.append("> The tests that demonstrated this no longer fail. "
                       "Confirm the fix, then remove the xfail markers and "
                       "this entry.")
            out.append("")
        elif status == "INCONCLUSIVE":
            out.append("> The tests for this issue failed for some other "
                       "reason, so this run neither confirms it nor clears "
                       "it.  Fix the failure first.")
            out.append("")
        elif status == "NOT EXERCISED":
            out.append("> No test in this run exercised this issue, so the "
                       "run says nothing about whether it is still present.")
            out.append("")

        for heading, text in (("What is wrong", defect.summary),
                              ("Evidence", defect.evidence),
                              ("Impact", defect.impact),
                              ("Suggested fix", defect.fix)):
            out.append(f"**{heading}.** {text}")
            out.append("")

        if defect.source:
            out.append("**In the build:** "
                       + ", ".join(f"`{ref}`" for ref in defect.source))
            out.append("")

        out.append("**Demonstrated by:**")
        out.append("")
        for outcome in sorted(grouped):
            nodes = grouped[outcome]
            shown = ", ".join(f"`{n.split('::', 1)[-1]}`" for n in nodes[:4])
            more = f" (+{len(nodes) - 4} more)" if len(nodes) > 4 else ""
            out.append(f"- {len(nodes)} {outcome}: {shown}{more}")
        if not grouped:
            out.append(f"- (none ran; expected {', '.join(defect.tests)})")
        out.append("")

    env_lines = _environment(run)
    if env_lines:
        out.append("## Run environment")
        out.append("")
        out.extend(env_lines)
        out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON,
                        help="pytest JSON report to read (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    run = load_run(args.json)

    zip_name = None
    try:
        from cbdb_desktop.config import load_config

        configured = load_config().zip_path
        zip_name = configured.name if configured else None
    except Exception:  # pragma: no cover - the report must not need a .env
        pass

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the target and rename: a crash halfway through must
    # not leave a truncated report where the previous good one was.
    scratch = args.out.with_name(args.out.name + ".new")
    scratch.write_text(render(run, zip_name), encoding="utf-8")
    os.replace(scratch, args.out)
    print(args.out)

    confirmed = sum(1 for d in DEFECTS.values()
                    if status_of(outcomes_for(run, d)) == "CONFIRMED")
    # stdout, not stderr: a caller that treats any stderr output as a
    # failure (PowerShell does) would otherwise report a successful run
    # as an error.
    print(f"{confirmed} of {len(DEFECTS)} recorded issues confirmed by this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
