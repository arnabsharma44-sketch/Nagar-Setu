# AI Model Validation Report

## What actually runs

| Component | Status | Evidence |
| --- | --- | --- |
| Synthetic scene detector | **PASS** | Job `312c3194` succeeded; `model=synthetic-scene-colour-marker`, `version=synthetic_scene_v1`, `rules=1.0.0`, 1 candidate event |
| IoU/ByteTrack-style tracking | **PASS (unit)** | Track IDs persisted on detections; association unit-covered |
| Six event rules | **PASS (unit)** | Real converging/decelerating scenarios in `tests/unit/test_event_detection.py` |
| Evidence rendering | **PASS** | Annotated frame 63,211 bytes stored, checksum recorded |
| YOLO adapter | **BLOCKED** | `torch`/`ultralytics` absent; no weights present, none downloaded |
| Road-damage model (RDD2022) | **NOT IMPLEMENTED** | No damage classifier exists; none is simulated |
| LLM analysis | **NOT IMPLEMENTED (config)** | Deterministic path; `LLM_PROVIDER=none` |

## Demonstrated behaviour

```
job 312c3194  succeeded 100%
model synthetic-scene-colour-marker  version synthetic_scene_v1  rules 1.0.0
events 1: near_miss_candidate  score 0.436  window 3.0–9.0 s
```

This proves the pipeline plumbing — decode, per-frame analysis, association, rule evaluation,
candidate persistence, evidence — not real-world detection accuracy.

## Metrics

**No real-world metric is reported.** There is no labelled footage, and the synthetic clip has
no independent ground truth beyond "one event was seeded to be visible". Precision/recall on
that clip would be theatre.

The evaluation tooling itself is proven: `scripts/datasets/evaluate_models.py` was run on a
five-record synthetic fixture where the prediction set is known, producing
`tp=2 fp=1 fn=0 precision=0.6667 recall=1.0 f1=0.8`, with per-class values matching by hand
(`DATASET_VALIDATION_REPORT.md`). Without a `--predictions` file it exits **BLOCKED** rather
than inventing numbers.

## Class mapping and thresholds

- Detector emits explicit `class_label`/`class_id`; tracker preserves class per track.
- Confidence is stored per detection; `model_score` on an incident is the rule's event score.
  **Model confidence and event confidence are separate fields** and are not conflated.
- Rules require temporal persistence, so a single noisy frame does not raise an event; normal
  congestion is not labelled an accident by construction (rules are near-miss, wrong-way,
  stopped-vehicle, pedestrian-exposure, deceleration and converging-trajectory checks).

## Constraints honoured

- No arbitrary pretrained weights downloaded.
- Synthetic evaluation kept separate from any future real evaluation.
- No training occurred, so no train/test leakage is possible yet; the splitter is
  sequence-aware for when it is.
- Every AI result is a candidate observation until a human reviews it, and the UI says so on
  every command-centre page.

## To close this gap

1. Supply AI City Track 4 (labels) → run detector → `evaluate_models.py --mode events`.
2. Install `torch` + `ultralytics` with reviewed weights → rerun the same clips → compare.
3. For damage, train/obtain an RDD2022-compatible model before any damage claim is made.
