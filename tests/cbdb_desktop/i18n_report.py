"""The translation check, written out for the people who fix translations.

``i18n`` finds; this module records.  One function builds the whole
result as plain data, and two writers turn it into a Markdown page (the
committed deliverable, ``reports/CBDB_Desktop_Translations.md``) and a
workbook (``.xlsx``, the same rows, for whoever works through them in
Excel beside ``FormLabels.xlsx``).

**Same input, same bytes.**  The maintainer's requirement for this check
is that repeating it gives the same answer, so nothing here records when
it ran: no timestamps in the Markdown, and the workbook's own creation
and modification times are fixed.  What *is* recorded is everything the
answer depends on -- the archive, the glossary's SHA-256 and the OpenCC
version -- so two reports that differ say why.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from . import i18n

#: The file the browser test leaves for the report: what the pages
#: showed, which only a rendered page can say.  The report includes it
#: when it was measured on the same build, and says so when it was not.
RENDERED_ARTIFACT = "translation_rendered.json"

_FIXED_TIME = datetime(2000, 1, 1)


def _opencc_version() -> str:
    from importlib import metadata
    for name in ("opencc", "OpenCC", "opencc-python-reimplemented"):
        try:
            return f"{name} {metadata.version(name)}"
        except metadata.PackageNotFoundError:
            continue
    return "unknown"


def checker_fingerprint(glossary_path: Path = i18n.GLOSSARY_PATH) -> str:
    """What the answer depends on besides the build: rules, reference, OpenCC.

    Recorded with the browser test's findings, so a report never merges
    on-screen results measured by an older version of the rules or
    against another glossary.
    """
    digest = hashlib.sha256()
    digest.update(Path(i18n.__file__).read_bytes())
    digest.update(glossary_path.read_bytes())
    for table in (i18n.REGIONAL_TERMS_PATH, i18n.ACCEPTED_CHARACTERS_PATH):
        if table.is_file():
            digest.update(table.read_bytes())
    digest.update(_opencc_version().encode())
    return digest.hexdigest()


def build_name(config, layout) -> str:
    """The build's name for reports: the archive's stem, or with
    ``CBDB_APP_DIR`` and no archive, the tree's own directory name."""
    from .staging import archive_stem
    if config.zip_path is not None:
        return archive_stem(config.zip_path)
    return layout.root.name


def build(pages: dict[str, Path], build_name: str,
          glossary_path: Path = i18n.GLOSSARY_PATH,
          rendered: dict | None = None) -> dict:
    """Everything the check found, as data that serialises to JSON.

    ``rendered`` is what ``load_rendered`` returned: the browser test's
    findings plus whether they cover every translated page.
    """
    rows = i18n.load_glossary(glossary_path)
    glossary = i18n.Glossary.build(rows)
    labels, findings = i18n.check_pages(pages, glossary)

    coverage = []
    unused = []
    for page in sorted(labels):
        page_labels = [label for label in labels[page] if label.used]
        unused += [label.ref for label in labels[page] if not label.used]
        judged = sum(
            1 for label in page_labels
            if label.english and (glossary.for_english(label.english, page)
                                  or any(glossary.for_chinese(t, page)
                                         for t in (label.traditional,
                                                   label.simplified)
                                         if t and i18n.has_cjk(t))))
        coverage.append({"page": page, "labels": len(page_labels),
                         "glossary_terms": len(glossary.by_page.get(page, ())),
                         "judged_against_glossary": judged})

    unreadable = []
    for page, path in sorted(pages.items()):
        unreadable += i18n.unreadable_tables(
            page, path.read_text(encoding="utf-8", errors="replace"))

    on_screen = list((rendered or {}).get("findings", []))
    all_findings = [f.as_dict() for f in findings] + on_screen
    all_findings.sort(key=lambda f: (i18n.KINDS.index(f["kind"]), f["page"],
                                     f["line"], f["ref"], f["detail"]))
    return {
        "build": build_name,
        "glossary": {"file": glossary_path.name,
                     "sha256": hashlib.sha256(
                         glossary_path.read_bytes()).hexdigest(),
                     "rows": len(rows)},
        "converter": _opencc_version(),
        "rendered": None if rendered is None else {
            "status": rendered["status"],
            "measured": rendered["measured"],
            "missing": rendered["missing"]},
        "coverage": coverage,
        "unused": unused,
        "unreadable": unreadable,
        "counts": {kind: sum(1 for f in all_findings if f["kind"] == kind)
                   for kind in i18n.KINDS},
        "findings": all_findings,
        "glossary_problems": i18n.glossary_problems(rows),
    }


