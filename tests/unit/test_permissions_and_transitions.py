"""Role boundaries and the work-order state machine are pure, testable rules."""

from __future__ import annotations

import pytest
from app.core.permissions import ROLE_PERMISSIONS, permissions_for_role, role_has_permission
from app.models.enums import WORK_ORDER_TRANSITIONS, WorkOrderStatus


def test_platform_admin_has_every_permission() -> None:
    every_permission: set[str] = set().union(*ROLE_PERMISSIONS.values())
    assert every_permission - set(permissions_for_role("platform_admin")) == set()


def test_org_admin_cannot_hold_platform_only_permission() -> None:
    assert "system:admin" in permissions_for_role("platform_admin")
    assert "system:admin" not in permissions_for_role("org_admin")


def test_auditor_is_read_only() -> None:
    permissions = set(permissions_for_role("auditor"))
    assert "audit:read" in permissions
    assert "incident:read" in permissions
    writes = {permission for permission in permissions if permission.split(":")[-1] in {"create", "manage", "approve", "verify", "process", "upload"}}
    assert writes == set(), f"auditor must not hold write permissions: {writes}"


def test_unknown_role_has_no_permissions() -> None:
    assert permissions_for_role("superuser_from_client") == frozenset()
    assert not role_has_permission("superuser_from_client", "incident:read")


def test_department_engineer_cannot_verify_work_orders() -> None:
    assert role_has_permission("department_engineer", "work_order:complete")
    assert not role_has_permission("department_engineer", "work_order:verify")


def test_reviewer_can_verify_but_not_complete() -> None:
    assert role_has_permission("reviewer", "work_order:verify")
    assert not role_has_permission("reviewer", "work_order:complete")


def test_pending_cannot_jump_straight_to_in_progress() -> None:
    assert WorkOrderStatus.IN_PROGRESS not in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]
    assert WorkOrderStatus.ASSIGNED in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]


def test_verified_and_cancelled_are_terminal() -> None:
    assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.VERIFIED] == set()
    assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.CANCELLED] == set()


def test_completion_requires_verification_step() -> None:
    allowed = WORK_ORDER_TRANSITIONS[WorkOrderStatus.IN_PROGRESS]
    assert WorkOrderStatus.COMPLETED_PENDING_VERIFICATION in allowed
    assert WorkOrderStatus.VERIFIED not in allowed


@pytest.mark.parametrize("status", list(WorkOrderStatus))
def test_every_status_has_a_transition_entry(status: WorkOrderStatus) -> None:
    assert status in WORK_ORDER_TRANSITIONS
