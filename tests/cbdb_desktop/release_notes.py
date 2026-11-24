"""The developers' notes that ship inside a distribution, as Markdown.

Since 2026-09-25 the archive carries more than the application: Word
documents and text files sit beside the ``CBDB-Desktop/`` tree (and one
inside it), each describing what a round of revisions changed and why.
They are the developers' own account of the build, and a round of
testing starts by reading them -- so they belong in this repository, in
the form everything else here is kept in, where a diff shows what a
build claims to have changed.

This module turns them into that form, the same way every time:

* **which files** -- every ``.docx``, ``.txt`` and ``.md`` at the root
  of the *staged* tree.  Staging already copies whatever shipped beside
  the wrapper (``archives.Archive.extract_to``) and re-verifies it
  against the archive's CRCs on every cache hit, so reading the staged
  copy is reading the archive.  ``Static/`` (the user guide PDF) is
  part of the application, not a note, and is not touched;
* **where** -- ``docs/release-notes/<archive stem>/``, one ``.md`` per
  note plus a ``README.md`` index, and the originals beside them under
  ``originals/`` so that nothing the conversion loses is lost;
* **how** -- deterministic: no timestamps, sorted inputs, one rendering
  of each Word construct.  Run it twice and the second run changes
  nothing, which is what lets ``run_tests.ps1`` run it every time.

What the notes are **not** is an expectation.  AGENTS.md § *Every run is
a fresh assessment*: a developer's "fixed" is a lead to verify against
this build, exactly like a maintainer's report, never a reason to skip
or to expect.

The Word documents use no heading styles -- every paragraph is
``Normal`` -- so structure is read from formatting, by fixed rules:

==========================================  ============================
paragraph                                   Markdown
==========================================  ============================
the first one, wholly bold                  ``# title``
wholly bold, not ending in a full stop      ``## heading``
wholly bold, ending in a full stop          ``**lead-in.**``
in a numbered/bulleted list (``w:numPr``)   ``- item`` (indented by level)
every run 10 pt (the code samples)          fenced code block
a table                                     a pipe table
==========================================  ============================
"""
from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

#: Note formats read, by suffix.  Anything else at the tree root
#: (``cbdb.exe``, the icons, the shortcut) is the application.
NOTE_SUFFIXES = (".docx", ".txt", ".md")

#: Point size the notes use for code samples.  The body text has no
#: explicit size, so "every run is exactly this size" is unambiguous.
_CODE_PT = 10.0


@dataclass(frozen=True)
class Note:
    source: Path    # the staged file
    markdown: str   # its rendering
    title: str


def find_notes(root: Path) -> list[Path]:
    """The notes at the root of a staged tree, sorted by name."""
    return sorted((p for p in root.iterdir()
                   if p.is_file() and p.suffix.lower() in NOTE_SUFFIXES),
                  key=lambda p: p.name.lower())


