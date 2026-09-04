"""Tests for the driver, and the first tests of the running application.

Everything here needs a real ``cbdb.exe``, so the whole file is marked
``app``.  It answers the questions the rest of the suite takes for
granted: does the shipped binary start against the shipped database, does
it stay up, does it tell us where it is listening, and does it let go of
everything when told to stop.
"""
from __future__ import annotations

import shutil
import socket
import time
from pathlib import Path

import pytest

from cbdb_desktop.app import AppError, CbdbApp
from cbdb_desktop.config import Config
from cbdb_desktop.staging import AppLayout

pytestmark = pytest.mark.app


@pytest.fixture(scope="module")
def private_db(layout: AppLayout, tmp_path_factory):
    """A database that is not the session's, restorable between tests.

    Several tests here need their own server, and each database copy is
    1.2 GB.  Copying per test filled 2.5 GB per run into pytest's
    retained temp directories; one module-scoped location, refreshed on
    demand and deleted at teardown, keeps that at zero.

    The fixture yields a *callable*: calling it restores the file from
    the pristine master, so "fresh" really means fresh rather than
    "whatever the last server left behind".
    """
    target = tmp_path_factory.mktemp("private-db") / "CBDB.db"

    def fresh() -> Path:
        for suffix in ("-wal", "-shm"):
            sidecar = target.with_name(target.name + suffix)
            try:
                sidecar.unlink()
            except OSError:
                pass
        shutil.copyfile(layout.db, target)
        return target

    try:
        yield fresh
    finally:
        for suffix in ("", "-wal", "-shm"):
            candidate = target.with_name(target.name + suffix)
            try:
                candidate.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# the launch contract
# ---------------------------------------------------------------------------

def test_launch_arguments_name_every_path_explicitly(
        layout: AppLayout, app_db: Path, config: Config):
    """The app is told where everything is, never left to its defaults.

    main.go defaults -db/-templates/-static/-schema to paths relative to
    the working directory.  Relying on those would mean a changed default
    silently repoints the application -- and, worse, that the tests could
    end up exercising the pristine master database instead of this
    session's copy.
    """
    argv = CbdbApp(layout, app_db, config).argv()

    assert argv[0] == str(layout.exe)
    flags = dict(zip(argv[1::2], argv[2::2]))
    assert flags["-port"] == "0", "a fixed port would collide between sessions"
    assert Path(flags["-db"]) == app_db.resolve()
    assert Path(flags["-db"]) != layout.db, "the app must never open the master"
    assert flags["-templates"].endswith("*.html")
    assert flags["-static"] == "Static"
    assert flags["-schema"].endswith("qbe_schema.json")


def test_the_application_starts_and_reports_a_usable_port(app: CbdbApp):
    assert app.alive
    assert app.port and 1024 < app.port < 65536
    assert app.base_url == f"http://localhost:{app.port}"

    # The port it announced is the port it is actually listening on.
    with socket.create_connection(("localhost", app.port), timeout=10):
        pass

    assert "CBDB server started" in app.log.text()
    assert "Form routes registered successfully" in app.log.text()


def test_health_reports_a_connected_database(app: CbdbApp):
    payload = app.json("GET", "/api/health")
    assert payload["status"] == "ok"
    assert payload["database_connected"] is True
    # The build stamps a version and a data date; both are worth pinning
    # in the record of a run even though their values are the app's own.
    assert payload.get("version")
    assert payload.get("last_update")


def test_the_browser_window_is_suppressed(app: CbdbApp, config: Config):
    """A test run must not spawn a browser window per session.

    main.go always calls openBrowser() and only logs the failure, so the
    suppression is visible in the application's own log rather than in
    anything the app returns.
    """
    if not config.suppress_browser:
        pytest.skip("CBDB_SUPPRESS_BROWSER=0: the browser is meant to open")

    # openBrowser() runs in a goroutine 300 ms after startup, so the line
    # is not there the moment the port appears.
    line = app.wait_for_log("Could not open browser automatically", timeout=30)
    assert line, ("cbdb.exe managed to launch a browser despite the sanitised "
                  f"PATH.\n--- output ---\n{app.log.text()}")
    assert "rundll32" in line


def test_the_app_writes_only_to_its_own_database(app: CbdbApp, layout: AppLayout,
                                                 app_db: Path):
    """A real query must leave the pristine master untouched.

    Every form query rewrites shared ZZ_SCRATCH_* tables, so this is the
    property that keeps the master usable as an oracle and comparable to
    the archive.
    """
    def state(path: Path):
        wal = path.with_name(path.name + "-wal")
        return (path.stat().st_size, path.stat().st_mtime_ns,
                wal.stat().st_size if wal.exists() else None)

    master_wal = layout.db.with_name(layout.db.name + "-wal")
    master_before = state(layout.db)
    # The WAL exists from startup (openDatabase pings with _journal_mode=WAL),
    # so its mere existence proves nothing -- its growth does.
    copy_before = state(app_db)

    response = app.post("/api/entry/query", json={
        "entryCodes": [188],
        "addrIds": [], "addrSubUnits": False, "addressFrame": 1,
        "yearFilterType": "none",
    })
    assert response.status_code == 200

    assert state(layout.db) == master_before, \
        "the application wrote to the pristine master database"
    assert not master_wal.exists(), \
        f"the application opened the master database: {master_wal} appeared"
    assert state(app_db) != copy_before, \
        "the query left no trace in the session copy -- is the app using it?"


