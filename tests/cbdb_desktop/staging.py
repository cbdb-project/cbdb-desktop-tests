"""Unpack the CBDB-Desktop distribution archive into a reusable work directory.

The archive is ~430 MB compressed and ~1.3 GB unpacked (``Data/CBDB.db``
alone is 1.2 GB), so staging is *content-addressed and cached*: a zip is
unpacked once per content fingerprint and every later session reuses that
directory.

Three properties matter, and each was learned from a way this can go
wrong:

* **Content-addressed, not mtime-addressed.**  The zip lives in Dropbox,
  which rewrites mtimes on re-download; an mtime key would restage a
  1.3 GB tree for a byte-identical archive, and could serve a rebuilt
  archive of the same size from the previous build's cache.  The key is a
  SHA-256 of the archive's bytes, and a cache hit re-verifies every
  immutable staged file against the archive's recorded CRCs (~0.1 s) --
  so a tree damaged after extraction is restaged, never served.

* **Crash-safe.**  Extraction goes to a process-unique ``.partial-*``
  directory; an existing tree is only moved aside once the new one is
  complete, and a build stranded by a crash mid-swap is recovered on the
  next run.  A failed or interrupted restage never destroys the build you
  already had.

* **Volatile files are not content.**  ``Data/CBDB.db`` is in WAL mode, so
  the app (and any reader) rewrites ``CBDB.db-wal`` / ``CBDB.db-shm`` and
  the database itself as soon as a query runs -- the app writes its
  ``ZZ_SCRATCH_*`` tables into it.  Those three are extracted but marked
  volatile in the manifest and excluded from the integrity comparison.
  The shipped sidecars do not survive staging -- a non-empty WAL is
  checkpointed into the database first -- so the staged master is always a
  clean, self-contained database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path

from .archives import Archive, ArchiveError
from .config import Config, load_config

MANIFEST_NAME = "_stage_manifest.json"
MANIFEST_VERSION = 2

# Files the application rewrites in place.  Present in the staged tree,
# excluded from every integrity comparison.
VOLATILE_ENTRIES = frozenset({
    "Data/CBDB.db",
    "Data/CBDB.db-wal",
    "Data/CBDB.db-shm",
})

# Matched on the *basename*, case-insensitively: Windows paths are
# case-insensitive and a future build could nest the tree one level deeper
# under the archive root.  Getting this wrong is silent -- the database
# would be compared byte-for-byte and every run after the first would fail
# with a confusing size mismatch -- so the match is deliberately loose.
_VOLATILE_BASENAMES = frozenset(name.rsplit("/", 1)[-1].lower()
                                for name in VOLATILE_ENTRIES)


def is_volatile(member_name: str) -> bool:
    """True if the application rewrites this archive member in place."""
    return member_name.rsplit("/", 1)[-1].lower() in _VOLATILE_BASENAMES

# SQLite sidecars do not survive staging: a -shm from another machine is
# meaningless, and a WAL left beside the master would make the oracle's
# immutable=1 connection silently ignore it.  A *non-empty* WAL is
# checkpointed into the database first -- deleting it would throw away
# committed data.
_DISCARD_AFTER_EXTRACT = ("Data/CBDB.db-wal", "Data/CBDB.db-shm")

# Headroom demanded on top of the unpacked size.
_FREE_SPACE_HEADROOM = 256 * 1024**2


class StagingError(RuntimeError):
    """The distribution could not be staged, or is not a CBDB-Desktop tree."""


@dataclass(frozen=True)
class AppLayout:
    """Where the pieces of a staged CBDB-Desktop distribution live.

    ``root`` is the *pristine master*: tests launch the application
    against a per-session copy of ``db`` (see ``conftest.app_db``) so the
    master stays byte-stable and can serve as an oracle.

    The distribution has not kept one shape.  The zip builds put both
    executables in ``Bin/`` and named the database ``Data/CBDB.db``; the
    2026-09-07 7z ships ``cbdb.exe`` at the tree root with an empty
    ``Bin/``, and a lower-case ``Data/cbdb.db``.  Each piece is therefore
    *looked up* among the shapes that have shipped, case-insensitively,
    rather than assumed -- so the suite tests the build it was given
    instead of failing to find it.  Windows would forgive the casing and
    Linux would not; the lookup makes both behave the same.
    """

    root: Path

    def _resolve(self, *candidates: str) -> Path:
        """First candidate that exists, else the first -- so errors name it.

        Matching falls back to a case-insensitive scan of the parent
        directory, which is where the build's casing has actually varied.
        """
        for relative in candidates:
            path = self.root.joinpath(*relative.split("/"))
            if path.exists():
                return path
            parent = path.parent
            if parent.is_dir():
                wanted = path.name.lower()
                for sibling in sorted(parent.iterdir()):
                    if sibling.name.lower() == wanted:
                        return sibling
        return self.root.joinpath(*candidates[0].split("/"))

    @property
    def exe(self) -> Path:
        return self._resolve("Bin/cbdb.exe", "cbdb.exe")

    @property
    def setup_exe(self) -> Path:
        return self._resolve("Bin/CBDBsetup.exe", "CBDBsetup.exe")

    @property
    def db(self) -> Path:
        return self._resolve("Data/CBDB.db")

    @property
    def schema_json(self) -> Path:
        return self._resolve("Data/qbe_schema.json")

    @property
    def schema_sql(self) -> Path:
        return self._resolve("Data/CBDB.db.schema.sql")

    @property
    def templates_dir(self) -> Path:
        return self.root / "Templates"

    @property
    def static_dir(self) -> Path:
        return self.root / "Static"

    @property
    def code_dir(self) -> Path:
        return self.root / "Code"

    @property
    def setup_code_dir(self) -> Path:
        return self.root / "CBDBSetUpCode"

    def go_sources(self) -> list[Path]:
        """The application's Go sources, sorted -- the code under test.

        ``*_test.go`` is excluded: ``go build`` leaves those out, so they
        are not part of the shipped binary and must not be read as if
        they described it.  The 2026-09-07 build ships one
        (``qbe_schema_test.go``, the developers' own guardrail for
        CBDB-D-002); ``go_test_sources`` returns those separately.
        """
        return sorted(p for p in self.code_dir.glob("*.go")
                      if not p.name.endswith("_test.go"))

    def go_test_sources(self) -> list[Path]:
        """The Go tests shipped alongside the source, sorted."""
        return sorted(self.code_dir.glob("*_test.go"))

    def form_templates(self) -> dict[str, Path]:
        """``{form directory name: index.html}`` for every form page."""
        return {p.parent.name: p for p in sorted(self.templates_dir.glob("*/index.html"))}

    def required_paths(self) -> dict[str, Path]:
        return {
            "exe": self.exe,
            "db": self.db,
            "schema_json": self.schema_json,
            "templates_dir": self.templates_dir,
            "static_dir": self.static_dir,
            "code_dir": self.code_dir,
        }

    def missing(self) -> list[str]:
        out: list[str] = []
        for name, path in self.required_paths().items():
            wants_dir = name.endswith("_dir")
            if wants_dir and not path.is_dir():
                out.append(f"{name}: missing directory {path}")
            elif not wants_dir and not path.is_file():
                out.append(f"{name}: missing file {path}")
        return out

    def verify(self) -> None:
        problems = self.missing()
        if problems:
            raise StagingError(
                f"{self.root} is not a complete CBDB-Desktop tree:\n  "
                + "\n  ".join(problems)
            )


# ---------------------------------------------------------------------------
# archive fingerprinting
# ---------------------------------------------------------------------------

#: Trees already staged in this process, and which of them were staged
#: with ``force``.  See :func:`stage_once`.
_STAGED_ONCE: dict[tuple[str, str, str], "AppLayout"] = {}
_FORCED_ONCE: set[tuple[str, str, str]] = set()


def stage_once(config: Config, *, force: bool = False,
               quiet: bool = True) -> "AppLayout":
    """:func:`stage`, at most once per process for a given archive.

    Two callers need the staged tree at two different moments of a
    pytest run and must not stage it twice: the ``layout`` fixture, and
    ``test_query_matrix.py``'s collection hook, which has to read the
    database before pytest decides which tests exist.

    Calling :func:`stage` twice is not merely wasteful.  With ``force``
    it re-extracts 1.3 GB, and on Windows the second pass renames the
    tree the first pass just installed -- which failed with
    ``PermissionError: [WinError 5]`` mid-swap and errored all 678 tests
    in a run.  A directory rename is not safe against a handle that was
    open inside the tree moments earlier, and "moments earlier" is
    exactly what a second staging in the same process means.

    ``force`` is honoured the first time and ignored afterwards: one
    ``--restage`` per run is a restage, not two.
    """
    key = (str(config.zip_path), str(config.app_dir_override),
           str(config.work_dir))
    if key in _STAGED_ONCE and (not force or key in _FORCED_ONCE):
        return _STAGED_ONCE[key]
    layout = stage(config, force=force, quiet=quiet)
    _STAGED_ONCE[key] = layout
    if force:
        _FORCED_ONCE.add(key)
    return layout


def _entries(archive: Archive) -> list[dict[str, object]]:
    """Manifest rows for every file member, volatile ones flagged."""
    return [
        {
            "name": m.name,
            "size": m.size,
            "crc": m.crc,
            "volatile": is_volatile(m.name),
        }
        for m in archive.members
    ]


def file_sha256(path: Path) -> str:
    """Streaming SHA-256 of one file (~1 s for the 1.2 GB database)."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError as exc:
        raise StagingError(f"cannot read {path}: {exc}") from exc
    return h.hexdigest()


