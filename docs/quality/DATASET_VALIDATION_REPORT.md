# Dataset Validation Report

## Real datasets

**BLOCKED.** No archive present, so no real annotation was validated, no real class
distribution exists, and no real metric was computed. The utilities exit `2` and say so.

## Tooling validation (synthetic fixture)

A five-record RDD2022-format fixture is generated reproducibly by
`scripts/datasets/build_fixtures.py`: two 64×48 JPEGs with Pascal VOC annotations
(`D40`, `D00`), one deliberately truncated JPEG, zipped as `RDD2022_India.zip`
(2,864 bytes). The fixture registry is `datasets/fixtures/fixture_manifest.yaml`, selected
with `ROADGUARD_DATASET_MANIFEST` so the real registry is never touched.

| Stage | Command | Output | Status |
| --- | --- | --- | --- |
| Verify | `verify_downloads.py --dataset rdd2022_india --record` | size matches, `sha256 b8a9e79b…`, zip ok | PASS (exit 0) |
| Extract | `extract_datasets.py --dataset rdd2022_india` | 5 entries → `extracted/` | PASS |
| Inspect | `inspect_datasets.py --sample 0` | images 3, annotations 2, decoded 3 (1 corrupt), classes `{D40:1, D00:1}` | PASS |
| Validate | `validate_annotations.py` | 2 files, 2 objects, 0 missing images, 0 bad classes, 0 bad boxes | PASS |
| Prepare | `prepare_datasets.py` | 3 images / 3 sequences → splits `{train:1,val:1,test:1}` | PASS |
| Evaluate (no predictions) | `evaluate_models.py --mode detection` | `[BLOCKED] --predictions is required and must exist`, exit 2 | PASS (refuses to invent) |
| Evaluate (known predictions) | same with `fixture_predictions.json` | `tp=2 fp=1 fn=0 precision=0.6667 recall=1.0 f1=0.8` | PASS |

The corrupt JPEG was detected by decode (`Premature end of JPEG file`), not skipped.

Assertions comparing generated output to `datasets/fixtures/expected_outputs/expected_rdd.json`
all passed, including per-class IoU matching:

```
D00 {tp:1, fp:0, fn:0, precision:1.0, recall:1.0, f1:1.0}
D40 {tp:1, fp:0, fn:0, precision:1.0, recall:1.0, f1:1.0}
overall precision 0.6667 (one extra low-score box correctly counted as FP)
```

## Split integrity

Splitting is by **sequence key**, hashed with SHA-256 and a fixed seed, never by adjacent frame.
For RDD the road prefix groups frames; for BDD the `<video>-000001.jpg` prefix groups frames;
for AI City the numeric scene id groups clips. Re-running produces identical output, and a whole
sequence cannot straddle two splits.

## Reports written

- `datasets/reports/inspection_summary.json`
- `datasets/reports/annotation_validation.json`
- `datasets/reports/evaluation_detection_rdd2022_india.json`

`datasets/reports/*` is git-ignored; the fixture inputs are committed.

## Caveat

This validates the **tooling**, not ROADGUARD's models. A passing fixture run says nothing about
detection quality on Indian roads.
