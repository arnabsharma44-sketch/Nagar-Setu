"""Tests for responsibility matching logic."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from app.models import (
    Asset, AssetType, ConditionStatus, Contract, ContractAsset, Contractor,
    Department, LocationQuality, ResponsibilityStatus,
)
from app.services.registry import build_responsibility


class TestResponsibilityMatching:
    @pytest.fixture
    def mock_session(self):
        session = Mock()
        return session

    @pytest.fixture
    def department(self):
        return Department(
            id=uuid4(),
            organization_id=uuid4(),
            name="DEMO Roads and Buildings",
            department_type="roads",
            normalized_name="demo roads and buildings",
            contact_email="roads@demo.gov",
        )

    @pytest.fixture
    def asset(self, department):
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
    def contractor(self):
        return Contractor(
            id=uuid4(),
            organization_id=uuid4(),
            name="DEMO Construction Co.",
            registration_number="CON-001",
            contact_email="contractor@demo.com",
            source_reference="contractor-reg-001",
        )

    def test_missing_contract_data_when_no_contracts_linked(
        self, mock_session, asset
    ):
        mock_session.get.return_value = asset
        mock_session.execute.return_value.scalars.return_value = []

        response = build_responsibility(mock_session, asset=asset, event_date=date(2024, 6, 15))

        assert response.status == ResponsibilityStatus.MISSING_CONTRACT_DATA
        assert "No contract record is linked to this asset" in response.missing_records
        assert response.contracts == []

    def test_requires_field_verification_when_no_department(
        self, mock_session, asset
    ):
        asset.department_id = None
        mock_session.get.return_value = asset
        mock_session.execute.return_value.scalars.return_value = []

        response = build_responsibility(mock_session, asset=asset, event_date=date(2024, 6, 15))

        assert response.status == ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION
        assert "The asset has no maintaining department recorded" in response.missing_records

    def test_ambiguous_match_when_multiple_active_contracts(
        self, mock_session, asset, department, contractor
    ):
        contract1 = Contract(
            id=uuid4(), organization_id=asset.organization_id,
            contractor_id=contractor.id, department_id=department.id,
            contract_number="CONTRACT-001", contract_type="maintenance",
            scope_description="Maintenance", start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31), source_reference="ref1"
        )
        contract2 = Contract(
            id=uuid4(), organization_id=asset.organization_id,
            contractor_id=contractor.id, department_id=department.id,
            contract_number="CONTRACT-002", contract_type="maintenance",
            scope_description="Maintenance", start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31), source_reference="ref2"
        )
        ca1 = ContractAsset(id=uuid4(), organization_id=asset.organization_id, contract_id=contract1.id, asset_id=asset.id)
        ca2 = ContractAsset(id=uuid4(), organization_id=asset.organization_id, contract_id=contract2.id, asset_id=asset.id)

        mock_session.get.return_value = asset
        mock_session.execute.return_value.scalars.return_value = [ca1, ca2]
        mock_session.execute.return_value.scalars.return_value = [contract1, contract2]

        response = build_responsibility(mock_session, asset=asset, event_date=date(2024, 6, 15))

        assert response.status == ResponsibilityStatus.AMBIGUOUS_MATCH
        assert len(response.contracts) == 2

    def test_expired_contract_reported_as_not_active(
        self, mock_session, asset, department, contractor
    ):
        contract = Contract(
            id=uuid4(), organization_id=asset.organization_id,
            contractor_id=contractor.id, department_id=department.id,
            contract_number="CONTRACT-001", contract_type="maintenance",
            scope_description="Maintenance", start_date=date(2020, 1, 1),
            end_date=date(2022, 12, 31), source_reference="ref"
        )
        ca = ContractAsset(id=uuid4(), organization_id=asset.organization_id, contract_id=contract.id, asset_id=asset.id)

        mock_session.get.return_value = asset
        mock_session.execute.return_value.scalars.return_value = [ca]
        mock_session.execute.return_value.scalars.return_value = [contract]

        response = build_responsibility(mock_session, asset=asset, event_date=date(2024, 6, 15))

        assert response.contracts[0].is_active_on_event_date is False
        assert "does not include the event date" in response.contracts[0].date_note

    def test_unknown_event_date_reported(
        self, mock_session, asset, department, contract, contract_asset
    ):
        mock_session.get.side_effect = lambda cls, id: {
            Asset: asset, Department: department, Contract: contract
        }.get(cls)
        mock_session.execute.return_value.scalars.return_value = [contract_asset]
        mock_session.execute.return_value.scalar_one_or_none.return_value = contract

        response = build_responsibility(mock_session, asset=asset, event_date=None)

        assert "Event date unknown" in response.contracts[0].date_note
    @pytest.fixture
    def contract(self, department, contractor, asset):
        return Contract(
            id=uuid4(),
            organization_id=contractor.organization_id,
            contractor_id=contractor.id,
            department_id=department.id,
            contract_number="CONTRACT-001",
            contract_type="maintenance",
            scope_description="Maintenance of pedestrian crossings",
            start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31),
            source_reference="contract-reg-001",
        )

    @pytest.fixture
    def contract_asset(self, contract, asset):
        return ContractAsset(
            id=uuid4(),
            organization_id=asset.organization_id,
            contract_id=contract.id,
            asset_id=asset.id,
            scope_notes="Full maintenance coverage",
        )

    def test_matched_records_when_active_contract_exists(
        self, mock_session, asset, department, contract, contract_asset
    ):
        mock_session.get.side_effect = lambda cls, id: {
            Asset: asset, Department: department, Contract: contract
        }.get(cls)

        mock_session.execute.return_value.scalars.return_value = [contract_asset]
        mock_session.execute.return_value.scalar_one_or_none.return_value = contract

        event_date = date(2024, 6, 15)
        response = build_responsibility(mock_session, asset=asset, event_date=event_date)

        assert response.status == ResponsibilityStatus.MATCHED_RECORDS
        assert response.owning_department_id == department.id
        assert response.owning_department_name == department.name
        assert len(response.contracts) == 1
        assert response.contracts[0].contract_number == "CONTRACT-001"
        assert response.contracts[0].is_active_on_event_date is True
        assert response.verification_required is True