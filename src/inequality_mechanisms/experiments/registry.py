"""On-disk experiment run registry (IM-016).

Each run lives under ``results/<run_id>/`` with a frozen config, captured
code revision and environment, and a manifest that indexes registered
outputs. Completed runs are immutable: existing completed directories are
never overwritten.
"""

from __future__ import annotations

import json
import os
import platform
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from inequality_mechanisms import __version__ as PACKAGE_VERSION
from inequality_mechanisms.experiments.config import (
    ExperimentConfig,
    experiment_config_to_yaml,
    load_experiment_config,
)

RunStatus = Literal["created", "running", "completed", "failed"]

_MANIFEST_NAME = "manifest.json"
_CONFIG_NAME = "config.yaml"
_REVISION_NAME = "revision.json"
_ENVIRONMENT_NAME = "environment.json"
_OUTPUTS_DIRNAME = "outputs"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_TRACKED_PACKAGES = (
    "numpy",
    "scipy",
    "pydantic",
    "pyyaml",
    "typer",
    "matplotlib",
)


class RunRegistryError(RuntimeError):
    """Raised when a registry operation violates immutability or layout rules."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def generate_run_id(*, seed: int | None = None) -> str:
    """Return a filesystem-safe unique run id.

    Format is ``YYYYMMDDTHHMMSSZ_<8hex>`` optionally prefixed with
    ``seed<N>_`` when ``seed`` is provided for easier browsing.
    """
    suffix = secrets.token_hex(4)
    stamp = _utc_stamp()
    if seed is None:
        return f"{stamp}_{suffix}"
    return f"seed{int(seed)}_{stamp}_{suffix}"


def validate_run_id(run_id: str) -> str:
    """Validate and return a filesystem-safe run id.

    Raises
    ------
    ValueError
        If ``run_id`` is empty, contains path separators, or fails the
        allowed character pattern.
    """
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")
    if "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
        raise ValueError(f"run_id must not contain path separators: {run_id!r}")
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            "run_id must match "
            r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$, "
            f"got {run_id!r}"
        )
    return run_id


def default_results_root() -> Path:
    """Return the repository ``results/`` directory when detectable.

    Falls back to ``Path('results')`` relative to the current working
    directory.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "results"
        if candidate.is_dir() and (parent / "pyproject.toml").is_file():
            return candidate
    return Path("results")


def capture_revision(*, cwd: Path | None = None) -> dict[str, Any]:
    """Capture package version and best-effort git revision metadata.

    Parameters
    ----------
    cwd :
        Working directory for git commands. Defaults to the process cwd.

    Returns
    -------
    dict
        Keys include ``package_version``, ``git_commit``, ``git_describe``,
        ``git_dirty``, and ``git_error`` (``None`` when git succeeds).
    """
    work = Path.cwd() if cwd is None else Path(cwd)
    payload: dict[str, Any] = {
        "package_version": PACKAGE_VERSION,
        "git_commit": None,
        "git_describe": None,
        "git_dirty": None,
        "git_error": None,
    }

    def _git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=work,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    try:
        payload["git_commit"] = _git("rev-parse", "HEAD")
        try:
            payload["git_describe"] = _git("describe", "--always", "--tags", "--dirty")
        except subprocess.CalledProcessError:
            payload["git_describe"] = payload["git_commit"]
        dirty_out = _git("status", "--porcelain")
        payload["git_dirty"] = bool(dirty_out)
    except (OSError, subprocess.CalledProcessError) as exc:
        payload["git_error"] = str(exc)
    return payload


def capture_environment() -> dict[str, Any]:
    """Capture interpreter, platform, and tracked dependency versions."""
    packages: dict[str, str | None] = {}
    for name in _TRACKED_PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": packages,
    }


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RunRegistryError(
            f"expected JSON object at {path}, got {type(data).__name__}"
        )
    return data


