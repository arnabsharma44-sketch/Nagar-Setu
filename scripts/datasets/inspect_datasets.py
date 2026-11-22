"""Inspect an extracted dataset: images, corrupt files, annotations, class balance.

    python scripts/datasets/inspect_datasets.py --dataset all
    python scripts/datasets/inspect_datasets.py --dataset rdd2022_india --sample 0

Corrupt-image detection samples by default (``--sample 0`` scans every image) because
a full decode of tens of thousands of photographs is slow and this is a smoke check,
not a training step.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    REPORTS_DIR,
    dataset_root,
    load_manifest,
    save_metadata,
    select_datasets,
    status_line,
    write_json,
)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ANNOTATION_SUFFIXES = {".json", ".xml", ".csv", ".txt"}


def _walk(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in suffixes)


def _corrupt_sample(images: list[Path], sample: int) -> tuple[int, list[str]]:
    if not images:
        return 0, []
    import cv2

    chosen = images if sample <= 0 else random.Random(0).sample(images, min(sample, len(images)))
    corrupt: list[str] = []
    for path in chosen:
        if cv2.imread(str(path)) is None:
            corrupt.append(str(path.relative_to(Path.cwd())) if path.is_relative_to(Path.cwd()) else str(path))
    return len(chosen), corrupt


def _rdd_classes(annotation_files: list[Path]) -> Counter:
    import xml.etree.ElementTree as ET

    counts: Counter = Counter()
    for path in annotation_files:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            counts["__parse_error__"] += 1
            continue
        for obj in tree.getroot().findall("object"):
            name = (obj.findtext("name") or "unknown").strip()
            counts[name] += 1
    return counts


def _bdd_labels(annotation_files: list[Path]) -> Counter:
    counts: Counter = Counter()
    for path in annotation_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            counts["__parse_error__"] += 1
            continue
        for frame in payload if isinstance(payload, list) else [payload]:
            for label in frame.get("labels", []) if isinstance(frame, dict) else []:
                counts[str(label.get("category", "unknown"))] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument(
        "--sample",
        type=int,
        default=100,
        help="Images to decode for corruption checks (0 = all, default 100).",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    any_content = False
    report: dict = {}

    for name, entry in selected.items():
        root = dataset_root(entry) / str(entry.get("extract_to", "extracted"))
        images = _walk(root, IMAGE_SUFFIXES)
        annotations = _walk(root, ANNOTATION_SUFFIXES)
        print(f"\n{name}")
        print(status_line(name, "root", str(root)))
        print(status_line(name, "images", str(len(images))))
        print(status_line(name, "annotations", str(len(annotations))))

        if not images and not annotations:
            print(status_line(name, "NOT_EXTRACTED", "nothing to inspect"))
            report[name] = {"images": 0, "annotations": 0, "status": "not_extracted"}
            continue

        any_content = True
        decoded, corrupt = _corrupt_sample(images, args.sample)
        print(status_line(name, "decoded_sample", f"{decoded} ({len(corrupt)} corrupt)"))
        for bad in corrupt[:5]:
            print(f"    corrupt: {bad}")

        classes: Counter = Counter()
        if name == "rdd2022_india":
            classes = _rdd_classes([path for path in annotations if path.suffix == ".xml"])
        elif name == "bdd100k":
            classes = _bdd_labels([path for path in annotations if path.suffix == ".json"])
        if classes:
            print(status_line(name, "classes", str(dict(classes.most_common(12)))))

        payload = {
            "status": "inspected",
            "root": str(root),
            "images": len(images),
            "annotations": len(annotations),
            "decoded_sample": decoded,
            "corrupt_images": corrupt,
            "class_distribution": dict(classes),
        }
        report[name] = payload
        save_metadata(entry, payload)
        write_json(REPORTS_DIR / f"inspection_{name}.json", payload)

    write_json(REPORTS_DIR / "inspection_summary.json", report)
    print(f"\nreport: {REPORTS_DIR / 'inspection_summary.json'}")
    if not any_content:
        print("No dataset content is extracted yet — acquisition is BLOCKED.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
