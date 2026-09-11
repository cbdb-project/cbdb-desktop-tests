"""The route surface: every path the build registers, driven for real.

This is the regression net the rest of the suite sits on.  It reads the
routing table out of the shipped ``Code/*.go`` and then asks the running
binary about every entry, so a route that disappears, moves, or changes
method in a future build fails here first -- without anyone maintaining a
hand-written list that drifts from the code.

Nothing here runs a form query, so the file is fast.  One endpoint it
touches is not read-only, though, and saying otherwise would set a trap
for the next increment: ``GET /api/browser/person/{id}/kinship``
truncates and rewrites ``ZZ_KIN_LIST``, ``ZZ_KIN_LIST_TMP``,
``ZZ_SCRATCH_KIN`` and ``ZZ_SCRATCH_KINNET``
(``browser_form_backend.go:1889``) before running its traversal.  Any
test that reads those tables must run its own kinship request first
rather than trusting what a previous test left there.
"""
from __future__ import annotations

import pytest

from cbdb_desktop import routes as R
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.staging import AppLayout

pytestmark = pytest.mark.app


@pytest.fixture(scope="module")
def routes(layout: AppLayout) -> list[R.Route]:
    found = R.all_routes(layout)
    assert found, "no routes were parsed out of Code/*.go"
    return found


def _ids(routes: list[R.Route]) -> list[str]:
    return [f"{'/'.join(r.methods)} {r.path}" for r in routes]


# ---------------------------------------------------------------------------
# the routing table itself
# ---------------------------------------------------------------------------

def test_the_build_registers_the_expected_route_surface(routes, layout: AppLayout):
    """A pinned count and shape, so a lost form cannot pass unnoticed.

    The numbers are deliberately exact.  A build that adds a route should
    fail this test and be looked at; a build that quietly drops eight of
    them must not slip through because a floor was set low enough to
    accommodate it.
    """
    assert len(routes) == 142, "\n".join(_ids(routes))

    methods = sorted({m for r in routes for m in r.methods})
    assert methods == ["GET", "POST"], methods

    per_form = {}
    for route in routes:
        per_form[route.form] = per_form.get(route.form, 0) + 1
    assert per_form == {
        "associations": 8, "assocpairs": 10, "browser": 14,
        "cbdb_navigation_backend": 5, "entry": 10, "groupdata": 8,
        "indexaddr": 5, "kinship": 15, "main": 8, "networks": 20,
        "office": 8, "places": 9, "qbe_handlers": 3, "status": 11,
        "texts": 8,
    }, per_form

    # Every route declares exactly one method: mux would otherwise accept
    # a verb the handler never expected.  Pinned here, in the parse test,
    # rather than by probing the network -- see the PATCH probe below for
    # why the two questions are kept apart.
    multi = [r for r in routes if len(r.methods) != 1]
    assert not multi, _ids(multi)

    assert {r.path for r in routes if r.methods == ("GET",)} & \
        {r.path for r in routes if r.methods == ("POST",)} == set(), \
        "a path registers both GET and POST; the probe assumptions need review"


def test_no_two_routes_collide(routes):
    """The same path registered twice means one handler is unreachable.

    gorilla/mux matches in registration order, so a duplicate is dead
    code -- and dead code that looks live is how a "fixed" handler stays
    unused for a release.
    """
    seen: dict[tuple[str, str], R.Route] = {}
    collisions = []
    for route in routes:
        for method in route.methods:
            key = (method, route.path)
            if key in seen:
                collisions.append(f"{method} {route.path}: "
                                  f"{seen[key].source} and {route.source}")
            else:
                seen[key] = route
    assert not collisions, "\n".join(collisions)


def test_every_registered_page_is_served(app: CbdbApp, routes):
    """Every GET page answers with HTML -- no 404s, no template errors."""
    failures = []
    for route in R.concrete_get_pages(routes):
        response = app.get(route.path)
        if response.status_code != 200:
            failures.append(f"{route.path} -> {response.status_code} "
                            f"({route.source})")
            continue
        body = response.text
        if "<html" not in body.lower():
            failures.append(f"{route.path} -> not HTML ({route.source})")
        if "Template error" in body or "Under Construction" in body:
            failures.append(f"{route.path} -> {body[:120]!r} ({route.source})")
    assert not failures, "\n".join(failures)


