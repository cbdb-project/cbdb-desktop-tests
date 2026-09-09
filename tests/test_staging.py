"""Tests for the staging layer itself, plus a distribution-integrity check.

Everything up to the last section runs on synthetic zips in ``tmp_path``
-- no CBDB, no Office, seconds to run, and deliberately insulated from
the maintainer's ``.env`` (every ``load_config`` call here passes an
explicit environment).  The final section asserts that the *real* staged
tree still matches the archive it came from, which is the provenance
guarantee every other test in the suite rests on.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.subjects import FIXED_INPUTS

from cbdb_desktop.config import (
    REPO_ROOT,
    Config,
    MissingConfig,
    _parse_env_file,
    load_config,
)
from cbdb_desktop import staging
from cbdb_desktop.archives import Archive, ArchiveError, common_root
from cbdb_desktop.staging import (
    MANIFEST_NAME,
    VOLATILE_ENTRIES,
    AppLayout,
    StagingError,
    archive_identity,
    content_fingerprint,
    immutable_entries,
    integrity_mismatches,
    is_volatile,
    read_manifest,
    stage,
    stage_key,
)

# The application's Go sources.  Pinned, not counted: a build that drops
# a form backend, or adds one nobody mentioned, is exactly the change a
# reviewer wants told about.
EXPECTED_GO_SOURCES = {
    "associations_form_backend.go", "assocpairs_form_backend.go",
    "browser_form_backend.go", "cbdb_navigation_backend.go",
    "cbdb_shared_utils.go", "entry_form_backend.go",
    "groupdata_form_backend.go", "indexaddr_form_backend.go",
    "kinship_form_backend.go", "main.go", "networks_form_backend.go",
    "networks_form_query.go", "office_form_backend.go",
    "places_form_backend.go", "qbe_criteria.go", "qbe_gridstate.go",
    "qbe_handlers.go", "qbe_request.go", "qbe_schema.go", "qbe_sqlgen.go",
    "status_form_backend.go", "texts_form_backend.go",
}

# The form pages the 2026-09 build ships.  A floor ("at least 10") would
# survive a build that silently dropped five forms; catching exactly that
# is the point, so the set is pinned.  (QBE is checked separately: it is
# the one page not nested as <form>/index.html.)
EXPECTED_FORM_TEMPLATES = {
    "association_pairs", "associations", "browser", "entry", "group_data",
    "index_addr", "kinship", "navigation", "networks", "office", "places",
    "status", "texts",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fake_distribution(zip_path: Path,
                       *, extra: dict[str, str | bytes] | None = None) -> Path:
    """A minimal archive with the layout the application expects."""
    members = {
        "Bin/cbdb.exe": "MZ-not-really",
        "Bin/CBDBsetup.exe": "MZ-not-really-either",
        "Data/CBDB.db": "SQLite format 3\x00",
        "Data/CBDB.db-wal": "",
        "Data/CBDB.db-shm": "shm",
        "Data/qbe_schema.json": '{"tables":[]}',
        "Data/CBDB.db.schema.sql": "CREATE TABLE BIOG_MAIN(c_personid INTEGER);",
        "Templates/navigation/index.html": "<html></html>",
        "Static/cbdb_styles.css": "body{}",
        "Code/main.go": "package main",
    }
    members.update(extra or {})
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, body in members.items():
            zf.writestr(name, body)
    return zip_path


#: The members every fake distribution carries, whatever the container.
_DISTRIBUTION_MEMBERS: dict[str, str] = {
    "Bin/cbdb.exe": "MZ-not-really",
    "Bin/CBDBsetup.exe": "MZ-not-really-either",
    "Data/CBDB.db": "SQLite format 3\x00",
    "Data/qbe_schema.json": '{"tables":[]}',
    "Data/CBDB.db.schema.sql": "CREATE TABLE BIOG_MAIN(c_personid INTEGER);",
    "Templates/navigation/index.html": "<html></html>",
    "Static/cbdb_styles.css": "body{}",
    "Code/main.go": "package main",
}


def _fake_distribution_7z(path: Path, *, root: str | None) -> Path:
    """The same minimal distribution, in a 7z, optionally wrapped in ``root``."""
    py7zr = pytest.importorskip("py7zr")
    staged = path.parent / (path.stem + "-src")
    base = staged / root if root else staged
    for name, body in _DISTRIBUTION_MEMBERS.items():
        member = base / name
        member.parent.mkdir(parents=True, exist_ok=True)
        member.write_text(body, encoding="utf-8")
    with py7zr.SevenZipFile(path, "w") as archive:
        for child in sorted(staged.iterdir()):
            archive.writeall(child, child.name)
    return path


def _config(tmp_path: Path, zip_path: Path | None, **kw) -> Config:
    return Config(
        zip_path=zip_path,
        work_dir=tmp_path / "work",
        app_dir_override=kw.get("app_dir_override"),
        startup_timeout=5,
        http_timeout=5,
        suppress_browser=True,
        keep_run_dir=False,
    )


def _refuse_to_extract(monkeypatch):
    """Make any extraction attempt fail loudly.

    Proving a cache *hit* by planting a marker file no longer works --
    an unexpected file is itself a cache miss now -- so the test instead
    asserts that staging never reaches the archive at all.
    """
    def boom(self, path=None, *args, **kwargs):
        raise AssertionError("stage() re-extracted the archive instead of "
                             "reusing the cached tree")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", boom)



# ---------------------------------------------------------------------------
# .env parsing and configuration
# ---------------------------------------------------------------------------

def test_env_file_keeps_windows_paths_verbatim(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "CBDB_DESKTOP_ZIP=C:\\Users\\x\\Dropbox\\cbdb-desktop_20260901.zip\n"
        'CBDB_WORK_DIR="D:\\cbdb work"\n'
        "BROKEN LINE WITHOUT EQUALS\n",
        encoding="utf-8",
    )
    values = _parse_env_file(env)
    assert values["CBDB_DESKTOP_ZIP"] == "C:\\Users\\x\\Dropbox\\cbdb-desktop_20260901.zip"
    assert values["CBDB_WORK_DIR"] == "D:\\cbdb work"
    assert "BROKEN LINE WITHOUT EQUALS" not in values


def test_explicit_env_ignores_the_local_env_file(tmp_path: Path):
    """A unit test must never inherit the maintainer's real settings."""
    from cbdb_desktop.config import ENV_FILE

    if not ENV_FILE.is_file() or "CBDB_DESKTOP_ZIP" not in ENV_FILE.read_text(
            encoding="utf-8-sig"):
        pytest.skip("no local .env with CBDB_DESKTOP_ZIP: nothing could leak")

    cfg = load_config({"CBDB_STARTUP_TIMEOUT": "12"})
    assert cfg.zip_path is None, "the repo-root .env leaked into an explicit env"
    assert cfg.startup_timeout == 12
    assert cfg.app_dir_override is None

    named = tmp_path / "other.env"
    named.write_text("CBDB_WORK_DIR=D:\\from-file\n", encoding="utf-8")
    cfg = load_config({"CBDB_DESKTOP_ZIP": "Z:\\x.zip"}, env_file=named)
    assert cfg.work_dir == Path("D:\\from-file")
    assert cfg.zip_path == Path("Z:\\x.zip")


