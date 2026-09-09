"""Launch and drive the real ``cbdb.exe``.

This is the whole point of the suite: the code under test is the shipped
Go binary, so the tests speak to it the way a user's browser does -- over
HTTP, against the real 1.2 GB database.  Nothing here interprets or
re-implements what the application does with a request.

Three details of the application shape this module, all read out of
``Code/main.go``:

* It logs through Go's ``log`` package, which writes to **stderr**, and
  announces its address as ``CBDB server started: http://localhost:<port>``.
  Passing ``-port 0`` lets the OS pick a free port, so parallel sessions
  never collide -- but the port is then only discoverable from that line,
  which means the output must be consumed continuously.  Go logs every
  request it serves; a full pipe buffer would stall the server mid-suite,
  which is a very confusing hang to debug.

* It opens the browser on startup (``openBrowser``), and only *logs* the
  failure if it cannot.  Launching it with a PATH that cannot resolve
  ``rundll32`` therefore suppresses the window with no other effect --
  system DLLs load from the default search path, not from PATH.

* Its defaults are relative (``Data/CBDB.db``, ``Templates/*.html``,
  ``Static``), and ``registerPickerRoutes`` derives ``Templates/pickers``
  from the ``-templates`` value, so the process must run with the staged
  tree as its working directory.

Failures here must always carry the application's own output: the
difference between "connection refused" and the ``log.Fatalf`` line that
explains why is the difference between a debuggable failure and an hour
of guessing.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .config import Config
from .staging import AppLayout

# "CBDB server started: http://localhost:57324" -- main.go
_PORT_RE = re.compile(r"CBDB server started:\s*http://localhost:(\d+)")

# Bounds on how long a single health probe may block while waiting for
# startup.  The overall budget is CBDB_STARTUP_TIMEOUT; this only keeps
# one attempt from swallowing all of it.
_HEALTH_PROBE_TIMEOUT = 10.0


class AppError(RuntimeError):
    """The application would not start, or died while the suite used it."""


@dataclass
class AppLog:
    """Everything the application wrote, kept for failure messages."""

    lines: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, line: str) -> None:
        with self._lock:
            self.lines.append(line)

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self.lines)

    def text(self, limit: int | None = None) -> str:
        lines = self.snapshot()
        return "".join(lines if limit is None else lines[-limit:])

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text(), encoding="utf-8")
        return path


class CbdbApp:
    """A running ``cbdb.exe``, addressable over HTTP.

    Use as a context manager, or call :meth:`start` and :meth:`stop`.
    The process is always reaped on the way out -- a leaked server holds
    the session's 1.2 GB database copy open, which on Windows makes the
    file undeletable and defeats every cleanup after it.
    """

    def __init__(self, layout: AppLayout, db_path: Path, config: Config,
                 *, log_path: Path | None = None):
        self.layout = layout
        self.db_path = Path(db_path)
        self.config = config
        self.log_path = log_path
        self.log = AppLog()
        self.port: int | None = None
        self.process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._reader_error: BaseException | None = None
        self._output_done = threading.Event()
        self._port_found = threading.Event()
        self._session = requests.Session()

    # -- lifecycle ---------------------------------------------------------

    def argv(self) -> list[str]:
        """The command line, mirroring main.go's own flag names.

        Every path is given explicitly rather than relying on the
        defaults, so that a change to those defaults shows up as a test
        failure instead of silently repointing the application -- most
        importantly at the pristine master database.
        """
        return [
            str(self.layout.exe),
            "-port", "0",
            "-db", str(self.db_path.resolve()),
            "-templates", str(Path("Templates") / "*.html"),
            "-static", "Static",
            "-schema", str(Path("Data") / "qbe_schema.json"),
        ]

    def _environment(self) -> dict[str, str] | None:
        if not self.config.suppress_browser:
            return None
        env = dict(os.environ)
        # openBrowser() resolves "rundll32" through PATH and merely logs
        # the failure.  Emptying PATH costs the app nothing else: its own
        # DLL imports are resolved by the loader, not by PATH.
        env["PATH"] = ""
        return env

    def start(self) -> "CbdbApp":
        if self.process is not None:
            raise AppError("this CbdbApp is already running")
        if not self.db_path.is_file():
            raise AppError(f"database to run against does not exist: {self.db_path}")

        # A previous run's port must never survive into this one: a stale
        # value would be accepted immediately, and the ephemeral port may
        # by now belong to a different server entirely.
        self.port = None
        self.log = AppLog()
        self._reader_error = None
        self._port_found = threading.Event()
        self._output_done = threading.Event()

        try:
            process = subprocess.Popen(
                self.argv(),
                cwd=str(self.layout.root),
                env=self._environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise AppError(f"could not launch {self.layout.exe}: {exc}") from exc

        self.process = process
        # From here on the child exists, so every failure path must reap
        # it -- including a failure to start the reader thread.
        try:
            self._reader = threading.Thread(
                target=self._drain, args=(process,), daemon=True,
                name="cbdb-log-reader")
            self._reader.start()

            deadline = time.monotonic() + self.config.startup_timeout
            self._await_port(deadline)
            self._await_health(deadline)
        except BaseException:
            self.stop()
            raise
        return self

    def _drain(self, process: subprocess.Popen[str]) -> None:
        """Consume the application's output for as long as it runs.

        Takes the process as an argument rather than reading
        ``self.process``: ``stop()`` clears that attribute, and a fast
        failure can call ``stop()`` before this thread has been scheduled
        at all -- which would kill the reader with an AttributeError and
        lose the very output the failure message needs.
        """
        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.log.add(line)
                if self.port is None:
                    match = _PORT_RE.search(line)
                    if match:
                        self.port = int(match.group(1))
                        self._port_found.set()
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            self._reader_error = exc
        finally:
            # Whatever happened, no one may block waiting for more output.
            self._port_found.set()
            self._output_done.set()

    def _fail(self, summary: str) -> AppError:
        return AppError(f"{summary}\n--- application output ---\n{self.log.text()}")

    def _await_port(self, deadline: float) -> None:
        while True:
            if self._port_found.wait(min(0.25, max(0.0, deadline - time.monotonic()))):
                if self.port is not None:
                    return
                # The event is also set when the output ends, so that no
                # one waits forever on a stream that will never speak
                # again.  Distinguish the two here rather than looping.
                if self._reader_error is not None:
                    raise self._fail(
                        f"the reader thread died before a port was announced: "
                        f"{self._reader_error!r}")
                if self._output_done.is_set():
                    raise self._fail(
                        "cbdb.exe closed its output before announcing a port")
            if self.process is not None and self.process.poll() is not None:
                raise self._fail(
                    f"cbdb.exe exited with code {self.process.returncode} before "
                    "it announced a port")
            if time.monotonic() >= deadline:
                raise self._fail(
                    f"cbdb.exe did not announce a port within "
                    f"{self.config.startup_timeout:g}s (CBDB_STARTUP_TIMEOUT)")

    def _await_health(self, deadline: float) -> None:
        """Wait until /api/health answers, then insist that it is healthy.

        Shares one deadline with the port wait, so CBDB_STARTUP_TIMEOUT is
        the whole startup budget rather than the budget per phase.
        """
        last: Exception | None = None
        while True:
            if self.process is not None and self.process.poll() is not None:
                raise self._fail(
                    f"cbdb.exe exited with code {self.process.returncode} while "
                    "starting up")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._fail(
                    f"cbdb.exe never became healthy on {self.base_url} within "
                    f"{self.config.startup_timeout:g}s (CBDB_STARTUP_TIMEOUT): "
                    f"{last}")
            try:
                response = self._session.get(
                    self.url("/api/health"),
                    timeout=min(_HEALTH_PROBE_TIMEOUT, remaining))
                payload = response.json()
                if response.status_code == 200 and payload.get("database_connected"):
                    return
                raise self._fail(
                    f"/api/health reported {response.status_code} {payload!r}")
            except (requests.RequestException, ValueError) as exc:
                last = exc
                time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))

    def stop(self, *, timeout: float = 20.0) -> None:
        """Reap the process and release everything it held.

        Safe to call twice, and safe to call from a fixture finalizer.
        The process reference is only cleared once the child has actually
        been waited for, so a failure partway through cannot leave the
        object claiming to be stopped while a server is still running.

        On Windows ``terminate()`` is ``TerminateProcess`` -- the same
        thing ``kill()`` does -- so the app never runs its ``defer
        db.Close()``.  That is fine for a throwaway copy of the database:
        the kernel releases the file handle before ``wait()`` returns,
        which is what makes the copy deletable again.
        """
        process = self.process
        try:
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        # Unkillable child.  Raising here would replace the
                        # real test failure with a finalizer error, so this
                        # warns instead -- and deliberately keeps
                        # self.process set, so `alive` keeps telling the
                        # truth about what is still running.
                        warnings.warn(
                            f"cbdb.exe (pid {process.pid}) survived kill(); it "
                            f"still holds {self.db_path}",
                            stacklevel=2)
                        return
                except OSError:
                    # Raced with the child exiting; reap it either way.
                    try:
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        warnings.warn(f"could not reap cbdb.exe (pid {process.pid})",
                                      stacklevel=2)
                        return
            if process is not None:
                self.process = None
        finally:
            # The dead child closes the write end of the pipe, so the
            # reader reaches EOF on its own.  Join it BEFORE closing the
            # handle: closing a file another thread is reading from
            # discards buffered output and raises in that thread -- and
            # the output being discarded is the app's dying words.
            if self._reader is not None:
                self._output_done.wait(timeout=5)
                self._reader.join(timeout=5)
                if not self._reader.is_alive():
                    self._reader = None
            if process is not None and process.stdout is not None:
                try:
                    process.stdout.close()
                except (OSError, ValueError):
                    pass
            self.port = None
            self._session.close()
            self._session = requests.Session()
            if self.log_path is not None:
                try:
                    self.log.save(self.log_path)
                except OSError:
                    pass

    def __enter__(self) -> "CbdbApp":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()

    # -- addressing --------------------------------------------------------

    @property
    def base_url(self) -> str:
        if self.port is None:
            raise AppError("the application has not announced a port yet")
        return f"http://localhost:{self.port}"

    def url(self, path: str) -> str:
        return self.base_url + path

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def check_alive(self) -> None:
        """Raise with the application's own output if it has died.

        Without this a dead server turns every later test into an opaque
        ConnectionError; with it, the first failure carries the panic or
        SQL error the application printed.
        """
        if self.process is not None and self.process.poll() is not None:
            raise self._fail(
                f"cbdb.exe exited with code {self.process.returncode} during the run")

    def wait_for_log(self, pattern: str, *, timeout: float = 15.0) -> str | None:
        """Wait for a line matching ``pattern``; return it, or None.

        Some of what the application does is only observable in its log,
        and not all of it happens before startup finishes -- openBrowser()
        runs in a goroutine after a 300 ms sleep, so a test that reads the
        log the instant the port appears races it.
        """
        expr = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while True:
            for line in self.log.snapshot():
                if expr.search(line):
                    return line
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.1)

    # -- requests ----------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json: Any = None, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, json=json, **kwargs)

    #: Every ``(method, path)`` any instance has requested in this
    #: process, with numeric path segments folded to ``{id}``.  A class
    #: attribute on purpose: the coverage gate in test_controls.py has
    #: to see the whole session, and three separate ``CbdbApp`` objects
    #: serve one run (the session's, the index-address file's, and the
    #: ones the driver tests start and stop).
    #:
    #: Recording here rather than counting on each test to declare what
    #: it drives is the difference between measured coverage and claimed
    #: coverage.  It costs one set insertion per request.
    requested: set[tuple[str, str]] = set()

    #: The status that means the *router* answered and the handler never
    #: ran.  A request that got it did not exercise the endpoint, so it
    #: must not count towards coverage.
    #:
    #: This is not a detail.  ``test_routes.py`` proves every registered
    #: route still exists by sending one ``PATCH`` to each and expecting
    #: 405 -- and gorilla/mux answers 405 *without entering the
    #: handler*, which is exactly why PATCH was chosen for the probe.
    #: While ``requested`` recorded that, one probe marked every
    #: ``/api/`` path driven for ever, the coverage gate reported 105
    #: reachable / 105 covered / 0 gaps, and fourteen endpoints that had
    #: never had a real request made to them were inside that 100%.
    #: Measured coverage that counts a 405 is claimed coverage wearing a
    #: number.
    #:
    #: 405 and *only* 405.  404 was in this set for one commit and that
    #: was wrong: a handler can answer 404 deliberately -- this build's
    #: ``/api/browser/person/{id}`` does for a person that does not
    #: exist, and a test drives exactly that -- so excluding 404 would
    #: discard a real exercise and invent a gap.  A 404 from an
    #: *unregistered* path is a different problem, and
    #: ``test_every_endpoint_the_pages_call_is_a_route_the_build_registers``
    #: is the test that owns it.
    _ROUTER_REFUSED = frozenset({405})

    @staticmethod
    def _coverage_key(method: str, path: str) -> tuple[str, str]:
        base = path.split("?", 1)[0]
        folded = "/".join("{id}" if segment.isdigit() else segment
                          for segment in base.split("/"))
        return method.upper(), folded

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """One HTTP call, with the application's health folded into errors."""
        kwargs.setdefault("timeout", self.config.http_timeout)
        try:
            response = self._session.request(method, self.url(path), **kwargs)
        except requests.RequestException as exc:
            self.check_alive()
            raise self._fail(f"{method} {path} failed: {exc}") from exc
        # Recorded after the answer, and only when the router did not
        # refuse it.  What this records is that a handler *ran* for the
        # path -- not that the control behind it worked: a 400 or a 500
        # counts, and should, because the handler ran and the run has
        # something to say about it.  Whether the answer was right is
        # every other test's job.
        if response.status_code not in self._ROUTER_REFUSED:
            CbdbApp.requested.add(self._coverage_key(method, path))
        return response

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        """A request whose response must be 200 and valid JSON."""
        response = self.request(method, path, **kwargs)
        if response.status_code != 200:
            raise AppError(
                f"{method} {path} -> HTTP {response.status_code}\n"
                f"{response.text[:2000]}")
        try:
            return response.json()
        except ValueError as exc:
            raise AppError(f"{method} {path} did not return JSON: "
                           f"{response.text[:2000]}") from exc
