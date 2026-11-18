"""Hotspot analysis over separate, labelled data sources.

Clusters combine located records but every cluster keeps per-source counts so a
cluster can never be presented as an "accident blackspot" built only from AI
candidates. Traffic-exposure normalization is not attempted because no exposure
denominator is available; the output is explicitly a record concentration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from app.core.audit import record_audit
from app.core.errors import ValidationError
from app.models import (
    AccidentRecord,
    HotspotAnalysis,
    Incident,
    ReviewStatus,
)
from app.schemas.domain import (
    FeatureCollection,
    HotspotAnalysisOut,
    HotspotAnalyzeRequest,
    HotspotCluster,
)
from sklearn.cluster import DBSCAN
from sqlalchemy import func, select
from sqlalchemy.orm import Session

METHOD = "dbscan_haversine_combined_layers"
METHODOLOGY_NOTE = (
    "Clusters located records with DBSCAN using geodesic distance. Historical "
    "accident records, human-confirmed observations and pending AI candidates are "
    "counted separately inside every cluster. No traffic-exposure denominator is "
    "available, so this is a record concentration, not a normalized risk rate."
)
DATA_SOURCES = [
    "historical_accident_records",
    "human_confirmed_observations",
    "pending_ai_candidates",
]


def _collect_records(
    session: Session, window_from: datetime | None, window_to: datetime | None
) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    unlocated = 0

    accident_filters = [AccidentRecord.latitude.is_not(None)]
    if window_from:
        accident_filters.append(AccidentRecord.accident_time >= window_from)
    if window_to:
        accident_filters.append(AccidentRecord.accident_time <= window_to)
    for record in session.execute(select(AccidentRecord).where(*accident_filters)).scalars():
        records.append(
            {
                "id": record.id,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "source": "historical_accident_records",
                "category": record.accident_type or "unspecified_accident",
                "seen_at": record.accident_time,
            }
        )
    unlocated += int(
        session.execute(
            select(func.count()).select_from(AccidentRecord).where(AccidentRecord.latitude.is_(None))
        ).scalar_one()
    )

    incident_filters = [Incident.latitude.is_not(None)]
    if window_from:
        incident_filters.append(Incident.event_time >= window_from)
    if window_to:
        incident_filters.append(Incident.event_time <= window_to)
    for incident in session.execute(select(Incident).where(*incident_filters)).scalars():
        source = (
            "human_confirmed_observations"
            if incident.review_status == ReviewStatus.CONFIRMED
            else "pending_ai_candidates"
            if incident.review_status == ReviewStatus.PENDING
            else None
        )
        if source is None:
            continue
        records.append(
            {
                "id": incident.id,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "source": source,
                "category": incident.incident_type.value,
                "seen_at": incident.event_time,
            }
        )
    unlocated += int(
        session.execute(
            select(func.count())
            .select_from(Incident)
            .where(Incident.latitude.is_(None), Incident.review_status != ReviewStatus.REJECTED_FALSE_POSITIVE)
        ).scalar_one()
    )
    return records, unlocated


def analyze(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_label: str | None,
    payload: HotspotAnalyzeRequest,
    request_id: str | None,
) -> HotspotAnalysis:
    if payload.window_from and payload.window_to and payload.window_from > payload.window_to:
        raise ValidationError("window_from must be before window_to.", code="INVALID_WINDOW")

    records, unlocated = _collect_records(session, payload.window_from, payload.window_to)
    clusters: list[HotspotCluster] = []

    if records:
        coordinates = np.radians(
            np.array([[record["latitude"], record["longitude"]] for record in records], dtype=float)
        )
        epsilon = payload.radius_meters / 6_371_000.0
        labels = DBSCAN(eps=epsilon, min_samples=payload.min_size, metric="haversine").fit_predict(
            coordinates
        )
        for label in sorted({int(value) for value in labels if value >= 0}):
            members = [record for record, assigned in zip(records, labels, strict=True) if int(assigned) == label]
            counts: dict[str, int] = {}
            categories: dict[str, int] = {}
            for member in members:
                counts[member["source"]] = counts.get(member["source"], 0) + 1
                categories[member["category"]] = categories.get(member["category"], 0) + 1
            latitudes = [member["latitude"] for member in members]
            longitudes = [member["longitude"] for member in members]
            seen = sorted(member["seen_at"] for member in members if member["seen_at"])
            cluster = HotspotCluster(
                cluster_key=f"cluster-{label}",
                latitude=float(sum(latitudes) / len(latitudes)),
                longitude=float(sum(longitudes) / len(longitudes)),
                radius_meters=payload.radius_meters,
                counts=counts,
                total_records=len(members),
                source_mix=sorted(counts),
                categories=categories,
                first_seen=seen[0] if seen else None,
                last_seen=seen[-1] if seen else None,
                record_ids=[member["id"] for member in members],
                label=_label_for(counts),
            )
            clusters.append(cluster)

    clusters.sort(key=lambda cluster: cluster.total_records, reverse=True)

    analysis = HotspotAnalysis(
        organization_id=organization_id,
        method=METHOD,
        radius_meters=payload.radius_meters,
        min_size=payload.min_size,
        window_from=payload.window_from,
        window_to=payload.window_to,
        parameters={
            "radius_meters": payload.radius_meters,
            "min_size": payload.min_size,
            "metric": "haversine",
            "combined_sources": DATA_SOURCES,
        },
        results={
            "clusters": [cluster.model_dump(mode="json") for cluster in clusters],
            "unlocated_count": unlocated,
            "record_count": len(records),
            "methodology_note": METHODOLOGY_NOTE,
        },
        generated_at=datetime.now(UTC),
        created_by=actor_id,
        is_demo=True,
    )
    session.add(analysis)
    session.flush()

    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="hotspot.analysis_created",
        entity_type="hotspot_analysis",
        entity_id=analysis.id,
        request_id=request_id,
        summary=f"Hotspot analysis computed over {len(records)} located records.",
        metadata={"clusters": len(clusters), "radius_meters": payload.radius_meters},
    )
    return analysis


def _label_for(counts: dict[str, int]) -> str:
    if counts.get("historical_accident_records", 0) and counts.get("human_confirmed_observations", 0):
        return "Historical accidents and confirmed observations concentrated"
    if counts.get("historical_accident_records", 0):
        return "Historical accident record concentration"
    if counts.get("human_confirmed_observations", 0):
        return "Confirmed observation concentration"
    return "Unreviewed AI candidate concentration (not an accident count)"


def to_schema(analysis: HotspotAnalysis) -> HotspotAnalysisOut:
    stored = analysis.results.get("clusters", [])
    return HotspotAnalysisOut(
        id=analysis.id,
        method=analysis.method,
        radius_meters=float(analysis.radius_meters),
        min_size=int(analysis.min_size),
        window_from=analysis.window_from,
        window_to=analysis.window_to,
        generated_at=analysis.generated_at,
        methodology_note=analysis.results.get("methodology_note", METHODOLOGY_NOTE),
        data_sources=DATA_SOURCES,
        clusters=[HotspotCluster.model_validate(cluster) for cluster in stored],
        unlocated_count=int(analysis.results.get("unlocated_count", 0)),
        is_demo=analysis.is_demo,
    )


def to_feature_collection(analysis: HotspotAnalysis) -> FeatureCollection:
    features: list[dict[str, Any]] = []
    for cluster in analysis.results.get("clusters", []):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [cluster["longitude"], cluster["latitude"]],
                },
                "properties": {
                    "cluster_key": cluster["cluster_key"],
                    "counts_by_source": cluster["counts"],
                    "total_records": cluster["total_records"],
                    "categories": cluster["categories"],
                    "radius_meters": cluster["radius_meters"],
                    "label": cluster["label"],
                    "record_ids": [str(record_id) for record_id in cluster["record_ids"]],
                    "first_seen": cluster["first_seen"],
                    "last_seen": cluster["last_seen"],
                },
            }
        )
    return FeatureCollection(
        features=features,
        properties={
            "analysis_id": str(analysis.id),
            "method": analysis.method,
            "generated_at": analysis.generated_at.isoformat(),
            "window_from": analysis.window_from.isoformat() if analysis.window_from else None,
            "window_to": analysis.window_to.isoformat() if analysis.window_to else None,
            "radius_meters": float(analysis.radius_meters),
            "data_sources": DATA_SOURCES,
            "methodology_note": analysis.results.get("methodology_note", METHODOLOGY_NOTE),
            "unlocated_count": analysis.results.get("unlocated_count", 0),
            "count_interpretation": (
                "Layers are counted separately; do not present a cluster as verified "
                "accident statistics unless it contains historical accident records."
            ),
        },
    )
