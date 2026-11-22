"""Build a deterministic, leakage-safe index for an extracted dataset.

Splitting adjacent frames or clips at random leaks almost identical scenes into the
test set. This script groups records by a *sequence key* (video id, image prefix or
explicit field), hashes the key, and assigns whole groups to train/val/test with a
fixed seed. Running it twice produces byte-identical output.

    python scripts/datasets/prepare_datasets.py --dataset rdd2022_india
    python scripts/datasets/prepare_datasets.py --dataset bdd100k --train 0.8 --val 0.1
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    dataset_root,
    load_manifest,
    save_metadata,
    select_datasets,
    status_line,
    write_json,
)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sequence_key(dataset: str, path: Path) -> str:
    """Group records so no group can straddle two splits."""
    stem = path.stem
    if dataset == "aicity2021_track4":
        match = re.search(r"(video[_-]?\d+|\d{3,})", stem, re.IGNORECASE)
        return match.group(1).lower() if match else stem
    if dataset == "rdd2022_india":
        # RDD filenames are <country><road><frame>. Group by the road prefix.
        match = re.match(r"([A-Za-z]+\d+[A-Za-z]*\d*)", stem)
        return match.group(1) if match else stem
    if dataset == "bdd100k":
        # BDD frames look like <video>-000001.jpg; the video is the sequence.
        return stem.rsplit("-", 1)[0]
    return stem


def split_for(key: str, train: float, val: float) -> str:
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < train:
        return "train"
    if bucket < train + val:
        return "val"
    return "test"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument("--train", type=float, default=0.7)
    parser.add_argument("--val", type=float, default=0.15)
    args = parser.parse_args(argv)

    if not 0 < args.train < 1 or not 0 <= args.val < 1 or args.train + args.val >= 1:
        raise SystemExit("split fractions must satisfy 0 < train, train + val < 1")

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    prepared = False

    for name, entry in selected.items():
        root = dataset_root(entry) / str(entry.get("extract_to", "extracted"))
        images = sorted(path for path in root.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES) if root.exists() else []
        if not images:
            print(status_line(name, "SKIPPED", "no extracted images"))
            continue

        prepared = True
        groups: dict[str, str] = {}
        records = []
        for image in images:
            key = sequence_key(name, image)
            groups.setdefault(key, split_for(key, args.train, args.val))
            records.append(
                {
                    "path": str(image.relative_to(root)).replace("\\", "/"),
                    "sequence": key,
                    "split": groups[key],
                }
            )

        counts = {"train": 0, "val": 0, "test": 0}
        for record in records:
            counts[record["split"]] += 1

        index = {
            "dataset": name,
            "root": str(root),
            "split_policy": {
                "method": "sha256(sequence_key) bucket",
                "train": args.train,
                "val": args.val,
                "test": round(1 - args.train - args.val, 6),
                "sequence_aware": True,
            },
            "sequences": len(groups),
            "counts": counts,
            "records": records,
        }
        target = dataset_root(entry) / "processed" / "index.json"
        write_json(target, index)
        save_metadata(
            entry,
            {"status": "prepared", "index": str(target), "counts": counts, "sequences": len(groups)},
        )
        print(status_line(name, "prepared", f"{len(records)} images / {len(groups)} sequences -> {target}"))
        print(f"    splits: {counts}")

    if not prepared:
        print("Nothing to prepare — no extracted dataset content.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