def load_rendered(artifacts_dir: Path, stage: str,
                  expected_pages: list[str]) -> dict | None:
    """The browser test's findings for this exact build and checker.

    ``None`` when there are none, or when they were measured on another
    staged tree (another archive, even one with the same name) or by
    other rules or another glossary -- stale results are not merged.
    Otherwise the findings plus ``status``: ``complete`` when every
    translated page was measured, ``partial`` when a filtered run or an
    erroring page left some out (listed in ``missing``).
    """
    path = artifacts_dir / RENDERED_ARTIFACT
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("stage") != stage
            or data.get("checker") != checker_fingerprint()):
        return None
    measured = sorted(data.get("measured", []))
    missing = sorted(set(expected_pages) - set(measured))
    return {"status": "partial" if missing else "complete",
            "measured": measured, "missing": missing,
            "findings": data.get("findings", [])}


def write_rendered(artifacts_dir: Path, stage: str, measured: list[str],
                   findings: list[i18n.Finding]) -> Path:
    path = artifacts_dir / RENDERED_ARTIFACT
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"stage": stage, "checker": checker_fingerprint(),
            "measured": sorted(set(measured)),
            "findings": [f.as_dict() for f in
                         sorted(findings, key=i18n.Finding.sort_key)]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return path


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return (" ".join(text.split()).replace("|", "\\|")
            .replace("<", "&lt;").replace(">", "&gt;"))


def render_markdown(data: dict) -> str:
    out: list[str] = []
    add = out.append
    add(f"# CBDB-Desktop translation check / 譯名檢查 -- `{data['build']}`")
    add("")
    add("Generated by `python check_translations.py` from the shipped page "
        "templates and the CBDB label glossary "
        f"(`docs/labels/{data['glossary']['file']}`, {data['glossary']['rows']} "
        f"rows, SHA-256 `{data['glossary']['sha256'][:12]}`), with "
        f"{data['converter']} for script conversion.  The rules are in "
        "`tests/cbdb_desktop/i18n.py`; the same inputs always give this "
        "same page.")
    add("")
    rendered = data["rendered"]
    if rendered is None:
        add("**Not included:** what the pages show when a language is "
            "chosen (`rendered_script`).  That needs the browser test "
            "(`tests/test_translations.py`) to have run on this build with "
            "these rules; run the suite, then this again.")
        add("")
    elif rendered["status"] == "partial":
        add(f"**Partly included:** what the pages show was measured on "
            f"{len(rendered['measured'])} of "
            f"{len(rendered['measured']) + len(rendered['missing'])} "
            f"translated pages; not measured: "
            f"{', '.join(rendered['missing'])}.  A filtered run, or a page "
            "whose browser test errored, leaves this.")
        add("")
    if data["unreadable"]:
        add("**Unreadable translation tables** (not checked at all): "
            + "; ".join(_cell(u) for u in data["unreadable"]))
        add("")
    add("## Summary / 摘要")
    add("")
    add("| kind | what it means | count |")
    add("|---|---|---|")
    for kind in i18n.KINDS:
        add(f"| `{kind}` | {i18n.KIND_TITLES[kind]} | {data['counts'][kind]} |")
    add("")
    add("### What the glossary could judge, per page")
    add("")
    add("A label is judged against the glossary when its English, or its "
        "Chinese, is a term the glossary defines for that page's Access "
        "form.  The rest are checked by the rules that need no glossary "
        "(all three languages present, script, 繁/简 agreement, cross-page "
        "consistency).")
    add("")
    add("| page | labels | glossary terms for its forms | judged against the glossary |")
    add("|---|---|---|---|")
    for row in data["coverage"]:
        add(f"| {row['page']} | {row['labels']} | {row['glossary_terms']} | "
            f"{row['judged_against_glossary']} |")
    add("")
    for kind in i18n.KINDS:
        rows = [f for f in data["findings"] if f["kind"] == kind]
        if not rows:
            continue
        add(f"## `{kind}` -- {i18n.KIND_TITLES[kind]} ({len(rows)})")
        add("")
        if kind == "inconsistent":
            add("| English | how the pages translate it |")
            add("|---|---|")
            for f in rows:
                add(f"| {_cell(f['english'])} | {_cell(f['detail'])} |")
        else:
            add("| page | label (line) | English | 繁 | 简 | finding | glossary rows |")
            add("|---|---|---|---|---|---|---|")
            for f in rows:
                where = f["ref"].split(":", 1)[-1]
                add(f"| {f['page']} | `{_cell(where)}` ({f['line']}) | "
                    f"{_cell(f['english'])} | {_cell(f['traditional'])} | "
                    f"{_cell(f['simplified'])} | {_cell(f['detail'])} | "
                    f"{_cell('; '.join(f['glossary']))} |")
        add("")
    if data["unused"]:
        add(f"## Labels nothing on the page reads ({len(data['unused'])})")
        add("")
        add("Defined in a translation table and never shown, so not "
            "judged.  Listed because a label that *is* shown through a key "
            "built at run time would land here too.")
        add("")
        add(", ".join(f"`{_cell(ref)}`" for ref in data["unused"]))
        add("")
    problems = data["glossary_problems"]
    add(f"## Problems in the glossary itself / 對照表本身的問題 ({len(problems)})")
    add("")
    add("Not findings against the build.  The comparisons above work on "
        "wording after converting both sides to one script, so none of "
        "these can make a page look wrong; they are listed so the glossary "
        "can be corrected.  Row references are `c_form#c_label_id`.")
    add("")
    for problem in problems:
        add(f"- {_cell(problem)}")
    add("")
    return "\n".join(out)