def _md_escape(text: str) -> str:
    """Prose made safe for Markdown: ``<filter>`` is not an HTML tag."""
    return (text.replace("\\", "\\\\").replace("*", "\\*")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _md_escape_cell(text: str) -> str:
    return (_md_escape(text).replace("|", "\\|")
            .replace("\r", "").replace("\n", "<br>").strip())


def _run_text(run) -> str:
    """A run's text, escaped for Markdown."""
    return _md_escape(run.text)


def _inner(paragraph):
    """``(text, bold)`` pieces of a paragraph, hyperlinks included.

    ``paragraph.runs`` leaves out runs inside ``w:hyperlink``, so a
    sentence with a link in it lost the link's words.  A hyperlink is
    written as ``[text](address)`` when it has an address, else as text.
    """
    from docx.text.hyperlink import Hyperlink
    for item in paragraph.iter_inner_content():
        if isinstance(item, Hyperlink):
            text = "".join(_run_text(r) for r in item.runs)
            address = getattr(item, "address", "") or ""
            if text and address:
                text = f"[{text}](<{address}>)"
            bold = bool(item.runs) and all(r.bold for r in item.runs
                                            if r.text.strip())
            yield text, bold
        else:
            yield _run_text(item), bool(item.bold)


def _inline(paragraph) -> str:
    """The paragraph's text, with bold runs marked ``**...**``."""
    out: list[str] = []
    pending_bold: list[str] = []

    def flush():
        if pending_bold:
            text = "".join(pending_bold)
            core = text.strip()
            if core:
                lead = text[:len(text) - len(text.lstrip())]
                tail = text[len(text.rstrip()):]
                out.append(f"{lead}**{core}**{tail}")
            else:
                out.append(text)
            pending_bold.clear()

    for text, bold in _inner(paragraph):
        if not text:
            continue
        if bold:
            pending_bold.append(text)
        else:
            flush()
            out.append(text)
    flush()
    return "".join(out)


def _is_code(paragraph) -> bool:
    runs = [r for r in paragraph.runs if r.text]
    return bool(runs) and all(
        r.font.size is not None and r.font.size.pt == _CODE_PT for r in runs)


def _is_bold(paragraph) -> bool:
    runs = [r for r in paragraph.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def _numbering(paragraph):
    """The paragraph's ``w:numPr``, from itself or its style chain."""
    from docx.oxml.ns import qn
    numpr = paragraph._p.find(".//" + qn("w:numPr"))
    style = paragraph.style
    while numpr is None and style is not None:
        numpr = style.element.find(f"{qn('w:pPr')}/{qn('w:numPr')}")
        style = style.base_style
    return numpr


def _list_marker(paragraph) -> tuple[int, str] | None:
    """``(level, marker)`` if the paragraph is a list item, else ``None``.

    Word attaches numbering either to the paragraph itself (the shipped
    notes do) or to its style (Word's own *List Bullet* does).  The
    marker is ``1.`` for a decimal list and ``-`` for anything else, read
    from the numbering definition the paragraph points at.
    """
    from docx.oxml.ns import qn
    numpr = _numbering(paragraph)
    if numpr is None:
        return None
    ilvl_el = numpr.find(qn("w:ilvl"))
    level = int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else 0
    num_el = numpr.find(qn("w:numId"))
    marker = "-"
    try:
        numbering = paragraph.part.numbering_part.element
        num_id = num_el.get(qn("w:val")) if num_el is not None else None
        for num in numbering.findall(qn("w:num")):
            if num.get(qn("w:numId")) != num_id:
                continue
            abstract = num.find(qn("w:abstractNumId")).get(qn("w:val"))
            for definition in numbering.findall(qn("w:abstractNum")):
                if definition.get(qn("w:abstractNumId")) != abstract:
                    continue
                for lvl in definition.findall(qn("w:lvl")):
                    if lvl.get(qn("w:ilvl")) == str(level):
                        fmt = lvl.find(qn("w:numFmt"))
                        if fmt is not None and fmt.get(qn("w:val")) == "decimal":
                            marker = "1."
    except (AttributeError, KeyError, NotImplementedError):
        pass
    return level, marker


def _fence(lines: list[str]) -> str:
    """A code fence longer than any run of backticks inside the block."""
    longest = max((len(run) for line in lines
                   for run in re.findall(r"`+", line)), default=0)
    return "`" * max(3, longest + 1)


def _table(table) -> list[str]:
    rows = [[_md_escape_cell(cell.text) for cell in row.cells]
            for row in table.rows]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |",
             "|" + "|".join(["---"] * width) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return lines


def _body_elements(body):
    """Paragraphs and tables in order, looking inside content controls."""
    for element in body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "sdt":
            for child in element.iterchildren():
                if child.tag.rsplit("}", 1)[-1] == "sdtContent":
                    yield from _body_elements(child)
        elif tag in ("p", "tbl"):
            yield tag, element


def docx_to_markdown(path: Path) -> tuple[str, str]:
    """``(title, markdown)`` for one Word document."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    blocks: list[list[str]] = []
    code: list[str] = []
    title = ""

    def close_code():
        while code and not code[-1].strip():
            code.pop()
        if code:
            fence = _fence(code)
            blocks.append([fence, *code, fence])
            code.clear()

    for tag, element in _body_elements(document.element.body):
        if tag == "tbl":
            close_code()
            blocks.append(_table(Table(element, document)))
            continue
        paragraph = Paragraph(element, document)
        text = paragraph.text
        if _is_code(paragraph):
            code.append(text.replace("\t", "    "))
            continue
        if code and not text.strip():
            # A blank line inside a code sample belongs to it; one after
            # the sample is dropped when the block closes.
            code.append("")
            continue
        close_code()
        if not text.strip():
            continue
        marker = _list_marker(paragraph)
        if not title and _is_bold(paragraph):
            title = text.strip()
            blocks.append([f"# {_md_escape(title)}"])
        elif marker is not None:
            level, bullet = marker
            item = f"{'   ' * level}{bullet} {_inline(paragraph).strip()}"
            # Consecutive items form one list: append to the previous
            # block when it is a list too.
            previous = blocks[-1][0].lstrip() if blocks and blocks[-1] else ""
            if previous.startswith(("- ", "1. ")):
                blocks[-1].append(item)
            else:
                blocks.append([item])
        elif _is_bold(paragraph) and not text.strip().endswith("."):
            blocks.append([f"## {_inline(paragraph).strip().strip('*')}"])
        else:
            blocks.append([_inline(paragraph).strip()])
    close_code()
    if not title:
        title = path.stem
        blocks.insert(0, [f"# {_md_escape(title)}"])
    return title, "\n\n".join("\n".join(b) for b in blocks) + "\n"


def _decode(path: Path) -> str:
    """A text note's characters, or a loud refusal.

    UTF-8 (with or without a BOM) and UTF-16 with a BOM are read.  Nothing
    is guessed: a GBK or Big5 note decoded as a Western code page turns
    Chinese into plausible-looking nonsense, which is worse than stopping.
    """
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{path.name} is not UTF-8 (byte {exc.start}: "
            f"{raw[exc.start:exc.start + 4]!r}); it may be GBK or Big5.  "
            "Not guessing an encoding -- save it as UTF-8, or convert it "
            "by hand.") from exc


def text_to_markdown(path: Path) -> tuple[str, str]:
    """``(title, markdown)`` for a plain-text note: kept verbatim."""
    text = _decode(path)
    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    if path.suffix.lower() == ".md":
        return path.stem, text
    fence = _fence(text.splitlines())
    return path.stem, f"# {path.stem}\n\n{fence}text\n{text}{fence}\n"


def convert(path: Path) -> Note:
    if path.suffix.lower() == ".docx":
        title, body = docx_to_markdown(path)
    else:
        title, body = text_to_markdown(path)
    return Note(source=path, markdown=body, title=title)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_if_changed(path: Path, text: str) -> bool:
    data = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


#: The first line of every file this module writes, apart from the copies
#: in ``originals/``.  Only files that carry it (or live in
#: ``originals/``) are ever deleted, so a note somebody adds to the folder
#: by hand survives the next run.
_GENERATED = "<!-- generated by release_notes.py"
_INDEX = "README.md"


def markdown_names(notes: list[Path]) -> dict[Path, str]:
    """The Markdown file name for each note.

    ``<stem>.md`` normally.  Two notes that share a stem (``Notes.txt``
    and ``Notes.docx``), or a note whose stem is the index's
    (``README``), keep their suffix instead (``Notes.txt.md``), so no
    note overwrites another or the index.
    """
    stems: dict[str, int] = {}
    for note in notes:
        stems[note.stem.lower()] = stems.get(note.stem.lower(), 0) + 1
    out = {}
    for note in notes:
        clash = (stems[note.stem.lower()] > 1
                 or note.stem.lower() == _INDEX.lower().removesuffix(".md"))
        out[note] = (note.name if clash else note.stem) + ".md"
    return out


def import_notes(root: Path, dest: Path, archive_name: str) -> list[Path]:
    """Write ``dest`` from the notes in ``root``; return what changed.

    Files this module generated that no note produces any more are
    removed, so the folder describes exactly one archive's notes; any
    other file in it is left alone.
    """
    if not dest.name.strip(".") or dest.resolve() == dest.resolve().parent:
        raise ValueError(f"refusing to write release notes into {dest}")
    sources = find_notes(root)
    names = markdown_names(sources)
    notes = [convert(p) for p in sources]
    wanted: dict[Path, str | Path] = {}
    index = [_GENERATED + " -->", "",
             f"# Release notes shipped in `{archive_name}`", "",
             "Converted by `python release_notes.py` from the files that "
             "ship beside the application tree.  The originals are in "
             "`originals/`; where this rendering and an original differ, "
             "the original is right.", "",
             "These are the developers' account of the build: leads to "
             "verify, not expectations (AGENTS.md § *Every run is a fresh "
             "assessment*).", "",
             "| note | original | SHA-256 (first 12) |", "|---|---|---|"]
    for note in notes:
        md_name = names[note.source]
        wanted[dest / md_name] = (
            f"{_GENERATED} from originals/{note.source.name}; "
            "do not edit, rerun it -->\n\n" + note.markdown)
        wanted[dest / "originals" / note.source.name] = note.source
        index.append(f"| [{_md_escape_cell(note.title)}](<{md_name}>) | "
                     f"`{note.source.name}` | `{_sha256(note.source)[:12]}` |")
    wanted[dest / _INDEX] = "\n".join(index) + "\n"

    changed: list[Path] = []
    for path, content in sorted(wanted.items()):
        if isinstance(content, Path):
            if path.is_file() and path.read_bytes() == content.read_bytes():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(content, path)
            changed.append(path)
        elif _write_if_changed(path, content):
            changed.append(path)
    if dest.is_dir():
        originals = dest / "originals"
        for path in sorted(dest.rglob("*"), reverse=True):
            if path.is_file() and path not in wanted and (
                    path.parent == originals or _is_generated(path)):
                path.unlink()
                changed.append(path)
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return changed


def _is_generated(path: Path) -> bool:
    if path.suffix != ".md":
        return False
    with path.open("rb") as handle:
        first = handle.readline().decode("utf-8", "replace")
    return first.startswith(_GENERATED)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .config import REPO_ROOT, load_config
    from .staging import archive_stem, stage

    ap = argparse.ArgumentParser(
        prog="python release_notes.py",
        description="Convert the notes shipped in CBDB_DESKTOP_ZIP into "
                    "docs/release-notes/<archive stem>/ as Markdown.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    config = load_config()
    if config.zip_path is None:
        # CBDB_APP_DIR with no archive: there is no shipped archive to
        # name the folder after, and nothing to convert from.
        print("no CBDB_DESKTOP_ZIP configured; no release notes to convert")
        return 0
    archive = config.require_zip()
    layout = stage(config, quiet=True)
    dest = REPO_ROOT / "docs" / "release-notes" / archive_stem(archive)
    changed = import_notes(layout.root, dest, archive.name)
    if not args.quiet:
        notes = find_notes(layout.root)
        print(f"{len(notes)} notes from {archive.name} -> "
              f"{dest.relative_to(REPO_ROOT)} ({len(changed)} files changed)")
    return 0
