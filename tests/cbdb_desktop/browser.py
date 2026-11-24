"""Drive the pages in a real browser, because some defects live only there.

Everything else in this suite talks HTTP.  That covers what the server
computes and nothing about what the user gets, and the difference is not
academic: three of the defects in the 2026-09-07 build are in the pages'
own JavaScript, where no HTTP test can see them.

* A control whose precondition is met and which stays greyed out.  The
  server is perfectly happy; the button does not work.
* An export that fires several downloads from one click.  The endpoint
  returns both files, identically, every time -- and the user gets one.
* A page that throws during load, after which nothing on it responds.
  None found in this build, and the cheapest possible check for it.

So this module launches Chromium (through Playwright, which is a
declared dependency) against the running application and reports three
things a page cannot hide: what it logged, what it downloaded, and which
of its controls are disabled.

**It is skipped, not failed, when the browser is missing.**  Playwright
needs its own Chromium download, which a fresh checkout will not have,
and a suite that fails because of that trains people to ignore it.
``available()`` says whether the tests can run; ``run_tests.ps1`` prints
it either way, so a run that skipped them says so.

**Two things it deliberately does not do.**

It does not replace the HTTP tests.  A browser test is slower by two
orders of magnitude and fails for reasons that have nothing to do with
the application; the HTTP suite stays the primary instrument and this is
for the layer it cannot reach.

And it is **not the user's browser**.  Downloads here are
auto-accepted, so the multiple-download block those handlers are really
up against does not happen -- headless Chromium saves both files.  Anything
that depends on a browser *permission* has to be checked another way
(for that one, by reading the page's own delivery code).  Recording that
limit is the point of writing it down.
"""
from __future__ import annotations

import contextlib
import json
import tempfile
from dataclasses import dataclass, field
from typing import Any, Iterator


def available() -> tuple[bool, str]:
    """``(usable, why not)`` for the browser tests."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, ("playwright is not installed -- "
                       "python -m pip install -r requirements.txt")
    try:
        with sync_playwright() as p:
            path = p.chromium.executable_path
    except Exception as exc:                       # noqa: BLE001 - reported
        return False, f"playwright could not start: {exc}"

    import os
    if not os.path.exists(path):
        return False, ("playwright has no Chromium installed -- "
                       "python -m playwright install chromium")
    return True, ""


@dataclass
class PageLog:
    """What one page said and did while a test drove it."""

    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    #: Files the browser accepted, by suggested filename.
    downloads: list[str] = field(default_factory=list)
    #: Downloads the *page* attempted, whether or not the browser took
    #: them.  Recorded by wrapping HTMLAnchorElement.prototype.click, so
    #: the page's intention and the browser's policy can be told apart.
    attempts: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.console_errors and not self.page_errors


_ATTEMPT_HOOK = """() => {
  window.__cbdbAttempts = [];
  const click = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    if (this.download) window.__cbdbAttempts.push(this.download);
    return click.apply(this, arguments);
  };
}"""

#: Which controls' disabled state a caller asks about.  Read off the
#: page rather than passed in, so a build that renames a button shows up
#: as a missing control rather than as a silently skipped assertion.
_STATE = """(ids) => Object.fromEntries(ids.map(id => {
  const e = document.getElementById(id);
  return [id, e === null ? 'MISSING' : (e.disabled ? 'disabled' : 'enabled')];
}))"""


#: Make ``navigator.languages`` -- and ``navigator.language``, its first
#: entry -- read as the list a test asked for, before any page script
#: runs.  Playwright's ``locale=`` sets a single tag; the application's
#: detection reads the whole ordered list and treats a bare ``zh`` at
#: the top differently from one further down, so a single tag cannot
#: pose the question the shipped code answers.  This is the same
#: substitution the developers' own note tells a tester to make by hand
#: ("change the browser's language order and reload the form").
_LANGUAGES_HOOK = """([tags]) => {
  Object.defineProperty(navigator, 'languages',
                        {get: () => tags, configurable: true});
  Object.defineProperty(navigator, 'language',
                        {get: () => tags[0], configurable: true});
}"""


@contextlib.contextmanager
def open_session(base_url: str, languages: list[str] | None = None):
    """One Chromium context, in which several pages can be opened in turn.

    ``open_page`` gives a page its own browser, which is the right unit
    for almost everything here and the wrong one for anything that
    travels *between* pages.  Since Build_20261102 the forms remember
    the reader's display language in ``localStorage``, which is per
    origin and per context: a choice made on one form is supposed to be
    there on the next, and two separate browsers can never show that.

    Yields ``open(path) -> (page, log)``.  Pages stay open until the
    context closes, so a test can act on one and then on another, the
    way a reader moves from form to form.

    ``languages`` replaces what the pages see as the browser's language
    preferences, in order, for every page opened in this context.
    """
    from playwright.sync_api import sync_playwright

    root = base_url.replace("localhost", "127.0.0.1").rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(downloads_path=tempfile.mkdtemp())
        try:
            context = browser.new_context(accept_downloads=True)
            if languages is not None:
                context.add_init_script(
                    f"({_LANGUAGES_HOOK})([{json.dumps(list(languages))}])")

            def open(path: str) -> tuple[Any, PageLog]:
                log = PageLog()
                page = context.new_page()
                page.on("console", lambda m: log.console_errors.append(
                    f"{m.type}: {m.text}") if m.type == "error" else None)
                page.on("pageerror", lambda e: log.page_errors.append(str(e)))
                page.on("download",
                        lambda d: log.downloads.append(d.suggested_filename))

                url = root + path
                page.goto(url, wait_until="networkidle")
                failure = page.evaluate(
                    "() => location.href.startsWith('chrome-error://')"
                    " ? document.querySelector('.error-code')?.textContent"
                    " : null")
                if failure:
                    raise RuntimeError(
                        f"the browser could not load {url}: {failure}.  The "
                        "application under test is not answering on that "
                        "address.")
                page.evaluate(_ATTEMPT_HOOK)
                return page, log

            yield open
        finally:
            browser.close()


@contextlib.contextmanager
def open_page(base_url: str, path: str,
              languages: list[str] | None = None) -> Iterator[tuple[Any, PageLog]]:
    """A Chromium page on ``base_url + path``, with a log of what it did.

    ``127.0.0.1``, never ``localhost``: the two are not always the same
    address family, and a Chromium that resolves the name to ``::1``
    against a server bound to IPv4 reports ERR_CONNECTION_REFUSED --
    which reads exactly like the application being broken.  From 20260925
    the application announces ``127.0.0.1`` itself and the driver passes
    that on, so the rewrite below is a no-op against it; it stays for a
    caller that builds a URL by hand, or a build that goes back.

    Each call gets its own browser, and therefore its own empty
    ``localStorage``: a language a previous test chose cannot leak into
    this one.  To follow a choice from one page to the next -- which is
    what Build_20261102's shared display language claims to do -- use
    ``open_session``.
    """
    with open_session(base_url, languages=languages) as open:
        yield open(path)


def control_states(page: Any, ids: list[str]) -> dict[str, str]:
    """``{id: 'enabled' | 'disabled' | 'MISSING'}``."""
    return page.evaluate(_STATE, ids)


def take_attempts(page: Any, log: PageLog) -> list[str]:
    """The downloads the page has attempted since the last call."""
    attempts = page.evaluate(
        "() => { const a = window.__cbdbAttempts || []; "
        "window.__cbdbAttempts = []; return a; }")
    log.attempts.extend(attempts)
    return attempts
