"""Class map for supported road-user detections.

The class map is part of the job metadata so a review always knows which labels
the active model could produce. Classes mirror the COCO identifiers used by
YOLO-style detectors; the synthetic-scene adapter uses the same map so event
rules do not depend on the detector implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassSpec:
    class_id: int
    label: str
    is_vehicle: bool
    is_vulnerable_user: bool


CLASS_MAP: dict[int, ClassSpec] = {
    0: ClassSpec(0, "person", is_vehicle=False, is_vulnerable_user=True),
    1: ClassSpec(1, "bicycle", is_vehicle=False, is_vulnerable_user=True),
    2: ClassSpec(2, "car", is_vehicle=True, is_vulnerable_user=False),
    3: ClassSpec(3, "motorcycle", is_vehicle=True, is_vulnerable_user=True),
    5: ClassSpec(5, "bus", is_vehicle=True, is_vulnerable_user=False),
    7: ClassSpec(7, "truck", is_vehicle=True, is_vulnerable_user=False),
}

LABEL_TO_ID: dict[str, int] = {spec.label: spec.class_id for spec in CLASS_MAP.values()}
VEHICLE_LABELS: frozenset[str] = frozenset(
    spec.label for spec in CLASS_MAP.values() if spec.is_vehicle
)
VULNERABLE_LABELS: frozenset[str] = frozenset(
    spec.label for spec in CLASS_MAP.values() if spec.is_vulnerable_user
)


def class_spec(class_id: int) -> ClassSpec | None:
    return CLASS_MAP.get(class_id)


def serialize_class_map() -> list[dict[str, object]]:
    return [
        {
            "class_id": spec.class_id,
            "label": spec.label,
            "is_vehicle": spec.is_vehicle,
            "is_vulnerable_user": spec.is_vulnerable_user,
        }
        for spec in CLASS_MAP.values()
    ]
