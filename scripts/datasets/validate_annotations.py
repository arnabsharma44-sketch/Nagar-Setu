"""Validate annotation files before any training or evaluation.

Checks performed:
* Pascal VOC (RDD2022): parses, has size/object boxes, coordinates inside the image,
  known damage class names, and every referenced image exists.
* BDD100K labels: valid JSON, every frame has a ``name`` and ``labels`` list.
* Any other JSON (for example AI City anomaly annotations): parses and reports the
  top-level shape so the mapping step is explicit rather than guessed.

    python scripts/datasets/validate_annotations.py --dataset rdd2022_india
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    REPORTS_DIR,
    dataset_root,
    load_manifest,
    select_datasets,
    status_line,
    write_json,
)

RDD_CLASSES = {
    "D00", "D01", "D10", "D11", "D20", "D40", "D43", "D44", "D50",
    "D0w0", "D10w0", "D20w0", "D40w0",
}


def validate_rdd(root: Path, limit: int) -> tuple[int, list[str], dict]:
    xmls = sorted(root.rglob("*.xml"))
    problems: list[str] = []
    stats = {"files": 0, "objects": 0, "missing_images": 0, "bad_classes": 0, "bad_boxes": 0}
    for path in xmls[: limit or None]:
        stats["files"] += 1
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            problems.append(f"{path.name}: XML parse error ({exc})")
            continue
        node = tree.getroot()
        filename = node.findtext("filename")
        size = node.find("size")
        width = int(float(size.findtext("width"))) if size is not None and size.findtext("width") else None
        height = int(float(size.findtext("height"))) if size is not None and size.findtext("height") else None
        image_hint = (path.parents[2] / "images" / filename) if filename else None
        if image_hint is not None and not image_hint.exists():
            stats["missing_images"] += 1
        for obj in node.findall("object"):
            stats["objects"] += 1
            name = (obj.findtext("name") or "").strip()
            if name not in RDD_CLASSES:
                stats["bad_classes"] += 1
                problems.append(f"{path.name}: unknown class {name!r}")
            box = obj.find("bndbox")
            if box is None:
                stats["bad_boxes"] += 1
                continue
            try:
                values = [float(box.findtext(tag)) for tag in ("xmin", "ymin", "xmax", "ymax")]
            except (TypeError, ValueError):
                stats["bad_boxes"] += 1
                problems.append(f"{path.name}: non-numeric bndbox")
                continue
            xmin, ymin, xmax, ymax = values
            if xmax <= xmin or ymax <= ymin:
                stats["bad_boxes"] += 1
                problems.append(f"{path.name}: degenerate box {values}")
            elif width and height and (xmax > width + 1 or ymax > height + 1):
                stats["bad_boxes"] += 1
                problems.append(f"{path.name}: box outside {width}x{height}")
    return stats["files"], problems, stats


def validate_bdd(root: Path, limit: int) -> tuple[int, list[str], dict]:
    labels = sorted(path for path in root.rglob("*.json") if "labels" in str(path).lower())
    problems: list[str] = []
    stats = {"files": 0, "frames": 0, "objects": 0}
    for path in labels[: limit or None]:
        stats["files"] += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"{path.name}: {type(exc).__name__}")
            continue
        frames = payload if isinstance(payload, list) else [payload]
        for frame in frames:
            if not isinstance(frame, dict) or "name" not in frame:
                problems.append(f"{path.name}: frame without 'name'")
                continue
            stats["frames"] += 1
            labels_list = frame.get("labels", [])
            if not isinstance(labels_list, list):
                problems.append(f"{path.name}: labels is not a list")
                continue
            stats["objects"] += len(labels_list)
    return stats["files"], problems, stats


def describe_json(root: Path) -> dict:
    """Report the shape of unknown JSON annotations instead of guessing a schema."""
    shapes: dict[str, int] = {}
    for path in sorted(root.rglob("*.json"))[:50]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            shapes["unparseable"] = shapes.get("unparseable", 0) + 1
            continue
        key = type(payload).__name__
        if isinstance(payload, dict):
            key = "dict:" + ",".join(sorted(payload)[:6])
        elif isinstance(payload, list) and payload:
            key = f"list[{len(payload)}]"
        shapes[key] = shapes.get(key, 0) + 1
    return shapes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs="+", default=["all"])
    parser.add_argument("--limit", type=int, default=0, help="Validate at most N files (0 = all).")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    selected = select_datasets(manifest, args.dataset)
    report: dict = {}
    failed = False

    for name, entry in selected.items():
        root = dataset_root(entry) / str(entry.get("extract_to", "extracted"))
        print(f"\n{name}")
        if not root.exists():
            print(status_line(name, "NOT_EXTRACTED", str(root)))
            report[name] = {"status": "not_extracted", "problems": []}
            continue

        if name == "rdd2022_india":
            files, problems, stats = validate_rdd(root, args.limit)
        elif name == "bdd100k":
            files, problems, stats = validate_bdd(root, args.limit)
        else:
            shapes = describe_json(root)
            files = sum(shapes.values())
            problems = []
            stats = {"files": files, "json_shapes": shapes}

        status = "ok" if not problems else "problems"
        print(status_line(name, status, f"{files} files"))
        for key, value in stats.items():
            print(f"    {key}: {value}")
        for problem in problems[:10]:
            print(f"    ! {problem}")
        if problems:
            failed = True
        report[name] = {"status": status, "stats": stats, "problems": problems[:200]}

    write_json(REPORTS_DIR / "annotation_validation.json", report)
    print(f"\nreport: {REPORTS_DIR / 'annotation_validation.json'}")
    return 1 if failed else (0 if report else 2)


if __name__ == "__main__":
    raise SystemExit(main())
