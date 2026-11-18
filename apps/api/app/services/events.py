"""Domain event envelope and organisation-scoped publication.

REST remains authoritative; websocket messages are hints for the UI to refresh.
Every envelope is built server-side from the authenticated organization, never
from a client-supplied organization id.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger("roadguard.events")

SCHEMA_VERSION = "1.0"

SUPPORTED_EVENT_TYPES = {
    "camera.status_changed",
    "video.processing_started",
    "video.processing_progress",
    "video.processing_completed",
    "incident.detected",
    "incident.reviewed",
    "investigation.updated",
    "work_order.updated",
}


def build_envelope(
    *,
    organization_id: uuid.UUID,
    event_type: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "organization_id": str(organization_id),
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "schema_version": SCHEMA_VERSION,
        "data": data,
    }


type Subscriber = tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]


class InProcessHub:
    """Fan-out for websocket clients connected to this API process.

    Request handlers are synchronous and run in a worker thread, so publication
    hops back onto the subscriber's loop instead of touching its queue directly.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[Subscriber]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, organization_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        subscriber: Subscriber = (asyncio.get_running_loop(), queue)
        async with self._lock:
            self._subscribers[organization_id].add(subscriber)
        return queue

    async def unsubscribe(self, organization_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            for subscriber in list(self._subscribers.get(organization_id, ())):
                if subscriber[1] is queue:
                    self._subscribers[organization_id].discard(subscriber)

    def publish(self, organization_id: str, envelope: dict[str, Any]) -> None:
        for loop, queue in list(self._subscribers.get(organization_id, ())):
            if loop.is_closed():  # pragma: no cover - defensive
                continue
            try:
                loop.call_soon_threadsafe(self._deliver, organization_id, queue, envelope)
            except RuntimeError:  # pragma: no cover - loop shutting down
                continue

    @staticmethod
    def _deliver(
        organization_id: str, queue: asyncio.Queue[dict[str, Any]], envelope: dict[str, Any]
    ) -> None:
        try:
            queue.put_nowait(envelope)
        except asyncio.QueueFull:  # pragma: no cover - slow consumer
            logger.warning("realtime_queue_full org=%s", organization_id)


hub = InProcessHub()

_redis_sync = None


def _get_sync_redis():
    global _redis_sync
    if _redis_sync is None:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
            client.ping()
            _redis_sync = client
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.info("realtime_redis_unavailable error=%s", type(exc).__name__)
            _redis_sync = False
    return _redis_sync or None


def channel_for(organization_id: str) -> str:
    return f"roadguard:org:{organization_id}"


def publish_event(
    *,
    organization_id: uuid.UUID,
    event_type: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Publish after a successful commit. Never raises into business logic."""
    if event_type not in SUPPORTED_EVENT_TYPES:
        logger.warning("unsupported_event_type type=%s", event_type)
    envelope = build_envelope(
        organization_id=organization_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
    )
    # Local subscribers always receive the hint; Redis only extends reach to
    # other API processes when a broker is configured.
    hub.publish(str(organization_id), envelope)

    client = _get_sync_redis()
    if client is not None:
        try:
            client.publish(channel_for(str(organization_id)), json.dumps(envelope))
        except Exception as exc:  # pragma: no cover - transient broker failure
            logger.warning("realtime_publish_failed error=%s", type(exc).__name__)
    return envelope
