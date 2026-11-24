"""The language a form opens in, and whether it is remembered.

New in Build_20261102, and the first behaviour this build added rather
than relabelled.  Until 20261028 every form opened in English --
``setLanguage('english')``, written into each page's load path -- and a
reader who wanted Chinese pressed 繁 or 简 again on every form they
opened.  20261102 moved that decision into one shipped file,
``Static/cbdb_language.js``, which the twelve translated pages load
before their own script and call twice:

* ``setLanguage(initialDisplayLanguage())`` at load, which is the saved
  choice if there is one and otherwise the language detected from the
  browser's (and so normally the operating system's) preferences;
* ``saveDisplayLanguage(lang)`` inside the page's own ``setLanguage``,
  which remembers the choice in ``localStorage`` under
  ``cbdbDisplayLanguage`` so it carries to every other form.

Three things can go wrong, and only the first is visible to any test
this suite already had:

1. **A page is not wired up.**  A form that still says
   ``setLanguage('english')`` opens in English for a Chinese reader
   while the eleven beside it do not, and nothing else notices: the
   page loads, every control works, and its translation table is
   complete.  Checked here from the build's own inventory, so a form
   added later is asked the same question without anyone remembering.
2. **Detection maps a reader to the wrong script.**  Checked against
   the mapping the developers wrote down in *Display language detection
   (Oct 31 2026)*, which is this feature's specification -- a table of
   browser tags and the display language each must produce.  The table
   is written out by hand here from that note; it is not read back out
   of the shipped script, which would make the check agree with the
   code including where the code is wrong (AGENTS.md, § ABSOLUTE
   PROHIBITION).
3. **The choice is not actually carried.**  Only a browser can show
   this, and only one that opens two forms in the same context, which
   is why ``browser.open_session`` exists.

**One known correction, deliberately kept.**  The Access original
mapped Hong Kong to Simplified and Singapore to Traditional; the note
says this was reversed here on purpose, so the table below follows the
note (HK → Traditional, SG → Simplified) and a build that went back to
the VBA's mapping fails.

**What the oracle is.**  Which language a page is showing is read from
the page's own statement of it: each of the twelve marks exactly one of
its three language buttons with the ``active`` class, and the button
ids come from the control inventory rather than from a list written
here.  Nothing in this module recomputes what the page should display.
"""
from __future__ import annotations

import json

import pytest

from cbdb_desktop import browser, controls, i18n
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.staging import AppLayout

#: Where the shared script is served from, and where it is shipped.
#: Both spellings, because a page referring to a file the build does not
#: ship and a build shipping a file no page loads are different faults
#: with the same symptom.
SHARED_SCRIPT_URL = "/static/cbdb_language.js"
SHARED_SCRIPT_FILE = "cbdb_language.js"

#: The key the choice is kept under, as the note names it.  Written here
#: so that a build that renamed it fails with the old name in the
#: message rather than with an empty ``localStorage``.
STORAGE_KEY = "cbdbDisplayLanguage"

#: The two functions every translated page calls from the shared file,
#: and where each is called.  A page that loads the file and calls
#: neither is no better off than one that does not load it.
HOOKS = {
    "initialDisplayLanguage": "decides the language the form opens in",
    "saveDisplayLanguage": "remembers the reader's choice for other forms",
}

