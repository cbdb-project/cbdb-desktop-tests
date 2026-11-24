"""The pages' three languages, checked against the CBDB label glossary.

Every form here has a language switch -- English, Traditional Chinese,
Simplified Chinese -- and keeps the three versions of its labels in one
object literal in its inline script (``const translations = {english:
{...}, traditional: {...}, simplified: {...}}``, or ``T``, or Kinship's
``LABELS = {n: {E, T, S}}``).  The maintainer found terms wrong in all
three, so this module reads those objects **as data** and asks of every
label the questions a reader of the three would ask, by fixed rules:

1. **Is it there in all three?**  A key missing from one language shows
   that language's reader ``undefined`` or the English.
2. **Is each Chinese version in its own script?**  A simplified
   character in the Traditional text (``之后``), or a traditional one in
   the Simplified text (``選擇`` under 简).
3. **Do the two Chinese versions say the same thing?**  ``指數年`` under
   繁 beside ``索引年`` under 简 would be two different words.  Compared
   through ``chinese_forms`` -- script conversion, OpenCC's Taiwan/mainland
   phrase tables, and the pairs in ``docs/labels/regional_terms.tsv`` --
   because a regional difference (匯出/导出, 連結/连接) is one word
   localised, never a finding (the maintainer's ruling, 2026-10-22); a
   script slip is reported by (2), not twice.
4. **Does the Chinese agree with the glossary?**  When the label's
   English is a term the glossary defines, its Chinese must be one the
   glossary gives for that term.
5. **Do English and Chinese agree, by the glossary?**  When the English
   is *not* a glossary term but the Chinese is, the English should be
   the glossary's for that Chinese -- or the Chinese is the wrong half.
   (Only then: if the English is a glossary term it is the anchor, and a
   disagreement is reported once, by 4, rather than once from each side.)

Plus one rule across pages (``inconsistencies``): one English label
translated more than one way on different forms.  Labels nothing on the
page reads (``Label.used``) are listed but not judged.

The glossary is ``docs/labels/FormLabels.xlsx``: the Access front end's
``FormLabels`` table, 643 labels over 29 forms, in English, 简体 and 繁體,
supplied by the maintainer as the reference.  ``FORM_PAGES`` says which
desktop page each Access form became, and a label is looked up **only**
in its own page's forms -- never in the whole glossary -- because one
English word legitimately has several Chinese renderings across forms
(``People`` is 社会关系的人 on Associations and 亲属网络的人 on Kinship).
Where several forms behind one page define a term with no wording in
common (the Browser stands for seventeen), the label is not judged.

**Why the result is the same on every run and every machine.**  Nothing
here samples, guesses or depends on the network: the inputs are the
staged templates and a committed spreadsheet, the rules are the ones
above, the outputs are sorted, and the one external table -- OpenCC's
character dictionaries -- is pinned to an exact version in
``requirements.txt`` because a different dictionary is a different
answer to question 2.

**How a character is judged to be in the wrong script** (question 2).
OpenCC converts text phrase by phrase into one of several standards:
``s2t`` writes the old-style forms (``羣``, ``臺``, ``裏``), ``s2tw``
Taiwan's (``群``, ``臺``, ``裡``), ``s2hk`` Hong Kong's (``羣``, ``台``,
``裏``).  None of them alone is a fair judge -- ``s2t`` would flag every
``群`` -- so a character in Traditional text is flagged only when **all
three** conversions change it, in context and on its own, and it is not
in ``docs/labels/accepted_characters.tsv`` (the maintainer's rulings:
``于`` is accepted in Traditional although all three write ``於``).
``后`` in ``之后`` is flagged; ``群`` and ``台`` are
not.  Simplified text is judged the same way by ``t2s``, ``tw2s`` and
``hk2s``.  Phrase context is kept, so ``乾隆`` is not read as ``干``.

**The rule's known limit.**  It is only as good as OpenCC's phrase
tables, and they do not know every proper name.  Characters that are
both a simplification *and* a legitimate traditional character in a
name -- the surname ``岳``, the era name ``咸平``, ``于闐``, ``云南`` as
written in older texts, ``范氏`` -- are flagged in Traditional text when
the phrase is not in OpenCC's dictionary.  No label in the build hits
this; place, era and person names in *data* would, which is one reason
the on-screen check judges only strings the template's author wrote.
``test_the_script_rule_on_characters_whose_answer_is_known`` pins one
such case, so the limit is visible rather than discovered.

**What this does not see.**  Text that is not in a translation object:
static bilingual labels written straight into the HTML (``Office 官职``)
that no language switch touches.  Those are what the user reads too,
and only a rendered page shows which strings a language switch leaves
alone -- ``test_translations.py`` drives that half in Chromium.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .config import REPO_ROOT

GLOSSARY_PATH = REPO_ROOT / "docs" / "labels" / "FormLabels.xlsx"

#: The three languages, in the order every output lists them.
LANGUAGES = ("english", "traditional", "simplified")

#: How the pages spell the language keys.  The forms use the words;
#: Kinship, ported from the VBA, uses the VBA's single letters.
_LANGUAGE_ALIASES = {
    "english": "english", "en": "english", "e": "english",
    "traditional": "traditional", "tc": "traditional", "t": "traditional",
    "zh_hant": "traditional", "zht": "traditional",
    "simplified": "simplified", "sc": "simplified", "s": "simplified",
    "zh_hans": "simplified", "zhs": "simplified",
}

#: Which desktop page each Access form became.  The Access form codes
#: are the glossary's ``c_form`` column.  ``None`` declares a form with
#: no desktop counterpart -- its labels still count in the whole-glossary
#: fallback, they just own no page.  Every code the glossary uses must be
#: declared here; ``test_translations.py`` fails on one that is not, so a
#: glossary that grows a form is read rather than silently half-used.
FORM_PAGES: dict[str, tuple[str, ...] | None] = {
    "LAA": ("associations",),
    "LAAP": ("association_pairs",),
    "LAE": ("entry",),
    "LAG": ("group_data",),
    "LAK": ("kinship",),
    "KRW": ("kinship",),            # the kinship-simplification warning
    "LAN": ("networks",),
    "LAO": ("office",),
    "LAP": ("places",),
    "LAS": ("status",),
    "LAT": ("texts",),
    "BROWSE": ("browser",),
    # The Access biography form and its subforms are what the desktop
    # Browser shows, read-only, tab by tab.
    "BIO": ("browser",),
    "SAN": ("browser",), "SEN": ("browser",),
    "SF_ADDR": ("browser",), "SF_ASD": ("browser",), "SF_BID": ("browser",),
    "SF_BSD": ("browser",), "SF_EVA": ("browser",), "SF_EVD": ("browser",),
    "SF_KIN": ("browser",), "SF_PADDR": ("browser",), "SF_POFF": ("browser",),
    "SF_POS": ("browser",), "SF_POST": ("browser",), "SF_STATUS": ("browser",),
    "SF_TEXTS": ("browser",),
    "POT": ("pickers/office_picker",),
}

#: The Access subforms (and the alt-name / entry data-entry forms) behind
#: the Browser.  Their labels are short column headers -- ``Type``,
#: ``Age``, ``Notes`` -- for one subform's field, while the Browser uses
#: the same words for other fields (its ``Type`` is the index year's
#: type, the address subform's is the address type).  They take part in
#: recognising a Chinese term, never in deciding what an English word
#: must be translated as.  See ``Glossary.for_english``.
SUBFORMS = frozenset(form for form in FORM_PAGES
                     if form.startswith("SF_") or form in {"SAN", "SEN"})

#: Glossary cells that are not terms: the Access language buttons, which
#: deliberately show the *other* language's name in each column.
_LANGUAGE_BUTTON_TEXT = frozenset({"English", "繁體", "简体", "簡體", "繁体"})


# ---------------------------------------------------------------------------
# the glossary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GlossaryRow:
    form: str
    label_id: int
    english: str
    simplified: str
    traditional: str

    @property
    def ref(self) -> str:
        return f"{self.form}#{self.label_id}"

    @property
    def is_language_button(self) -> bool:
        return bool({self.english, self.simplified, self.traditional}
                    & _LANGUAGE_BUTTON_TEXT)


def _cell(value) -> str:
    return "" if value is None else str(value)


@lru_cache(maxsize=None)
def load_glossary(path: Path = GLOSSARY_PATH) -> tuple[GlossaryRow, ...]:
    """Every row of the glossary, in sheet order.

    The header row is checked rather than assumed: a sheet whose columns
    were reordered would otherwise compare English against 繁體 and report
    every label as wrong.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        header = tuple(_cell(v).strip() for v in next(rows))
        wanted = ("c_form", "c_label_id", "c_english", "c_jianti", "c_fanti")
        if header[:5] != wanted:
            raise ValueError(f"{path.name}: expected columns {wanted}, "
                             f"found {header[:5]}")
        out = []
        for row in rows:
            if row is None or all(v is None for v in row[:5]):
                continue
            form, label_id, english, jianti, fanti = row[:5]
            out.append(GlossaryRow(form=_cell(form).strip(),
                                   label_id=int(label_id),
                                   english=_cell(english),
                                   simplified=_cell(jianti),
                                   traditional=_cell(fanti)))
        return tuple(out)
    finally:
        workbook.close()


