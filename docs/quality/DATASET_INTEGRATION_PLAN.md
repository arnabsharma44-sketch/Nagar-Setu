# Dataset Integration Plan

## Purpose

ROADGUARD currently demonstrates on a synthetic clip. Real evaluation requires labelled
footage and road-damage annotations. This plan defines how external data enters the system
without contaminating the demo, leaking labels into training, or overstating model quality.

## Pipeline

| Stage | Tool | Output | Gate |
| --- | --- | --- | --- |
| Acquire | `scripts/datasets/download_datasets.py` | archive in `datasets/external/<ds>/raw/` | Licence reviewed by a human; refuses without `--i-have-reviewed-license` |
| Verify | `verify_downloads.py` | size, SHA-256, zip integrity in `dataset_metadata.json` | Missing/ corrupt archive stops the pipeline (exit 2/1) |
| Extract | `extract_datasets.py` | `extracted/` | Zip-slip rejected; raw archive preserved |
| Inspect | `inspect_datasets.py` | counts, corrupt images, class distribution | Corrupt images reported, never silently dropped |
| Validate | `validate_annotations.py` | pass/problems per record | VOC boxes inside image bounds; BDD frames have `name`+`labels` |
| Prepare | `prepare_datasets.py` | `processed/index.json` | Deterministic, sequence-aware split; no frame-level leakage |
| Evaluate | `evaluate_models.py` | precision/recall/F1 + per-class | Requires real predictions; exits BLOCKED without them |

## Dataset → product mapping

### AI City 2021 Track 4 (traffic anomaly)

1. Map each labelled anomaly window to `(video_id, start_seconds, end_seconds)`.
2. Run the detector over the same clips, producing incident candidates with the existing
   schema (`incident_type`, `start_offset_seconds`, `end_offset_seconds`, `model_score`).
3. Match with temporal IoU ≥ 0.3; report event-level precision, recall and F1.
4. Do **not** use the unlabelled test split as ground truth. Normal congestion is not an
   accident and must not be force-labelled as one.

### RDD2022 India (road damage)

1. VOC XML → damage classes D00/D01/D10/D11/D20/D40/D43/D44/D50.
2. Map to infrastructure fault categories (pothole, crack, patch) for inspection records.
3. Requires a damage model; none is installed. Until then the honest status is
   **NOT IMPLEMENTED**, and the parser/evaluator stay dormant rather than emitting guesses.
4. Damage findings are infrastructure observations and are excluded from CCTV event counts.

### BDD100K (object detection)

1. 100K images + Detection 2020 labels only; the 1.8 TB video set is out of scope.
2. Benchmark the YOLO adapter's vehicle/pedestrian detection with the same IoU matcher.
3. BDD labels never become accident labels.

## Non-negotiable rules

- No fabricated predictions, no mock metrics, no random images standing in for a dataset.
- Synthetic evaluations are reported separately and labelled synthetic.
- Model confidence and event confidence remain distinct fields.
- Every AI output stays a candidate observation pending human review.
- Raw archives, extracted frames and weights never enter Git.

## Current state

No archive acquired. All three sources returned BLOCKED (see
`DATASET_ACQUISITION_REPORT.md`). The pipeline itself is proven end to end on a synthetic
RDD-format fixture (`DATASET_VALIDATION_REPORT.md`), so the remaining work is data + weights,
not code.