def write_xlsx(data: dict, path: Path) -> None:
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    wb.properties.created = _FIXED_TIME
    wb.properties.modified = _FIXED_TIME
    wb.properties.creator = "check_translations.py"

    summary = wb.active
    summary.title = "Summary"
    summary.append(["build", data["build"]])
    summary.append(["glossary", data["glossary"]["file"],
                    data["glossary"]["sha256"]])
    summary.append(["converter", data["converter"]])
    summary.append(["on-screen check",
                    "not included" if data["rendered"] is None
                    else data["rendered"]["status"]])
    summary.append([])
    summary.append(["kind", "what it means", "count"])
    for kind in i18n.KINDS:
        summary.append([kind, i18n.KIND_TITLES[kind], data["counts"][kind]])

    sheet = wb.create_sheet("Findings")
    header = ["kind", "page", "label", "line", "English", "繁", "简",
              "finding", "glossary rows"]
    sheet.append(header)
    for f in data["findings"]:
        sheet.append([f["kind"], f["page"], f["ref"], f["line"],
                      f["english"], f["traditional"], f["simplified"],
                      f["detail"], "\n".join(f["glossary"])])

    problems = wb.create_sheet("Glossary problems")
    problems.append(["problem"])
    for problem in data["glossary_problems"]:
        problems.append([problem])

    for ws in wb.worksheets:
        for cell in ws[1 if ws.title != "Summary" else 6]:
            cell.font = Font(bold=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    _normalise_xlsx(path)


def _normalise_xlsx(path: Path) -> None:
    """Make the saved workbook depend only on its content.

    openpyxl stamps the save time into ``docProps/core.xml`` whatever the
    properties say, and every zip entry carries the time it was written.
    Both are rewritten to one fixed instant, so two runs over the same
    findings produce the same bytes.
    """
    import re
    import zipfile

    stamp = _FIXED_TIME.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as src:
        entries = [(info, src.read(info.filename)) for info in src.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info, data in entries:
            if info.filename == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</)",
                    rb"\g<1>" + stamp.encode() + rb"\g<2>", data)
            fixed = zipfile.ZipInfo(info.filename,
                                    date_time=_FIXED_TIME.timetuple()[:6])
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            dst.writestr(fixed, data)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from . import controls
    from .config import REPO_ROOT, load_config
    from .staging import stage

    ap = argparse.ArgumentParser(
        prog="python check_translations.py",
        description="Check the shipped pages' English, 繁體 and 简体 labels "
                    "against docs/labels/FormLabels.xlsx.")
    ap.add_argument("--out", default=str(REPO_ROOT / "reports"),
                    help="directory for CBDB_Desktop_Translations.md/.xlsx")
    args = ap.parse_args(argv)

    config = load_config()
    layout = stage(config, quiet=True)
    name = build_name(config, layout)
    pages = controls.pages(layout)
    translated = sorted(
        page for page, path in pages.items()
        if i18n.has_language_switch(path.read_text(encoding="utf-8",
                                                   errors="replace")))
    rendered = load_rendered(REPO_ROOT / "artifacts", layout.root.name,
                             translated)
    data = build(pages, name, rendered=rendered)

    out = Path(args.out)
    md = out / "CBDB_Desktop_Translations.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_bytes(render_markdown(data).encode("utf-8"))
    write_xlsx(data, out / "CBDB_Desktop_Translations.xlsx")
    counts = ", ".join(f"{k} {v}" for k, v in data["counts"].items() if v)
    print(f"{md}  ({counts or 'no findings'}; "
          f"{len(data['glossary_problems'])} glossary problems"
          f"; on-screen check "
          f"{'not included' if rendered is None else rendered['status']})")
    return 0