def alternatives(cell: str) -> list[str]:
    """A glossary cell as the terms it offers.

    One cell (``LAE#18``) holds two renderings on two lines, joined by an
    Excel carriage-return escape (``_x000d_``); each line is a term.
    """
    text = re.sub(r"_x000[dD]_", "\n", cell)
    return [part.strip() for part in text.split("\n") if part.strip()]


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------

def _singular(word: str) -> str:
    """``years`` -> ``year``, ``dynasties`` -> ``dynasty``, ``ids`` -> ``id``.

    Deliberately crude and fixed: a label's number is not its wording
    (the glossary itself writes ``Index Year`` on one form and ``Index
    Years`` on the next), and a rule anyone can predict is worth more
    here than a clever one.  Words ending in ``ss``, ``us`` or ``is``
    (``address``, ``status``, ``analysis``) are left alone.
    """
    if len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def norm_english(text: str) -> str:
    """``'Run Query:'``, ``'run  query'`` and ``'Run Queries'`` are one term."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_singular(w) for w in re.findall(r"[a-z0-9]+", text))


def _letters(text: str) -> str:
    """Letters and digits only: punctuation, spaces and ▶ are not wording."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text
                   if unicodedata.category(c)[0] in "LN")


@lru_cache(maxsize=None)
def _converter(config: str):
    import opencc
    return opencc.OpenCC(config)


def to_simplified(text: str) -> str:
    return _converter("t2s").convert(text)


def norm_chinese(text: str) -> str:
    """The wording of a Chinese label, independent of its script."""
    return to_simplified(_letters(text)).casefold()


