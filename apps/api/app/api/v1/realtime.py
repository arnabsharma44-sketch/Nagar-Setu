"""WebSocket gateway.

The socket authenticates with a single-use, 60-second ticket issued over an
authenticated REST call. The organization is taken from that signed ticket — a
client can never subscribe to another tenant's channel by supplying an id.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from datetime import UTC, datetime

from app.api.deps import CurrentContext, RequestContext
from app.core.config import settings
from app.core.errors import AuthenticationError
from app.core.security import REALTIME_TOKEN_TYPE, create_realtime_ticket, decode_token
from app.db.session import tenant_session
from app.models import User
from app.schemas.common import Envelope, ok
from app.services.events import channel_for, hub
from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect

logger = logging.getLogger("roadguard.realtime")

router = APIRouter(tags=["realtime"])

TICKET_TTL_SECONDS = 60


@router.post("/realtime/ticket", response_model=Envelope[dict])
def create_ticket(request: Request, ctx: RequestContext = CurrentContext) -> Envelope[dict]:
    ticket = create_realtime_ticket(
        user_id=ctx.principal.user_id, organization_id=ctx.organization_id
    )
    return ok(
        {
            "ticket": ticket,
            "expires_in": TICKET_TTL_SECONDS,
            "path": f"{settings.api_prefix}/ws/command-center",
        },
        request,
    )


def _verify_ticket(ticket: str) -> tuple[uuid.UUID, uuid.UUID]:
    payload = decode_token(ticket, expected_type=REALTIME_TOKEN_TYPE)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        organization_id = uuid.UUID(str(payload["org"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("The realtime ticket is not valid.") from exc
    with tenant_session(organization_id) as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("This account can no longer open a realtime connection.")
    return user_id, organization_id


async def _redis_listener(websocket: WebSocket, organization_id: str) -> None:
    import redis.asyncio as aioredis

    client = aioredis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel_for(organization_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            await websocket.send_text(str(data))
    except asyncio.CancelledError:  # pragma: no cover - normal shutdown
        raise
    except Exception as exc:  # pragma: no cover - broker outage
        logger.info("realtime_redis_listener_stopped error=%s", type(exc).__name__)
    finally:
        try:
            await pubsub.unsubscribe(channel_for(organization_id))
            await client.aclose()
        except Exception:  # pragma: no cover
            pass


async def _queue_pump(websocket: WebSocket, queue: asyncio.Queue) -> None:
    try:
        while True:
            envelope = await queue.get()
            await websocket.send_text(json.dumps(envelope))
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception:  # pragma: no cover - client went away
        return


@router.websocket("/ws/command-center")
async def command_center_socket(websocket: WebSocket, ticket: str = Query(...)) -> None:
    try:
        user_id, organization_id = _verify_ticket(ticket)
    except AuthenticationError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    organization_key = str(organization_id)
    queue = await hub.subscribe(organization_key)
    tasks = [asyncio.create_task(_queue_pump(websocket, queue))]
    try:
        import redis.asyncio  # noqa: F401

        tasks.append(asyncio.create_task(_redis_listener(websocket, organization_key)))
    except ImportError:  # pragma: no cover - redis client optional
        logger.info("realtime_redis_client_unavailable")

    await websocket.send_json(
        {
            "event_type": "connected",
            "schema_version": "1.0",
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": {"user_id": str(user_id), "organization_id": organization_key},
        }
    )
    try:
        while True:
            # The client may send a keepalive; nothing it sends changes scope.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover
        pass
    finally:
        for task in tasks:
            task.cancel()
        await hub.unsubscribe(organization_key, queue)
        with contextlib.suppress(Exception):  # pragma: no cover - socket already gone
            await websocket.close()
