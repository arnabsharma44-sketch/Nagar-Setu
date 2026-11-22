# Datasets for ROADGUARD AI

This note records what was actually found while looking for traffic footage, what
can be downloaded today, and what the platform therefore needs from the operator.

## Bottom line

**No open dataset of Indian municipal fixed-CCTV accident footage with raw video was
found.** Every candidate below is either dashcam footage, a benchmark that requires a
request/registration, a paid sample, or statistics with no video. For a Bhubaneswar
(or any city) pilot, the footage has to come from the city: the traffic police /
smart-city control room, or the road-owning agency.

The pipeline is usable the moment such footage exists: `scripts/prepare_dataset.py`
validates clips against the ingestion limits, hashes them for provenance, writes a
manifest, and can push them through the normal upload → job → review flow.

## Candidates evaluated

| Dataset | Camera type | Size | Access | Fit for this platform |
| --- | --- | --- | --- | --- |
| **AI City Challenge 2020, Track 4 — Traffic Anomaly Detection** | Fixed highway CCTV | 10.7 GB | Open download, no request form ([dataset access](https://www.aicitychallenge.org/ai-city-challenge-dataset-access), [2020 data](https://www.aicitychallenge.org/2020-data-and-evaluation)) | **Best available fit.** Fixed camera, anomaly annotations, manageable size. Needs conversion of its annotation format into this project's event model. |
| **DoTA — Detection of Traffic Anomaly** | Fixed/dashcam mix | ~55 GB | Open (Google Drive, split archives) ([repo](https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly)) | Large but usable for offline evaluation of anomaly rules; annotations are clip-level, not per-frame tracks. |
| **ACCIDENT benchmark** | Fixed CCTV | 2,027 real + 2,211 synthetic clips | Access page ([accidentbench.github.io](https://accidentbench.github.io)) | Purpose-built for CCTV accident localisation. Best match conceptually; access is gated, and its labels are accident time/location/type, not our governance fields. |
| **AI City Challenge 2021/2022 tracks** | Fixed city cameras | 60+ hours | Open | Good for detection/tracking tuning and multi-camera behaviour; not accident-labelled. |
| **Woven Traffic Safety (WTS)** | Overhead + ego, staged events | 1.2k events | Google Form request ([repo](https://github.com/woven-visionai/wts-dataset)) | High-quality staged conflicts; request-gated and not a city CCTV corpus. |
| **Nexar Dashcam Collision Prediction** | Dashcam | 1,500 clips | Challenge terms | Dashcam perspective; wrong geometry for fixed-camera near-miss rules. |
| **Car Crash Dataset (CCD)** | Dashcam | ~4,500 clips | Open (Google Drive) ([repo](https://github.com/Cogito2012/CarCrashDataset)) | Dashcam; useful only for collision-anticipation experiments. |
| **IDD / IDD-117k / IDD-CRS** | Dashcam, Indian roads | 72 GB / 411 GB | IDD open with registration; IDD-CRS private ([IIIT](https://insaan.iiit.ac.in/datasets)) | Best Indian *road-scene* data, but ego-vehicle imagery, not junction CCTV. IDD-CRS (90 h of critical scenarios) is request-gated. |
| **Pune heterogeneous traffic counts (Mendeley)** | Junction CCTV, **counts only** | CSV | Open ([Mendeley](https://data.mendeley.com/datasets/xnf2k6n288/1)) | No video, but the only Indian junction dataset found; potentially useful later as exposure/volume input for hotspot rates. |
| **Kaggle "Real-Time Traffic Dataset – 500 videos"** | Fixed surveillance | 500 videos | Paid/unidata.pro sample | Commercial; licence is per-purchase, so not used here. |

Also checked, with nothing usable: India Data Exchange smart-mobility listings
(mostly private/gated), OpenCity Bengaluru (camera *locations* only, no footage),
and the public IDD mirrors.

## What this project ships instead

- `scripts/generate_demo_clip.py` produces a synthetic 800×450, 25 fps, 12 s clip with
  known vehicle interactions. Every artefact derived from it is labelled
  `SYNTHETIC_SCENE_DETECTOR` / DEMO, and it is what the automated smoke test uses.
- `datasets/sample_accidents/demo_accidents.csv` is a **fixture**, not statistics.

Neither is real-world validation. No accuracy metric for this project exists.

## What to provide

For each junction you want covered, the useful minimum is:

1. **Video** — continuous clips of 10 s to 10 min, fixed camera, ideally 1080p or
   better, containing at least a few interactions. Files are accepted as `.mp4`,
   `.mov`, `.mkv` or `.webm`; up to 200 MB and 600 s per file by default
   (`MAX_UPLOAD_BYTES`, `MAX_VIDEO_DURATION_SECONDS`).
2. **Metadata** — camera code/name, junction name, latitude/longitude (or a surveyed
   point), recording date/time and timezone, and the direction of travel the camera
   faces.
3. **Provenance and permission** — who owns the footage, the legal basis for
   processing it, whether faces/plates must be blurred, and the retention period.

Nice to have, not blocking: traffic volume counts (for exposure-normalised rates),
police crash records as a separate CSV with source references (the importer already
requires `source_name` and `source_reference` per row).

## Preparing and ingesting footage

```bash
# Validate first; writes datasets/manifests/prepared.json
python scripts/prepare_dataset.py --input datasets/incoming

# Then ingest the ready clips and wait for the AI job
DEMO_SEED_PASSWORD=... python scripts/prepare_dataset.py \
  --input datasets/incoming --upload \
  --api-url http://localhost:8000 --email ops@demo.roadguard.ai --wait-seconds 300
```

Every clip is SHA-256 hashed, checked against the API's size/duration/resolution
limits, and rejected with a reason if it would fail later. The manifest is the
provenance record; the API stores the same hash on the video row after upload.

## Honest caveats

- The default detector (`synthetic_scene`) is tuned for the synthetic clip's colour
  markers. Real footage needs `DETECTOR_BACKEND=yolo` with weights installed, which is
  **not installed or validated** in this environment.
- None of the public datasets were downloaded here: the smallest useful one is 10.7 GB
  and its licence/labels need review before it becomes a benchmark claim.
- Processing real CCTV requires a retention/deletion policy, which is still missing
  (see `docs/KNOWN_LIMITATIONS.md`).