def chinese_forms(text: str) -> frozenset[str]:
    """Every wording ``text`` counts as, across script *and* region.

    Taiwan and the mainland use different everyday words for the same
    computing terms -- 匯出/导出 (export), 資料庫/数据库 (database),
    檔案/文件 (file), 儲存/保存 (save), 搜尋/搜索 (search).  A Traditional
    page written in Taiwan's vocabulary beside a Simplified page in the
    mainland's is a localisation, not two translations, so both regional
    conversions are applied as well as the script one: OpenCC's
    ``tw2sp`` (Taiwan -> mainland, with phrases) and ``s2twp`` (the other
    way, then reduced to simplified).  Two labels say the same thing when
    their sets of forms meet.  The phrase tables are OpenCC's, pinned
    with it, so the equivalence is the same on every run.
    """
    base = _letters(text)
    forms = {
        to_simplified(base),
        _letters(_converter("tw2sp").convert(base)),
        to_simplified(_letters(_converter("s2twp").convert(base))),
    }
    # Pairs OpenCC does not know, from docs/labels/regional_terms.tsv:
    # each form also counts with either side of a pair swapped for the
    # other (one pass, in file order, so the result is fixed).
    for taiwan, mainland in regional_terms():
        for form in list(forms):
            if taiwan in form:
                forms.add(form.replace(taiwan, mainland))
            if mainland in form:
                forms.add(form.replace(mainland, taiwan))
    return frozenset(f.casefold() for f in forms if f)


REGIONAL_TERMS_PATH = REPO_ROOT / "docs" / "labels" / "regional_terms.tsv"


@lru_cache(maxsize=None)
def regional_terms(path: Path = REGIONAL_TERMS_PATH) -> tuple[tuple[str, str], ...]:
    """Taiwan/mainland word pairs that name the same thing.

    Read from a committed table the maintainer edits, so that a
    regional difference is never a finding and never a special case in
    code.  Both sides are reduced to Simplified, as everything compared
    here is.
    """
    if not path.is_file():
        return ()
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            raise ValueError(f"{path.name}: expected 'Taiwan<TAB>mainland', "
                             f"got {line!r}")
        taiwan, mainland = (to_simplified(_letters(f)).casefold()
                            for f in fields[:2])
        if taiwan and mainland:
            out.append((taiwan, mainland))
    return tuple(out)


def same_wording(a: str, b: str) -> bool:
    return bool(chinese_forms(a) & chinese_forms(b))


def has_cjk(text: str) -> bool:
    return any(_is_han(c) for c in text)


def _is_han(char: str) -> bool:
    return ("㐀" <= char <= "鿿" or "豈" <= char <= "﫿"
            or "\U00020000" <= char <= "\U0003134f")


#: The conversions that define each script.  A character is in the wrong
#: script only when *every* conversion into the right one changes it.
_INTO = {
    "traditional": ("s2t", "s2tw", "s2hk"),
    "simplified": ("t2s", "tw2s", "hk2s"),
}


def wrong_script(text: str, script: str) -> list[str]:
    """Characters of ``text`` that every OpenCC conversion into ``script``
    changes (see the module docstring for the rule's known limit).

    A character is flagged only when every conversion changes it **both**
    in context and on its own.  In context, so that phrase knowledge
    clears a character the phrase legitimately uses (``公里`` keeps its
    ``里``, ``乾隆`` its ``乾``).  On its own, so that a phrase table's
    *preference* for a variant does not condemn an ordinary character:
    OpenCC writes ``娘家`` as ``孃家`` in all three traditional standards,
    and ``娘`` is nonetheless plain traditional.  A conversion that
    changed the length falls back to one character at a time.
    """
    flagged_by: list[set[int]] = []
    for config in _INTO[script]:
        converter = _converter(config)
        converted = converter.convert(text)
        alone = {i for i, c in enumerate(text) if converter.convert(c) != c}
        if len(converted) == len(text):
            changed = {i for i, (a, b) in enumerate(zip(text, converted))
                       if a != b} & alone
        else:
            changed = alone
        flagged_by.append(changed)
    positions = set.intersection(*flagged_by) if flagged_by else set()
    accepted = accepted_characters().get(script, frozenset())
    out: list[str] = []
    for i in sorted(positions):
        if (_is_han(text[i]) and text[i] not in out
                and text[i] not in accepted):
            out.append(text[i])
    return out


ACCEPTED_CHARACTERS_PATH = REPO_ROOT / "docs" / "labels" / "accepted_characters.tsv"


@lru_cache(maxsize=None)
def accepted_characters(path: Path = ACCEPTED_CHARACTERS_PATH
                        ) -> dict[str, frozenset[str]]:
    """``{script: characters}`` never flagged in that script.

    The maintainer's rulings, kept as a committed table rather than as
    exceptions in this module: ``于`` is acceptable in Traditional Chinese
    (2026-10-22), although every OpenCC conversion writes ``於``.
    """
    out: dict[str, set[str]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            script = fields[0].strip().casefold()
            if len(fields) < 2 or script not in _INTO or len(fields[1].strip()) != 1:
                raise ValueError(f"{path.name}: expected "
                                 f"'traditional|simplified<TAB>one character', "
                                 f"got {line!r}")
            out.setdefault(script, set()).add(fields[1].strip())
    return {script: frozenset(chars) for script, chars in out.items()}


# ---------------------------------------------------------------------------
# reading the pages' translation objects
# ---------------------------------------------------------------------------

class _Unparsable(Exception):
    pass


@dataclass
class _Cursor:
    text: str
    pos: int

    def peek(self) -> str:
        self.skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def skip(self) -> None:
        text = self.text
        while self.pos < len(text):
            c = text[self.pos]
            if c.isspace():
                self.pos += 1
            elif text.startswith("//", self.pos):
                end = text.find("\n", self.pos)
                self.pos = len(text) if end < 0 else end + 1
            elif text.startswith("/*", self.pos):
                end = text.find("*/", self.pos + 2)
                if end < 0:
                    raise _Unparsable("unclosed comment")
                self.pos = end + 2
            else:
                return

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise _Unparsable(f"expected {char!r} at {self.pos}")
        self.pos += 1


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
            "v": "\v", "0": "\0"}