#: The specification, from the developers' note of 2026-10-31: browser
#: language preferences in, display language out.
#:
#: Each row is an ordered ``navigator.languages`` and the language the
#: note says it must produce.  The note states the rule in three parts
#: and every part has rows here, because a table that exercised only the
#: easy half would pass on a detection that got the rest wrong:
#:
#: * the script and region mapping (Hant/TW/HK/MO vs Hans/CN/SG);
#: * "the top choice decides" -- Chinese anywhere but first is English,
#:   which is the half the steering committee is still choosing between
#:   and so the half most likely to change;
#: * a bare ``zh`` at the top resolved by a later, more specific entry,
#:   and defaulting to Simplified when nothing is more specific.
DETECTION: tuple[tuple[tuple[str, ...], str], ...] = (
    # script and region
    (("zh-Hant",), "traditional"),
    (("zh-TW",), "traditional"),
    (("zh-HK",), "traditional"),          # the VBA said Simplified
    (("zh-MO",), "traditional"),
    (("zh-Hans",), "simplified"),
    (("zh-CN",), "simplified"),
    (("zh-SG",), "simplified"),           # the VBA said Traditional
    (("zh",), "simplified"),
    # anything else, and the case the mapping is for
    (("en-US",), "english"),
    (("en-GB", "fr-FR"), "english"),
    (("ja-JP",), "english"),
    # the top choice decides
    (("en-US", "zh-TW"), "english"),
    (("en-US", "zh-CN"), "english"),
    (("zh-TW", "en-US"), "traditional"),
    (("zh-CN", "en-US"), "simplified"),
    # a bare zh at the top, resolved by a later entry or defaulted
    (("zh", "zh-TW", "en-US"), "traditional"),
    (("zh", "zh-CN", "en-US"), "simplified"),
    (("zh", "en-US"), "simplified"),
)

#: The browser preference every form is opened with end-to-end, and the
#: language each must then be showing.  One row, not the whole table
#: above: what that pass asks is whether a page *applies* what detection
#: returned, which is a yes or a no per page and does not become a
#: different question in another language.  The mapping is covered
#: above, English by the carry test's own first assertion, and the cost
#: of a second language here is twelve more page loads for nothing.
APPLIED_TAGS = ("zh-TW",)
APPLIED_LANGUAGE = "traditional"


# ---------------------------------------------------------------------------
# what the shipped files say
# ---------------------------------------------------------------------------

def pytest_generate_tests(metafunc):
    """Parametrise over the pages the build translates, as the build has them.

    The same derivation ``test_translations.py`` uses, and for the same
    reason: no page name is written down, so a form that gains or loses
    a language switch changes what is checked by itself.
    """
    if "page" in metafunc.fixturenames:
        from cbdb_desktop.config import load_config
        from cbdb_desktop.staging import stage_once
        layout = stage_once(load_config(),
                            force=metafunc.config.getoption("--restage"))
        metafunc.parametrize("page", sorted(
            name for name, path in controls.pages(layout).items()
            if i18n.has_language_switch(
                path.read_text(encoding="utf-8", errors="replace"))))


def _html(layout: AppLayout, page: str) -> str:
    return controls.pages(layout)[page].read_text(encoding="utf-8",
                                                  errors="replace")


def _why(names) -> str:
    """The hooks named, each with what the page loses without it."""
    return "; ".join(f"{name} {HOOKS[name]}" for name in names)


def _inline(html: str):
    from cbdb_desktop import jsscan
    return jsscan.inline_scripts(html)


def test_the_build_ships_the_shared_language_script(layout: AppLayout):
    """An empty check is a failure: the file has to be there to be checked.

    Everything below asks what the pages do with this file.  If the
    build stopped shipping it, each of those questions would still have
    an answer -- the wrong one, quietly -- so the file's existence is
    asserted once, here, by itself.
    """
    path = layout.static_dir / SHARED_SCRIPT_FILE
    assert path.is_file(), (
        f"the build does not ship Static/{SHARED_SCRIPT_FILE}, which every "
        f"translated page loads as {SHARED_SCRIPT_URL}.  Each of those "
        "pages calls two functions from it on load; without the file the "
        "call throws and the page's whole inline script dies with it")
    source = path.read_text(encoding="utf-8", errors="replace")
    missing = [name for name in HOOKS if f"function {name}" not in source]
    assert not missing, (
        f"Static/{SHARED_SCRIPT_FILE} does not define {missing}, which the "
        f"pages call: {_why(missing)}")