# ---------------------------------------------------------------------------
# failure handling
# ---------------------------------------------------------------------------

def test_a_missing_database_fails_before_launching_anything(
        layout: AppLayout, config: Config, tmp_path: Path):
    """A driver that hangs on a broken app is worse than one that fails."""
    server = CbdbApp(layout, tmp_path / "does-not-exist.db", config)
    with pytest.raises(AppError, match="does not exist"):
        server.start()
    assert server.process is None, "a process was launched despite the bad path"
    assert not server.alive


def test_an_app_that_cannot_open_its_database_is_reported(
        layout: AppLayout, config: Config, tmp_path: Path):
    """The application's own diagnosis reaches the test's failure message."""
    from dataclasses import replace

    broken = tmp_path / "CBDB.db"
    broken.write_bytes(b"this is not a SQLite database")

    server = CbdbApp(layout, broken, replace(config, startup_timeout=30))
    try:
        with pytest.raises(AppError) as exc:
            server.start()
    finally:
        server.stop()

    message = str(exc.value)
    assert "cbdb.exe" in message
    # Whatever the app said about the file must be in the message: that
    # is the difference between a debuggable failure and a mystery.
    assert "database" in message.lower()
    assert not server.alive


def test_the_failure_message_carries_the_applications_own_output(
        layout: AppLayout, config: Config, tmp_path: Path):
    """Even a failure the driver spots first must quote the app.

    The reader thread and the shutdown path used to race here: a fast
    failure could clear the process before the thread had read a single
    line, leaving "--- application output ---" followed by nothing.
    """
    from dataclasses import replace

    broken = tmp_path / "CBDB.db"
    broken.write_bytes(b"not a database")

    server = CbdbApp(layout, broken, replace(config, startup_timeout=30))
    try:
        with pytest.raises(AppError) as exc:
            server.start()
    finally:
        server.stop()

    message = str(exc.value)
    assert "--- application output ---" in message
    body = message.split("--- application output ---", 1)[1].strip()
    assert body, "the application's output was lost before it could be reported"
    assert "CBDB" in body or "database" in body.lower()


def test_stop_reaps_the_process_and_releases_the_database(
        layout: AppLayout, config: Config, private_db):
    """Nothing may hold the session's database once the server is stopped.

    A leaked cbdb.exe keeps a 1.2 GB copy locked, which then defeats the
    run-directory cleanup and, on Windows, any attempt to restage.
    """
    db = private_db()
    server = CbdbApp(layout, db, config)
    try:
        server.start()
        assert server.alive
        pid = server.process.pid if server.process else None
        assert pid
    finally:
        server.stop()
        server.stop()  # a second stop must be harmless

    assert not server.alive
    assert server.process is None

    # Renaming proves no handle survives: Windows refuses to rename a file
    # a running process still holds open.
    moved = db.with_name("moved.db")
    db.rename(moved)
    moved.rename(db)


def test_two_servers_can_run_side_by_side(
        layout: AppLayout, app_db: Path, config: Config, private_db):
    """-port 0 must really mean "any free port".

    Two builds get compared often enough that a hardcoded port would be a
    standing trap; this pins the property before anything relies on it.
    """
    with CbdbApp(layout, app_db, config) as first, \
            CbdbApp(layout, private_db(), config) as second:
        assert first.port != second.port
        assert first.json("GET", "/api/health")["database_connected"] is True
        assert second.json("GET", "/api/health")["database_connected"] is True


def test_a_restarted_driver_never_reuses_the_previous_port(
        layout: AppLayout, config: Config, private_db):
    """A stale port would silently address the wrong server.

    Ephemeral ports get recycled: after a stop, the number the last run
    announced may already belong to somebody else's process.
    """
    server = CbdbApp(layout, private_db(), config)
    try:
        server.start()
        first_port = server.port
        server.stop()

        assert server.port is None, "the stopped driver still points at a port"
        with pytest.raises(AppError, match="has not announced a port"):
            _ = server.base_url

        server.start()
        assert server.port is not None
        assert server.json("GET", "/api/health")["database_connected"] is True
        # The port in use is the one THIS run announced.  The number may
        # legitimately repeat -- the OS is free to hand back the same
        # ephemeral port -- so the assertion is about provenance, not
        # inequality: the log was reset at start(), so a stale port could
        # not appear in it.
        assert f"http://localhost:{server.port}" in server.log.text()
        assert first_port is not None
    finally:
        server.stop()


def test_the_driver_reports_a_dead_server_instead_of_a_connection_error(
        layout: AppLayout, config: Config, private_db):
    """When the app dies, the failure must say so and carry its output."""
    server = CbdbApp(layout, private_db(), config)
    try:
        server.start()
        assert server.process is not None
        server.process.kill()
        server.process.wait(timeout=20)

        with pytest.raises(AppError, match="exited with code"):
            server.get("/api/health")
    finally:
        server.stop()


def test_the_application_log_survives_the_run(app: CbdbApp, artifacts_dir: Path):
    """The post-mortem record must outlive the session that wrote it.

    Writing it into the run directory looked right and was useless: that
    directory is deleted at teardown, seconds after the log lands in it.
    """
    assert app.log_path is not None
    assert app.log_path.parent == artifacts_dir
    saved = app.log.save(app.log_path)
    assert "CBDB server started" in saved.read_text(encoding="utf-8")