def _string(cur: _Cursor) -> str:
    quote = cur.text[cur.pos]
    cur.pos += 1
    out: list[str] = []
    text = cur.text
    while cur.pos < len(text):
        c = text[cur.pos]
        if c == quote:
            cur.pos += 1
            return "".join(out)
        if c == "\\":
            nxt = text[cur.pos + 1]
            if nxt == "u":
                if text[cur.pos + 2] == "{":
                    end = text.index("}", cur.pos)
                    out.append(chr(int(text[cur.pos + 3:end], 16)))
                    cur.pos = end + 1
                else:
                    out.append(chr(int(text[cur.pos + 2:cur.pos + 6], 16)))
                    cur.pos += 6
                continue
            if nxt == "x":
                out.append(chr(int(text[cur.pos + 2:cur.pos + 4], 16)))
                cur.pos += 4
                continue
            if nxt == "\n":
                cur.pos += 2
                continue
            out.append(_ESCAPES.get(nxt, nxt))
            cur.pos += 2
            continue
        if c == "$" and quote == "`" and text.startswith("${", cur.pos):
            raise _Unparsable("template literal with a substitution")
        if c == "\n" and quote != "`":
            raise _Unparsable("unterminated string")
        out.append(c)
        cur.pos += 1
    raise _Unparsable("unterminated string")


_KEY = re.compile(r"[A-Za-z_$][\w$]*|\d+")


def _key(cur: _Cursor) -> str:
    c = cur.peek()
    if c in "'\"":
        return _string(cur)
    m = _KEY.match(cur.text, cur.pos)
    if not m:
        raise _Unparsable(f"expected a key at {cur.pos}")
    cur.pos = m.end()
    return m.group()


def _value(cur: _Cursor):
    """A string, a nested object, or ``None`` for anything else."""
    c = cur.peek()
    if c in "'\"`":
        return _string(cur)
    if c == "{":
        return _object(cur)
    # Anything else (a number, an identifier, a call, an arrow function)
    # is not a label.  Skip it to the next ``,`` or ``}`` at this depth.
    depth = 0
    text = cur.text
    while cur.pos < len(text):
        c = text[cur.pos]
        if c in "'\"`":
            _string(cur)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return None
            depth -= 1
        elif c == "," and depth == 0:
            return None
        cur.pos += 1
    raise _Unparsable("unterminated value")


def _object(cur: _Cursor) -> dict:
    cur.expect("{")
    out: dict = {}
    while True:
        if cur.peek() == "}":
            cur.pos += 1
            return out
        key = _key(cur)
        cur.expect(":")
        out[key] = _value(cur)
        nxt = cur.peek()
        if nxt == ",":
            cur.pos += 1
        elif nxt != "}":
            raise _Unparsable(f"expected ',' or '}}' at {cur.pos}")