def test_environment_overrides_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CBDB_DESKTOP_ZIP=Z:\\from-file.zip\nCBDB_STARTUP_TIMEOUT=99\n",
        encoding="utf-8")
    cfg = load_config({"CBDB_DESKTOP_ZIP": str(tmp_path / "override.zip"),
                       "CBDB_WORK_DIR": str(tmp_path / "w"),
                       "CBDB_STARTUP_TIMEOUT": "12",
                       "CBDB_SUPPRESS_BROWSER": "0"}, env_file=env_file)
    assert cfg.zip_path == tmp_path / "override.zip"
    assert cfg.work_dir == tmp_path / "w"
    assert cfg.startup_timeout == 12
    assert cfg.suppress_browser is False


@pytest.mark.parametrize("bad", [{"CBDB_STARTUP_TIMEOUT": "soon"},
                                 {"CBDB_HTTP_TIMEOUT": "-3"},
                                 {"CBDB_SUPPRESS_BROWSER": "maybe"},
                                 {"CBDB_KEEP_RUN_DIR": "sometimes"}])
def test_malformed_settings_fail_loudly(bad: dict[str, str]):
    with pytest.raises(MissingConfig, match=next(iter(bad))):
        load_config(bad)


def test_missing_zip_is_a_clear_error(tmp_path: Path):
    with pytest.raises(MissingConfig, match="CBDB_DESKTOP_ZIP is not set"):
        _config(tmp_path, None).require_zip()
    with pytest.raises(MissingConfig, match="does not exist"):
        _config(tmp_path, tmp_path / "nope.zip").require_zip()


# ---------------------------------------------------------------------------
# cache identity
# ---------------------------------------------------------------------------

def test_cache_key_follows_content_not_timestamps(tmp_path: Path):
    """Same name, same size, same mtime, different bytes -> different key.

    The archive lives in Dropbox, which rewrites mtimes on re-download, so
    an mtime-keyed cache would both restage identical archives and (the
    dangerous half) serve a same-size rebuild from the previous build's
    directory.
    """
    import os

    a = _fake_distribution(tmp_path / "dist.zip", extra={"Data/payload.txt": "AAAA"})
    before_key = stage_key(a)
    before_stat = a.stat()

    _fake_distribution(a, extra={"Data/payload.txt": "BBBB"})  # same length
    os.utime(a, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))

    assert a.stat().st_size == before_stat.st_size, "sizes must match for this test"
    assert a.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert stage_key(a) != before_key

    # A byte-identical archive keeps its fingerprint, so a re-downloaded
    # zip does not trigger a needless 1.3 GB restage.
    b = tmp_path / "copy.zip"
    b.write_bytes(a.read_bytes())
    assert content_fingerprint(a) == content_fingerprint(b)

    # Same members, same sizes, same CRCs, different bytes on disk: a
    # fingerprint taken from the central directory alone would call these
    # the same build and serve the wrong tree from cache.
    twin = tmp_path / "twin.zip"
    twin.write_bytes(a.read_bytes() + b"\x00trailing comment bytes")
    assert archive_identity(twin)[1] == archive_identity(a)[1], \
        "the two archives must be indistinguishable from the central directory"
    assert content_fingerprint(twin) != content_fingerprint(a)


def test_cache_key_separates_different_builds(tmp_path: Path):
    a = _fake_distribution(tmp_path / "dist.zip")
    b = _fake_distribution(tmp_path / "dist2.zip", extra={"Data/extra.txt": "more"})
    assert stage_key(a) != stage_key(b)


def test_a_corrupt_archive_is_reported_not_crashed(tmp_path: Path):
    bad = tmp_path / "truncated.zip"
    bad.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(StagingError, match="not a readable zip"):
        stage(_config(tmp_path, bad), quiet=True)


# ---------------------------------------------------------------------------
# staging behaviour
# ---------------------------------------------------------------------------

def test_stage_unpacks_and_is_cached(tmp_path: Path, monkeypatch):
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)

    layout = stage(cfg, quiet=True)
    layout.verify()
    assert layout.exe.is_file()
    assert layout.db.read_text(encoding="utf-8").startswith("SQLite format 3")

    manifest = read_manifest(layout.root)
    assert manifest is not None
    assert manifest["zip_name"] == "dist.zip"
    assert {e["name"] for e in manifest["entries"]} >= {"Bin/cbdb.exe", "Data/CBDB.db"}
    assert manifest["master_db_sha256"]

    # A second stage() must reuse the directory rather than unpack again.
    _refuse_to_extract(monkeypatch)
    again = stage(cfg, quiet=True)
    assert again.root == layout.root
    monkeypatch.undo()

    # ...and --restage must unpack regardless.
    extracted = []
    real_extractall = zipfile.ZipFile.extractall

    def record(self, path=None, *args, **kwargs):
        extracted.append(path)
        return real_extractall(self, path, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "extractall", record)
    fresh = stage(cfg, force=True, quiet=True)
    monkeypatch.undo()
    assert fresh.root == layout.root
    assert extracted, "--restage reused the cache instead of unpacking"


