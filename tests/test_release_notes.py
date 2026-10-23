"""Are the developers' notes converted faithfully, and the same way twice?

``release_notes.py`` turns the Word and text notes shipped beside the
tree into ``docs/release-notes/<archive stem>/``.  Nothing in the suite
*judges* the build by them -- they are leads, not expectations -- but a
round starts by reading them, so a converter that silently dropped a
link, a table or a line of code would hand the reader a wrong account of
what the developers said.

Three kinds of check.  An extractor is tested against an answer written
down (AGENTS.md, coverage property 6): a small document built here with
every construct the converter claims to handle, and the exact Markdown
it must produce.  The real notes are checked for **conservation** --
every piece of text in each document appears in its rendering -- which
is the property a reader relies on and the one a rendering rule can
break without anyone noticing.  And the folder handling is checked where
it can do harm: two notes with one name, a note called README, a file
somebody added by hand, an encoding the converter cannot know.
"""
from __future__ import annotations

import html
from pathlib import Path

import pytest

from cbdb_desktop import release_notes
from cbdb_desktop.staging import AppLayout


def _add_hyperlink(paragraph, text: str, url: str) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    rel = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK,
                                   is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _demo_docx(path: Path) -> None:
    import docx
    from docx.shared import Pt

    document = docx.Document()
    document.add_paragraph().add_run("CBDB-Desktop: Demo revisions").bold = True
    document.add_paragraph("Intro with a <filter> and a *pointer.")
    linked = document.add_paragraph("See ")
    _add_hyperlink(linked, "the guide", "https://example.org/guide")
    linked.add_run(" for details.")
    document.add_paragraph().add_run("Summary").bold = True
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Ref", "Issue"
    table.cell(1, 0).text, table.cell(1, 1).text = "X-1", "a | b"
    lead = document.add_paragraph()
    lead.add_run("Change.").bold = True
    lead.add_run(" Body text.")
    document.add_paragraph().add_run("For the user's guide.").bold = True
    document.add_paragraph("first item", style="List Bullet")
    document.add_paragraph("second item", style="List Bullet")
    document.add_paragraph("step one", style="List Number")
    for line in ("if x {", "\treturn", "", "}"):
        document.add_paragraph().add_run(line).font.size = Pt(10)
    document.add_paragraph("")
    document.add_paragraph("After the code.")
    document.save(str(path))


_DEMO_MARKDOWN = """# CBDB-Desktop: Demo revisions

Intro with a &lt;filter&gt; and a \\*pointer.

See [the guide](<https://example.org/guide>) for details.

## Summary

| Ref | Issue |
|---|---|
| X-1 | a \\| b |

**Change.** Body text.

**For the user's guide.**

- first item
- second item
1. step one

```
if x {
    return

}
```

After the code.
"""


def test_the_converter_renders_each_construct_as_written_down(tmp_path):
    path = tmp_path / "demo.docx"
    _demo_docx(path)
    title, markdown = release_notes.docx_to_markdown(path)
    assert title == "CBDB-Desktop: Demo revisions"
    assert markdown == _DEMO_MARKDOWN


def test_a_text_note_is_kept_verbatim(tmp_path):
    path = tmp_path / "Build_notes.txt"
    path.write_bytes("Line one\r\n\tLine ```two```\r\n".encode("utf-8"))
    title, markdown = release_notes.text_to_markdown(path)
    assert (title, markdown) == (
        "Build_notes",
        "# Build_notes\n\n````text\nLine one\n\tLine ```two```\n````\n")


def test_a_note_in_an_unknown_encoding_is_refused_not_guessed(tmp_path):
    """GBK read as a Western code page is plausible nonsense; stop instead."""
    gbk = tmp_path / "gbk.txt"
    gbk.write_bytes("修正了地址查询".encode("gbk"))
    with pytest.raises(ValueError, match="not UTF-8"):
        release_notes.text_to_markdown(gbk)
    utf16 = tmp_path / "utf16.txt"
    utf16.write_bytes("修正".encode("utf-16"))
    assert "修正" in release_notes.text_to_markdown(utf16)[1]


def _words(text: str) -> list[str]:
    return [w for w in text.split() if w]


def test_no_text_in_a_shipped_note_is_lost(layout: AppLayout):
    """Conservation: every paragraph and cell of each note is in its page.

    Compared word by word after undoing the Markdown escapes, so the test
    is about content, not about how a construct is drawn.  This is the
    property a reader of docs/release-notes/ relies on.
    """
    import docx

    notes = [p for p in release_notes.find_notes(layout.root)
             if p.suffix.lower() == ".docx"]
    if not notes:
        pytest.skip("this build ships no Word notes beside its tree")
    for path in notes:
        rendered = release_notes.convert(path).markdown
        flat = " ".join(html.unescape(rendered).replace("**", "")
                        .replace("\\", "").split())
        document = docx.Document(str(path))
        pieces = [p.text for p in document.paragraphs]
        pieces += [cell.text for table in document.tables
                   for row in table.rows for cell in row.cells]
        for piece in pieces:
            for word in _words(piece):
                assert word in flat, f"{path.name}: {word!r} is missing"


def test_the_shipped_notes_convert_the_same_way_twice(layout: AppLayout,
                                                      tmp_path):
    notes = release_notes.find_notes(layout.root)
    if not notes:
        pytest.skip("this build ships no notes beside its tree")
    first, second = tmp_path / "a", tmp_path / "b"
    release_notes.import_notes(layout.root, first, "archive.7z")
    release_notes.import_notes(layout.root, second, "archive.7z")
    files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(second) for p in second.rglob("*")
                           if p.is_file())
    for relative in files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes(), relative
    # One Markdown file per note, one original per note, and the index.
    assert len(files) == 2 * len(notes) + 1, files
    # A rerun over an unchanged folder changes nothing.
    assert release_notes.import_notes(layout.root, first, "archive.7z") == []


def test_two_notes_with_one_name_and_a_note_called_readme_all_survive(
        tmp_path):
    root, dest = tmp_path / "tree", tmp_path / "out"
    root.mkdir()
    for name in ("Notes.txt", "Notes.md", "README.txt"):
        (root / name).write_text(f"body of {name}\n", encoding="utf-8")
    release_notes.import_notes(root, dest, "a.7z")
    rendered = {p.name: p.read_text(encoding="utf-8")
                for p in dest.glob("*.md")}
    assert sorted(rendered) == ["Notes.md.md", "Notes.txt.md", "README.md",
                                "README.txt.md"]
    assert "body of README.txt" in rendered["README.txt.md"]
    assert "Release notes shipped in" in rendered["README.md"]


def test_a_file_added_by_hand_is_never_deleted(tmp_path):
    root, dest = tmp_path / "tree", tmp_path / "out"
    root.mkdir()
    (root / "Old.txt").write_text("old\n", encoding="utf-8")
    release_notes.import_notes(root, dest, "a.7z")
    (dest / "my-annotations.md").write_text("mine\n", encoding="utf-8")
    (root / "Old.txt").unlink()
    (root / "New.txt").write_text("new\n", encoding="utf-8")
    release_notes.import_notes(root, dest, "a.7z")
    names = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")
                   if p.is_file())
    assert names == ["New.md", "README.md", "my-annotations.md",
                     "originals/New.txt"]


def test_it_refuses_a_destination_that_is_no_folder_of_its_own(tmp_path):
    with pytest.raises(ValueError):
        release_notes.import_notes(tmp_path, tmp_path / "..", "...7z")
