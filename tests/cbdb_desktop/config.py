"""Environment / configuration for the CBDB-Desktop test suite.

Values come from the process environment first, then from the repo-root
``.env`` file (see ``.env.example``).  Nothing else in the suite reads
``os.environ`` directly.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal ``KEY=VALUE`` reader.

    Deliberately dependency-free and deliberately dumb: no interpolation,
    no export keyword, no multi-line values.  Windows paths contain
    backslashes and colons, so values are taken verbatim -- the only
    processing is stripping surrounding whitespace and one optional layer
    of matching quotes.
    """
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


class MissingConfig(RuntimeError):
    """A required setting is absent, or a supplied setting is malformed."""


@dataclass(frozen=True)
class Config:
    """Resolved settings for one test session."""

    zip_path: Path | None
    work_dir: Path
    app_dir_override: Path | None
    startup_timeout: float
    http_timeout: float
    suppress_browser: bool
    keep_run_dir: bool

    @property
    def stage_root(self) -> Path:
        """Directory holding the unpacked distributions."""
        return self.work_dir / "stage"

    @property
    def run_root(self) -> Path:
        """Directory holding per-session working copies of the database."""
        return self.work_dir / "run"

    def require_zip(self) -> Path:
        if self.zip_path is None:
            raise MissingConfig(
                "CBDB_DESKTOP_ZIP is not set.  Copy .env.example to .env and "
                "point CBDB_DESKTOP_ZIP at the cbdb-desktop_<date>.zip you "
                "want to test (or set CBDB_APP_DIR to an unpacked tree)."
            )
        if not self.zip_path.is_file():
            raise MissingConfig(f"CBDB_DESKTOP_ZIP does not exist: {self.zip_path}")
        return self.zip_path


def _as_bool(value: str, *, name: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise MissingConfig(f"{name} must be a boolean-ish value, got {value!r}")


def _as_float(value: str, *, name: str) -> float:
    try:
        out = float(value)
    except ValueError as exc:
        raise MissingConfig(f"{name} must be a number, got {value!r}") from exc
    # nan slips past every comparison ("nan <= 0" is False) and would make
    # each downstream deadline check silently false, so screen it here.
    if not math.isfinite(out) or out <= 0:
        raise MissingConfig(f"{name} must be a finite number > 0, got {value!r}")
    return out


# Sentinel distinguishing "caller said nothing about the env file" from
# "caller explicitly asked for this file" -- see load_config.
_DEFAULT_ENV_FILE = object()


def load_config(env: dict[str, str] | None = None, env_file=_DEFAULT_ENV_FILE) -> Config:
    """Resolve the configuration.

    With no arguments: the repo-root ``.env`` supplies defaults and the
    process environment overrides them.

    Passing ``env`` replaces the process environment *and* suppresses the
    ``.env`` file unless ``env_file`` names one explicitly -- so a unit
    test of this module never inherits the maintainer's local settings.
    """
    if env_file is _DEFAULT_ENV_FILE:
        path = None if env is not None else ENV_FILE
    else:
        path = env_file

    source: dict[str, str] = dict(_parse_env_file(Path(path))) if path else {}
    source.update(os.environ if env is None else env)

    def get(name: str, default: str | None = None) -> str | None:
        value = source.get(name)
        if value is None or value.strip() == "":
            return default
        return value.strip()

    zip_raw = get("CBDB_DESKTOP_ZIP")
    app_raw = get("CBDB_APP_DIR")
    work_raw = get("CBDB_WORK_DIR")

    return Config(
        zip_path=Path(zip_raw) if zip_raw else None,
        work_dir=Path(work_raw) if work_raw else REPO_ROOT / "work",
        app_dir_override=Path(app_raw) if app_raw else None,
        startup_timeout=_as_float(get("CBDB_STARTUP_TIMEOUT", "180"),
                                  name="CBDB_STARTUP_TIMEOUT"),
        http_timeout=_as_float(get("CBDB_HTTP_TIMEOUT", "300"),
                               name="CBDB_HTTP_TIMEOUT"),
        suppress_browser=_as_bool(get("CBDB_SUPPRESS_BROWSER", "1"),
                                  name="CBDB_SUPPRESS_BROWSER"),
        keep_run_dir=_as_bool(get("CBDB_KEEP_RUN_DIR", "0"),
                              name="CBDB_KEEP_RUN_DIR"),
    )
