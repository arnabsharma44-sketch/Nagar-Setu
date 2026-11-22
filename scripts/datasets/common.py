"""Shared helpers for the external-dataset utilities.

Every script in ``scripts/datasets`` reads the same registry (``datasets/manifest.yaml``)
and writes to the same report directory, so path handling, hashing and safe
extraction live here instead of being copied five times.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = ROOT / "datasets"
EXTERNAL_DIR = DATASETS_DIR / "external"
REPORTS_DIR = DATASETS_DIR / "reports"
MANIFEST_PATH = Path(
    os.environ.get("ROADGUARD_DATASET_MANIFEST", DATASETS_DIR / "manifest.yaml")
).resolve()


def load_manifest() -> dict[str, Any]:
    """Read manifest.yaml. PyYAML is optional; a tiny parser covers this file."""
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"manifest not found: {MANIFEST_PATH}")
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        print(
            "PyYAML is not installed. Install it with: pip install pyyaml",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def dataset_root(entry: dict[str, Any]) -> Path:
    return ROOT / str(entry["root"])


def archive_path(entry: dict[str, Any]) -> Path:
    return dataset_root(entry) / str(entry["raw_dir"]) / str(entry["archive_name"])


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def human_bytes(size: int | None) -> str:
    if size is None:
        return "unknown"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"


def safe_extract(archive: Path, destination: Path) -> list[Path]:
    """Extract a zip without allowing entries to escape ``destination``."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise SystemExit(f"refusing unsafe archive member: {member.filename}")
        bundle.extractall(destination)
        written = [(destination / name).resolve() for name in bundle.namelist()]
    return written


def zip_is_intact(archive: Path) -> tuple[bool, str | None]:
    try:
        with zipfile.ZipFile(archive) as bundle:
            bad = bundle.testzip()
            if bad is not None:
                return False, f"corrupt member: {bad}"
        return True, None
    except (zipfile.BadZipFile, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metadata_path(entry: dict[str, Any]) -> Path:
    return dataset_root(entry) / "dataset_metadata.json"


def load_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    path = metadata_path(entry)
    return read_json(path) if path.exists() else {}


def save_metadata(entry: dict[str, Any], updates: dict[str, Any]) -> Path:
    payload = load_metadata(entry)
    payload.setdefault("dataset", entry.get("title"))
    payload.setdefault("source_url", entry.get("source_url"))
    payload.setdefault("license", " ".join(str(entry.get("license", "")).split()))
    payload["updated_at"] = datetime.now(UTC).isoformat()
    payload.update(updates)
    return write_json(metadata_path(entry), payload)


def select_datasets(manifest: dict[str, Any], wanted: list[str] | None) -> dict[str, Any]:
    datasets = manifest.get("datasets", {})
    if not wanted or "all" in wanted:
        return datasets
    unknown = [name for name in wanted if name not in datasets]
    if unknown:
        raise SystemExit(
            f"unknown dataset(s): {', '.join(unknown)}. Known: {', '.join(sorted(datasets))}"
        )
    return {name: datasets[name] for name in wanted}


def status_line(label: str, status: str, detail: str = "") -> str:
    """One aligned line so CLI output is readable and greppable."""
    return f"[{status:<14}] {label:<20} {detail}".rstrip()


def manual_instructions(entry: dict[str, Any], name: str = "") -> str:
    """Exact human steps when automated download is not permitted."""
    root = str(entry["root"])
    archive = f"{root}/{entry['raw_dir']}/{entry['archive_name']}"
    return "\n".join(
        [
            f"Dataset : {entry['title']}",
            f"Source  : {entry['source_url']}",
            f"Archive : {entry['archive_name']}",
            f"Size    : {entry.get('expected_bytes') or 'not published'}",
            f"Licence : {' '.join(str(entry.get('license', '')).split())}",
            f"Why     : {' '.join(str(entry.get('access_note', '')).split())}",
            f"Save to : {archive}",
            "Then    : python scripts/datasets/verify_downloads.py --dataset " + (name or "all"),
        ]
    )


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)
