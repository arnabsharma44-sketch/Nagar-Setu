"""Validate operator-supplied CCTV footage and optionally ingest it.

Public accident/CCTV corpora are either enormous, dashcam-only, or gated behind a
request form (see ``docs/DATASETS.md``). The practical path for a city pilot is to
supply its own footage. This script makes that safe and repeatable:

* probes each file with OpenCV (resolution, fps, frame count, duration);
* hashes it with SHA-256 so a clip can be named in an audit trail;
* rejects anything the API would reject (container, size, duration, resolution);
* writes a provenance manifest (JSON) next to the clips;
* with ``--upload``, signs in and pushes each ready clip through the same
  upload-url -> PUT -> complete-upload flow the web application uses.

Examples
--------
    python scripts/prepare_dataset.py --input datasets/incoming
    python scripts/prepare_dataset.py --input datasets/incoming --upload \
        --api-url http://localhost:8000 --email ops@demo.roadguard.ai

The password is read from ``DEMO_SEED_PASSWORD`` or prompted for; it is never
passed on the command line.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "apps" / "api", ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.core.config import settings  # noqa: E402

CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/quicktime",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}
VIDEO_EXTENSIONS = set(CONTENT_TYPES)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict | None:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        return None
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    duration = round(frames / fps, 3) if fps > 0 and frames > 0 else None
    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "frame_count": frames,
        "duration_seconds": duration,
    }


def evaluate(path: Path, size: int, meta: dict | None) -> list[str]:
    problems: list[str] = []
    suffix = path.suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        problems.append(f"UNSUPPORTED_CONTAINER ({suffix or 'no extension'})")
    if meta is None:
        problems.append("UNREADABLE_VIDEO")
        return problems
    if size == 0:
        problems.append("EMPTY_FILE")
    if size > settings.max_upload_bytes:
        problems.append(
            f"TOO_LARGE ({size} bytes > MAX_UPLOAD_BYTES {settings.max_upload_bytes})"
        )
    if meta["width"] > settings.max_video_width or meta["height"] > settings.max_video_height:
        problems.append(
            f"RESOLUTION_LIMIT ({meta['width']}x{meta['height']} > "
            f"{settings.max_video_width}x{settings.max_video_height})"
        )
    duration = meta.get("duration_seconds")
    if duration is None:
        problems.append("UNKNOWN_DURATION")
    elif duration > settings.max_video_duration_seconds:
        problems.append(
            f"TOO_LONG ({duration}s > MAX_VIDEO_DURATION_SECONDS "
            f"{settings.max_video_duration_seconds}s)"
        )
    return problems


def collect(inputs: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            files.extend(
                sorted(
                    candidate
                    for candidate in path.glob(pattern)
                    if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS
                )
            )
        elif path.is_file():
            files.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def upload_clip(client, path: Path, camera_id: str | None, wait_seconds: int) -> dict:
    import httpx

    content_type = CONTENT_TYPES[path.suffix.lower()]
    payload = {
        "filename": path.name,
        "content_type": content_type,
        "file_size_bytes": path.stat().st_size,
    }
    if camera_id:
        payload["camera_id"] = camera_id
    signed = client.post("/api/v1/videos/upload-url", json=payload)
    signed.raise_for_status()
    data = signed.json()["data"]

    target = data["upload_url"]
    if target.startswith("/"):
        target = str(client.base_url).rstrip("/") + target
    with path.open("rb") as handle:
        pushed = httpx.put(
            target,
            content=handle.read(),
            headers={"content-type": content_type},
            timeout=600.0,
        )
    pushed.raise_for_status()

    finalised = client.post(f"/api/v1/videos/{data['video_id']}/complete-upload")
    finalised.raise_for_status()
    video = finalised.json()["data"]

    result = {"video_id": video["id"], "status": video["status"], "job": None}
    jobs = client.get("/api/v1/jobs", params={"video_id": video["id"]}).json()["data"]
    if not jobs:
        client.post(f"/api/v1/videos/{video['id']}/process", json={"force_reprocess": False})
        jobs = client.get("/api/v1/jobs", params={"video_id": video["id"]}).json()["data"]
    if not jobs:
        return result
    job_id = jobs[0]["id"]
    result["job"] = {"job_id": job_id, "status": jobs[0]["status"]}

    deadline = time.time() + wait_seconds
    while wait_seconds > 0 and time.time() < deadline:
        current = client.get(f"/api/v1/jobs/{job_id}").json()["data"]
        result["job"] = {
            "job_id": job_id,
            "status": current["status"],
            "stage": current.get("stage"),
            "progress": current.get("progress"),
        }
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(2.0)
    return result


def sign_in(api_url: str, email: str):
    import httpx

    password = os.environ.get("DEMO_SEED_PASSWORD") or getpass.getpass(
        f"Password for {email}: "
    )
    client = httpx.Client(base_url=api_url.rstrip("/"), timeout=60.0)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"Sign-in failed ({response.status_code}): {response.text[:300]}")
    client.headers["x-csrf-token"] = response.json()["data"]["user"]["csrf_token"]
    return client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and optionally ingest local CCTV footage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Video file(s) or director(ies) containing footage.",
    )
    parser.add_argument("--recursive", action="store_true", help="Search directories recursively.")
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "datasets" / "manifests" / "prepared.json"),
        help="Where to write the provenance manifest.",
    )
    parser.add_argument("--dataset-label", default="operator_provided_cctv")
    parser.add_argument("--licence", default="operator-supplied; confirm usage rights before processing")
    parser.add_argument("--provenance-url", default="")
    parser.add_argument("--upload", action="store_true", help="Ingest ready clips through the API.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--email", default="ops@demo.roadguard.ai")
    parser.add_argument("--camera-id", default=None, help="Associate every clip with this camera.")
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=0,
        help="Poll the processing job for up to N seconds per clip after upload.",
    )
    args = parser.parse_args(argv)

    files = collect(args.input, args.recursive)
    if not files:
        print("No video files found.", file=sys.stderr)
        return 2

    client = sign_in(args.api_url, args.email) if args.upload else None
    entries: list[dict] = []
    hashes: dict[str, str] = {}
    ready = 0

    for path in files:
        size = path.stat().st_size
        meta = probe(path)
        problems = evaluate(path, size, meta)
        digest = sha256_file(path)
        if digest in hashes:
            problems.append(f"DUPLICATE_OF {hashes[digest]}")
        else:
            hashes[digest] = path.name
        entry = {
            "file": str(path),
            "sha256": digest,
            "bytes": size,
            "probe": meta,
            "status": "ready" if not problems else "rejected",
            "problems": problems,
        }
        if not problems:
            ready += 1
        if client is not None and not problems:
            entry["ingest"] = upload_clip(client, path, args.camera_id, args.wait_seconds)
        entries.append(entry)

    manifest = {
        "manifest_version": 1,
        "prepared_at": datetime.now(UTC).isoformat(),
        "dataset_label": args.dataset_label,
        "licence": args.licence,
        "provenance_url": args.provenance_url or None,
        "api_limits": {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_video_duration_seconds": settings.max_video_duration_seconds,
            "max_video_width": settings.max_video_width,
            "max_video_height": settings.max_video_height,
            "supported_content_types": sorted(settings.supported_video_content_types),
        },
        "files": entries,
        "summary": {
            "total": len(entries),
            "ready": ready,
            "rejected": len(entries) - ready,
        },
        "notes": [
            "A clip being ready means it satisfies ingestion limits; it is not evidence.",
            "AI output produced from this footage is a candidate observation until a human reviews it.",
            "Record the footage owner and legal basis before processing real CCTV.",
        ],
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for entry in entries:
        marker = "ok  " if entry["status"] == "ready" else "FAIL"
        detail = ""
        if entry["probe"]:
            probe_info = entry["probe"]
            detail = (
                f" {probe_info['width']}x{probe_info['height']} "
                f"{probe_info['fps']}fps {probe_info['duration_seconds']}s"
            )
        print(f"[{marker}] {entry['file']}{detail}")
        for problem in entry["problems"]:
            print(f"       - {problem}")
        if entry.get("ingest"):
            ingest = entry["ingest"]
            job = ingest.get("job") or {}
            print(
                f"       -> video {ingest['video_id']} "
                f"job {job.get('job_id')} {job.get('status')}"
            )

    print(
        f"\n{ready}/{len(entries)} ready. Manifest: {manifest_path}"
    )
    return 0 if ready == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
