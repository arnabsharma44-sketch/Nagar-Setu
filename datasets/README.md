# Datasets

External road-safety data for ROADGUARD AI, plus the fixtures that keep the
dataset tooling testable without shipping multi-gigabyte archives in Git.

Nothing in `external/` is committed. `manifest.yaml` is the registry: it records the
official source, licence, expected archive name, access mode and destination for every
dataset. The utilities in `scripts/datasets/` read that file and never contain
credentials.

## Layout

```
datasets/
├── manifest.yaml            provenance + access policy (committed)
├── README.md                this file (committed)
├── external/                downloaded data (never committed)
│   ├── aicity2021_track4/
│   │   ├── raw/             AICity21-Track4-Anomaly-Detection.zip
│   │   ├── extracted/       unpacked archive
│   │   ├── processed/       leakage-safe index.json
│   │   └── dataset_metadata.json
│   ├── rdd2022_india/
│   │   ├── raw/             RDD2022_India.zip
│   │   ├── extracted/       images/ + annotations/xmls/
│   │   ├── processed/
│   │   └── dataset_metadata.json
│   └── bdd100k/
│       ├── raw/             bdd100k_images_100k.zip, det_20 labels
│       ├── extracted/
│       ├── processed/
│       └── dataset_metadata.json
├── fixtures/                small synthetic records used to test the tooling
│   ├── valid_videos/        generated demo clip (not committed)
│   ├── invalid_videos/      corrupt/empty upload fixtures
│   ├── sample_images/       one synthetic "road" image + VOC annotation
│   └── expected_outputs/    expected inspection/validation results
└── reports/                 generated JSON metrics (not committed)
```

## Status of the three external datasets

| Dataset | Task | Automated download | Why |
| --- | --- | --- | --- |
| AI City 2021 Track 4 | traffic anomaly | **BLOCKED** | Official link is a Google Drive file that only returns the interstitial/quota page; save it by hand. |
| RDD2022 India | road damage | **BLOCKED** | The published S3 object answers HTTP 403 to anonymous requests. |
| BDD100K | object detection | **BLOCKED** | Portal requires account registration and licence acceptance. |

Exact filenames, destination paths and post-download commands are in
`docs/quality/DATASET_ACQUISITION_REPORT.md`. No dataset content was fabricated to
stand in for a missing archive.

## Commands

```bash
# 1. Probe sources / print manual instructions (never accepts a licence for you)
python scripts/datasets/download_datasets.py --dataset all

# 2. After the archive is in place: size, SHA-256, zip integrity
python scripts/datasets/verify_downloads.py --dataset all --record

# 3. Unpack safely (zip-slip rejected, archive preserved)
python scripts/datasets/extract_datasets.py --dataset all

# 4. Structure, corrupt images, class distribution
python scripts/datasets/inspect_datasets.py --dataset all

# 5. Annotation validity (VOC boxes, BDD JSON, unknown-JSON shapes)
python scripts/datasets/validate_annotations.py --dataset all

# 6. Deterministic, sequence-aware train/val/test index
python scripts/datasets/prepare_datasets.py --dataset all

# 7. Metrics — only with real predictions; exits BLOCKED otherwise
python scripts/datasets/evaluate_models.py --mode detection --dataset rdd2022_india \
    --predictions datasets/reports/rdd_predictions.json
```

All commands exit `0` (ok), `1` (validation problem) or `2` (BLOCKED / content
missing), so they are safe to chain in CI.

## Rules

- Authoritative sources only; no mirrors, scraping or login bypass.
- Licence acceptance is a human action. `--i-have-reviewed-license` is required for
  any automated fetch.
- Never commit archives, extracted images, model weights or generated frames.
- Road-damage observations are infrastructure findings, never evidence of accident
  causation, and stay out of CCTV event counts.
- Synthetic footage and the synthetic detector are demo fixtures, not real-world
  accuracy evidence.