@dataclass
class ExperimentRun:
    """Handle for one registered experiment run directory.

    Attributes
    ----------
    run_id :
        Directory name under ``results_root``.
    path :
        Absolute path to the run directory.
    """

    run_id: str
    path: Path
    _manifest: dict[str, Any] = field(repr=False)

    @property
    def manifest_path(self) -> Path:
        """Path to ``manifest.json``."""
        return self.path / _MANIFEST_NAME

    @property
    def config_path(self) -> Path:
        """Path to the frozen ``config.yaml``."""
        return self.path / _CONFIG_NAME

    @property
    def outputs_dir(self) -> Path:
        """Directory for registered output artifacts."""
        return self.path / _OUTPUTS_DIRNAME

    @property
    def status(self) -> RunStatus:
        """Current run status from the on-disk manifest."""
        return self._manifest["status"]  # type: ignore[no-any-return]

    @property
    def seed(self) -> int:
        """Master RNG seed recorded for this run."""
        return int(self._manifest["seed"])

    @property
    def outputs(self) -> dict[str, str]:
        """Copy of logical output name -> relative path mapping."""
        raw = self._manifest.get("outputs", {})
        if not isinstance(raw, dict):
            raise RunRegistryError("manifest.outputs must be a mapping")
        return {str(k): str(v) for k, v in raw.items()}

    @property
    def revision(self) -> dict[str, Any]:
        """Revision metadata recorded at run creation."""
        return dict(self._manifest.get("revision", {}))

    @property
    def environment(self) -> dict[str, Any]:
        """Environment metadata recorded at run creation."""
        return dict(self._manifest.get("environment", {}))

    @property
    def failure_reason(self) -> str | None:
        """Failure reason when status is ``failed``, else ``None``."""
        value = self._manifest.get("failure_reason")
        return None if value is None else str(value)

    def load_config(self) -> ExperimentConfig:
        """Load and validate the frozen run config."""
        return load_experiment_config(self.config_path)

    def reload(self) -> ExperimentRun:
        """Re-read the manifest from disk into this handle."""
        self._manifest = _read_json(self.manifest_path)
        return self

    def _require_writable(self) -> None:
        if self.status == "completed":
            raise RunRegistryError(
                f"refusing to modify completed run {self.run_id!r} at {self.path}"
            )

    def _write_manifest(self) -> None:
        self._manifest["updated_at"] = _utc_now_iso()
        _atomic_write_json(self.manifest_path, self._manifest)

    def mark_running(self) -> None:
        """Transition ``created``/``running``/``failed`` -> ``running``."""
        self._require_writable()
        if self.status == "failed":
            self._manifest["failure_reason"] = None
        self._manifest["status"] = "running"
        if "started_at" not in self._manifest or self._manifest["started_at"] is None:
            self._manifest["started_at"] = _utc_now_iso()
        self._write_manifest()

    def mark_completed(self) -> None:
        """Mark the run completed (immutable thereafter)."""
        self._require_writable()
        self._manifest["status"] = "completed"
        self._manifest["completed_at"] = _utc_now_iso()
        self._manifest["failure_reason"] = None
        self._write_manifest()

    def mark_failed(self, reason: str) -> None:
        """Mark the run failed and record ``reason``.

        Failed runs remain writable so retries or partial outputs can be
        preserved; only ``completed`` runs are immutable.
        """
        self._require_writable()
        if not reason:
            raise ValueError("failure reason must be a non-empty string")
        self._manifest["status"] = "failed"
        self._manifest["failure_reason"] = str(reason)
        self._manifest["completed_at"] = _utc_now_iso()
        self._write_manifest()

    def resolve_output(self, name: str) -> Path:
        """Return the absolute path for a registered output name.

        Raises
        ------
        KeyError
            If ``name`` is not registered.
        """
        rel = self.outputs.get(name)
        if rel is None:
            raise KeyError(f"output {name!r} is not registered on run {self.run_id!r}")
        return self.path / rel

    def register_output(self, name: str, relative_path: str) -> Path:
        """Register an existing artifact path under the run directory.

        Use this for binary outputs (e.g. PNG figures) written outside
        ``write_json`` / ``write_text``. The file must already exist at
        ``self.path / relative_path``.

        Parameters
        ----------
        name :
            Logical output key (single path segment).
        relative_path :
            Path relative to the run directory (typically under
            ``outputs/``).

        Returns
        -------
        Path
            Absolute path of the registered file.

        Raises
        ------
        RunRegistryError
            If the run is completed, or ``name`` is already bound to a
            different path.
        FileNotFoundError
            If the artifact file is missing.
        ValueError
            If ``name`` or ``relative_path`` is invalid.
        """
        self._require_writable()
        rel = str(relative_path).replace("\\", "/")
        if not rel or rel.startswith("/") or ".." in Path(rel).parts:
            raise ValueError(f"invalid relative_path: {relative_path!r}")
        path = self.path / rel
        if not path.is_file():
            raise FileNotFoundError(f"cannot register missing artifact: {path}")
        self._register(name, rel)
        return path

    def _register(self, name: str, relative_path: str) -> None:
        if not name or "/" in name or "\\" in name:
            raise ValueError(f"output name must be a single path segment, got {name!r}")
        outputs = dict(self._manifest.get("outputs", {}))
        if name in outputs and outputs[name] != relative_path:
            raise RunRegistryError(
                f"output {name!r} already registered as {outputs[name]!r}; "
                f"refusing to rebind to {relative_path!r}"
            )
        outputs[name] = relative_path
        self._manifest["outputs"] = outputs
        self._write_manifest()

    def write_json(self, name: str, payload: Any) -> Path:
        """Write a JSON artifact under ``outputs/`` and register it.

        Parameters
        ----------
        name :
            Logical output key (also used as the basename stem).
        payload :
            JSON-serializable object.

        Returns
        -------
        Path
            Absolute path of the written file.
        """
        self._require_writable()
        relative = f"{_OUTPUTS_DIRNAME}/{name}.json"
        path = self.path / relative
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        _atomic_write_text(path, text)
        self._register(name, relative)
        return path

    def write_text(self, name: str, text: str, *, suffix: str = ".txt") -> Path:
        """Write a text artifact under ``outputs/`` and register it."""
        self._require_writable()
        if not suffix.startswith("."):
            raise ValueError(f"suffix must start with '.', got {suffix!r}")
        relative = f"{_OUTPUTS_DIRNAME}/{name}{suffix}"
        path = self.path / relative
        _atomic_write_text(path, text)
        self._register(name, relative)
        return path

    def append_jsonl(self, name: str, records: list[dict[str, Any]]) -> Path:
        """Append JSON Lines records and register the artifact.

        Failed trial records should be written through this path so
        analysis can read failures without mutating raw files later.
        Creating the file when absent is allowed; overwriting an existing
        completed run is not.
        """
        self._require_writable()
        if not isinstance(records, list):
            raise TypeError("records must be a list of dicts")
        relative = f"{_OUTPUTS_DIRNAME}/{name}.jsonl"
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                if not isinstance(record, dict):
                    raise TypeError("each JSONL record must be a dict")
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._register(name, relative)
        return path

    def read_json(self, name: str) -> Any:
        """Load a registered JSON output."""
        path = self.resolve_output(name)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        """Load a registered JSONL output as a list of objects."""
        path = self.resolve_output(name)
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                if not isinstance(obj, dict):
                    raise RunRegistryError(
                        f"{path}:{line_no}: expected JSON object, "
                        f"got {type(obj).__name__}"
                    )
                rows.append(obj)
        return rows


