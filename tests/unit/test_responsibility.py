"""Unit tests for deterministic responsibility matching.

``build_responsibility`` makes exactly two queries: the contract ids linked to the
asset, then the contracts themselves. A tiny stub reproduces that shape so the
tests exercise the real matcher without a database or an unconfigured Mock.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from app.models import (
    Asset,
    AssetType,
    ConditionStatus,
    Contract,
    Contractor,
    Department,
    LocationQuality,
    ResponsibilityStatus,
)
from app.services.registry import build_responsibility


class _Rows:
    """Result stand-in supporting both ``.all()`` and ``.scalars().all()``."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return list(self._rows)

    def scalars(self) -> _Rows:
        return self

    def __iter__(self):
        return iter(self._rows)


class StubSession:
    """The two queries ``build_responsibility`` performs, plus entity lookups."""

    def __init__(
        self,
        *,
        department: Department | None,
        contract_ids: list,
        contracts: list,
        contractor: Contractor | None = None,
    ) -> None:
        self.department = department
        self.contractor = contractor
        self.contract_ids = list(contract_ids)
        self.contracts = list(contracts)
        self.execute_calls = 0

    def get(self, model, key):  # noqa: ANN001, ARG002
        if model is Department:
            return self.department
        if model is Contractor:
            return self.contractor
        return None

    def execute(self, statement):  # noqa: ANN001, ARG002
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _Rows([(contract_id,) for contract_id in self.contract_ids])
        return _Rows(self.contracts)


@pytest.fixture
def department() -> Department:
    return Department(
        id=uuid4(),
        organization_id=uuid4(),
        name="DEMO Roads and Buildings",
        department_type="roads",
        normalized_name="demo roads and buildings",
        contact_email="roads@demo.gov",
    )


@pytest.fixture
def asset(department: Department) -> Asset:
    return Asset(
        id=uuid4(),
        organization_id=department.organization_id,
        department_id=department.id,
        asset_code="ASSET-001",
        name="Main Street Crossing",
        asset_type=AssetType.PEDESTRIAN_CROSSING,
        address="Main St & 1st Ave",
        location_quality=LocationQuality.SURVEYED,
        condition_status=ConditionStatus.FAIR,
        source_reference="asset-reg-001",
    )


@pytest.fixture
def contractor(asset: Asset) -> Contractor:
    return Contractor(
        id=uuid4(),
        organization_id=asset.organization_id,
        name="DEMO Construction Co.",
        registration_number="CON-001",
        contact_email="contractor@demo.com",
        source_reference="contractor-reg-001",
    )


def make_contract(
    asset: Asset,
    department: Department,
    contractor: Contractor,
    *,
    number: str,
    start: date,
    end: date,
) -> Contract:
    return Contract(
        id=uuid4(),
        organization_id=asset.organization_id,
        contractor_id=contractor.id,
        department_id=department.id,
        contract_number=number,
        contract_type="maintenance",
        scope_description="Maintenance of pedestrian crossings",
        start_date=start,
        end_date=end,
        source_reference=f"contract-reg-{number}",
    )


class TestResponsibilityMatching:
    def test_missing_contract_data_when_no_contracts_linked(
        self, asset: Asset, department: Department
    ) -> None:
        session = StubSession(department=department, contract_ids=[], contracts=[])
        response = build_responsibility(
            session,  # type: ignore[arg-type]
            asset=asset,
            event_date=date(2024, 6, 15),
        )

        assert response.status == ResponsibilityStatus.MISSING_CONTRACT_DATA
        assert "No contract record is linked to this asset." in response.missing_records
        assert response.contracts == []

    def test_requires_field_verification_when_no_department(self, asset: Asset) -> None:
        asset.department_id = None
        session = StubSession(department=None, contract_ids=[], contracts=[])
        response = build_responsibility(
            session,  # type: ignore[arg-type]
            asset=asset,
            event_date=date(2024, 6, 15),
        )

        assert response.status == ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION
        assert "The asset has no maintaining department recorded." in response.missing_records

    def test_ambiguous_match_when_multiple_active_contracts(
        self, asset: Asset, department: Department, contractor: Contractor
    ) -> None:
        first = make_contract(
            asset,
            department,
            contractor,
            number="CONTRACT-001",
            start=date(2023, 1, 1),
            end=date(2025, 12, 31),
        )
        second = make_contract(
            asset,
            department,
            contractor,
            number="CONTRACT-002",
            start=date(2023, 1, 1),
            end=date(2025, 12, 31),
        )
        session = StubSession(
            department=department,
            contract_ids=[first.id, second.id],
            contracts=[first, second],
            contractor=contractor,
        )

        response = build_responsibility(
            session,  # type: ignore[arg-type]
            asset=asset,
            event_date=date(2024, 6, 15),
        )

        assert response.status == ResponsibilityStatus.AMBIGUOUS_MATCH
        assert len(response.contracts) == 2

    def test_expired_contract_reported_as_not_active(
        self, asset: Asset, department: Department, contractor: Contractor
    ) -> None:
        expired = make_contract(
            asset,
            department,
            contractor,
            number="CONTRACT-003",
            start=date(2020, 1, 1),
            end=date(2022, 12, 31),
        )
        session = StubSession(
            department=department,
            contract_ids=[expired.id],
            contracts=[expired],
            contractor=contractor,
        )

        response = build_responsibility(
            session,  # type: ignore[arg-type]
            asset=asset,
            event_date=date(2024, 6, 15),
        )

        assert response.contracts[0].is_active_on_event_date is False
        assert "does not include the event date" in response.contracts[0].date_note
        assert response.status == ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION

    def test_unknown_event_date_reported(
        self, asset: Asset, department: Department, contractor: Contractor
    ) -> None:
        contract = make_contract(
            asset,
            department,
            contractor,
            number="CONTRACT-004",
            start=date(2023, 1, 1),
            end=date(2025, 12, 31),
        )
        session = StubSession(
            department=department,
            contract_ids=[contract.id],
            contracts=[contract],
            contractor=contractor,
        )

        response = build_responsibility(session, asset=asset, event_date=None)  # type: ignore[arg-type]

        assert "Event date unknown" in response.contracts[0].date_note
        assert response.status == ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION

    def test_matched_records_when_active_contract_exists(
        self, asset: Asset, department: Department, contractor: Contractor
    ) -> None:
        contract = make_contract(
            asset,
            department,
            contractor,
            number="CONTRACT-005",
            start=date(2023, 1, 1),
            end=date(2025, 12, 31),
        )
        session = StubSession(
            department=department,
            contract_ids=[contract.id],
            contracts=[contract],
            contractor=contractor,
        )

        response = build_responsibility(
            session,  # type: ignore[arg-type]
            asset=asset,
            event_date=date(2024, 6, 15),
        )

        assert response.status == ResponsibilityStatus.MATCHED_RECORDS
        assert response.owning_department_id == department.id
        assert response.owning_department_name == department.name
        assert len(response.contracts) == 1
        assert response.contracts[0].contract_number == "CONTRACT-005"
        assert response.contracts[0].is_active_on_event_date is True
        assert response.verification_required is True
