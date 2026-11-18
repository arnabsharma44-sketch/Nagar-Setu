"""Generate the synthetic demonstration clip.

The clip is drawn locally with OpenCV: coloured markers on a rendered road scene.
No real surveillance footage is used, so there are no privacy or licensing issues.
The colours match ``ai_engine.detection.synthetic_scene.MARKER_PALETTE`` so the
detector has to measure the pixels of the encoded video to find them.

A JSON sidecar documents the synthetic ground truth for human review of the demo
(it is *not* read by the detector).

Usage::

    python scripts/generate_demo_clip.py
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "datasets" / "sample_videos"

FPS = 25
WIDTH, HEIGHT = 800, 450
DURATION_SECONDS = 12

COLOURS = {
    "car": (40, 40, 220),
    "truck": (40, 180, 40),
    "motorcycle": (220, 40, 220),
    "bicycle": (40, 200, 240),
    "person": (30, 160, 255),
    "bus": (220, 120, 40),
}

SIZES = {
    "car": (72, 34),
    "truck": (92, 44),
    "motorcycle": (44, 30),
    "bicycle": (40, 32),
    "person": (24, 46),
    "bus": (100, 46),
}


@dataclass
class Actor:
    label: str
    keyframes: list[tuple[float, float, float]]  # (time, x, y) centre positions

    def position(self, t: float) -> tuple[float, float] | None:
        frames = self.keyframes
        if t < frames[0][0] or t > frames[-1][0]:
            return None
        for index in range(len(frames) - 1):
            t0, x0, y0 = frames[index]
            t1, x1, y1 = frames[index + 1]
            if t0 <= t <= t1:
                if t1 == t0:
                    return x0, y0
                ratio = (t - t0) / (t1 - t0)
                return x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio
        return None


ACTORS: list[Actor] = [
    # Eastbound car in the near lane.
    Actor("car", [(0.0, -90, 300), (11.0, 890, 300)]),
    # Truck that pulls out of the far lane and merges toward the car's lane,
    # producing a converging near-miss around t=5.5s.
    Actor("truck", [(1.5, 880, 190), (4.4, 470, 190), (6.2, 300, 268), (10.5, -120, 268)]),
    # A second car further away for track continuity.
    Actor("car", [(2.0, 900, 190), (11.5, -120, 190)]),
    # Motorcycle weaving across the near lane.
    Actor("motorcycle", [(3.0, 620, 380), (5.0, 470, 360), (7.0, 470, 300), (9.0, 620, 268)]),
    # Pedestrian crossing toward the road edge (pedestrian/vehicle conflict check).
    Actor("person", [(4.0, 700, 415), (7.5, 700, 250)]),
]


def render_background() -> np.ndarray:
    frame = np.full((HEIGHT, WIDTH, 3), (52, 50, 48), dtype=np.uint8)
    # Road surface
    cv2.rectangle(frame, (0, 150), (WIDTH, 420), (92, 92, 92), -1)
    # Kerbs
    cv2.rectangle(frame, (0, 140), (WIDTH, 152), (150, 150, 150), -1)
    cv2.rectangle(frame, (0, 418), (WIDTH, 430), (150, 150, 150), -1)
    # Lane markings (white dashes, deliberately far from every marker colour)
    for x in range(0, WIDTH, 80):
        cv2.rectangle(frame, (x, 268), (x + 40, 276), (245, 245, 245), -1)
    # Crosswalk near the right side
    for y in range(150, 420, 34):
        cv2.rectangle(frame, (686, y), (700, y + 16), (235, 235, 235), -1)
    return frame


def draw_actor(frame: np.ndarray, actor: Actor, position: tuple[float, float]) -> None:
    width, height = SIZES[actor.label]
    x, y = position
    x1 = int(round(x - width / 2))
    y1 = int(round(y - height / 2))
    x2 = int(round(x + width / 2))
    y2 = int(round(y + height / 2))
    cv2.rectangle(frame, (x1, y1), (x2, y2), COLOURS[actor.label], -1)
    if actor.label == "person":
        # Head marker keeps the same colour family but a round outline.
        cv2.circle(frame, (int(round(x)), y1 + 8), 6, COLOURS[actor.label], -1)


def generate(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    background = render_background()
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT)
    )
    total_frames = FPS * DURATION_SECONDS
    for index in range(total_frames):
        timestamp = index / FPS
        frame = background.copy()
        for actor in ACTORS:
            position = actor.position(timestamp)
            if position is not None:
                draw_actor(frame, actor, position)
        cv2.putText(
            frame,
            "SYNTHETIC DEMO SCENE - ROADGUARD AI",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"t={timestamp:05.2f}s",
            (WIDTH - 110, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        writer.write(frame)
    writer.release()

    manifest = {
        "file": output.name,
        "synthetic": True,
        "notice": (
            "Generated locally with OpenCV. Contains no real footage, no people and no "
            "vehicle registrations. Used only to demonstrate the processing pipeline."
        ),
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "duration_seconds": DURATION_SECONDS,
        "actors": [
            {
                "label": actor.label,
                "keyframes": [
                    {"t": t, "x": x, "y": y} for t, x, y in actor.keyframes
                ],
            }
            for actor in ACTORS
        ],
        "expected_candidate_window_seconds": [4.0, 7.5],
    }
    manifest_path = output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic demo clip")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "demo_intersection_synthetic.mp4"),
        help="output path",
    )
    args = parser.parse_args()
    path = generate(Path(args.output))
    print(f"generated: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
