"""Verify dataset archives: presence, size, SHA-256 and zip integrity.

    python scripts/datasets/verify_downloads.py --dataset all
    python scripts/datasets/verify_downloads.py --dataset rdd2022_india --record
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    archive_path,
    human_bytes,
    load_manifest,
    load_metadata,
    save_metadata,
    select_datasets,
    sha256_file,
    status_line,
    zip_is_intact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument(
        "--record",
        action="store_true",
        help="Write the observed size and SHA-256 into dataset_metadata.json.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    problems = 0
    missing = 0

    for name, entry in selected.items():
        archive = archive_path(entry)
        if not archive.exists():
            missing += 1
            print(status_line(name, "MISSING", f"expected {archive}"))
            continue

        size = archive.stat().st_size
        expected = entry.get("expected_bytes")
        size_ok = expected is None or int(expected) == size
        print(status_line(name, "size", f"{human_bytes(size)} (expected {human_bytes(expected)})"))
        if not size_ok:
            problems += 1
            print(status_line(name, "SIZE_MISMATCH", ""))

        digest = sha256_file(archive)
        print(status_line(name, "sha256", digest))
        recorded = load_metadata(entry).get("sha256")
        if recorded and recorded != digest:
            problems += 1
            print(status_line(name, "HASH_MISMATCH", f"recorded {recorded}"))

        intact, reason = zip_is_intact(archive)
        print(status_line(name, "zip", "ok" if intact else f"BROKEN ({reason})"))
        if not intact:
            problems += 1

        if args.record and intact and size_ok:
            save_metadata(
                entry,
                {
                    "status": "verified",
                    "archive": str(archive),
                    "bytes": size,
                    "sha256": digest,
                },
            )

    if problems:
        return 1
    if missing:
        print(f"\n{missing} archive(s) not present — see docs/quality/DATASET_ACQUISITION_REPORT.md")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
