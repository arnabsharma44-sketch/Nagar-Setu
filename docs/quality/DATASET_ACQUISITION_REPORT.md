# Dataset Acquisition Report

## Probes executed

| Source | Probe | Result |
| --- | --- | --- |
| AI City 2021 Track 4 page | `GET https://www.aicitychallenge.org/2021-track4-download/` | 200 (instructions page) |
| AI City Drive file | `HEAD https://drive.google.com/uc?export=download&id=1gsR4pIEiWK7htPmIjiZjXetaa1X-T-Am` | 303 → `drive.usercontent.google.com` → 200, `Content-Length: 0`, no archive bytes (interstitial/quota) |
| RDD2022 India S3 | `HEAD …/RDD2022_India.zip` | **403 Forbidden**, `application/xml` |
| BDD100K portal | `GET https://bdd-data.berkeley.edu/` | connection failed (status 000) from this host |

`scripts/datasets/download_datasets.py --dataset all` exits **2** and prints the manual steps.
`verify_downloads.py --dataset all` reports all three **MISSING** (exit 2). No archive was
created, no placeholder data was substituted.

## Manual steps (exact)

### 1. AI City Challenge 2021 — Track 4 (traffic anomaly)

1. **Name:** AI City Challenge 2021 Track 4 — Traffic Anomaly Detection.
2. **Source:** https://www.aicitychallenge.org/2021-track4-download/
3. **Archive:** `AICity21-Track4-Anomaly-Detection.zip` (verify the exact filename shown on the page).
4. **Size:** not published on the page; check before extracting.
5. **Access:** open the official Google Drive link from that page, accept the challenge terms,
   and download. Do not use mirrors. Automated fetch returns an HTML interstitial.
6. **Destination:** `datasets/external/aicity2021_track4/raw/AICity21-Track4-Anomaly-Detection.zip`
7. **Extract:** `python scripts/datasets/verify_downloads.py --dataset aicity2021_track4 --record`
   then `python scripts/datasets/extract_datasets.py --dataset aicity2021_track4`
8. **Validate:** `python scripts/datasets/inspect_datasets.py --dataset aicity2021_track4`
   and `python scripts/datasets/validate_annotations.py --dataset aicity2021_track4`
9. **Expected structure:** video clips per scene plus annotation files (JSON) with anomaly
   intervals; the inspector reports the real shape rather than assuming one.
10. **Labels:** map anomaly windows to `start_seconds`/`end_seconds`. The unlabelled test split
    must not be used as ground truth.

### 2. RDD2022 India (road damage)

1. **Name:** RDD2022 / CRDDC2022 country-specific India subset.
2. **Source:** https://github.com/sekilab/RoadDamageDetector
3. **Archive:** `RDD2022_India.zip`.
4. **Size:** not published at the S3 URL (HEAD is forbidden).
5. **Access:** follow the repository's documented download link and accept its terms; the
   published S3 object returns 403 to anonymous requests.
6. **Destination:** `datasets/external/rdd2022_india/raw/RDD2022_India.zip`
7. **Extract:** `python scripts/datasets/verify_downloads.py --dataset rdd2022_india --record`
   then `extract_datasets.py --dataset rdd2022_india`
8. **Validate:** `validate_annotations.py --dataset rdd2022_india` (Pascal VOC boxes, class set
   D00/D01/D10/D11/D20/D40/D43/D44/D50, image existence, box bounds).
9. **Expected structure:** `India/train/images/*.jpg`, `India/train/annotations/xmls/*.xml`
   (plus test split if distributed).
10. **Mapping:** damage classes → infrastructure fault categories. Never accident causation.

### 3. BDD100K (object detection)

1. **Name:** BDD100K — 100K Images + Detection 2020 labels.
2. **Source:** https://bdd-data.berkeley.edu/ (docs:
   https://github.com/bdd100k/bdd100k/blob/master/doc/source/download.rst)
3. **Archives:** `bdd100k_images_100k.zip` and the det_20 label archive.
4. **Size:** tens of GB combined; the 1.8 TB video set is explicitly out of scope.
5. **Access:** register, accept the BDD100K licence, download. Educational access does not imply
   commercial rights — confirm before any commercial use.
6. **Destination:** `datasets/external/bdd100k/raw/`
7. **Extract:** `verify_downloads.py --dataset bdd100k --record` then
   `extract_datasets.py --dataset bdd100k`
8. **Validate:** `validate_annotations.py --dataset bdd100k` (frames have `name`, `labels` list).
9. **Expected structure:** `images/100k/{train,val,test}/*.jpg`, `labels/det_20/*.json`.
10. **Use:** object-detection benchmarking only; never accident labels.

## What unblocks everything

Drop the three archives at the paths above (or tell me where they were saved) and run:

```bash
python scripts/datasets/verify_downloads.py --dataset all --record
python scripts/datasets/extract_datasets.py --dataset all
python scripts/datasets/inspect_datasets.py --dataset all
python scripts/datasets/validate_annotations.py --dataset all
python scripts/datasets/prepare_datasets.py --dataset all
```

No credentials belong in the repository or in chat; a save dialog on the local machine is enough.
