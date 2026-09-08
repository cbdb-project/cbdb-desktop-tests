"""Read a CBDB-Desktop distribution archive, whichever container it uses.

The distribution has been shipped as a ``.zip`` and, since the
2026-09-07 build, as a ``.7z``.  Nothing above this module should care
which: staging wants the same three things from either one --

* a **list of members** carrying each file's uncompressed size and
  CRC-32, so a staged tree can be re-verified against the archive on
  every cache hit without unpacking it again;
* an **extraction** that refuses any member which would escape the
  destination;
* a **stable member naming**, so a manifest written from one archive
  format is comparable with the tree on disk.

The last of those is the one with a wrinkle.  The zip builds put the
tree at the archive root (``cbdb.exe``, ``Data/CBDB.db``); the 7z build
wraps it in a single ``CBDB-Desktop/`` directory.  A member list that
kept the wrapper would make every path in the manifest -- and every
staged path -- one level deeper than the suite expects, so a lone common
root directory is **stripped**, here, once, and the rest of the suite
never learns it existed.

Why not shell out to ``7z.exe``: it is not part of any Python
environment this suite installs, its output would have to be scraped for
the CRCs, and a missing installation would turn "test the shipped build"
into "test nothing".  ``py7zr`` is a declared dependency and reports
size and CRC-32 as data.
"""
from __future__ import annotations

import os
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class ArchiveError(RuntimeError):
    """The archive cannot be read, or holds a member that must not be extracted."""


@dataclass(frozen=True)
class Member:
    """One file inside a distribution archive, named relative to the tree root."""

    name: str   # POSIX-separated, with any common root directory stripped
    size: int
    crc: int


def _unsafe(name: str) -> bool:
    """True if extracting this member could write outside the destination."""
    return (name.startswith("/")
            or "\\" in name
            or ".." in Path(name).parts
            or (len(name) > 1 and name[1] == ":"))


def common_root(names: list[str]) -> str | None:
    """The single directory every member sits inside, if there is one.

    Returns ``None`` when members live at the archive root, when they
    are spread across more than one top-level directory, or when a
    *file* sits at the root next to the candidate directory -- stripping
    then would silently drop that file.
    """
    if not names:
        return None
    roots = {name.split("/", 1)[0] for name in names}
    if len(roots) != 1:
        return None
    root = roots.pop()
    if root in ("", ".", "..") or _unsafe(root):
        # Not a directory that can be stripped.  Stripping ".." would
        # also turn a traversal member into an innocent-looking one --
        # safety is enforced on the raw names either way, but the two
        # views of the archive must not disagree about a member's name.
        return None
    if any(name == root for name in names):   # a root-level file, not a directory
        return None
    return root


def _replace_with_retry(source: Path, dest: Path, *, attempts: int = 6) -> None:
    """``os.replace`` with backoff, and an error that says what it was doing."""
    for attempt in range(attempts):
        try:
            os.replace(source, dest)
            return
        except OSError as exc:
            if attempt == attempts - 1:
                raise ArchiveError(
                    f"could not move the unpacked tree into place "
                    f"({source} -> {dest}): {exc}") from exc
            time.sleep(0.5 * (attempt + 1))


