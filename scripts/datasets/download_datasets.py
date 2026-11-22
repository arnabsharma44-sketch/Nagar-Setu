"""Acquire external datasets from their official sources.

The script never accepts a licence on the operator's behalf and never bypasses a
login. It downloads only when the registry marks the source as directly
downloadable and ``--i-have-reviewed-license`` is passed. Anything else prints the
exact manual steps and exits with ``2`` (BLOCKED), which is what the audit reports.

    python scripts/datasets/download_datasets.py --dataset all --dry-run
    python scripts/datasets/download_datasets.py --dataset rdd2022_india \
        --i-have-reviewed-license
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    archive_path,
    fail,
    human_bytes,
    load_manifest,
    manual_instructions,
    save_metadata,
    select_datasets,
    status_line,
)

CHUNK = 1024 * 1024
USER_AGENT = "roadguard-dataset-fetcher/1.0"


def _probe(url: str) -> tuple[int, int | None, str | None]:
    """HEAD the URL. Returns (status, content_length, content_type)."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            length = response.headers.get("Content-Length")
            return response.status, int(length) if length else None, response.headers.get(
                "Content-Type"
            )
    except urllib.error.HTTPError as exc:
        return exc.code, None, exc.headers.get("Content-Type") if exc.headers else None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, None, f"{type(exc).__name__}: {exc}"


def _download(url: str, target: Path, expected: int | None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.stat().st_size if target.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as exc:
        fail(f"download refused: HTTP {exc.code} {exc.reason}", 2)

    mode = "ab" if existing and response.status == 206 else "wb"
    if mode == "wb":
        existing = 0
    total = expected or int(response.headers.get("Content-Length") or 0) + existing
    started = time.time()
    with target.open(mode) as handle:
        while chunk := response.read(CHUNK):
            handle.write(chunk)
            existing += len(chunk)
            if total:
                pct = existing / total * 100
                rate = existing / max(1e-6, time.time() - started)
                print(
                    f"\r  {pct:5.1f}%  {human_bytes(existing)} / {human_bytes(total)}"
                    f"  {human_bytes(int(rate))}/s",
                    end="",
                    flush=True,
                )
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument("--dry-run", action="store_true", help="Probe sources without downloading.")
    parser.add_argument(
        "--i-have-reviewed-license",
        action="store_true",
        help="Required for any download; confirms the operator reviewed the terms.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    blocked = 0

    for name, entry in selected.items():
        target = archive_path(entry)
        url = entry.get("archive_url")
        access = str(entry.get("access", "manual"))
        print(f"\n{name}: {entry['title']}")

        if target.exists() and target.stat().st_size > 0:
            print(status_line(name, "present", f"{target} ({human_bytes(target.stat().st_size)})"))
            continue

        if access != "direct":
            blocked += 1
            print(status_line(name, "BLOCKED", f"access={access}"))
            print("  " + manual_instructions(entry, name).replace("\n", "\n  "))
            save_metadata(entry, {"status": "blocked", "access": access})
            continue

        if not url:
            blocked += 1
            print(status_line(name, "BLOCKED", "no archive URL in manifest"))
            continue

        status, length, content_type = _probe(str(url))
        print(status_line(name, "probe", f"HTTP {status} size={human_bytes(length)} type={content_type}"))
        if status in {401, 403}:
            blocked += 1
            print(status_line(name, "BLOCKED", f"HTTP {status} — credentials/licence required"))
            print("  " + manual_instructions(entry).replace("\n", "\n  "))
            save_metadata(entry, {"status": "blocked", "http_status": status})
            continue
        if status >= 400 or status == 0:
            blocked += 1
            print(status_line(name, "BLOCKED", f"HTTP {status}"))
            continue
        if (content_type or "").startswith("text/html"):
            blocked += 1
            print(status_line(name, "BLOCKED", "HTML interstitial instead of an archive"))
            print("  " + manual_instructions(entry, name).replace("\n", "\n  "))
            save_metadata(entry, {"status": "blocked", "reason": "html_interstitial"})
            continue

        if args.dry_run:
            print(status_line(name, "downloadable", "dry run; no bytes fetched"))
            continue
        if not args.i_have_reviewed_license:
            blocked += 1
            print(status_line(name, "BLOCKED", "pass --i-have-reviewed-license after review"))
            continue

        print(status_line(name, "downloading", str(target)))
        _download(str(url), target, length)
        actual = target.stat().st_size
        save_metadata(
            entry,
            {
                "status": "downloaded",
                "archive": str(target),
                "bytes": actual,
                "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        print(status_line(name, "downloaded", human_bytes(actual)))

    if blocked:
        print(f"\n{blocked} dataset(s) need a human step. See the instructions above.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
