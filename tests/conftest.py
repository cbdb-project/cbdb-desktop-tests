"""pytest fixtures for the CBDB-Desktop test suite.

The staged distribution is treated as a **pristine master**: the
application never runs against it.  Each session copies ``Data/CBDB.db``
into ``work/run/<id>/`` and launches the app there, because the app is
not read-only -- every form query rewrites the shared ``ZZ_SCRATCH_*``
tables in whatever database it was pointed at.  That split gives two
things at once: a stable master to use as an oracle, and a working copy
whose contamination cannot leak into the next session.

Session scopes:

  * ``config``      -- resolved .env / environment settings
  * ``layout``      -- the staged CBDB-Desktop tree (pristine master)
  * ``run_dir``     -- per-session scratch directory, removed at teardown
  * ``app_db``      -- the working copy of CBDB.db the app runs against
  * ``sqlite_conn`` -- read-only oracle over the *master* database
  * ``artifacts_dir`` -- where tests drop payloads worth keeping
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
import time
import warnings
from pathlib import Path

import pytest

from cbdb_desktop.config import REPO_ROOT, Config, MissingConfig, load_config
from cbdb_desktop.staging import AppLayout, StagingError, _rmtree, stage


def pytest_addoption(parser):
    parser.addoption(
        "--restage", action="store_true", default=False,
        help="Force a fresh unpack of CBDB_DESKTOP_ZIP even if one is cached.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "app: test drives the real cbdb.exe over HTTP (slow)")
    config.addinivalue_line(
        "markers", "slow: test runs a full-dataset query (minutes)")


@pytest.fixture(scope="session")
def config() -> Config:
    return load_config()


@pytest.fixture(scope="session")
def layout(request, config: Config) -> AppLayout:
    """The staged distribution under test -- the pristine master.

    Staging failures are hard errors, not skips: a suite that silently
    tests nothing is worse than one that fails loudly.
    """
    try:
        return stage(config, force=request.config.getoption("--restage"))
    except (MissingConfig, StagingError) as exc:
        pytest.fail(f"cannot stage the distribution under test: {exc}", pytrace=False)


_RUN_DIR_RE = re.compile(r"\d{8}-\d{6}-(\d+)\Z")


def _process_is_alive(pid: int) -> bool:
    """True if a process with this id currently exists.

    Used only to decide whether a run directory is abandoned, so the safe
    answer when anything is uncertain is True -- keeping a stale directory
    costs disk space; deleting a live one costs a running session its
    database.
    """
    if pid <= 0:
        return True
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER (87) means "no such process"; any
            # other failure (access denied, say) means it probably exists.
            return ctypes.get_last_error() != 87
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _prune_stale_runs(run_root: Path, *, max_age_s: float = 24 * 3600) -> None:
    """Reclaim run directories a crashed session left behind.

    Each holds a 1.2 GB copy of the database, so silently leaking one per
    crash fills a disk within a week of bad days -- but deleting one that
    is still in use would pull the database out from under a running
    session, so a directory is removed only when its owning process is
    demonstrably gone.

    The owner's pid is in the directory name.  When that cannot be read,
    the fallback is age -- taken from the newest file *inside*, never the
    directory's own mtime, because SQLite writing into an existing copy
    leaves the directory's timestamp untouched.
    """
    if not run_root.is_dir():
        return
    cutoff = time.time() - max_age_s
    for candidate in run_root.iterdir():
        try:
            if not candidate.is_dir():
                continue
            match = _RUN_DIR_RE.match(candidate.name)
            if match:
                pid = int(match.group(1))
                if pid == os.getpid():
                    continue
                # An owner that is still running keeps its directory --
                # unless the directory is old enough that the pid has
                # almost certainly been reused by an unrelated process
                # (no pytest session runs for a week), or the pid belongs
                # to the reserved range no user process can occupy.
                if pid > 4 and _process_is_alive(pid) and                         candidate.stat().st_mtime > time.time() - 7 * 24 * 3600:
                    continue
            else:
                newest = candidate.stat().st_mtime
                for child in candidate.rglob("*"):
                    try:
                        newest = max(newest, child.stat().st_mtime)
                    except OSError:
                        continue
                if newest >= cutoff:
                    continue
            _rmtree(candidate)
        except (OSError, ValueError, StagingError):
            continue


@pytest.fixture(scope="session")
def run_dir(config: Config) -> Path:
    """Scratch directory for this session, removed unless CBDB_KEEP_RUN_DIR.

    Teardown is loud on failure: a surviving ``cbdb.exe`` holding the
    copied database keeps a 1.2 GB file alive, and a silent
    ``ignore_errors`` would hide that until the disk filled.
    """
    _prune_stale_runs(config.run_root)
    path = config.run_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        if config.keep_run_dir:
            print(f"\nrun directory kept (CBDB_KEEP_RUN_DIR=1): {path}")
        else:
            try:
                _rmtree(path)
            except StagingError as exc:
                warnings.warn(
                    f"could not remove the session run directory -- a "
                    f"{path.stat().st_size if path.exists() else 0}-byte tree "
                    f"is leaking at {path}: {exc}",
                    stacklevel=1,
                )


@pytest.fixture(scope="session")
def app_db(layout: AppLayout, run_dir: Path) -> Path:
    """A private copy of the shipped database for the app to write to.

    The app writes ``ZZ_SCRATCH_*`` on every query, so running it against
    the master would make the staged tree drift from the archive and make
    results order-dependent between sessions.
    """
    target = run_dir / "CBDB.db"
    shutil.copyfile(layout.db, target)
    return target


@pytest.fixture(scope="session")
def sqlite_conn(layout: AppLayout, config: Config):
    """Read-only oracle over the *master* database.

    ``immutable=1`` promises SQLite the file will not change under it,
    which is true of the master by construction -- and it means the
    connection creates no ``-shm``/``-wal`` sidecars, so merely consulting
    the oracle cannot make the staged tree differ from the archive.

    That promise is checked, not assumed: with a ``-wal`` present,
    ``immutable=1`` makes SQLite *ignore* the log and silently serve
    pre-WAL data while ``PRAGMA quick_check`` still answers "ok" -- an
    oracle that lies quietly.  Under ``CBDB_APP_DIR`` the master may be a
    live tree, so the promise is dropped there.

    Scope rule for anything using this fixture: query **base** tables for
    invariants and cross-checks.  Never read ``ZZ_*`` tables, and never
    reproduce a backend's join/filter chain here -- that would test the
    transcription instead of the application.

    One deliberate exception: ``test_a_fresh_install_starts_with_no_working
    _state`` reads the ``ZZ_*`` tables precisely because their *contents in
    the shipped file* are what it is about (CBDB-D-005).  That is a
    question about the artefact, not about what a handler computed.
    """
    wal = layout.db.with_name(layout.db.name + "-wal")
    if config.app_dir_override is not None:
        uri = layout.db.resolve().as_uri() + "?mode=ro"
    else:
        if wal.exists():
            pytest.fail(
                f"a write-ahead log sits beside the master database ({wal}).\n"
                "Something ran the application against the pristine tree "
                "instead of a per-session copy.  Restage with --restage.",
                pytrace=False)
        uri = layout.db.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def app(layout: AppLayout, app_db: Path, config: Config, artifacts_dir: Path):
    """The real cbdb.exe, running against this session's database copy.

    Session-scoped: startup opens a 1.2 GB database, so one server serves
    the whole run.  It depends on ``app_db`` (not merely on ``layout``)
    so that pytest tears the server down *before* the run directory that
    holds its database -- the other order leaves a locked file behind.

    The log goes to ``artifacts/``, not into the run directory: the run
    directory is deleted at teardown, which would destroy the post-mortem
    record moments after writing it.
    """
    from cbdb_desktop.app import AppError, CbdbApp

    log_path = artifacts_dir / f"cbdb-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.log"
    server = CbdbApp(layout, app_db, config, log_path=log_path)
    try:
        server.start()
    except (AppError, OSError) as exc:
        pytest.fail(f"could not start the application under test: {exc}",
                    pytrace=False)
    try:
        yield server
    finally:
        server.stop()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Remember each test's outcome so teardown can stay quiet on failure."""
    outcome = yield
    setattr(item, f"_report_{call.when}", outcome.get_result())


@pytest.fixture(autouse=True)
def _app_still_alive(request):
    """Turn "the server died three tests ago" into a failure that says so.

    Only speaks up for a test that otherwise passed: a test that already
    failed does not need the same news reported twice, and the request
    path folds ``check_alive`` into its own errors anyway.
    """
    yield
    server = request.node.funcargs.get("app")
    if server is None:
        return
    report = getattr(request.node, "_report_call", None)
    if report is not None and not report.passed:
        return
    server.check_alive()


@pytest.fixture(scope="session")
def artifacts_dir() -> Path:
    """Committed-artifact-free directory for payloads worth inspecting."""
    path = REPO_ROOT / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path