def test_sqlite_sidecars_are_discarded(tmp_path: Path):
    """The shipped -wal/-shm are extracted then removed.

    A stale sidecar beside a database SQLite is about to open is at best
    useless; keeping them would also make them look like content.
    """
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    layout = stage(_config(tmp_path, zip_path), quiet=True)

    assert not (layout.root / "Data" / "CBDB.db-wal").exists()
    assert not (layout.root / "Data" / "CBDB.db-shm").exists()

    manifest = read_manifest(layout.root)
    volatile = {e["name"] for e in manifest["entries"] if e.get("volatile")}
    assert volatile == VOLATILE_ENTRIES & {e["name"] for e in manifest["entries"]}
    assert "Data/CBDB.db" in volatile


def test_integrity_check_ignores_the_database_but_catches_real_damage(tmp_path: Path):
    """The comparison must be blind to app writes and loud about anything else."""
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    layout = stage(_config(tmp_path, zip_path), quiet=True)
    manifest = read_manifest(layout.root)
    assert integrity_mismatches(layout, manifest) == []

    # Sidecars reappearing beside the master are not content: SQLite makes
    # them whenever the file is opened, and they say nothing about drift.
    (layout.root / "Data" / "CBDB.db-wal").write_bytes(b"x" * 4096)
    (layout.root / "Data" / "CBDB.db-shm").write_bytes(b"x" * 32)
    assert integrity_mismatches(layout, manifest) == []

    # The database itself cannot be compared against the archive (staging
    # may have checkpointed a WAL into it), so it is pinned to the hash it
    # had when staging finished -- a substituted master is still caught.
    layout.db.write_text("SQLite format 3\x00 plus ZZ_SCRATCH_ENTRY rows",
                         encoding="utf-8")
    assert any("CBDB.db" in m and "SHA-256" in m
               for m in integrity_mismatches(layout, manifest))
    assert integrity_mismatches(layout, manifest, check_db=False) == []
    stage(_config(tmp_path, zip_path), quiet=True)  # restore the tree
    manifest = read_manifest(layout.root)
    assert integrity_mismatches(layout, manifest) == []

    # A file the archive never shipped changes what the app serves.
    planted = layout.templates_dir / "entry" / "index.html"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("<html>injected</html>", encoding="utf-8")
    assert any("not part of the distribution" in m
               for m in integrity_mismatches(layout, manifest))
    planted.unlink()
    assert integrity_mismatches(layout, manifest) == []

    # The sidecar allowance is by path, not by name: a file that merely
    # calls itself CBDB.db somewhere else is an injected file like any
    # other, and the app would happily serve it from Templates/.
    decoy = layout.templates_dir / "entry" / "CBDB.db"
    decoy.write_text("not the database", encoding="utf-8")
    assert any("not part of the distribution" in m
               for m in integrity_mismatches(layout, manifest))
    decoy.unlink()
    assert integrity_mismatches(layout, manifest) == []

    # A damaged immutable file is not tolerated.  The replacement is the
    # SAME LENGTH as the original, so only the CRC branch can catch it --
    # a size comparison alone would call this tree pristine.
    original = layout.schema_json.read_text(encoding="utf-8")
    corrupted = '{"tables":{}}'
    assert len(corrupted) == len(original), "the corruption must not change size"
    layout.schema_json.write_text(corrupted, encoding="utf-8")
    mismatches = integrity_mismatches(layout, manifest)
    assert any("qbe_schema.json" in m and "CRC" in m for m in mismatches), mismatches

    # Above the CRC limit files are compared by size only, so the same
    # corruption goes unnoticed.  Pinning that keeps the cutoff honest.
    assert integrity_mismatches(layout, manifest, crc_limit=0) == []

    layout.exe.unlink()
    assert any("cbdb.exe: missing" in m for m in integrity_mismatches(layout, manifest))


def test_leftover_partial_directory_is_never_adopted(tmp_path: Path):
    """An interrupted extraction must not be mistaken for a staged tree."""
    import os
    import time

    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    app_dir = cfg.stage_root / stage_key(zip_path)

    stale = app_dir.with_name(app_dir.name + ".partial-999-deadbeef")
    (stale / "Data").mkdir(parents=True)
    (stale / "Data" / "CBDB.db").write_text("truncated", encoding="utf-8")
    old = time.time() - 24 * 3600
    os.utime(stale, (old, old))

    fresh = app_dir.with_name(app_dir.name + ".partial-1000-cafebabe")
    (fresh / "Data").mkdir(parents=True)
    (fresh / "Data" / "CBDB.db").write_text("in flight", encoding="utf-8")

    layout = stage(cfg, quiet=True)
    assert layout.db.read_text(encoding="utf-8").startswith("SQLite format 3")
    assert not stale.exists(), "an abandoned .partial tree was left behind"
    # A fresh one may belong to a session still extracting -- and the app
    # runs out of the staged tree, so deleting it could pull files out
    # from under a live cbdb.exe.
    assert fresh.is_dir(), "an in-flight .partial of another session was deleted"


def test_a_corrupt_archive_never_reaches_the_staged_tree(tmp_path: Path):
    """A broken zip fails before anything on disk is touched."""
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)
    assert layout.exe.is_file()

    zip_path.write_bytes(b"PK\x03\x04 truncated by a bad sync")
    with pytest.raises(StagingError):
        stage(cfg, force=True, quiet=True)

    assert layout.exe.is_file(), "the previously staged build was destroyed"
    assert read_manifest(layout.root) is not None


def test_a_restage_that_dies_midway_keeps_the_previous_tree(tmp_path: Path, monkeypatch):
    """The crash-safety property, tested where it actually applies.

    The archive is unchanged -- so the restage targets the *same*
    directory as the good build -- and the failure happens during
    extraction, the one moment a naive implementation would already have
    deleted the tree it is replacing.
    """
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)
    before = read_manifest(layout.root)

    def die_halfway(self, path=None, *args, **kwargs):
        Path(path, "Data").mkdir(parents=True, exist_ok=True)
        Path(path, "Data", "CBDB.db").write_text("half", encoding="utf-8")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(zipfile.ZipFile, "extractall", die_halfway)
    with pytest.raises(OSError):
        stage(cfg, force=True, quiet=True)
    monkeypatch.undo()

    assert layout.exe.is_file(), "the previously staged build was destroyed"
    assert read_manifest(layout.root) == before
    assert integrity_mismatches(layout, before) == []
    assert not [p for p in cfg.stage_root.iterdir() if ".partial-" in p.name]

    # ...and the next attempt still works.
    assert stage(cfg, force=True, quiet=True).exe.is_file()