def test_every_registered_api_route_still_exists(app: CbdbApp, routes):
    """Each API route answers 405 to a verb no route registers.

    gorilla/mux returns 405 only when the *path* matched but the method
    did not, so one PATCH proves the route is still there while being
    incapable of reaching a handler.

    Two alternatives were rejected.  POSTing an empty body to every
    endpoint took 143 seconds -- an unfiltered query is a query over the
    whole database -- and left the shared ZZ_SCRATCH_* tables full of
    whatever those probes computed, quietly making every later test
    order-dependent.  Probing with "the other verb" is cheap but assumes
    each path registers exactly one method; the day a build registers
    both GET and POST on a path, that probe would silently start
    invoking the handler and reintroduce the same problem.  PATCH cannot.
    """
    # A route that declared PATCH would turn the probe into a real call.
    # No build has done so, but the probe must not depend on another
    # test having noticed -- especially under -k selection.
    patchable = [r for r in routes if "PATCH" in r.methods]
    assert not patchable, \
        f"these routes accept PATCH; the probe would invoke them: {_ids(patchable)}"

    failures = []
    for route in routes:
        if not route.path.startswith("/api/") or "{" in route.path:
            continue
        response = app.request("PATCH", route.path)
        if response.status_code == 404:
            failures.append(f"{route.path} is gone: PATCH -> 404 ({route.source})")
        elif response.status_code != 405:
            failures.append(f"PATCH {route.path} -> {response.status_code}, "
                            f"expected 405 ({route.source})")
    assert not failures, "\n".join(failures)


def test_the_per_person_browser_routes_exist(app: CbdbApp, routes):
    """The wildcard routes, probed with a person the data really has.

    These are the only routes with a path variable, and they are all
    read-only GETs about one person, so unlike the form queries they are
    cheap enough to call for real.
    """
    wildcards = [r for r in routes
                 if "{id}" in r.path and r.path.startswith("/api/")]
    # The person summary plus ten sub-resources.  (The build's twelfth
    # wildcard is the navigation catch-all /{page}, which is not an API
    # route and is covered by the navigation tests.)
    assert len(wildcards) == 11, _ids(wildcards)

    failures = []
    for route in wildcards:
        # 1762 is Wang Anshi, present in every edition of the data.
        path = R.probe_path(route, person_id=1762)
        response = app.get(path)
        if response.status_code != 200:
            failures.append(f"{path} -> {response.status_code} ({route.source})")
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# navigation
# ---------------------------------------------------------------------------

def test_every_navigation_shortcut_redirects_to_its_page(app: CbdbApp,
                                                         layout: AppLayout):
    """The /{page} map, driven end to end.

    The map lives only in HandlePageNavigation, so it is read from there
    and every entry is followed: a shortcut that points at a page the
    build no longer serves is a broken button on the front page.
    """
    mapping = R.page_map(layout)
    assert mapping, "the navigation page map could not be read"

    failures = []
    for shortcut, target in mapping.items():
        response = app.get(f"/{shortcut}", allow_redirects=False)
        if response.status_code != 303:
            failures.append(f"/{shortcut} -> {response.status_code}, expected 303")
            continue
        if response.headers.get("Location") != f"/{target}":
            failures.append(f"/{shortcut} -> {response.headers.get('Location')}, "
                            f"expected /{target}")
            continue
        followed = app.get(f"/{shortcut}")
        if followed.status_code != 200 or "<html" not in followed.text.lower():
            failures.append(f"/{shortcut} -> {target} -> {followed.status_code}")
    assert not failures, "\n".join(failures)


def test_an_unknown_page_is_a_clean_404(app: CbdbApp):
    response = app.get("/no-such-page")
    assert response.status_code == 404
    assert "Page not found" in response.text


def test_the_query_builder_is_only_reachable_by_its_exact_path(app: CbdbApp,
                                                               layout: AppLayout):
    """/QBE works; /qbe does not -- pinned because it is a real trap.

    Every other form has a lower-case shortcut in the navigation map.
    QBE was added without one, so the URL a user would guess 404s.  This
    test documents the asymmetry rather than asserting it is correct: if
    a future build adds the shortcut, it fails and gets updated.
    """
    assert app.get("/QBE").status_code == 200
    assert "qbe" not in R.page_map(layout)
    assert app.get("/qbe").status_code == 404


