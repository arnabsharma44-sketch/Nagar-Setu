"""API v1 router aggregation."""

from app.api.v1 import (
    accidents,
    audit,
    auth,
    cameras,
    health,
    incidents,
    investigations,
    realtime,
    registry,
    storage,
    videos,
    work_orders,
)
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(registry.router)
api_router.include_router(cameras.router)
api_router.include_router(videos.router)
api_router.include_router(incidents.router)
api_router.include_router(accidents.router)
api_router.include_router(investigations.router)
api_router.include_router(work_orders.router)
api_router.include_router(audit.router)
api_router.include_router(storage.router)
api_router.include_router(realtime.router)

__all__ = ["api_router"]