def test_a_failed_final_swap_puts_the_previous_tree_back(tmp_path: Path, monkeypatch):
    """The old tree is moved aside, never deleted, until the new one lands.

    An implementation that deletes the previous tree before renaming the
    new one into place has a window where a failure leaves the machine
    with no staged build at all.  Failing exactly that rename is the only
    way to observe the difference.
    """
    import os as _os

    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)
    before = read_manifest(layout.root)

    real_replace = _os.replace
    state = {"failed": False}

    def fail_the_first_swap_in(src, dst, *args, **kwargs):
        if not state["failed"] and Path(dst) == layout.root:
            state["failed"] = True
            raise OSError(5, "Access is denied")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(staging.os, "replace", fail_the_first_swap_in)
    with pytest.raises(OSError):
        stage(cfg, force=True, quiet=True)
    monkeypatch.undo()

    assert state["failed"], "the swap under test never happened"
    assert layout.root.is_dir(), "the machine was left with no staged build"
    assert read_manifest(layout.root) == before
    assert integrity_mismatches(layout, before) == []
    assert not [p for p in cfg.stage_root.iterdir() if ".partial-" in p.name]


def test_manifest_from_another_version_or_archive_is_ignored(tmp_path: Path):
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)
    manifest_path = layout.root / MANIFEST_NAME

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["manifest_version"] = 999
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    assert read_manifest(layout.root) is None
    stage(cfg, quiet=True)
    assert read_manifest(layout.root) is not None

    # A manifest whose fingerprint belongs to a different archive is not a
    # cache hit either, even though the directory name matches.
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["content_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    (layout.root / "Data" / "marker.txt").write_text("stale", encoding="utf-8")
    stage(cfg, quiet=True)
    assert not (layout.root / "Data" / "marker.txt").exists()


def test_incomplete_tree_is_restaged(tmp_path: Path):
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)

    layout.exe.unlink()
    assert layout.missing()
    stage(cfg, quiet=True)
    assert layout.exe.is_file()


def test_superseded_builds_are_pruned(tmp_path: Path):
    """Staging a new build of the same archive reclaims the old tree."""
    zip_path = _fake_distribution(tmp_path / "dist.zip", extra={"Data/p.txt": "v1"})
    cfg = _config(tmp_path, zip_path)
    old = stage(cfg, quiet=True).root

    _fake_distribution(zip_path, extra={"Data/p.txt": "v2"})
    new = stage(cfg, quiet=True).root

    assert new != old
    assert not old.exists(), "the superseded 1.3 GB tree was orphaned"


def test_pruning_spares_other_archives(tmp_path: Path):
    """Only *this* archive's superseded builds are reclaimed.

    A prefix match would delete cbdb-desktop_20260901_rc2's tree while
    staging cbdb-desktop_20260901 -- and both are plausible names for
    builds a maintainer wants staged side by side.
    """
    main_zip = _fake_distribution(tmp_path / "dist.zip", extra={"Data/p.txt": "v1"})
    rc_zip = _fake_distribution(tmp_path / "dist_rc2.zip", extra={"Data/p.txt": "rc"})
    other_zip = _fake_distribution(tmp_path / "other.zip", extra={"Data/p.txt": "o"})

    cfg_main = _config(tmp_path, main_zip)
    cfg_rc = _config(tmp_path, rc_zip)
    cfg_other = _config(tmp_path, other_zip)

    stage(cfg_main, quiet=True)
    rc_tree = stage(cfg_rc, quiet=True).root
    other_tree = stage(cfg_other, quiet=True).root

    _fake_distribution(main_zip, extra={"Data/p.txt": "v2"})
    stage(cfg_main, quiet=True)

    assert rc_tree.is_dir(), "a different archive's staged build was deleted"
    assert other_tree.is_dir(), "an unrelated staged build was deleted"


@pytest.mark.parametrize("member", [
    "../escaped.txt",         # classic traversal
    "../../escaped.txt",      # two levels: lands outside work/ entirely
    "sub/../../escaped.txt",  # traversal hidden mid-path
    "/abs-escaped.txt",       # absolute, caught by the leading-slash rule
    "C:/abs-escaped.txt",     # drive-qualified: only the resolve() check sees it
])
def test_zip_slip_is_refused(tmp_path: Path, member: str):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(member, "pwned")
    with zipfile.ZipFile(zip_path) as check:
        assert check.namelist() == [member], "the archive was normalised, not hostile"

    cfg = _config(tmp_path, zip_path)
    with pytest.raises(StagingError, match="Refusing to extract"):
        stage(cfg, quiet=True)

    # Nothing may appear anywhere along the path the escape aimed at.
    for probe in (cfg.stage_root, cfg.stage_root.parent, cfg.work_dir.parent, tmp_path):
        if probe.is_dir():
            names = {p.name for p in probe.rglob("*")}
            assert "escaped.txt" not in names and "abs-escaped.txt" not in names


def test_backslash_members_are_refused(tmp_path: Path):
    """Separator-confusion members are rejected on their own merits.

    Python's zipfile rewrites ``\\`` to ``/`` both when writing and when
    reading a central directory, so this shape cannot be delivered through
    a real ZipFile on Windows -- but a hostile archive can still carry it,
    and the guard is what stops "..\\x" and UNC paths from being treated
    as ordinary relative names.  Driving the archive layer with a forged
    member list is the only way to hold that branch honest.
    """
    class ForgedArchive(Archive):
        def __init__(self, names):
            super().__init__(tmp_path / "forged.zip")
            self.names = names
            self.extracted = False

        def _open(self):
            pass

        def _raw_members(self):
            for name in self.names:
                yield name, 0, 0

        def _extractall(self, dest):  # pragma: no cover - must never run
            self.extracted = True

    for hostile in ("..\\escaped.txt", "\\\\server\\share\\escaped.txt",
                    "sub\\..\\..\\escaped.txt"):
        forged = ForgedArchive([hostile])
        with pytest.raises(ArchiveError, match="unsafe archive member"):
            forged.extract_to(tmp_path / "dest")
        assert not forged.extracted, "extraction started despite a hostile member"

    # A member that is merely unusual, not hostile, still extracts.
    ok = ForgedArchive(["Data/CBDB.db", "Templates/entry/index.html"])
    ok.extract_to(tmp_path / "dest")
    assert ok.extracted


