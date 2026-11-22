"""Extract verified dataset archives without ever touching the raw archive.

    python scripts/datasets/extract_datasets.py --dataset all
    python scripts/datasets/extract_datasets.py --dataset rdd2022_india --force

Zip-slip is rejected, the archive is kept, and the metadata file records where the
content landed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    archive_path,
    dataset_root,
    load_manifest,
    safe_extract,
    save_metadata,
    select_datasets,
    status_line,
    zip_is_intact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument("--force", action="store_true", help="Re-extract over existing files.")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    missing = 0

    for name, entry in selected.items():
        archive = archive_path(entry)
        if not archive.exists():
            missing += 1
            print(status_line(name, "MISSING", str(archive)))
            continue
        intact, reason = zip_is_intact(archive)
        if not intact:
            print(status_line(name, "BROKEN_ARCHIVE", str(reason)))
            return 1

        destination = dataset_root(entry) / str(entry.get("extract_to", "extracted"))
        if destination.exists() and any(destination.iterdir()) and not args.force:
            print(status_line(name, "already_extracted", str(destination)))
            continue

        written = safe_extract(archive, destination)
        save_metadata(
            entry,
            {
                "status": "extracted",
                "extracted_to": str(destination),
                "extracted_entries": len(written),
            },
        )
        print(status_line(name, "extracted", f"{len(written)} entries -> {destination}"))

    if missing:
        print(f"\n{missing} archive(s) missing; nothing extracted for them.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