def create_run(
    config: ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    revision: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    revision_cwd: Path | str | None = None,
) -> ExperimentRun:
    """Create a new run directory and write provenance metadata.

    Parameters
    ----------
    config :
        Validated experiment configuration (seed is copied into the
        manifest; the full config is frozen as ``config.yaml``).
    results_root :
        Parent directory for runs. Defaults to :func:`default_results_root`.
    run_id :
        Optional explicit id; otherwise :func:`generate_run_id` is used.
    revision, environment :
        Optional pre-captured metadata; defaults call
        :func:`capture_revision` / :func:`capture_environment`.
    revision_cwd :
        Working directory for git capture when ``revision`` is omitted.

    Returns
    -------
    ExperimentRun
        Handle for the new run (status ``created``).

    Raises
    ------
    FileExistsError
        If the run directory already exists (never overwrites).
    ValueError
        If ``run_id`` is invalid.
    """
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")

    root = Path(results_root) if results_root is not None else default_results_root()
    root.mkdir(parents=True, exist_ok=True)

    if run_id is not None:
        rid = validate_run_id(run_id)
    else:
        rid = generate_run_id(seed=config.seed)
    run_dir = root / rid
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")

    rev = (
        dict(revision)
        if revision is not None
        else capture_revision(cwd=None if revision_cwd is None else Path(revision_cwd))
    )
    env = dict(environment) if environment is not None else capture_environment()

    run_dir.mkdir(parents=False, exist_ok=False)
    (run_dir / _OUTPUTS_DIRNAME).mkdir()

    config_text = experiment_config_to_yaml(config)
    _atomic_write_text(run_dir / _CONFIG_NAME, config_text)
    _atomic_write_json(run_dir / _REVISION_NAME, rev)
    _atomic_write_json(run_dir / _ENVIRONMENT_NAME, env)

    created = _utc_now_iso()
    manifest: dict[str, Any] = {
        "run_id": rid,
        "status": "created",
        "seed": int(config.seed),
        "created_at": created,
        "updated_at": created,
        "started_at": None,
        "completed_at": None,
        "failure_reason": None,
        "config_path": _CONFIG_NAME,
        "revision_path": _REVISION_NAME,
        "environment_path": _ENVIRONMENT_NAME,
        "revision": rev,
        "environment": env,
        "outputs": {},
    }
    _atomic_write_json(run_dir / _MANIFEST_NAME, manifest)
    return ExperimentRun(run_id=rid, path=run_dir.resolve(), _manifest=manifest)