# ---------------------------------------------------------------------------
# archive containers: the distribution has shipped as both .zip and .7z
# ---------------------------------------------------------------------------

def test_a_seven_zip_distribution_stages_like_a_zip(tmp_path: Path):
    """The container is an implementation detail above the archive layer.

    The 2026-09-07 build switched from .zip to .7z *and* moved the tree
    under a ``CBDB-Desktop/`` wrapper.  Staging must produce the same
    layout from either -- otherwise every path-shaped assertion in the
    suite silently starts describing a directory one level up.
    """
    seven = _fake_distribution_7z(tmp_path / "dist.7z", root="CBDB-Desktop")
    layout = stage(_config(tmp_path, seven), quiet=True)

    layout.verify()
    assert not (layout.root / "CBDB-Desktop").exists(), "the wrapper was not stripped"
    assert layout.db.read_bytes().startswith(b"SQLite format 3")

    manifest = read_manifest(layout.root)
    names = {str(e["name"]) for e in manifest["entries"]}
    assert "Data/CBDB.db" in names
    assert not any(n.startswith("CBDB-Desktop/") for n in names)
    # And the cached tree is re-verifiable, which is the property the
    # CRCs in the manifest exist for.
    assert integrity_mismatches(layout, manifest) == []


def test_an_unwrapped_seven_zip_is_staged_as_it_stands(tmp_path: Path):
    """Only a *lone* common root is stripped, and only when it is one."""
    seven = _fake_distribution_7z(tmp_path / "flat.7z", root=None)
    layout = stage(_config(tmp_path, seven), quiet=True)
    layout.verify()
    assert (layout.root / "Data").is_dir()


def test_a_root_level_file_beside_the_wrapper_is_not_stripped():
    """A file at the archive root means there is no wrapper to strip.

    Stripping on a prefix match instead would drop that file from both
    the member list and the staged tree, with nothing to notice it.
    """
    assert common_root(["CBDB-Desktop/Data/CBDB.db",
                        "CBDB-Desktop/cbdb.exe"]) == "CBDB-Desktop"
    assert common_root(["CBDB-Desktop/Data/CBDB.db", "CBDB-Desktop"]) is None
    assert common_root(["CBDB-Desktop/a", "Other/b"]) is None
    assert common_root(["cbdb.exe", "Data/CBDB.db"]) is None
    assert common_root(["../escaped.txt"]) is None
    assert common_root([]) is None


def test_a_corrupt_seven_zip_is_reported_not_crashed(tmp_path: Path):
    bad = tmp_path / "bad.7z"
    bad.write_bytes(b"7z\xbc\xaf\x27\x1c" + b"not really" * 40)
    with pytest.raises(StagingError, match="7z"):
        stage(_config(tmp_path, bad), quiet=True)


def test_an_unknown_archive_type_is_refused(tmp_path: Path):
    rar = tmp_path / "dist.rar"
    rar.write_bytes(b"Rar!\x1a\x07\x00")
    with pytest.raises(StagingError, match="unsupported distribution archive type"):
        stage(_config(tmp_path, rar), quiet=True)


def test_app_dir_override_skips_staging(tmp_path: Path):
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    unpacked = stage(_config(tmp_path, zip_path), quiet=True).root

    cfg = _config(tmp_path / "other", None, app_dir_override=unpacked)
    assert stage(cfg, quiet=True).root == unpacked.resolve()

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(StagingError, match="not a complete CBDB-Desktop tree"):
        stage(_config(tmp_path / "other", None, app_dir_override=empty), quiet=True)


def test_free_space_is_checked_before_extracting(tmp_path: Path, monkeypatch):
    """A too-small disk is reported, not discovered halfway through 1.3 GB."""
    import shutil as _shutil

    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)

    Usage = type("Usage", (), {})
    def tiny(_path):
        u = Usage()
        u.total, u.used, u.free = 1 << 30, 1 << 30, 1024
        return u
    monkeypatch.setattr(_shutil, "disk_usage", tiny)

    with pytest.raises(StagingError, match="Not enough free space"):
        stage(cfg, quiet=True)
    monkeypatch.undo()

    # ...and the same archive stages fine once the disk is real again.
    assert stage(cfg, quiet=True).exe.is_file()


def test_rmtree_names_the_process_holding_the_tree(tmp_path: Path, monkeypatch):
    """A sharing violation becomes a diagnosable error, not a raw OSError."""
    victim = tmp_path / "locked"
    victim.mkdir()
    held = victim / "cbdb.exe"
    held.write_bytes(b"MZ")

    monkeypatch.setattr(staging, "_holders", lambda d: ["4242 " + str(held)])
    with held.open("rb"):  # Windows refuses to delete an open file
        if sys.platform != "win32":
            pytest.skip("POSIX allows deleting an open file")
        with pytest.raises(StagingError) as exc:
            staging._rmtree(victim, attempts=1)
    assert "may still hold the tree open" in str(exc.value)
    assert "4242" in str(exc.value)

    staging._rmtree(victim, attempts=1)  # succeeds once the handle is closed
    assert not victim.exists()


@pytest.mark.parametrize("body", ["not json at all",
                                  '{"manifest_version": 2}',
                                  '{"manifest_version": 2, "entries": "nope"}',
                                  "[]"])
def test_unusable_manifests_are_rejected(tmp_path: Path, body: str):
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)

    (layout.root / MANIFEST_NAME).write_text(body, encoding="utf-8")
    assert read_manifest(layout.root) is None

    stage(cfg, quiet=True)  # an unreadable manifest means restage, not crash
    assert read_manifest(layout.root) is not None


