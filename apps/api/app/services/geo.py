"""WGS84 geography helpers.

Points are stored as ``GEOGRAPHY(POINT, 4326)`` and mirrored into explicit
``latitude``/``longitude`` columns so list endpoints can serialise coordinates
without a spatial round-trip. Every write must go through :func:`set_point` so
the two representations cannot drift.

Physical distance and speed are never derived from pixels here.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ValidationError
from app.models.enums import LocationQuality
from geoalchemy2.elements import WKTElement


def validate_coordinates(latitude: float | None, longitude: float | None) -> None:
    if latitude is None and longitude is None:
        return
    if latitude is None or longitude is None:
        raise ValidationError("Both latitude and longitude are required to set a location.")
    if not (-90.0 <= latitude <= 90.0):
        raise ValidationError("Latitude must be between -90 and 90.", code="INVALID_COORDINATE")
    if not (-180.0 <= longitude <= 180.0):
        raise ValidationError("Longitude must be between -180 and 180.", code="INVALID_COORDINATE")


def set_point(
    instance: Any,
    latitude: float | None,
    longitude: float | None,
    quality: LocationQuality | None = None,
) -> None:
    """Assign a point to a model that has location/latitude/longitude columns."""
    validate_coordinates(latitude, longitude)
    if latitude is None or longitude is None:
        instance.location = None
        instance.latitude = None
        instance.longitude = None
        if quality is not None:
            instance.location_quality = LocationQuality.UNKNOWN
        return
    instance.location = WKTElement(f"POINT({longitude} {latitude})", srid=4326)
    instance.latitude = float(latitude)
    instance.longitude = float(longitude)
    if quality is not None:
        instance.location_quality = quality


def point_payload(instance: Any) -> dict[str, Any] | None:
    latitude = getattr(instance, "latitude", None)
    longitude = getattr(instance, "longitude", None)
    if latitude is None or longitude is None:
        return None
    return {
        "latitude": latitude,
        "longitude": longitude,
        "quality": getattr(instance, "location_quality", LocationQuality.UNKNOWN),
    }
