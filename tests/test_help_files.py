"""Help: does each form's Help button open its help, in the reader's language?

New in Build_20261124.  Every translated form gained an ⓘ button
(``id="btnHelp"``, ``onclick="openHelp()"``) and a table naming one PDF
per display language under ``Static/HelpFiles/``::

    const HELP_DIR   = '/static/HelpFiles/';
    const HELP_FILES = { english: '...ENG...', traditional: '...CHN-T...',
                         simplified: '...CHN-S...' };

``openHelp`` sends a **HEAD** for the current language's file, falls back
to English if that fails, and alerts "no help file" if both do.  The
Navigation page's *Users Guide* link does the same for the three
``Static/CBDB_UserGuide_*.pdf`` through ``USERS_GUIDE_FILES``.

What can go wrong, and none of it is visible to any other test here:

1. **A named file is not served** -- misspelt, not shipped, or answered
   only to GET.  The fallback hides the first two behind English, and
   the third behind English for *every* language, so the reader sees a
   help file and never learns it is the wrong one.
2. **The page asks for the wrong language.**  Kinship keeps its language
   as ``E``/``T``/``S`` and needed a ``helpLanguage()`` mapper the other
   eleven do not; a page whose key does not match the table's falls back
   to English, silently.
3. **A page has the button and no table**, or a table short a language.

The tables are read out of the shipped pages as data.  What a page
*should* open is not taken from its own table -- that would agree with a
table that swapped two languages -- but from the build's naming
convention (``_ENG``, ``_CHN-T``, ``_CHN-S``), which all 42 files follow.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import pytest

from cbdb_desktop import browser, controls, i18n
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.staging import AppLayout

#: The language a file is for, as the build's file names spell it.
CONVENTION = {"english": "_ENG", "traditional": "_CHN-T",
              "simplified": "_CHN-S"}

#: Pages with a Help button on Build_20261124: the twelve forms plus the
#: Query Builder.  Exact, so a page that gains or loses the button fails
#: here and is read (AGENTS.md, operating principle 5).
HELP_BUTTON_PAGES = 13

_MAP = re.compile(r"const\s+(HELP_FILES|USERS_GUIDE_FILES)\s*=\s*\{(.*?)\}",
                  re.S)
_ENTRY = re.compile(r"(\w+)\s*:\s*'([^']+)'")
_DIR = re.compile(r"const\s+HELP_DIR\s*=\s*'([^']+)'")
_BUTTON = 'id="btnHelp"'


def _html(layout: AppLayout, page: str) -> str:
    return controls.pages(layout)[page].read_text(encoding="utf-8",
                                                  errors="replace")


def _help_urls(html: str) -> dict[str, str]:
    """``{language: URL}`` a page's help table names, or ``{}``.

    ``HELP_FILES`` holds bare names that ``openHelp`` prefixes with
    ``HELP_DIR`` and passes through ``encodeURIComponent``;
    ``USERS_GUIDE_FILES`` holds whole paths.
    """
    found = _MAP.search(html)
    if not found:
        return {}
    kind, body = found.groups()
    entries = dict(_ENTRY.findall(body))
    if kind == "USERS_GUIDE_FILES":
        return entries
    directory = _DIR.search(html)
    assert directory, "a page with HELP_FILES and no HELP_DIR"
    return {lang: directory.group(1) + quote(name, safe="")
            for lang, name in entries.items()}


def _tables(layout: AppLayout) -> dict[str, dict[str, str]]:
    return {page: urls for page in controls.pages(layout)
            if (urls := _help_urls(_html(layout, page)))}


def test_every_help_button_has_a_file_for_each_language(layout: AppLayout):
    """The button and the table come together, and the table is whole."""
    tables = _tables(layout)
    with_button = sorted(page for page in controls.pages(layout)
                         if _BUTTON in _html(layout, page))
    assert len(with_button) == HELP_BUTTON_PAGES, (
        f"{len(with_button)} pages have a Help button, pinned at "
        f"{HELP_BUTTON_PAGES}: {with_button}")
    bare = [page for page in with_button if page not in tables]
    assert not bare, (
        f"these pages have a Help button and no HELP_FILES table, so "
        f"openHelp throws on every press: {bare}")
    short = {page: sorted(urls) for page, urls in tables.items()
             if set(urls) != set(CONVENTION)}
    assert not short, (
        f"help tables without exactly the three display languages "
        f"{sorted(CONVENTION)}: {short}")
    misnamed = {f"{page}:{lang}": url for page, urls in tables.items()
                for lang, url in urls.items()
                if CONVENTION[lang] not in url}
    assert not misnamed, (
        f"these entries name a file that by its own name is for another "
        f"language: {misnamed}")


@pytest.mark.app
def test_every_help_file_a_page_names_is_served_as_a_pdf(
        app: CbdbApp, layout: AppLayout):
    """GET *and* HEAD: ``openHelp`` decides with a HEAD.

    A file answered to GET and not to HEAD looks missing to the page,
    which then opens English -- in every language, with no error.
    """
    tables = _tables(layout)
    assert tables, "no page in this build names a help file"
    wrong: list[str] = []
    for page, urls in sorted(tables.items()):
        for lang, url in sorted(urls.items()):
            head = app.request("HEAD", url)
            got = app.get(url)
            if head.status_code != 200:
                wrong.append(f"{page}/{lang}: HEAD {url} -> {head.status_code}")
            if got.status_code != 200 or not got.content.startswith(b"%PDF"):
                wrong.append(f"{page}/{lang}: GET {url} -> {got.status_code}, "
                             f"{got.content[:8]!r}")
    assert not wrong, (
        f"{len(wrong)} help files the pages name are not served as PDFs "
        "(openHelp then falls back to English, or alerts that there is no "
        "help):\n  " + "\n  ".join(wrong))


_USABLE, _WHY_NOT = browser.available()

#: Stand in for the tab ``openHelp`` opens: record where it is sent, and
#: record an alert instead of blocking the page on it.
_CAPTURE = """() => {
  window.__helpOpened = [];
  window.open = () => {
    const location = {};
    Object.defineProperty(location, 'href',
      {set: v => window.__helpOpened.push(v), get: () => ''});
    return {location, close() {}, closed: false};
  };
  window.alert = m => window.__helpOpened.push('ALERT: ' + m);
}"""


def _route_of(layout: AppLayout) -> dict[str, str]:
    from cbdb_desktop.routes import all_routes, concrete_get_pages, page_map
    route_of = {name: "/" + target
                for name, target in page_map(layout).items()}
    for route in concrete_get_pages(all_routes(layout)):
        if route.path == "/QBE":
            route_of["qbe"] = route.path
    return route_of


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_help_opens_the_file_for_the_language_on_screen(
        app: CbdbApp, layout: AppLayout):
    """Press 简, press Help: the Simplified help file, on every form.

    The page's own language buttons choose the language, the real
    ``openHelp`` runs -- its HEAD requests included -- and only the
    new tab is stood in for.  Every page and language is tried before
    reporting, because which ones is the whole content of a failure.
    """
    route_of = _route_of(layout)
    pages = sorted(page for page in controls.pages(layout)
                   if _BUTTON in _html(layout, page))
    assert pages, "no page in this build has a Help button"
    wrong: list[str] = []
    with browser.open_session(app.base_url, languages=["en-US"]) as open:
        for page in pages:
            switch = i18n.language_buttons(controls.inventory(layout)[page][0])
            assert set(switch) == set(CONVENTION), (
                f"{page}: the control inventory found language buttons "
                f"{sorted(switch)}, so a language cannot be chosen on it")
            tab, log = open(route_of[page])
            for lang in sorted(CONVENTION):
                tab.evaluate(_CAPTURE)
                tab.click(f"#{switch[lang]}")
                tab.click("#btnHelp")
                tab.wait_for_function("() => window.__helpOpened.length > 0",
                                      timeout=10_000)
                opened = tab.evaluate("() => window.__helpOpened")
                if len(opened) != 1 or CONVENTION[lang] not in opened[0]:
                    wrong.append(f"{page} in {lang}: opened {opened}"
                                 f"{'; page errors ' + str(log.page_errors) if log.page_errors else ''}")
    assert not wrong, (
        f"{len(wrong)} of {len(pages) * len(CONVENTION)} Help presses did not "
        f"open the file for the language on screen (expected a name "
        f"containing {CONVENTION}):\n  " + "\n  ".join(wrong))