def test_volatile_matching_survives_a_renamed_or_nested_tree():
    """Volatility follows the file, not the exact path it shipped at."""
    assert is_volatile("Data/CBDB.db")
    assert is_volatile("Data/CBDB.db-wal")
    assert is_volatile("cbdb-desktop_20260901/Data/CBDB.db")  # nested build
    assert is_volatile("Data/cbdb.db")                        # Windows casing
    assert not is_volatile("Data/CBDB.db.schema.sql")
    assert not is_volatile("Bin/cbdb.exe")


def test_app_dir_override_wins_over_a_zip(tmp_path: Path):
    """Both set is not an error: the unpacked tree is what gets tested."""
    cfg = load_config({"CBDB_DESKTOP_ZIP": str(tmp_path / "x.zip"),
                       "CBDB_APP_DIR": str(tmp_path / "tree")})
    assert cfg.app_dir_override == tmp_path / "tree"
    assert cfg.zip_path == tmp_path / "x.zip"

    a_file = tmp_path / "afile"
    a_file.write_text("not a tree", encoding="utf-8")
    with pytest.raises(StagingError, match="not a complete CBDB-Desktop tree"):
        stage(_config(tmp_path, None, app_dir_override=a_file), quiet=True)


def test_work_dir_defaults_into_the_repo(tmp_path: Path):
    cfg = load_config({"CBDB_DESKTOP_ZIP": str(tmp_path / "x.zip")})
    assert cfg.work_dir == REPO_ROOT / "work"
    assert cfg.stage_root == REPO_ROOT / "work" / "stage"
    assert cfg.run_root == REPO_ROOT / "work" / "run"


def test_a_vanished_archive_is_reported_as_a_staging_error(tmp_path: Path):
    """Dropbox can remove the file between the check and the read."""
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    fingerprint, _ = archive_identity(zip_path)
    zip_path.unlink()
    with pytest.raises(StagingError, match="disappeared"):
        stage_key(zip_path, fingerprint)


def test_a_corrupted_staged_file_is_not_served_from_cache(tmp_path: Path):
    """A cache hit means verified bytes, not merely a manifest.

    A staged file can be damaged after extraction -- a failed sync, an
    antivirus quarantine-and-restore, a maintainer editing a template
    "just to try something".  Trusting the manifest alone would test that
    tree for weeks under the shipped build's name.
    """
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)

    template = layout.templates_dir / "navigation" / "index.html"
    original = template.read_text(encoding="utf-8")
    tampered = "<html>x</htm>"  # same length: only a checksum can see this
    assert len(tampered) == len(original)
    template.write_text(tampered, encoding="utf-8")

    restaged = stage(cfg, quiet=True)
    assert restaged.root == layout.root
    assert template.read_text(encoding="utf-8") == "<html></html>", \
        "a corrupted tree was served from the cache"


