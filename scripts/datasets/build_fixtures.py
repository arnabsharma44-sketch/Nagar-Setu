"""Build the tiny RDD2022-format fixture used to test the dataset utilities.

The fixture is deliberately synthetic and tiny (three JPEGs, two VOC files, one
truncated image). It exercises the real code paths — zip verification, safe
extraction, VOC parsing, corrupt-image detection, sequence-aware splitting and IoU
matching — without pretending to be the India dataset.

    python scripts/datasets/build_fixtures.py
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "datasets" / "fixtures" / "rdd2022_mini"
MANIFEST = ROOT / "datasets" / "fixtures" / "fixture_manifest.yaml"

VOC = """<?xml version="1.0" encoding="utf-8"?>
<annotation>
  <folder>images</folder>
  <filename>{filename}</filename>
  <size><width>64</width><height>48</height><depth>3</depth></size>
  <object>
    <name>{label}</name>
    <bndbox><xmin>10</xmin><ymin>10</ymin><xmax>40</xmax><ymax>30</ymax></bndbox>
  </object>
</annotation>
"""


def make_image(path: Path, shade: int) -> None:
    image = np.full((48, 64, 3), shade, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (40, 30), (shade + 60, shade + 40, shade + 20), -1)
    cv2.imwrite(str(path), image)


def main() -> int:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    train = FIXTURE / "India" / "train"
    images = train / "images"
    xmls = train / "annotations" / "xmls"
    raw = FIXTURE / "raw"
    for directory in (images, xmls, raw):
        directory.mkdir(parents=True, exist_ok=True)

    records = [
        ("India_001_0001.jpg", "D40", 90),
        ("India_002_0002.jpg", "D00", 120),
    ]
    for filename, label, shade in records:
        make_image(images / filename, shade)
        (xmls / f"{Path(filename).stem}.xml").write_text(
            VOC.format(filename=filename, label=label), encoding="utf-8"
        )

    # A truncated JPEG: the utilities must report it, not silently skip it.
    (images / "India_003_0003.jpg").write_bytes(b"\xff\xd8\xff\xe0 truncated")

    archive = raw / "RDD2022_India.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(train.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(FIXTURE).as_posix())

    MANIFEST.write_text(
        f"""# Fixture registry: same shape as datasets/manifest.yaml, tiny synthetic data.
version: 1
datasets:
  rdd2022_india:
    title: Fixture — RDD2022-format miniature
    task: road_damage_detection
    source_url: synthetic
    archive_url: null
    archive_name: RDD2022_India.zip
    expected_bytes: {archive.stat().st_size}
    license: Synthetic fixture, no third-party data.
    access: fixture
    root: datasets/fixtures/rdd2022_mini
    raw_dir: raw
    extract_to: extracted
    annotations_glob: "**/annotations/xmls/*.xml"
""",
        encoding="utf-8",
    )

    expected = {
        "images": 3,
        "annotations": 2,
        "valid_images": 2,
        "corrupt_images": 1,
        "class_distribution": {"D40": 1, "D00": 1},
    }
    (ROOT / "datasets" / "fixtures" / "expected_outputs" / "expected_rdd.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )
    print(f"fixture: {FIXTURE}")
    print(f"archive: {archive} ({archive.stat().st_size} bytes)")
    print(f"manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