class Archive:
    """A distribution archive, opened for listing and extraction.

    Use as a context manager.  ``members`` is populated on entry; it is
    the archive's own central directory, not a scan of anything on disk.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.members: list[Member] = []
        self.root: str | None = None
        self._handle = None

    # -- construction ------------------------------------------------------

    @classmethod
    def open(cls, path: Path) -> "Archive":
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".zip":
            return _ZipArchive(path)
        if suffix == ".7z":
            return _SevenZipArchive(path)
        raise ArchiveError(
            f"{path.name}: unsupported distribution archive type {suffix!r}.  "
            "The suite reads .zip and .7z.")

    def __enter__(self) -> "Archive":
        self._open()
        try:
            raw = list(self._raw_members())
            self.root = common_root([name for name, _, _ in raw])
            prefix = f"{self.root}/" if self.root else ""
            self.members = [
                Member(name=name[len(prefix):], size=size, crc=crc)
                for name, size, crc in raw
                if name != self.root
            ]
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        """Release the reader.  Idempotent, and safe to call mid-use."""
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.close()

    # -- backend interface -------------------------------------------------

    def _open(self) -> None:
        raise NotImplementedError

    def _raw_members(self) -> Iterator[tuple[str, int, int]]:
        """``(name, size, crc)`` per *file* member, names as stored."""
        raise NotImplementedError

    def _extractall(self, dest: Path) -> None:
        raise NotImplementedError

    # -- use ---------------------------------------------------------------

    @property
    def unpacked_size(self) -> int:
        return sum(m.size for m in self.members)

    def check_safe(self) -> None:
        """Refuse the whole archive if any member could escape its destination.

        Checked before a single byte is written: a per-member skip would
        leave a partial tree that looks staged.
        """
        for name, _, _ in self._raw_members():
            if _unsafe(name):
                raise ArchiveError(
                    f"Refusing to extract unsafe archive member: {name!r}")

    def extract_to(self, dest: Path) -> None:
        """Unpack the tree into ``dest``, which must not already exist.

        When the archive wraps everything in one directory, extraction
        goes to a sibling scratch directory and the wrapper is *renamed*
        into place -- a rename on the same volume, not a 1.3 GB copy.
        """
        self.check_safe()
        if dest.exists():
            raise ArchiveError(f"refusing to extract over an existing tree: {dest}")
        if not self.root:
            self._extractall(dest)
            return

        scratch = dest.with_name(dest.name + ".unwrap")
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            self._extractall(scratch)
            inner = scratch / self.root
            if not inner.is_dir():
                raise ArchiveError(
                    f"{self.path.name}: expected every member under "
                    f"{self.root!r}, but it did not appear on extraction")
            # The reader is released first.  py7zr leaves the archive --
            # and, on Windows, handles under the extraction directory --
            # open after extractall, and Windows refuses to rename a
            # directory anything still holds open: this failed here once,
            # after a full 1.3 GB extraction had already succeeded.  The
            # retries cover the other likely holder of two freshly
            # written 30 MB executables, an antivirus scan mid-sweep.
            self.close()
            _replace_with_retry(inner, dest)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


class _ZipArchive(Archive):
    def _open(self) -> None:
        try:
            self._handle = zipfile.ZipFile(self.path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ArchiveError(
                f"{self.path} is not a readable zip archive: {exc}") from exc

    def _raw_members(self) -> Iterator[tuple[str, int, int]]:
        for info in self._handle.infolist():
            if info.is_dir():
                continue
            yield info.filename, info.file_size, info.CRC

    def _extractall(self, dest: Path) -> None:
        self._handle.extractall(dest)


class _SevenZipArchive(Archive):
    def _open(self) -> None:
        try:
            import py7zr
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ArchiveError(
                "reading a .7z distribution needs py7zr.  Run: "
                "python -m pip install -r requirements.txt") from exc
        self._py7zr = py7zr
        try:
            self._handle = py7zr.SevenZipFile(self.path, mode="r")
        except (py7zr.Bad7zFile, OSError) as exc:
            raise ArchiveError(
                f"{self.path} is not a readable 7z archive: {exc}") from exc

    def _raw_members(self) -> Iterator[tuple[str, int, int]]:
        for info in self._handle.list():
            if info.is_directory:
                continue
            # py7zr normalises separators to "/" and reports crc32 as
            # None for an empty file, where zipfile reports 0.
            yield info.filename, info.uncompressed, info.crc32 or 0

    def _extractall(self, dest: Path) -> None:
        # A SevenZipFile is a one-shot reader: py7zr consumes the stream
        # on extract, and list() after that returns nothing useful.  The
        # members are already captured, so simply reopen.
        self._handle.close()
        self._handle = self._py7zr.SevenZipFile(self.path, mode="r")
        try:
            self._handle.extractall(path=dest)
        except self._py7zr.exceptions.ArchiveError as exc:
            raise ArchiveError(f"could not extract {self.path}: {exc}") from exc
