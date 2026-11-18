"""Role → permission mapping and authorization helpers.

Permissions are explicit strings (see docs/05_API_SPEC.md §13). The frontend
uses the same strings only to hide controls; the backend remains authoritative.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    CAMERA_READ = "camera:read"
    CAMERA_MANAGE = "camera:manage"
    VIDEO_UPLOAD = "video:upload"
    VIDEO_READ = "video:read"
    VIDEO_PROCESS = "video:process"
    INCIDENT_READ = "incident:read"
    INCIDENT_REVIEW = "incident:review"
    INCIDENT_CREATE = "incident:create"
    ASSET_READ = "asset:read"
    ASSET_MANAGE = "asset:manage"
    CONTRACT_READ = "contract:read"
    CONTRACT_MANAGE = "contract:manage"
    CONTRACTOR_READ = "contractor:read"
    CONTRACTOR_MANAGE = "contractor:manage"
    DEPARTMENT_READ = "department:read"
    DEPARTMENT_MANAGE = "department:manage"
    INVESTIGATION_READ = "investigation:read"
    INVESTIGATION_MANAGE = "investigation:manage"
    INVESTIGATION_ASSIGN = "investigation:assign"
    RECOMMENDATION_REVIEW = "recommendation:review"
    WORK_ORDER_READ = "work_order:read"
    WORK_ORDER_MANAGE = "work_order:manage"
    WORK_ORDER_COMPLETE = "work_order:complete"
    WORK_ORDER_VERIFY = "work_order:verify"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    ANALYTICS_READ = "analytics:read"
    ACCIDENT_READ = "accident:read"
    ACCIDENT_IMPORT = "accident:import"
    HOTSPOT_ANALYZE = "hotspot:analyze"
    EVIDENCE_READ = "evidence:read"
    SYSTEM_ADMIN = "system:admin"


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    POLICE_ADMIN = "police_admin"
    REVIEWER = "reviewer"
    DEPARTMENT_ENGINEER = "department_engineer"
    AUDITOR = "auditor"


ALL_PERMISSIONS: frozenset[str] = frozenset(permission.value for permission in Permission)

_READ_ONLY: set[Permission] = {
    Permission.CAMERA_READ,
    Permission.VIDEO_READ,
    Permission.INCIDENT_READ,
    Permission.ASSET_READ,
    Permission.CONTRACT_READ,
    Permission.CONTRACTOR_READ,
    Permission.DEPARTMENT_READ,
    Permission.INVESTIGATION_READ,
    Permission.WORK_ORDER_READ,
    Permission.ANALYTICS_READ,
    Permission.ACCIDENT_READ,
    Permission.EVIDENCE_READ,
}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.PLATFORM_ADMIN: ALL_PERMISSIONS,
    Role.ORG_ADMIN: ALL_PERMISSIONS - {Permission.SYSTEM_ADMIN},
    Role.POLICE_ADMIN: frozenset(
        {
            p.value
            for p in _READ_ONLY
            | {
                Permission.CAMERA_MANAGE,
                Permission.VIDEO_UPLOAD,
                Permission.VIDEO_PROCESS,
                Permission.INCIDENT_REVIEW,
                Permission.INCIDENT_CREATE,
                Permission.INVESTIGATION_MANAGE,
                Permission.INVESTIGATION_ASSIGN,
                Permission.RECOMMENDATION_REVIEW,
                Permission.WORK_ORDER_MANAGE,
                Permission.WORK_ORDER_VERIFY,
                Permission.AUDIT_READ,
                Permission.HOTSPOT_ANALYZE,
                Permission.ACCIDENT_IMPORT,
            }
        }
    ),
    Role.REVIEWER: frozenset(
        {
            p.value
            for p in _READ_ONLY
            | {
                Permission.INCIDENT_REVIEW,
                Permission.INCIDENT_CREATE,
                Permission.INVESTIGATION_MANAGE,
                Permission.RECOMMENDATION_REVIEW,
                Permission.WORK_ORDER_VERIFY,
                Permission.VIDEO_UPLOAD,
            }
        }
    ),
    Role.DEPARTMENT_ENGINEER: frozenset(
        {
            p.value
            for p in {
                Permission.ASSET_READ,
                Permission.CONTRACT_READ,
                Permission.CONTRACTOR_READ,
                Permission.DEPARTMENT_READ,
                Permission.INVESTIGATION_READ,
                Permission.INCIDENT_READ,
                Permission.VIDEO_READ,
                Permission.WORK_ORDER_READ,
                Permission.WORK_ORDER_MANAGE,
                Permission.WORK_ORDER_COMPLETE,
                Permission.ANALYTICS_READ,
                Permission.EVIDENCE_READ,
            }
        }
    ),
    Role.AUDITOR: frozenset({p.value for p in _READ_ONLY} | {Permission.AUDIT_READ}),
}


def permissions_for_role(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: str, permission: str | Permission) -> bool:
    value = permission.value if isinstance(permission, Permission) else permission
    return value in permissions_for_role(role)


def all_permissions_for_roles(roles: list[str]) -> frozenset[str]:
    granted: set[str] = set()
    for role in roles:
        granted |= permissions_for_role(role)
    return frozenset(granted)