def test_a_shipped_write_ahead_log_is_checkpointed_not_discarded(tmp_path: Path):
    """Committed WAL frames must survive staging.

    The oracle opens the master with immutable=1, which ignores a WAL
    without complaining, so a WAL that reached the master would make the
    oracle quietly answer from pre-WAL data.  The fix is to fold it in,
    not to delete it.
    """
    import sqlite3

    source = tmp_path / "seed.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE BIOG_MAIN(c_personid INTEGER)")
    conn.execute("INSERT INTO BIOG_MAIN VALUES (1762)")
    conn.commit()
    conn.close()

    # Re-open, write more, and snapshot BOTH files while the connection is
    # still open.  Closing it first would checkpoint the frames into the
    # database, and the test would then prove nothing: the row would be in
    # the archived database whether or not staging preserves a WAL.
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("INSERT INTO BIOG_MAIN VALUES (99999)")
    conn.commit()
    db_bytes = source.read_bytes()
    wal_bytes = source.with_name(source.name + "-wal").read_bytes()
    conn.close()
    assert wal_bytes, "the fixture failed to produce a non-empty WAL"

    # The captured database on its own must NOT contain the WAL-only row,
    # or the assertion at the end of this test would be vacuous.
    captured = tmp_path / "captured.db"
    captured.write_bytes(db_bytes)
    probe = sqlite3.connect(captured.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        assert {r[0] for r in probe.execute("SELECT c_personid FROM BIOG_MAIN")} == {1762}
    finally:
        probe.close()

    zip_path = _fake_distribution(
        tmp_path / "dist.zip",
        extra={"Data/CBDB.db": db_bytes, "Data/CBDB.db-wal": wal_bytes})

    layout = stage(_config(tmp_path, zip_path), quiet=True)
    assert not layout.db.with_name("CBDB.db-wal").exists()

    manifest = read_manifest(layout.root)
    assert manifest["wal_checkpointed"] is True

    # The row that lived only in the WAL is now in the database itself --
    # and visible through an immutable connection, which is how the oracle
    # reads it.
    uri = layout.db.resolve().as_uri() + "?mode=ro&immutable=1"
    check = sqlite3.connect(uri, uri=True)
    try:
        rows = {r[0] for r in check.execute("SELECT c_personid FROM BIOG_MAIN")}
    finally:
        check.close()
    assert rows == {1762, 99999}, rows


def test_a_build_stranded_by_a_crash_is_recovered(tmp_path: Path, monkeypatch):
    """A crash between the two renames must not lose the staged build.

    The exception handler that normally puts the tree back cannot run if
    the process dies outright, so the next session has to recognise the
    ``.old-*`` directory and adopt it.
    """
    zip_path = _fake_distribution(tmp_path / "dist.zip")
    cfg = _config(tmp_path, zip_path)
    layout = stage(cfg, quiet=True)
    before = read_manifest(layout.root)

    # Exactly the state a kill -9 in the swap window leaves behind.
    stranded = layout.root.with_name(layout.root.name + ".old-deadbeef")
    layout.root.rename(stranded)
    assert not layout.root.exists()

    # If recovery failed, this would have to unpack the archive again.
    _refuse_to_extract(monkeypatch)
    recovered = stage(cfg, quiet=True)
    monkeypatch.undo()

    assert recovered.root == layout.root
    assert layout.exe.is_file()
    assert read_manifest(layout.root) == before
    assert integrity_mismatches(layout, before) == []
    assert not stranded.exists()


def test_run_directories_are_reclaimed_only_once_their_owner_is_gone(tmp_path: Path):
    """Liveness comes from the owning pid, not from timestamps.

    A session can legitimately go a day without writing to its copy of the
    database -- a long query, a debugger, a paused run -- and deleting its
    1.2 GB working copy underneath it would be far worse than leaking one.
    """
    import os
    import time

    from conftest import _prune_stale_runs

    run_root = tmp_path / "run"
    mine = run_root / f"20260101-120000-{os.getpid()}"     # this very session
    dead = run_root / "20260101-120000-4"                  # pid 4 is not a session
    for path in (mine, dead):
        path.mkdir(parents=True)
        (path / "CBDB.db").write_text("copy", encoding="utf-8")

    # Both look ancient by mtime; only ownership distinguishes them.
    old = time.time() - 72 * 3600
    for path in (mine, dead):
        os.utime(path / "CBDB.db", (old, old))
        os.utime(path, (old, old))

    _prune_stale_runs(run_root)

    assert mine.is_dir(), "a live session's run directory was deleted"
    # pid 4 is the Windows System process: alive, but it can never own a
    # pytest session, so its directory is reclaimed anyway.
    assert not dead.exists(), "a directory no session could own was kept"


def test_a_reused_pid_does_not_strand_a_run_directory_forever(tmp_path: Path):
    """Liveness alone would leak a copy whenever a pid is recycled.

    The owning process is long gone, but its number now belongs to
    something unrelated -- this session, in the test.  Age breaks the tie:
    no pytest run lasts a week.
    """
    import os
    import time

    from conftest import _prune_stale_runs

    run_root = tmp_path / "run"
    recycled = run_root / f"20250101-120000-{os.getpid()}"
    recycled.mkdir(parents=True)
    (recycled / "CBDB.db").write_text("copy", encoding="utf-8")

    _prune_stale_runs(run_root)
    assert recycled.is_dir(), "this session's own directory was deleted"

    ancient = time.time() - 30 * 24 * 3600
    os.utime(recycled / "CBDB.db", (ancient, ancient))
    os.utime(recycled, (ancient, ancient))

    # Rename so it is no longer *this* process's directory, only one whose
    # pid happens to be live.
    stale = run_root / f"20250101-120000-{os.getpid() + 1}"
    if _running(os.getpid() + 1):
        recycled.rename(stale)
        os.utime(stale, (ancient, ancient))
        _prune_stale_runs(run_root)
        assert not stale.exists(), "a month-old directory with a recycled pid was kept"


def _running(pid: int) -> bool:
    from conftest import _process_is_alive
    return _process_is_alive(pid)


def test_an_unrecognisable_run_directory_falls_back_to_age(tmp_path: Path):
    """Without a pid to consult, age decides -- read from the files inside.

    SQLite writing into an existing copy does not touch the directory's
    own mtime, so judging by that alone would delete a busy session's
    database.
    """
    import os
    import time

    from conftest import _prune_stale_runs

    run_root = tmp_path / "run"
    busy = run_root / "handmade-copy"
    ancient = run_root / "handmade-old"
    for path in (busy, ancient):
        path.mkdir(parents=True)
        (path / "CBDB.db").write_text("copy", encoding="utf-8")

    old = time.time() - 72 * 3600
    os.utime(busy, (old, old))                    # directory looks ancient...
    assert (busy / "CBDB.db").stat().st_mtime > old   # ...but the file is live
    os.utime(ancient / "CBDB.db", (old, old))
    os.utime(ancient, (old, old))

    _prune_stale_runs(run_root)

    assert busy.is_dir(), "a directory with live writes was deleted"
    assert not ancient.exists(), "an abandoned directory was left behind"


# ---------------------------------------------------------------------------
# the real distribution
# ---------------------------------------------------------------------------

def test_staged_distribution_matches_the_archive(layout: AppLayout, config: Config):
    """Every immutable staged file matches the archive, size and CRC.

    This is the provenance check for the whole suite: it proves the tree
    the tests drive really is the shipped build, not a leftover or a
    hand-patched copy.  The database and its sidecars are excluded by
    design -- the application rewrites them (see staging.VOLATILE_ENTRIES).
    """
    if config.app_dir_override is not None:
        pytest.skip("CBDB_APP_DIR points at a hand-unpacked tree: no archive to "
                    "compare against.  Unset it to check provenance.")

    manifest = read_manifest(layout.root)
    assert manifest is not None, "staged tree has no manifest"
    assert manifest["zip_path"] == str(config.zip_path)

    checked = immutable_entries(manifest)
    assert len(checked) > 50, f"only {len(checked)} files compared -- check vacuous?"

    # The exclusion must apply to the database and nothing surprising: if a
    # future build renames or nests it, the volatile flag would silently
    # stop matching and this test would fail confusingly on the second run.
    volatile = {e["name"] for e in manifest["entries"] if e.get("volatile")}
    # Case-insensitively: the 2026-09-07 build ships "Data/cbdb.db", the
    # zip builds shipped "Data/CBDB.db", and Windows treats the two as
    # the same file while this comparison would not.
    assert any(name.lower().endswith("cbdb.db") for name in volatile), volatile
    assert not any(name.endswith(".go") or name.endswith(".exe") for name in volatile)

    mismatches = integrity_mismatches(layout, manifest)
    assert not mismatches, "staged tree differs from the archive:\n  " + "\n  ".join(
        mismatches)


def test_distribution_ships_the_expected_pieces(layout: AppLayout):
    """The shipped tree has the shape main.go's defaults assume."""
    assert layout.setup_exe.is_file()
    assert layout.schema_sql.is_file()

    assert {p.name for p in layout.go_sources()} == EXPECTED_GO_SOURCES

    assert set(layout.form_templates()) == EXPECTED_FORM_TEMPLATES

    # QBE is the one page not nested as <form>/index.html: SetupQBERoutes
    # resolves Templates/qbe/qbe.html (qbe_handlers.go).
    assert (layout.templates_dir / "qbe" / "qbe.html").is_file()

    assert (layout.static_dir / "cbdb_styles.css").is_file()
    pickers = sorted(p.name for p in (layout.templates_dir / "pickers").glob("*.html"))
    assert pickers == [
        "address_picker.html", "associations_picker.html", "dynasty_picker.html",
        "entry_picker.html", "office_picker.html", "people_picker.html",
        "status_picker.html", "texts_picker.html",
    ], pickers


#: A template that was saved with the date in its name and shipped next
#: to the live one: ``entry.index.20260906.html``, ``qbe.20260827.html``,
#: ``address_picker.20260729.html``.
_DATED_WORKING_COPY = re.compile(r"\.\d{8}\.html$")


def test_the_distribution_ships_no_dated_working_copies(config):
    """Read the archive's own directory: what did the release include?

    Separate from ``test_distribution_ships_the_expected_pieces``, which
    pins the *shape* the build has to have and fails on anything new for
    a reader to judge.  This one recognises one specific thing and names
    it, so the finding is reported as a finding rather than as "the
    shape changed".

    Read from the archive rather than from the staged tree on purpose:
    the question is what the release contains, and a tree can be
    modified after extraction.  No application and no database needed --
    the cheapest check in the suite, for a defect that cannot depend on
    data.
    """
    if config.app_dir_override is not None:
        pytest.skip("CBDB_APP_DIR points at a hand-unpacked tree: there is "
                    "no archive whose contents could be judged.")

    with Archive.open(config.zip_path) as archive:
        names = [member.name for member in archive.members]

    assert names, "the archive listed no members at all"
    dated = sorted(name for name in names
                   if _DATED_WORKING_COPY.search(name))
    if dated:
        raise KnownShippedDefect(
            f"{len(dated)} of the archive's {len(names)} members are dated "
            f"working copies of templates, shipped beside the live file: "
            f"{dated}")


@pytest.mark.slow
def test_master_database_is_clean_and_valid(layout: AppLayout, sqlite_conn):
    """The master is a usable SQLite database with no leftover sidecars.

    If a ``-wal`` shows up beside the master, something ran the app
    against the pristine tree instead of a per-session copy.
    """
    # By the shipped database's own name, whatever the build calls it:
    # the 2026-09-07 build renamed it to lower case, and a hard-coded
    # "CBDB.db-wal" would look for a sidecar that could never exist and
    # pass without checking anything.
    assert not layout.db.with_name(layout.db.name + "-wal").exists()
    assert not layout.db.with_name(layout.db.name + "-shm").exists()
    assert layout.db.stat().st_size > 1024**3

    assert sqlite_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    tables = {r[0] for r in sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"BIOG_MAIN", "ADDRESSES", "DYNASTIES"} <= tables
    assert sqlite_conn.execute("SELECT COUNT(*) FROM BIOG_MAIN").fetchone()[0] > 100_000


def test_app_gets_a_writable_copy_that_cannot_touch_the_master(
        app_db: Path, layout: AppLayout, tmp_path: Path):
    """Writes to a working copy must leave the master untouched.

    This is the property the whole pristine-master design rests on: the
    application writes ZZ_SCRATCH_* on every query, and none of it may
    reach the tree the oracle and the provenance check read.

    The writing is done to a **fresh** copy taken here rather than to
    the session's ``app_db``.  An earlier version wrote to the session
    copy and asserted its size still matched the master's, which made
    the test order-dependent for no benefit: by the time this file runs,
    the application has legitimately filled the session copy's scratch
    tables, and whether that changes the file's size is up to SQLite's
    page reuse.  It passed against the 2026-09-01 build and failed
    against 2026-09-07 without either build doing anything wrong.

    ``app_db`` is still requested, because the property under test is
    about the design of that fixture -- that it hands out a copy and not
    the master.
    """
    import sqlite3 as _sqlite3

    assert app_db.resolve() != layout.db.resolve()

    private = tmp_path / layout.db.name
    shutil.copyfile(layout.db, private)
    assert private.stat().st_size == layout.db.stat().st_size

    before = (layout.db.stat().st_size, layout.db.stat().st_mtime_ns)

    conn = _sqlite3.connect(private)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS ZZ_TEST_ISOLATION(x INTEGER)")
        conn.execute("INSERT INTO ZZ_TEST_ISOLATION VALUES (1)")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM ZZ_TEST_ISOLATION").fetchone()[0] == 1
        conn.execute("DROP TABLE ZZ_TEST_ISOLATION")
        conn.commit()
    finally:
        conn.close()

    assert (layout.db.stat().st_size, layout.db.stat().st_mtime_ns) == before
    assert not layout.db.with_name(layout.db.name + "-wal").exists()


# ---------------------------------------------------------------------------
# the inputs this suite fixes rather than discovers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixed", [pytest.param(f, id=f"{f.name}-{f.table}") for f in FIXED_INPUTS])
def test_a_fixed_input_still_exists_in_the_shipped_data(fixed, sqlite_conn):
    """Every hand-picked input is a row the shipped data still has.

    Almost every input in this suite is discovered from the data; three
    are fixed, because a browser test that also has to choose its own
    input is two experiments in one (see ``cbdb_desktop/subjects.py``).
    The price of fixing them is that a data refresh can retire one
    silently -- and for ``ASSOC_CODE`` only its *presence* matters to the
    control it enables, so the precondition using it would go on passing
    while the claim beside it had quietly become false.

    Lives here, and not beside the browser tests that use them, because
    it needs no browser: there it would be skipped by the module-wide
    Chromium guard, and a retired input would go unnoticed on exactly
    the machines that skip.

    Membership in a base table -- a fact about the shipped artefact, not
    a reconstruction of anything a handler computes.
    """
    rows = sqlite_conn.execute(
        f'SELECT COUNT(*) FROM "{fixed.table}" WHERE "{fixed.column}" = ?',
        (fixed.value,)).fetchone()[0]

    if fixed.unique:
        assert rows == 1, (
            f"{fixed.name} = {fixed.value} matches {rows} rows in "
            f"{fixed.table}.{fixed.column}, not exactly one.  It is "
            f"{fixed.why}")
    else:
        assert rows, (
            f"{fixed.name} = {fixed.value} matches no row in "
            f"{fixed.table}.{fixed.column}.  It is {fixed.why}")
