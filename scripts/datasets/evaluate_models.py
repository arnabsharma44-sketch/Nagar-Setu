"""Evaluate predictions against ground truth — only when predictions actually exist.

The script never invents predictions. Without ``--predictions`` it exits ``2``
(BLOCKED) and says which artifact is missing, so a report can never claim a metric
that was not computed from real output.

Two evaluation modes:

``detection``  object boxes vs Pascal-VOC labels (RDD2022) or a truth JSON.
``events``     temporal event windows vs labelled anomaly windows, matched by
               temporal IoU, which is how AI City anomaly labels are comparable.

    python scripts/datasets/evaluate_models.py --mode detection \
        --dataset rdd2022_india --predictions datasets/reports/rdd_predictions.json
    python scripts/datasets/evaluate_models.py --mode events \
        --labels datasets/external/aicity2021_track4/annotations/events.json \
        --predictions datasets/reports/aicity_events.json
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    REPORTS_DIR,
    dataset_root,
    load_manifest,
    select_datasets,
    status_line,
    write_json,
)


def _iou(box_a: list[float], box_b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _temporal_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    inter = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    return inter / union if union > 0 else 0.0


def load_voc_truth(root: Path) -> list[dict[str, Any]]:
    truth: list[dict[str, Any]] = []
    for xml_path in sorted(root.rglob("*.xml")):
        try:
            node = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        filename = node.findtext("filename") or xml_path.stem
        boxes = []
        for obj in node.findall("object"):
            box = obj.find("bndbox")
            if box is None:
                continue
            try:
                boxes.append(
                    {
                        "label": (obj.findtext("name") or "").strip(),
                        "box": [
                            float(box.findtext("xmin")),
                            float(box.findtext("ymin")),
                            float(box.findtext("xmax")),
                            float(box.findtext("ymax")),
                        ],
                    }
                )
            except (TypeError, ValueError):
                continue
        truth.append({"image": filename, "boxes": boxes})
    return truth


def evaluate_detection(truth: list[dict[str, Any]], predictions: list[dict[str, Any]], iou_threshold: float) -> dict:
    pred_by_image: dict[str, list[dict]] = {}
    for row in predictions:
        pred_by_image.setdefault(str(row.get("image")), []).extend(row.get("boxes", []))

    tp = fp = fn = 0
    per_class: dict[str, dict[str, int]] = {}
    for record in truth:
        image = str(record.get("image"))
        remaining = sorted(pred_by_image.get(image, []), key=lambda item: -float(item.get("score", 0)))
        for target in record.get("boxes", []):
            label = target["label"]
            stats = per_class.setdefault(label, {"tp": 0, "fp": 0, "fn": 0})
            best_index, best_iou = -1, 0.0
            for index, candidate in enumerate(remaining):
                if candidate.get("label") != label:
                    continue
                score = _iou(target["box"], candidate["box"])
                if score > best_iou:
                    best_index, best_iou = index, score
            if best_iou >= iou_threshold and best_index >= 0:
                tp += 1
                stats["tp"] += 1
                remaining.pop(best_index)
            else:
                fn += 1
                stats["fn"] += 1
        for _extra in remaining:
            fp += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    for stats in per_class.values():
        local_p = stats["tp"] / (stats["tp"] + stats["fp"]) if stats["tp"] + stats["fp"] else 0.0
        local_r = stats["tp"] / (stats["tp"] + stats["fn"]) if stats["tp"] + stats["fn"] else 0.0
        stats["precision"] = round(local_p, 4)
        stats["recall"] = round(local_r, 4)
        stats["f1"] = round(2 * local_p * local_r / (local_p + local_r), 4) if local_p + local_r else 0.0
    return {
        "mode": "detection",
        "iou_threshold": iou_threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "per_class": per_class,
    }


def evaluate_events(labels: list[dict], predictions: list[dict], threshold: float) -> dict:
    matched_predictions: set[int] = set()
    tp = 0
    for label in labels:
        best_index, best = -1, 0.0
        for index, prediction in enumerate(predictions):
            if index in matched_predictions:
                continue
            score = _temporal_iou(
                float(label["start"]), float(label["end"]), float(prediction["start"]), float(prediction["end"])
            )
            if score > best:
                best_index, best = index, score
        if best >= threshold and best_index >= 0:
            matched_predictions.add(best_index)
            tp += 1
    fp = len(predictions) - len(matched_predictions)
    fn = len(labels) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "mode": "events",
        "temporal_iou_threshold": threshold,
        "labels": len(labels),
        "predictions": len(predictions),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["detection", "events"], default="detection")
    parser.add_argument("--dataset", default=None, help="Dataset name from manifest (for detection truth).")
    parser.add_argument("--truth", default=None, help="Truth JSON for detection mode (overrides --dataset).")
    parser.add_argument("--labels", default=None, help="Labelled event windows for events mode.")
    parser.add_argument("--predictions", required=False, default=None)
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args(argv)

    if not args.predictions or not Path(args.predictions).exists():
        print(
            status_line("evaluation", "BLOCKED", "--predictions is required and must exist"),
            file=sys.stderr,
        )
        print(
            "No model output was produced, so no metric can be reported. Produce predictions "
            "first (for example run the detector over the dataset and write JSON), then re-run.",
            file=sys.stderr,
        )
        return 2

    predictions = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    if isinstance(predictions, dict):
        predictions = predictions.get("predictions", [])

    if args.mode == "detection":
        if args.truth:
            truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
        elif args.dataset:
            manifest = load_manifest()
            entry = select_datasets(manifest, [args.dataset])[args.dataset]
            root = dataset_root(entry) / str(entry.get("extract_to", "extracted"))
            truth = load_voc_truth(root)
            if not truth:
                print(status_line(args.dataset, "BLOCKED", "no Pascal VOC annotations found"), file=sys.stderr)
                return 2
        else:
            print("detection mode needs --truth or --dataset", file=sys.stderr)
            return 2
        metrics = evaluate_detection(truth, predictions, args.iou)
    else:
        if not args.labels or not Path(args.labels).exists():
            print(status_line("evaluation", "BLOCKED", "--labels is required"), file=sys.stderr)
            return 2
        labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
        if isinstance(labels, dict):
            labels = labels.get("events", [])
        metrics = evaluate_events(labels, predictions, args.iou)

    target = REPORTS_DIR / f"evaluation_{args.mode}_{args.dataset or 'custom'}.json"
    write_json(target, metrics)
    for key, value in metrics.items():
        if key != "per_class":
            print(f"{key}: {value}")
    print(f"report: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