def test_every_page_with_a_language_switch_loads_the_shared_script(
        page: str, layout: AppLayout):
    """A form that does not load the file cannot be in the shared language.

    The failure this prevents is a silent one and it is per form: eleven
    forms open in the reader's language and the twelfth opens in
    English, with no error anywhere.  A build that adds a thirteenth
    translated form is asked the same question, because the page list is
    the build's.
    """
    html = _html(layout, page)
    from cbdb_desktop import jsscan
    srcs = jsscan.external_script_srcs(html)
    assert SHARED_SCRIPT_URL in srcs, (
        f"{page} offers a choice of language but does not load "
        f"{SHARED_SCRIPT_URL} (its <script src> tags: {srcs or 'none'}), so "
        "it cannot open in the language the reader chose on another form")


def test_every_page_with_a_language_switch_calls_both_shared_functions(
        page: str, layout: AppLayout):
    """Loading the file is not using it.

    Two calls, two different losses.  Without
    ``initialDisplayLanguage`` the form opens in English however the
    reader left the last one; without ``saveDisplayLanguage`` the form
    works but teaches the others nothing, so a choice made here is
    forgotten on the next form -- the half a reader would report as
    "it sometimes remembers".
    """
    html = _html(layout, page)
    source = "".join(body for _line, body in _inline(html))
    missing = [name for name in HOOKS if name not in source]
    assert not missing, (
        f"{page}'s script never calls {missing}: {_why(missing)}.  "
        "The page loads the shared file and then does not use it")


def test_no_page_still_opens_in_a_language_written_into_it(
        page: str, layout: AppLayout):
    """The thing the feature replaced, and the shape a half-done port leaves.

    Every page used to open with a literal -- ``setLanguage('english')``
    on eleven of them, Kinship's own inline ``navigator.language`` read
    on the twelfth.  A page that still does is one the port missed, and
    it is indistinguishable from a working page until a Chinese reader
    opens it.  Checked at the source because it costs nothing and names
    the line, beside the browser pass below that checks what a reader
    actually gets (AGENTS.md, operating principle 9).
    """
    html = _html(layout, page)
    source = "".join(body for _line, body in _inline(html))
    written_in = ("'english'", '"english"', "'E'", '"E"',
                  "'traditional'", '"traditional"', "'T'", '"T"',
                  "'simplified'", '"simplified"', "'S'", '"S"')
    literal = [
        line.strip() for line in source.splitlines()
        if ("setLanguage(" in line or "changeDisplayLanguage(" in line)
        and "addEventListener" not in line          # the buttons, which must
        and "onclick" not in line                   # pass a literal language
        and any(q in line for q in written_in)]
    assert not literal, (
        f"{page} still opens in a language written into the page rather "
        f"than the reader's: {literal}.  Every other translated form calls "
        "setLanguage(initialDisplayLanguage())")


# ---------------------------------------------------------------------------
# what a reader actually gets
# ---------------------------------------------------------------------------

_USABLE, _WHY_NOT = browser.available()


def _route_of(layout: AppLayout) -> dict[str, str]:
    """``page -> route``, as ``test_translations`` derives it."""
    from cbdb_desktop.routes import all_routes, concrete_get_pages, page_map
    route_of = {name: "/" + target
                for name, target in page_map(layout).items()}
    for route in concrete_get_pages(all_routes(layout)):
        if route.path == "/QBE":
            route_of["qbe"] = route.path
    return route_of


#: Which language a loaded page says it is showing: the one language
#: button it marked ``active``.  Asked of the ids the control inventory
#: found, so the question is about this build's buttons.
_ACTIVE = """(ids) => Object.entries(ids)
  .filter(([, id]) => document.getElementById(id)
                   && document.getElementById(id).classList.contains('active'))
  .map(([language]) => language)"""


def _shown_language(tab, switch: dict[str, str]) -> list[str]:
    return tab.evaluate(_ACTIVE, switch)