def load_run(
    run_id_or_path: str | Path,
    *,
    results_root: Path | str | None = None,
) -> ExperimentRun:
    """Load an existing run by id or by directory path.

    Parameters
    ----------
    run_id_or_path :
        Run id under ``results_root``, or a path to a run directory
        containing ``manifest.json``.
    results_root :
        Used when ``run_id_or_path`` is a bare run id.

    Returns
    -------
    ExperimentRun

    Raises
    ------
    FileNotFoundError
        If the run directory or manifest is missing.
    RunRegistryError
        If the manifest is malformed.
    """
    candidate = Path(run_id_or_path)
    if candidate.is_dir() and (candidate / _MANIFEST_NAME).is_file():
        run_dir = candidate.resolve()
    else:
        rid = validate_run_id(str(run_id_or_path))
        if results_root is not None:
            root = Path(results_root)
        else:
            root = default_results_root()
        run_dir = (root / rid).resolve()
        if not run_dir.is_dir():
            raise FileNotFoundError(f"run directory not found: {run_dir}")

    manifest_path = run_dir / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    manifest = _read_json(manifest_path)
    rid = str(manifest.get("run_id", run_dir.name))
    if "status" not in manifest or "seed" not in manifest:
        raise RunRegistryError(f"manifest missing required fields at {manifest_path}")
    if not (run_dir / _CONFIG_NAME).is_file():
        raise RunRegistryError(f"missing frozen config at {run_dir / _CONFIG_NAME}")
    return ExperimentRun(run_id=rid, path=run_dir, _manifest=manifest)


def list_runs(
    results_root: Path | str | None = None,
    *,
    status: RunStatus | None = None,
) -> list[ExperimentRun]:
    """List runs under ``results_root``, optionally filtered by status.

    Runs are sorted by ``created_at`` ascending (missing timestamps last),
    then by ``run_id``.
    """
    root = Path(results_root) if results_root is not None else default_results_root()
    if not root.is_dir():
        return []

    runs: list[ExperimentRun] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (child / _MANIFEST_NAME).is_file():
            continue
        try:
            run = load_run(child)
        except (RunRegistryError, OSError, json.JSONDecodeError):
            continue
        if status is not None and run.status != status:
            continue
        runs.append(run)

    def _sort_key(run: ExperimentRun) -> tuple[str, str]:
        created = str(run._manifest.get("created_at") or "9999")
        return (created, run.run_id)

    return sorted(runs, key=_sort_key)


def dump_manifest(run: ExperimentRun) -> dict[str, Any]:
    """Return a deep copy of the run manifest suitable for inspection."""
    copied: dict[str, Any] = json.loads(json.dumps(run._manifest))
    return copied