_DECLARATION = re.compile(r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*\{")
_SCRIPT = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script>",
                     re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Label:
    """One translatable label of one page, in the three languages."""

    page: str
    table: str          # the JavaScript name of the object it came from
    key: str
    line: int           # where its English (or first) value is written
    english: str | None
    traditional: str | None
    simplified: str | None
    #: Whether anything on the page reads this label (see ``_used``).
    used: bool = True

    def text(self, language: str) -> str | None:
        return getattr(self, language)

    @property
    def ref(self) -> str:
        return f"{self.page}:{self.table}.{self.key}"


def _language(key: str) -> str | None:
    return _LANGUAGE_ALIASES.get(key.casefold())


def _blank_comments(text: str) -> str:
    """``text`` with every JavaScript comment replaced by spaces.

    Offsets and line breaks are kept, so positions found in the result
    are positions in the original.  Strings are walked so that ``//``
    inside ``'http://...'`` is not a comment.  A commented-out table
    (``/* const T = {...} */``) is therefore not read as a live one, and
    a key's line is not found in a ``// 3: ...`` note above it.
    """
    out = list(text)
    i, n = 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            for j in range(i, end):
                out[j] = " "
            i = end
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            for j in range(i, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def _labels_from(page: str, name: str, obj: dict, source: str,
                 start: int, end: int) -> list[Label]:
    """``obj`` as labels, if it is a translation table; else ``[]``.

    Two shapes ship.  Language-major: ``{english: {key: text}, ...}``.
    Key-major: ``{key: {E: text, T: text, S: text}}``, where an entry
    missing a language is kept (rule 1 reports the gap) rather than
    disqualifying the whole table.  Anything else is some other object.
    ``source`` is the page with comments blanked; ``start``/``end`` is the
    table's own span, which is excluded when asking whether a key is used.
    """
    langs = {_language(k): v for k, v in obj.items() if _language(k)}
    if set(langs) == set(LANGUAGES) and all(isinstance(v, dict)
                                            for v in langs.values()):
        keys: list[str] = []
        for language in LANGUAGES:
            for key in langs[language]:
                if key not in keys:
                    keys.append(key)
        out = []
        for key in keys:
            values = {lang: langs[lang].get(key) for lang in LANGUAGES}
            if not any(isinstance(v, str) for v in values.values()):
                continue
            out.append(Label(page=page, table=name, key=key,
                             line=_line_of(source, start, key),
                             used=_used(source, start, end, name, key,
                                        key_major=False),
                             **{lang: v if isinstance(v, str) else None
                                for lang, v in values.items()}))
        return out

    entries = [(k, v) for k, v in obj.items() if isinstance(v, dict)]
    if entries and len(entries) == len(obj) and all(
            any(_language(k) for k in v) for _, v in entries) and any(
            {_language(k) for k in v} >= set(LANGUAGES) for _, v in entries):
        out = []
        for key, value in entries:
            texts = {_language(k): t for k, t in value.items() if _language(k)}
            out.append(Label(page=page, table=name, key=str(key),
                             line=_line_of(source, start, key),
                             used=_used(source, start, end, name, str(key),
                                        key_major=True),
                             **{lang: texts.get(lang) if isinstance(
                                 texts.get(lang), str) else None
                                for lang in LANGUAGES}))
        return out
    return []


def _used(source: str, start: int, end: int, table: str, key: str, *,
          key_major: bool) -> bool:
    """Whether anything outside the table reads this label.

    A label nothing reads is never shown, so judging its wording would
    report text no reader sees (Kinship keeps seven VBA-era labels with
    no element, and says so in a comment).  Language-major tables are
    read as ``t.key``, ``t['key']``, or by passing the key as a string to
    a helper (the Browser's ``T('fldCbdbId')``, ``labelKey:
    'tabBasicInfo'``) -- so any quoted occurrence counts; key-major ones
    through a ``data-lbl-idx="key"`` attribute (numbered keys, until
    Build_20261028), a ``data-lbl="key"`` one (Kinship's named keys since
    then -- not ``data-lbl-prefix``, which decorates such an element) or
    ``TABLE[key]``.  A key
    *built* at run time (``'fld' + name``) would read as unused; none is
    in this build, and the report lists unused labels so one would show.
    """
    outside = source[:start] + " " * (end - start) + source[end:]
    k = re.escape(key)
    if key_major:
        pattern = (rf"""data-lbl(?:-idx)?\s*=\s*["']{k}["']"""
                   rf"""|\b{re.escape(table)}\s*\[\s*['"]?{k}['"]?\s*\]""")
    else:
        pattern = rf"""\.{k}\b|['"`]{k}['"`]"""
    return re.search(pattern, outside) is not None


def _line_of(source: str, start: int, key: str) -> int:
    """Line of the first ``key:`` at or after ``start``, outside comments."""
    m = re.compile(r"(?<![\w$'\"])['\"]?" + re.escape(str(key))
                   + r"['\"]?\s*:").search(source, start)
    index = m.start() if m else start
    return source.count("\n", 0, index) + 1


#: Declarations that look like a translation table even when they do not
#: parse: a language key near the opening brace.  Such a table failing to
#: parse is reported (``unreadable_tables``), never silently skipped.
_LOOKS_TRANSLATED = re.compile(
    r"""\{\s*(?:['"]?(?:english|traditional|simplified)['"]?\s*:"""
    r"""|['"]?\w+['"]?\s*:\s*\{\s*['"]?(?:E|T|S|english)['"]?\s*:)""")


def _scan_tables(page: str, html: str):
    """``(tables, unreadable)`` for one page: see the two public readers."""
    blanked = _blank_comments_in_scripts(html)
    tables: dict[str, list[Label]] = {}
    unreadable: list[str] = []
    for script in _SCRIPT.finditer(blanked):
        body_start = script.start("body")
        body = script.group("body")
        for decl in _DECLARATION.finditer(body):
            cur = _Cursor(body, decl.end() - 1)
            name = decl.group("name")
            try:
                obj = _object(cur)
            except (_Unparsable, IndexError, ValueError) as exc:
                head = body[decl.end() - 1:decl.end() + 200]
                if _LOOKS_TRANSLATED.match(head):
                    line = blanked.count("\n", 0, body_start + decl.start()) + 1
                    unreadable.append(f"{page}:{name} (line {line}): {exc}")
                continue
            labels = _labels_from(page, name, obj, blanked,
                                  body_start + decl.start(),
                                  body_start + cur.pos)
            if labels:
                key = name
                suffix = 2
                while key in tables:
                    key = f"{name}#{suffix}"
                    suffix += 1
                if key != name:
                    labels = [Label(**{**label.__dict__, "table": key})
                              for label in labels]
                tables[key] = labels
    return tables, unreadable


def _blank_comments_in_scripts(html: str) -> str:
    """The page with comments blanked inside its ``<script>`` bodies only."""
    parts = []
    last = 0
    for script in _SCRIPT.finditer(html):
        parts.append(html[last:script.start("body")])
        parts.append(_blank_comments(script.group("body")))
        last = script.end("body")
    parts.append(html[last:])
    return "".join(parts)


def translation_tables(page: str, html: str) -> dict[str, list[Label]]:
    """``{table name: labels}`` for every translation table on a page.

    Two tables declared under one name (in two scripts) are both kept,
    the second as ``NAME#2``, rather than one silently replacing the
    other.
    """
    return _scan_tables(page, html)[0]


def unreadable_tables(page: str, html: str) -> list[str]:
    """Declarations that look like translation tables and did not parse.

    The reader understands plain string values; a table that grows a
    template literal with ``${...}``, a spread or a function value stops
    parsing, and before this existed it would simply have vanished from
    the check while its page still had other tables.
    """
    return _scan_tables(page, html)[1]


_LANGUAGE_SWITCH = re.compile(
    r"""\b(?:setLanguage|changeDisplayLanguage|switchLanguage)\s*\(""")


def has_language_switch(html: str) -> bool:
    """Whether a page offers the reader a choice of language."""
    return bool(_LANGUAGE_SWITCH.search(html))


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------

#: The finding kinds, in the order they are reported.
KINDS = ("missing", "script", "chinese_disagree", "glossary_chinese",
         "glossary_english", "inconsistent", "rendered_script")

#: One line each, for reports and failure messages.
KIND_TITLES = {
    "missing": "a label missing from one of the three languages",
    "script": "Chinese text in the other script",
    "chinese_disagree": "繁 and 简 using different words for one label",
    "glossary_chinese": "Chinese that differs from the glossary's term",
    "glossary_english": "English and Chinese that disagree by the glossary "
                        "(the Chinese is a glossary term, the English is "
                        "not its English -- either side may be the wrong one)",
    "inconsistent": "one English label translated differently on "
                    "different pages",
    "rendered_script": "text on screen in the wrong script for the "
                       "language chosen",
}


@dataclass(frozen=True)
class Finding:
    kind: str
    page: str
    ref: str
    line: int
    english: str | None
    traditional: str | None
    simplified: str | None
    detail: str
    glossary: tuple[str, ...] = ()     # the rows the judgement rests on

    def sort_key(self):
        return (KINDS.index(self.kind), self.page, self.line, self.ref,
                self.detail)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "page": self.page, "ref": self.ref,
                "line": self.line, "english": self.english,
                "traditional": self.traditional,
                "simplified": self.simplified, "detail": self.detail,
                "glossary": list(self.glossary)}


@dataclass
class Glossary:
    """The glossary, as each desktop page sees it.

    Lookups are **scoped to the page's own Access forms** and never fall
    back to the whole glossary.  One English word means different things
    on different forms -- ``Occasion`` is an association's occasion on
    the Browser's subform and a genre of writing on Networks -- and a
    fallback that matched the other form's term would report a correct
    label as wrong.  ``test_translations.py`` checks that every page
    with a translation table owns at least one form, so scoping can never
    quietly mean "checked against nothing".
    """

    rows: tuple[GlossaryRow, ...]
    by_page: dict[str, list[GlossaryRow]] = field(default_factory=dict)

    @classmethod
    def build(cls, rows: tuple[GlossaryRow, ...]) -> "Glossary":
        g = cls(rows=rows)
        for row in rows:
            if row.is_language_button:
                continue
            for page in FORM_PAGES.get(row.form) or ():
                g.by_page.setdefault(page, []).append(row)
        return g

    def form_count(self, page: str) -> int:
        return len({row.form for row in self.by_page.get(page, ())})

    def for_english(self, english: str, page: str) -> list[GlossaryRow]:
        """Rows whose English is ``english``, excluding ``SUBFORMS``.

        A subform's short column headers (``Type``, ``Age``, ``Notes``)
        name *its* field; the Browser shows other fields under the same
        words, so a subform row may recognise a Chinese term but not
        decide what an English word must be translated as.
        """
        key = norm_english(english)
        return [r for r in self.by_page.get(page, ())
                if r.form not in SUBFORMS and key in _english_terms(r)]

    def for_chinese(self, chinese: str, page: str) -> list[GlossaryRow]:
        forms = chinese_forms(chinese)
        return [r for r in self.by_page.get(page, ())
                if forms & _chinese_forms_of(r)]


@lru_cache(maxsize=None)
def _chinese_forms_of(row: GlossaryRow) -> frozenset[str]:
    return frozenset().union(*(chinese_forms(t)
                               for column in (row.simplified, row.traditional)
                               for t in alternatives(column)))


@lru_cache(maxsize=None)
def _english_terms(row: GlossaryRow) -> frozenset[str]:
    return frozenset(norm_english(t) for t in alternatives(row.english)
                     if not has_cjk(t)) - {""}


def _show(rows: list[GlossaryRow]) -> tuple[str, ...]:
    return tuple(" ".join(f"{r.ref} {r.english} / {r.traditional} / "
                          f"{r.simplified}".split()) for r in rows)


def _ambiguous(rows: list[GlossaryRow]) -> bool:
    """True when the rows come from several forms that share no wording."""
    by_form: dict[str, frozenset[str]] = {}
    for row in rows:
        by_form[row.form] = by_form.get(row.form, frozenset()) | _chinese_forms_of(row)
    if len(by_form) < 2:
        return False
    return not frozenset.intersection(*by_form.values())


def check_label(label: Label, glossary: Glossary) -> list[Finding]:
    """Every finding for one label, by the five rules in the docstring."""
    out: list[Finding] = []

    def finding(kind, detail, rows=()):
        out.append(Finding(kind=kind, page=label.page, ref=label.ref,
                           line=label.line, english=label.english,
                           traditional=label.traditional,
                           simplified=label.simplified, detail=detail,
                           glossary=_show(list(rows))))

    missing = [lang for lang in LANGUAGES if label.text(lang) is None]
    if missing:
        finding("missing", "no " + " / ".join(missing) + " text")

    for script, other in (("traditional", "simplified"),
                          ("simplified", "traditional")):
        text = label.text(script)
        if text:
            bad = wrong_script(text, script)
            if bad:
                finding("script", f"the {script} text has {other} "
                        f"characters: {' '.join(bad)}")

    trad, simp = label.traditional, label.simplified
    chinese = [t for t in (trad, simp) if t and has_cjk(t)]
    if (trad and simp and has_cjk(trad) and has_cjk(simp)
            and not same_wording(trad, simp)):
        finding("chinese_disagree",
                f"繁 '{trad}' and 简 '{simp}' are different words")

    english = label.english
    if not (english and not has_cjk(english) and norm_english(english)
            and chinese):
        return out
    rows = glossary.for_english(english, label.page)
    if rows and glossary.form_count(label.page) > 1 and any(
            glossary.for_chinese(t, label.page) for t in chinese):
        # A page built from several Access forms (the Browser: the
        # biography form and sixteen subforms) can match a short English
        # word on the wrong subform -- its 'Age' sits under Age at Death,
        # and the entry subform's 'Age' is age at entry.  When the label's
        # Chinese is itself a glossary term on this page (享年 is the
        # biography form's Age at Death) the pair is a real term, and
        # judging it against the other subform's would be a false alarm.
        return out
    if rows and _ambiguous(rows):
        # Several Access forms behind this page define the term, each
        # with its own Chinese and none shared -- the Browser stands for
        # seventeen of them, and its 'Age' is 享年 on the biography form
        # and 入仕年齡 on the entry subform.  Which one the label means is
        # not something a rule can know, so it is not judged.
        return out
    if rows:
        expected = frozenset().union(*(_chinese_forms_of(r) for r in rows))
        wrong = [t for t in dict.fromkeys(chinese)
                 if not chinese_forms(t) & expected]
        # One finding per label: when 繁 and 简 are the same wording they
        # are one wrong term, and both are quoted in it.
        if wrong:
            finding("glossary_chinese",
                    f"'{english}' is rendered "
                    + " / ".join(f"'{t}'" for t in wrong)
                    + "; the glossary gives "
                    + " / ".join(sorted({" ".join(r.traditional.split())
                                         for r in rows})),
                    rows)
        return out
    hits: list[GlossaryRow] = []
    for text in chinese:
        for row in glossary.for_chinese(text, label.page):
            if row not in hits:
                hits.append(row)
    expected_en = frozenset().union(*(_english_terms(r) for r in hits))
    if expected_en and norm_english(english) not in expected_en:
        finding("glossary_english",
                f"'{chinese[0]}' is labelled '{english}' in English; the "
                "glossary gives "
                + " / ".join(sorted({r.english for r in hits})),
                hits)
    return out


def check_pages(pages: dict[str, Path], glossary: Glossary
                ) -> tuple[dict[str, list[Label]], list[Finding]]:
    """``({page: labels}, findings)`` for every page with a table.

    Every label is returned; only labels the page reads (``Label.used``)
    are judged.  The rest are listed by the report as unused.
    """
    labels: dict[str, list[Label]] = {}
    findings: list[Finding] = []
    for page, path in sorted(pages.items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        for table, table_labels in sorted(
                translation_tables(page, html).items()):
            labels.setdefault(page, []).extend(table_labels)
            for label in table_labels:
                if label.used:
                    findings.extend(check_label(label, glossary))
    findings.extend(inconsistencies(
        {page: [label for label in page_labels if label.used]
         for page, page_labels in labels.items()}))
    findings.sort(key=Finding.sort_key)
    return labels, findings


def inconsistencies(labels: dict[str, list[Label]]) -> list[Finding]:
    """One finding per English label the pages translate more than one way.

    Needs no glossary: ``Save to GIS`` written 保存到GIS on one form,
    儲存至GIS on another and 存至GIS on a third is a reader learning three
    words for one button, whichever of them the glossary prefers.  Labels
    are grouped by their English (normalised as everywhere here) and split
    into classes of ``same_wording`` -- in 繁 *and* in 简, so two pages
    that agree in one script and differ in the other are two classes;
    more than one class, across more than one page, is a finding.
    Classes are formed in page order, so the grouping -- and the report --
    is the same on every run.
    """

    def same(a: Label, b: Label) -> bool:
        for language in ("traditional", "simplified"):
            x, y = a.text(language), b.text(language)
            if x and y and has_cjk(x) and has_cjk(y) and not same_wording(x, y):
                return False
        return True

    groups: dict[str, list[Label]] = {}
    for page in sorted(labels):
        for label in labels[page]:
            english = label.english
            chinese = label.traditional or label.simplified
            if (english and chinese and has_cjk(chinese)
                    and not has_cjk(english) and norm_english(english)):
                groups.setdefault(norm_english(english), []).append(label)
    out: list[Finding] = []
    for key, members in sorted(groups.items()):
        classes: list[tuple[str, list[Label]]] = []
        for label in members:
            for wording, bucket in classes:
                if same(bucket[0], label):
                    bucket.append(label)
                    break
            else:
                classes.append((label.traditional or label.simplified,
                                [label]))
        # Within one page, one short English word over several Chinese
        # labels is how a form names fields in context -- the Browser's
        # 'Range' is 生年時限 beside Born and 卒年時限 beside Died, as in the
        # glossary itself.  Only a difference *between* pages is a reader
        # meeting two words for one thing.
        if len(classes) < 2 or len({m.page for m in members}) < 2:
            continue
        detail = "; ".join(
            f"'{wording}' on " + ", ".join(sorted({m.ref for m in bucket}))
            for wording, bucket in classes)
        first = members[0]
        out.append(Finding(
            kind="inconsistent", page="*", ref=f"'{first.english.strip()}'",
            line=0, english=first.english, traditional=None,
            simplified=None,
            detail=f"'{first.english.strip()}' is translated "
                   f"{len(classes)} ways: {detail}"))
    return out


_SWITCH_CALL = re.compile(
    r"""\b(?:setLanguage|changeDisplayLanguage|switchLanguage)\s*\(\s*['"](?P<lang>\w+)['"]""")


def language_buttons(buttons) -> dict[str, str]:
    """``{language: element id}`` of a page's own language buttons.

    Read from the control inventory (``controls.Button``), whichever way
    the button is wired -- inline ``setLanguage('traditional')`` on most
    forms, a listener calling ``changeDisplayLanguage('T')`` on Kinship.
    """
    out: dict[str, str] = {}
    for button in buttons:
        m = _SWITCH_CALL.search(button.handler or "")
        language = _language(m.group("lang")) if m else None
        if language and button.element_id:
            out.setdefault(language, button.element_id)
    return out


#: What a reader sees: every visible text node, plus the placeholders
#: and tooltips of visible controls and the document title.  "Visible"
#: is the browser's own answer -- an element with no client rects is not
#: on screen (``display: none``, a closed tab), so its text is not judged.
RENDERED_TEXT_JS = r"""() => {
  const out = [];
  const visible = el => {
    if (!el || el.closest('script,style,template,noscript')) return false;
    const cs = getComputedStyle(el);
    return el.getClientRects().length > 0 && cs.visibility !== 'hidden';
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = (node.nodeValue || '').trim();
    if (text && visible(node.parentElement)) out.push(text);
  }
  document.querySelectorAll('[placeholder],[title]').forEach(el => {
    if (!visible(el)) return;
    for (const attr of ['placeholder', 'title']) {
      const v = (el.getAttribute(attr) || '').trim();
      if (v) out.push(v);
    }
  });
  document.querySelectorAll('input[type=button],input[type=submit]').forEach(el => {
    if (visible(el) && el.value.trim()) out.push(el.value.trim());
  });
  if (document.title.trim()) out.push(document.title.trim());
  return out;
}"""


def _squash(text: str) -> str:
    return " ".join(text.split())


def authored_strings(html: str) -> str:
    """The template as one whitespace-normalised, entity-decoded string.

    A string on screen is judged only if it occurs in this -- that is, if
    the page's own author wrote it.  Names and titles fetched from the
    database (a dynasty, an office) are CBDB's data, written in whatever
    script the data is in, and are not the page's translation to judge.
    """
    import html as html_lib
    return _squash(html_lib.unescape(html))


#: The language buttons label themselves in their own language by
#: design -- 简 is how a Traditional reader finds Simplified.
_LANGUAGE_NAMES = frozenset({"EN", "English", "繁", "简", "繁體", "繁体",
                             "簡體", "简体", "簡", "English 英文"})


def rendered_findings(page: str, language: str, shown: list[str],
                      html: str) -> list[Finding]:
    """Findings for what one page shows in one Chinese language."""
    template = authored_strings(html)
    # A string that *is* one of the page's translations in this language
    # is already judged by the table rules; reporting it again from the
    # screen would count one slip twice.  What is left is what the
    # language switch never wrote.
    from_tables = {_squash(label.text(language))
                   for labels in translation_tables(page, html).values()
                   for label in labels if label.text(language)}
    out: list[Finding] = []
    seen: set[str] = set()
    for text in shown:
        text = _squash(text)
        if (text in seen or text in _LANGUAGE_NAMES or not has_cjk(text)
                or text not in template or text in from_tables):
            continue
        seen.add(text)
        bad = wrong_script(text, language)
        if bad:
            other = ("simplified" if language == "traditional"
                     else "traditional")
            index = html.find(text)
            if index < 0:
                # Written with an entity (``&nbsp;``) or split across
                # lines in the template: find its longest run of Chinese.
                runs = re.findall(r"[㐀-鿿豈-﫿]+", text)
                if runs:
                    index = html.find(max(runs, key=len))
            out.append(Finding(
                kind="rendered_script", page=page, ref=f"{page}@{language}",
                line=html.count("\n", 0, index) + 1 if index >= 0 else 0,
                english=None,
                traditional=text if language == "traditional" else None,
                simplified=text if language == "simplified" else None,
                detail=f"with {language} chosen, '{text}' is on screen "
                       f"with {other} characters: {' '.join(bad)}"))
    out.sort(key=Finding.sort_key)
    return out


def glossary_problems(rows: tuple[GlossaryRow, ...]) -> list[str]:
    """What is wrong with the glossary itself, by the same script rules.

    Not a finding against the build: the glossary is the reference, and
    these are reported so the maintainer can correct it.  The checks
    above compare wording after converting to one script, so a script
    slip in the glossary cannot make a page look wrong.
    """
    out: list[str] = []
    for row in rows:
        if row.is_language_button:
            continue
        cells = {"c_english": row.english, "c_jianti": row.simplified,
                 "c_fanti": row.traditional}
        for column, text in cells.items():
            # Only U+FFFD: a '?' here is a real question mark -- 'Female'
            # is '女?' and 'Assumed Post?' is '是否赴任', both yes/no fields.
            if "�" in text:
                out.append(f"{row.ref} {column} '{text}': a character was "
                           "lost in an encoding conversion (U+FFFD)")
            if re.search(r"_x000[dD]_", text):
                out.append(f"{row.ref} {column} {text!r}: two terms in one "
                           "cell, joined by an Excel line-break escape")
        if has_cjk(row.english):
            out.append(f"{row.ref} c_english '{row.english}' is Chinese")
        for column, script in (("c_jianti", "simplified"),
                               ("c_fanti", "traditional")):
            bad = wrong_script(cells[column], script)
            if bad:
                other = "traditional" if script == "simplified" else "simplified"
                out.append(f"{row.ref} {column} '{cells[column]}' has "
                           f"{other} characters: {' '.join(bad)}")
        # The same equivalence the page rules use, so a regional pair the
        # pages may write (超链接 / 超連結) is not called two words here.
        if (has_cjk(row.simplified) and has_cjk(row.traditional)
                and not same_wording(row.simplified, row.traditional)):
            out.append(f"{row.ref} c_jianti '{row.simplified}' and c_fanti "
                       f"'{row.traditional}' are different words")
    return out