def _translated(layout: AppLayout) -> list[str]:
    """The pages that offer a choice of language, from the build."""
    return sorted(name for name in controls.pages(layout)
                  if i18n.has_language_switch(_html(layout, name)))


def _switch_of(layout: AppLayout, page: str) -> dict[str, str]:
    """``{language: button id}`` for one page, from the control inventory."""
    switch = i18n.language_buttons(controls.inventory(layout)[page][0])
    assert set(switch) == {"english", "traditional", "simplified"}, (
        f"{page}: the control inventory found {sorted(switch)} language "
        "buttons, so what the page is showing cannot be read off it")
    return switch


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_detection_maps_the_browsers_languages_as_the_note_specifies(
        app: CbdbApp, layout: AppLayout):
    """The shipped ``detectDisplayLanguage``, against the written-down table.

    Run in a browser rather than reasoned about, because the function
    reads ``navigator.languages`` and the answer depends on how a real
    engine lexes and normalises the tags it is handed.  The expected
    values come from the developers' note of 2026-10-31, not from the
    script, so this can fail -- which is the second question AGENTS.md
    asks of every assertion here.

    One page, and the preference list is replaced between calls: the
    function is pure and reads the list each time, so eighteen rows cost
    one browser rather than eighteen.  Every row is tried before the
    test reports, because "which of the eighteen" is the whole content
    of the failure -- a detection that is wrong about Hong Kong and
    right about everything else is a one-line fix, and a detection that
    is wrong about all of them is a feature that never ran.
    """
    route = _route_of(layout)[_translated(layout)[0]]
    wrong: list[str] = []
    with browser.open_page(app.base_url, route) as (tab, log):
        for tags, expected in DETECTION:
            got = tab.evaluate(
                "([tags]) => { Object.defineProperty("
                "navigator, 'languages', {get: () => tags,"
                " configurable: true});"
                " return [detectDisplayLanguage(),"
                " navigator.languages.join(',')]; }",
                [list(tags)])
            answer, seen = got
            assert seen == ",".join(tags), (
                f"the browser did not take the language list under test: "
                f"asked for {list(tags)}, it reports {seen!r} -- the rest "
                "of this test would be about the wrong input")
            if answer != expected:
                wrong.append(f"{list(tags)} -> {answer!r}, "
                             f"the note specifies {expected!r}")
    assert not wrong, (
        f"{len(wrong)} of {len(DETECTION)} browser language preferences map "
        "to a display language the developers' note of 2026-10-31 does not "
        "specify:\n  " + "\n  ".join(wrong) +
        f"\nPage errors: {log.page_errors}")


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_every_form_opens_in_the_language_detection_chose(
        app: CbdbApp, layout: AppLayout):
    """Detection is only half of it: the form has to apply what it returned.

    A page can load the shared file, call the function, and still open
    in English -- its own ``setLanguage`` may not understand the words
    the shared file hands it, which is exactly the hazard on Kinship,
    whose switch speaks ``E``/``T``/``S`` and was re-plumbed for this
    build.  So the question is put to each page: which language button
    did you mark active?

    Every form is asked, and all of them are asked before the test
    reports, because one form left out of the port is the failure this
    exists for and naming it is the whole report.
    """
    route_of = _route_of(layout)
    pages = _translated(layout)
    assert pages, "no page in this build offers a choice of language"

    wrong: dict[str, list[str]] = {}
    errors: dict[str, list[str]] = {}
    with browser.open_session(app.base_url,
                              languages=list(APPLIED_TAGS)) as open:
        for name in pages:
            route = route_of.get(name)
            assert route, f"{name}: no route in the navigation map"
            tab, log = open(route)
            active = _shown_language(tab, _switch_of(layout, name))
            if active != [APPLIED_LANGUAGE]:
                wrong[name] = active
                errors[name] = log.page_errors

    assert not wrong, (
        f"a reader whose browser prefers {list(APPLIED_TAGS)} should get "
        f"every form in {APPLIED_LANGUAGE}; these open in another language "
        f"(the language button each marks active): {wrong}.  "
        f"Page errors: {errors}")


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_a_choice_made_on_one_form_is_how_the_next_form_opens(
        app: CbdbApp, layout: AppLayout):
    """The claim the whole feature is for, driven across every form.

    A reader presses 繁 once and every form they open afterwards is in
    Traditional.  One browser context throughout, because the choice
    lives in ``localStorage`` and two browsers could never show it
    travelling; the first form is the one that chooses and every other
    translated form is then opened in turn and asked what it opened in.

    An English browser is used on purpose, so that a form opening in
    Traditional can only be the saved choice and never detection
    agreeing with it by accident.
    """
    route_of = _route_of(layout)
    pages = sorted(name for name in controls.pages(layout)
                   if i18n.has_language_switch(_html(layout, name)))
    assert len(pages) > 1, (
        f"only {pages} offers a language switch, so there is no second "
        "form for a choice to carry to")

    chooser, rest = pages[0], pages[1:]
    switch = i18n.language_buttons(controls.inventory(layout)[chooser][0])
    wrong: dict[str, list[str]] = {}
    with browser.open_session(app.base_url, languages=["en-US"]) as open:
        tab, log = open(route_of[chooser])
        assert _shown_language(tab, switch) == ["english"], (
            f"{chooser} did not open in English for an en-US browser, so "
            "this test cannot tell a carried choice from a detected one")
        tab.click(f"#{switch['traditional']}")
        assert _shown_language(tab, switch) == ["traditional"], (
            f"{chooser}: pressing 繁 did not switch the form "
            f"(page errors: {log.page_errors})")
        saved = tab.evaluate(
            f"() => localStorage.getItem({json.dumps(STORAGE_KEY)})")
        assert saved == "traditional", (
            f"{chooser} switched to Traditional but wrote {saved!r} to "
            f"localStorage[{STORAGE_KEY}]; no other form can read that")

        for name in rest:
            other = i18n.language_buttons(controls.inventory(layout)[name][0])
            next_tab, _next_log = open(route_of[name])
            active = _shown_language(next_tab, other)
            if active != ["traditional"]:
                wrong[name] = active

    assert not wrong, (
        f"after a reader chose 繁 on {chooser}, these forms still opened in "
        f"another language: {wrong}.  The choice is kept in "
        f"localStorage[{STORAGE_KEY}] and every form is supposed to open "
        "with it")


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_a_saved_choice_outranks_what_the_browser_prefers(
        app: CbdbApp, layout: AppLayout):
    """A reader who chose English on a Chinese machine keeps English.

    Detection is a default, not a policy: the note is explicit that it
    "runs only when no choice is saved".  The failure this prevents is
    the irritating one -- a form that re-detects on every load and undoes
    the reader's choice each time they open another page.
    """
    route_of = _route_of(layout)
    pages = sorted(name for name in controls.pages(layout)
                   if i18n.has_language_switch(_html(layout, name)))
    chooser = pages[0]
    switch = i18n.language_buttons(controls.inventory(layout)[chooser][0])

    with browser.open_session(app.base_url, languages=["zh-TW"]) as open:
        tab, log = open(route_of[chooser])
        assert _shown_language(tab, switch) == ["traditional"], (
            f"{chooser} did not open in Traditional for a zh-TW browser, so "
            "there is no detected language for a choice to outrank "
            f"(page errors: {log.page_errors})")
        tab.click(f"#{switch['english']}")
        again, _ = open(route_of[chooser])
        active = _shown_language(again, switch)

    assert active == ["english"], (
        f"a reader on a zh-TW browser chose English on {chooser} and "
        f"reopened it; it came back in {active or 'no language'}.  A saved "
        "choice is supposed to outrank detection")