def test_the_front_page_links_to_every_form(app: CbdbApp, layout: AppLayout):
    """Each shortcut in the map is actually offered by the navigation page."""
    body = app.get("/").text
    # A bare substring test would pass on a page that merely mentions the
    # word -- "status" appears in an element id and in two scripts, so
    # deleting the Status button entirely would go unnoticed.  The page
    # links relatively ("../entry"), which resolves from both / and
    # /navigation.
    missing = [name for name in R.page_map(layout)
               if f'href="../{name}"' not in body and f'href="/{name}"' not in body]
    assert not missing, f"navigation page has no link to: {missing}"


# ---------------------------------------------------------------------------
# static assets and pickers
# ---------------------------------------------------------------------------

def test_every_picker_is_served_from_the_shipped_file(app: CbdbApp,
                                                      layout: AppLayout):
    """The picker routes serve the exact files the archive shipped."""
    files = R.picker_files(layout)
    assert len(files) == 8, files

    for name in files:
        on_disk = layout.templates_dir / "pickers" / name
        assert on_disk.is_file(), f"{name} is registered but not shipped"

        response = app.get(f"/Templates/pickers/{name}")
        assert response.status_code == 200, f"{name} -> {response.status_code}"
        assert response.content == on_disk.read_bytes(), \
            f"{name} served content that differs from the shipped file"


def test_the_stylesheet_is_served(app: CbdbApp, layout: AppLayout):
    response = app.get("/static/cbdb_styles.css")
    assert response.status_code == 200
    assert response.content == (layout.static_dir / "cbdb_styles.css").read_bytes()


def test_static_files_come_from_the_working_directory_not_the_flag(
        layout: AppLayout):
    """Two handlers claim /static/, and the first one registered wins.

    cbdb_navigation_backend.go serves ./Static/ relative to the process's
    working directory; main.go registers the same prefix again from the
    -static flag, and never gets a request.  The suite depends on this:
    the driver only serves the right stylesheet because it launches the
    app with the staged tree as its cwd.  Pinned so that a build which
    reorders the two registrations -- making -static suddenly load-bearing
    -- is noticed here rather than through a mysteriously blank page.
    """
    prefixes = []
    for path in layout.go_sources():
        found = R.parse_path_prefixes(path.read_text(encoding="utf-8",
                                                     errors="replace"))
        prefixes.extend((path.name, prefix) for prefix in found)

    assert [p for _, p in prefixes] == ["/static/", "/static/"], prefixes
    assert prefixes[0][0] == "cbdb_navigation_backend.go", \
        f"the winning /static/ registration moved: {prefixes}"


@pytest.mark.parametrize("attempt", [
    "/static/%2e%2e/Data/CBDB.db",
    "/static/%2e%2e%2fData%2fqbe_schema.json",
    "/static/%2e%2e/Bin/cbdb.exe",
    "/static/..%2f..%2fData%2fCBDB.db",
])
def test_static_serving_does_not_escape_its_directory(app: CbdbApp, attempt: str):
    """A traversal must not reach the database or the binary.

    The dot segments are percent-encoded on purpose: written plainly,
    urllib3 collapses them before the request leaves the test process, so
    the server never sees a traversal and the test proves nothing.
    Redirects are followed for the same reason -- mux answers some of
    these with a 301 to the cleaned path, and it is the *destination*
    that must not serve the file.
    """
    response = app.get(attempt)
    assert response.status_code == 404, \
        f"{attempt} -> {response.status_code} ({len(response.content)} bytes)"
    assert b"SQLite format" not in response.content[:64]
    assert not response.content.startswith(b"MZ")


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def test_health_has_the_documented_shape(app: CbdbApp):
    payload = app.json("GET", "/api/health")
    assert set(payload) == {"status", "database_connected", "version",
                            "last_update"}, sorted(payload)
    assert payload["status"] == "ok"
    assert payload["database_connected"] is True
    # Both are hardcoded in the handler rather than derived from the data,
    # so they are a build stamp, not a data stamp.  Pinned so that a build
    # which starts deriving them is noticed.
    assert payload["version"] == "BI"
    assert payload["last_update"] == "2025-05-20"