def content_fingerprint(zip_path: Path) -> str:
    """SHA-256 of the archive's bytes -- its content identity.

    The obvious cheaper option, hashing the central directory's
    name/size/CRC rows, is not enough: a rebuild can leave the directory
    identical while the payload differs (CRC-32 is 32 bits and not
    collision-resistant), and the cache would then serve the previous
    build under the new build's name -- the exact failure the cache key
    exists to prevent.  Hashing the file costs ~0.3 s for 430 MB.
    """
    return file_sha256(zip_path)


def archive_identity(zip_path: Path) -> tuple[str, list[dict[str, object]]]:
    """``(fingerprint, entries)`` for one distribution archive."""
    try:
        with Archive.open(zip_path) as archive:
            entries = _entries(archive)
    except ArchiveError as exc:
        raise StagingError(str(exc)) from exc
    return content_fingerprint(zip_path), entries


def archive_stem(zip_path: Path) -> str:
    """The archive's file stem, reduced to characters safe in a directory."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", zip_path.stem)


def stage_key(zip_path: Path, fingerprint: str | None = None) -> str:
    """Cache-directory name for one distribution: stem + size + fingerprint.

    Two different builds never collide, and a rebuilt archive of the same
    name -- even at the same size and mtime -- gets its own directory.
    ``fingerprint`` may be supplied by a caller that already computed it,
    so staging need not re-read the archive's central directory.
    """
    if fingerprint is None:
        fingerprint, _ = archive_identity(zip_path)
    try:
        size = zip_path.stat().st_size
    except OSError as exc:  # a sync client can remove it mid-run
        raise StagingError(f"{zip_path} disappeared while staging: {exc}") from exc
    return f"{archive_stem(zip_path)}_{size}_{fingerprint[:16]}"


# Directory names this module produces: <stem>_<size>_<16 hex digits>.
def _staged_dir_pattern(stem: str) -> re.Pattern[str]:
    return re.compile(rf"{re.escape(stem)}_\d+_[0-9a-f]{{16}}\Z")


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

def read_manifest(app_dir: Path) -> dict | None:
    """Return the staging manifest of ``app_dir``, or None if unusable."""
    path = app_dir / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("manifest_version") != MANIFEST_VERSION:
        return None
    if not isinstance(data.get("entries"), list):
        return None
    return data


def immutable_entries(manifest: dict) -> list[dict]:
    """Manifest rows whose bytes must still match the archive exactly."""
    return [e for e in manifest["entries"] if not e.get("volatile")]


# Every immutable file is CRC-checked by default: the whole immutable
# payload is ~120 MB and CRC-32 runs it in ~0.1 s, so exempting the two
# ~30 MB binaries would trade the check that matters most (a corrupt or
# swapped cbdb.exe) for nothing measurable.  The limit stays a parameter
# so a caller can trade coverage for time deliberately.
DEFAULT_CRC_LIMIT = float("inf")


def integrity_mismatches(layout: AppLayout, manifest: dict,
                         *, crc_limit: float = DEFAULT_CRC_LIMIT,
                         check_db: bool = True) -> list[str]:
    """Compare a staged tree against the archive's own central directory.

    Returns one human-readable line per discrepancy, empty when the tree
    is exactly what the archive said it was.  Volatile files (the database
    and its sidecars) are excluded: the application rewrites them.

    This lives in production code rather than in a test because it is a
    drift check worth running before any session -- and because a
    provenance guarantee enforced only by test-local code is not a
    guarantee at all.
    """
    out: list[str] = []
    for entry in immutable_entries(manifest):
        path = layout.root / str(entry["name"])
        if not path.is_file():
            out.append(f"{entry['name']}: missing")
            continue
        size = path.stat().st_size
        if size != entry["size"]:
            out.append(f"{entry['name']}: size {size} != {entry['size']}")
            continue
        if size <= crc_limit:
            crc = 0
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    crc = zlib.crc32(chunk, crc)
            if crc != entry["crc"]:
                out.append(f"{entry['name']}: CRC {crc} != {entry['crc']}")

    # The database is excluded from the archive comparison -- staging may
    # have checkpointed a WAL into it, and the application rewrites it --
    # but it is far too important to leave unchecked.  It is pinned to the
    # hash it had when staging finished, so a substituted or truncated
    # 1.2 GB master is caught even though it can never match the archive
    # byte for byte.
    expected_db = manifest.get("master_db_sha256")
    if check_db and expected_db:
        if not layout.db.is_file():
            out.append("Data/CBDB.db: missing")
        elif file_sha256(layout.db) != expected_db:
            out.append("Data/CBDB.db: content differs from the staged master "
                       "(SHA-256 mismatch)")

    # Anything the archive did not ship has no business in the tree: an
    # extra template or static asset changes what the application serves,
    # and would otherwise ride along through every cache hit.
    expected_names = {str(e["name"]) for e in manifest["entries"]} | {MANIFEST_NAME}
    # SQLite recreates the sidecars beside the database whenever the file
    # is opened, so those exact paths are allowed back.  The allowance is
    # by full path, not by basename: a stray "Templates/entry/CBDB.db"
    # is an injected file like any other.
    # Case-insensitively: the 2026-09-07 build renamed it to "cbdb.db",
    # and missing it here would report the database's own -wal as a file
    # that is "not part of the distribution".
    db_name = next((str(e["name"]) for e in manifest["entries"]
                    if str(e["name"]).lower().endswith("cbdb.db")), "Data/CBDB.db")
    expected_names |= {db_name, db_name + "-wal", db_name + "-shm"}
    for path in sorted(layout.root.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(layout.root).as_posix()
        if name in expected_names:
            continue
        out.append(f"{name}: not part of the distribution")
    return out


# ---------------------------------------------------------------------------
# filesystem helpers
# ---------------------------------------------------------------------------

def _check_free_space(target: Path, need: int) -> None:
    anchor = target
    while not anchor.exists():
        parent = anchor.parent
        if parent == anchor:
            break
        anchor = parent
    free = shutil.disk_usage(anchor).free
    if free < need:
        raise StagingError(
            f"Not enough free space to stage the distribution under {target}: "
            f"{free / 1024**3:.2f} GB free, {need / 1024**3:.2f} GB needed.  "
            "Point CBDB_WORK_DIR at a roomier disk."
        )


def _holders(directory: Path) -> list[str]:
    """Best-effort list of running processes with an image under ``directory``.

    Only used to turn an opaque Windows sharing violation into an error
    that names the culprit -- a leftover ``cbdb.exe`` from a crashed
    session is the expected cause.
    """
    if sys.platform != "win32":
        return []
    # The path travels in the environment, never spliced into the script: a
    # directory containing an apostrophe would break the quoting, and -like
    # would read "[" and "]" as a wildcard character class.
    script = (
        "$d = $env:CBDB_HOLDER_DIR; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ExecutablePath -and "
        "$_.ExecutablePath.StartsWith($d, 'OrdinalIgnoreCase') } | "
        "ForEach-Object { \"$($_.ProcessId) $($_.ExecutablePath)\" }"
    )
    env = dict(os.environ)
    env["CBDB_HOLDER_DIR"] = str(directory) + os.sep
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _rmtree(path: Path, *, attempts: int = 5) -> None:
    """``shutil.rmtree`` with backoff, and a diagnosable error on failure.

    Windows refuses to delete a file another process holds open, and an
    antivirus scan can hold one for a moment after extraction.
    """
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if attempt == attempts - 1:
                holders = _holders(path)
                detail = ("\n  still running: " + "\n  still running: ".join(holders)
                          if holders else "")
                raise StagingError(
                    f"Could not remove {path}: {exc}.  A cbdb.exe from an "
                    f"earlier session may still hold the tree open.{detail}"
                ) from exc
            time.sleep(0.5 * (attempt + 1))


def _settle_database(tree: Path) -> bool:
    """Fold any shipped write-ahead log into the database, then drop sidecars.

    A distribution normally ships an empty WAL, but if one ever carries
    committed frames, deleting it would silently discard data -- and the
    oracle opens the master with ``immutable=1``, which ignores a WAL
    without complaining.  Checkpointing first means the master is always
    a complete, self-contained database.

    Returns True if a non-empty WAL had to be checkpointed.
    """
    db = AppLayout(tree).db
    wal = db.with_name(db.name + "-wal")
    checkpointed = False

    if wal.is_file() and wal.stat().st_size > 0:
        wal_size = wal.stat().st_size
        try:
            conn = sqlite3.connect(db)
            try:
                row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise StagingError(
                f"the distribution ships a non-empty write-ahead log "
                f"({wal_size} bytes) that could not be checkpointed into "
                f"{db}: {exc}.  Staging refuses to discard it, because the "
                "master database would then be missing committed data."
            ) from exc
        # A blocked checkpoint reports busy=1 in the result row instead of
        # raising, and would leave frames behind for the unlink below to
        # throw away.  Both the status and the resulting file are checked.
        if row is not None and row[0] != 0:
            raise StagingError(
                f"checkpointing the shipped write-ahead log into {db} "
                f"reported busy (result {row!r}); refusing to discard "
                f"{wal_size} bytes of committed data."
            )
        if wal.is_file() and wal.stat().st_size > 0:
            raise StagingError(
                f"{wal} still holds {wal.stat().st_size} bytes after "
                "checkpointing; refusing to discard committed data."
            )
        checkpointed = True

    for suffix in ("-wal", "-shm"):
        sidecar = db.with_name(db.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
    return checkpointed

def _prune_siblings(stage_root: Path, keep: Path, stem: str) -> None:
    """Delete *superseded builds of the same archive*, and nothing else.

    Without this, every rebuild leaves a 1.3 GB orphan behind.  The match
    is deliberately exact rather than a prefix: ``startswith(stem + "_")``
    also matches a different archive whose stem extends this one
    (``cbdb-desktop_20260901`` vs ``cbdb-desktop_20260901_rc2``) and --
    worse -- matches another session's in-flight ``.partial-*``, which the
    application may be running out of.  Failures are ignored: pruning is
    housekeeping, never a reason to fail a run.
    """
    if not stage_root.is_dir():
        return
    pattern = _staged_dir_pattern(stem)
    for candidate in stage_root.iterdir():
        if candidate == keep or not candidate.is_dir():
            continue
        if not pattern.fullmatch(candidate.name):
            continue
        try:
            _rmtree(candidate)
        except StagingError:
            pass


# A ``.partial-*`` younger than this may belong to a session that is still
# extracting; older than this, its owner is gone and it is dead weight.
_PARTIAL_MAX_AGE_S = 6 * 3600


def _prune_partials(stage_root: Path, stem: str, *, now: float | None = None) -> None:
    """Remove abandoned extraction directories.

    Our own leftovers go immediately; another process's only once they are
    old enough that no live session could still be writing into them.  The
    application runs out of the staged tree, so deleting a directory a
    concurrent session is using would pull files out from under a running
    ``cbdb.exe``.
    """
    if not stage_root.is_dir():
        return
    now = time.time() if now is None else now
    marker = f".partial-{os.getpid()}-"
    for candidate in stage_root.iterdir():
        if not candidate.is_dir() or ".partial-" not in candidate.name:
            continue
        if not candidate.name.startswith(stem + "_"):
            continue
        try:
            age = now - candidate.stat().st_mtime
        except OSError:
            continue
        if marker in candidate.name or age > _PARTIAL_MAX_AGE_S:
            try:
                _rmtree(candidate)
            except StagingError:
                pass


# ---------------------------------------------------------------------------
# staging
# ---------------------------------------------------------------------------

def _cache_hit(app_dir: Path, fingerprint: str, *, verify: bool = True) -> bool:
    """True if ``app_dir`` holds a *verified* tree for this archive.

    Presence of a manifest is not enough.  A staged file can be corrupted
    or replaced after extraction -- by a failed sync, an antivirus
    quarantine-and-restore, or a maintainer patching a template "just to
    try something" -- and the resulting build would be tested for weeks
    under the shipped build's name.  Re-checking every immutable file
    costs ~0.1 s, so it happens on every cache hit rather than only when
    a test asks.
    """
    manifest = read_manifest(app_dir)
    if manifest is None or manifest.get("content_fingerprint") != fingerprint:
        return False
    layout = AppLayout(app_dir)
    if layout.missing():
        return False
    if not verify:
        return True
    return not integrity_mismatches(layout, manifest)


def _recover_interrupted_swap(app_dir: Path, fingerprint: str) -> bool:
    """Restore a build stranded by a crash between the two renames.

    ``stage`` moves the previous tree to ``<name>.old-<hex>`` and only
    then renames the new one into place.  A power cut or a killed process
    in that window leaves no ``app_dir`` at all, and the good build --
    fully intact -- sitting under a name nothing looks for.
    """
    if app_dir.exists():
        return False
    for candidate in sorted(app_dir.parent.glob(app_dir.name + ".old-*"),
                            key=lambda p: p.stat().st_mtime, reverse=True):
        if not _cache_hit(candidate, fingerprint, verify=False):
            continue
        try:
            os.replace(candidate, app_dir)
        except OSError:
            continue
        return True
    return False


def stage(config: Config, *, force: bool = False, quiet: bool = False) -> AppLayout:
    """Unpack the configured zip (cached) and return its layout.

    ``CBDB_APP_DIR`` short-circuits the whole thing: an already-unpacked
    tree is verified and used as-is.
    """
    if config.app_dir_override is not None:
        layout = AppLayout(config.app_dir_override.resolve())
        layout.verify()
        # No archive, so nothing can vouch for these bytes.  Say so once,
        # loudly: every result from this session describes whatever is in
        # that directory, not a shipped build.
        warnings.warn(
            f"CBDB_APP_DIR is set: testing the unpacked tree at {layout.root} "
            "with no archive to verify it against.  Results are NOT certified "
            "against a shipped distribution.",
            stacklevel=2,
        )
        return layout

    zip_path = config.require_zip()
    fingerprint, entries = archive_identity(zip_path)
    app_dir = config.stage_root / stage_key(zip_path, fingerprint)
    layout = AppLayout(app_dir)

    if _recover_interrupted_swap(app_dir, fingerprint) and not quiet:
        print(f"recovered a staged build stranded by an interrupted swap: {app_dir}",
              file=sys.stderr, flush=True)

    if not force and _cache_hit(app_dir, fingerprint):
        return layout

    partial = app_dir.with_name(f"{app_dir.name}.partial-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    partial.parent.mkdir(parents=True, exist_ok=True)

    unpacked = sum(int(e["size"]) for e in entries)
    # A restage holds both trees at once: the new one is complete before
    # the old one is touched, so the peak is twice the unpacked size.
    need = unpacked * (2 if app_dir.exists() else 1) + _FREE_SPACE_HEADROOM
    _check_free_space(partial.parent, need)
    if not quiet:
        print(
            f"staging {zip_path.name} -> {app_dir} "
            f"({len(entries)} entries, {unpacked / 1024**3:.2f} GB unpacked)",
            file=sys.stderr, flush=True,
        )

    superseded: Path | None = None
    try:
        try:
            with Archive.open(zip_path) as archive:
                archive.extract_to(partial)
        except ArchiveError as exc:
            raise StagingError(str(exc)) from exc

        checkpointed = _settle_database(partial)
        master_db_sha256 = file_sha256(AppLayout(partial).db)

        st = zip_path.stat()
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "zip_path": str(zip_path),
            "zip_name": zip_path.name,
            "zip_size": st.st_size,
            "zip_mtime_ns": st.st_mtime_ns,
            "content_fingerprint": fingerprint,
            "stage_key": app_dir.name,
            "discarded_after_extract": list(_DISCARD_AFTER_EXTRACT),
            "wal_checkpointed": checkpointed,
            "master_db_sha256": master_db_sha256,
            "entries": entries,
        }
        (partial / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        AppLayout(partial).verify()

        # Only now is it safe to disturb whatever is already in place: a
        # failure above leaves the previous good tree untouched.
        if app_dir.exists():
            if not force and _cache_hit(app_dir, fingerprint):
                # A concurrent session finished first; adopt its tree.  A
                # stubborn lock on our own leftovers is not worth failing
                # a run whose result already exists.
                try:
                    _rmtree(partial)
                except StagingError:
                    pass
                return layout
            superseded = app_dir.with_name(f"{app_dir.name}.old-{uuid.uuid4().hex[:8]}")
            os.replace(app_dir, superseded)
        os.replace(partial, app_dir)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        if superseded is not None and not app_dir.exists():
            # The swap failed after the old tree was moved aside: put it
            # back rather than leaving the machine with no staged build.
            try:
                os.replace(superseded, app_dir)
                superseded = None
            except OSError:
                pass
        raise

    # Deleting ~1.3 GB is slow and can fail on a lock; it happens only
    # after the new tree is safely in place, so a failure here costs disk
    # space, never the build.
    if superseded is not None:
        try:
            _rmtree(superseded)
        except StagingError:
            pass

    stem = archive_stem(zip_path)
    _prune_siblings(config.stage_root, app_dir, stem)
    _prune_partials(config.stage_root, stem)
    layout.verify()
    return layout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python stage.py",
        description="Stage the CBDB-Desktop zip named by CBDB_DESKTOP_ZIP.")
    ap.add_argument("--force", action="store_true",
                    help="Restage even if a complete tree is already cached.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    layout = stage(load_config(), force=args.force, quiet=args.quiet)
    print(layout.root)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
