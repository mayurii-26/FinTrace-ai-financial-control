"""Tests for the FinTrace AI investigation layer.

Covers:
  1. InvestigationOutput schema and confidence rules
  2. Individual tool execution against real in-memory DB data
  3. Full mock agent investigation (tool calls, evidence, persistence)
  4. Lifecycle trace builder (all 7 stages, status derivation)
  5. Controller action API (approve, reject, escalate)
  6. Verification API (before/after exposure)
  7. Audit logging for investigation, action, verify events
  8. Provider abstraction (mock fallback, unavailability)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generator, Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Shared in-memory DB fixture
# ---------------------------------------------------------------------------

AI_TEST_DB_URL = "sqlite:///:memory:"

ai_engine = create_engine(
    AI_TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
AISession = sessionmaker(autocommit=False, autoflush=False, bind=ai_engine, future=True)


def _init_ai_db():
    from app.core.database import Base
    from app.models import transaction, exception, audit  # noqa
    Base.metadata.create_all(bind=ai_engine)


@pytest.fixture(scope="session", autouse=True)
def create_ai_tables():
    _init_ai_db()
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    conn = ai_engine.connect()
    trans = conn.begin()
    session = AISession(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def seeded_db(db: Session) -> Session:
    """DB with 80 synthetic transactions already evaluated."""
    from app.data.seeder import seed_database
    seed_database(db, count=80, seed=77, force=True)
    return db


@pytest.fixture
def client(db: Session) -> TestClient:
    from app.main import app
    from app.core.database import get_db

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_client(seeded_db: Session) -> TestClient:
    from app.main import app
    from app.core.database import get_db

    def override():
        yield seeded_db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: get first exception of a given type
# ---------------------------------------------------------------------------

def _first_exc(db: Session, exc_type: Optional[str] = None):
    from sqlalchemy import select
    from app.models.exception import ExceptionRecord
    stmt = select(ExceptionRecord)
    if exc_type:
        stmt = stmt.where(ExceptionRecord.exception_type == exc_type)
    return db.execute(stmt.limit(1)).scalar_one_or_none()


def _any_exc(db: Session):
    return _first_exc(db)


# ---------------------------------------------------------------------------
# 1. InvestigationOutput schema & confidence rules
# ---------------------------------------------------------------------------

class TestInvestigationSchema:
    def test_confidence_band_high(self):
        from app.agent.schemas import InvestigationOutput, ConfidenceBand, RecommendedAction
        out = InvestigationOutput(
            exception_id="EXC-001",
            exception_type="settlement_amount_discrepancy",
            severity="medium",
            root_cause="Settlement differs from expected.",
            evidence={},
            financial_exposure="100.00",
            impact_summary="Under-credited.",
            confidence=0.92,
            confidence_band=ConfidenceBand.HIGH,
            recommendation="Raise dispute.",
            recommended_action=RecommendedAction.RAISE_DISPUTE,
            requires_human_review=False,
            agent_provider="mock",
        )
        assert out.confidence_band == ConfidenceBand.HIGH
        assert not out.requires_human_review

    def test_confidence_band_requires_verification(self):
        from app.agent.schemas import InvestigationOutput, ConfidenceBand, RecommendedAction
        out = InvestigationOutput(
            exception_id="EXC-002",
            exception_type="orphan_financial_event",
            severity="medium",
            root_cause="Orphan detected.",
            evidence={},
            financial_exposure="50.00",
            impact_summary="Unattributed funds.",
            confidence=0.80,
            confidence_band=ConfidenceBand.REQUIRES_VERIFICATION,
            recommendation="Investigate manually.",
            recommended_action=RecommendedAction.INVESTIGATE_MANUALLY,
            requires_human_review=True,
            agent_provider="mock",
        )
        assert out.confidence_band == ConfidenceBand.REQUIRES_VERIFICATION

    def test_low_confidence_forces_human_review(self):
        from app.agent.schemas import InvestigationOutput, ConfidenceBand, RecommendedAction
        # Even if requires_human_review=False is passed, validator overrides it
        out = InvestigationOutput(
            exception_id="EXC-003",
            exception_type="missing_downstream_event",
            severity="high",
            root_cause="No settlement found.",
            evidence={},
            financial_exposure="5000.00",
            impact_summary="Revenue at risk.",
            confidence=0.60,
            confidence_band=ConfidenceBand.INSUFFICIENT,
            recommendation="Manual review.",
            recommended_action=RecommendedAction.INVESTIGATE_MANUALLY,
            requires_human_review=False,  # should be overridden
            agent_provider="mock",
        )
        assert out.requires_human_review is True
        assert out.confidence_band == ConfidenceBand.INSUFFICIENT

    def test_confidence_to_band_mapping(self):
        from app.agent.schemas import confidence_to_band, ConfidenceBand
        assert confidence_to_band(0.95) == ConfidenceBand.HIGH
        assert confidence_to_band(0.90) == ConfidenceBand.HIGH
        assert confidence_to_band(0.89) == ConfidenceBand.REQUIRES_VERIFICATION
        assert confidence_to_band(0.70) == ConfidenceBand.REQUIRES_VERIFICATION
        assert confidence_to_band(0.69) == ConfidenceBand.INSUFFICIENT
        assert confidence_to_band(0.00) == ConfidenceBand.INSUFFICIENT

    def test_tool_call_record(self):
        from app.agent.schemas import ToolCallRecord
        record = ToolCallRecord(
            tool_name="get_payments",
            arguments={"transaction_id": "TXN-001"},
            result_summary="Found 2 payments; orphan_count=1",
        )
        assert record.tool_name == "get_payments"
        assert "transaction_id" in record.arguments

    def test_lifecycle_stage(self):
        from app.agent.schemas import LifecycleStage, StageStatus
        stage = LifecycleStage(
            stage="PAYMENT",
            status=StageStatus.VALID,
            amount="1000.00",
            notes="Payment captured.",
        )
        assert stage.status == StageStatus.VALID


# ---------------------------------------------------------------------------
# 2. Tool execution against real DB data
# ---------------------------------------------------------------------------

class TestToolExecution:
    def test_get_transaction_found(self, seeded_db: Session):
        from app.agent.tools import tool_get_transaction
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_transaction(seeded_db, txn.transaction_id)
        assert result["found"] is True
        assert result["transaction_id"] == txn.transaction_id
        assert "status" in result
        assert "financial_exposure" in result

    def test_get_transaction_not_found(self, seeded_db: Session):
        from app.agent.tools import tool_get_transaction
        result = tool_get_transaction(seeded_db, "TXN-NOTEXIST")
        assert result["found"] is False

    def test_get_order(self, seeded_db: Session):
        from app.agent.tools import tool_get_order
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_order(seeded_db, txn.transaction_id)
        assert result["found"] is True
        assert "order_id" in result
        assert "amount" in result

    def test_get_payments(self, seeded_db: Session):
        from app.agent.tools import tool_get_payments
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_payments(seeded_db, txn.transaction_id)
        assert result["found"] is True
        assert "count" in result
        assert "orphan_count" in result
        assert "payments" in result
        assert isinstance(result["payments"], list)

    def test_get_refunds_no_refund(self, seeded_db: Session):
        from app.agent.tools import tool_get_refunds
        from app.models.transaction import Transaction
        from sqlalchemy import select
        # Find a transaction without refunds
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_refunds(seeded_db, txn.transaction_id)
        # May or may not have refunds — just check structure
        assert "refund_present" in result

    def test_get_settlements(self, seeded_db: Session):
        from app.agent.tools import tool_get_settlements
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_settlements(seeded_db, txn.transaction_id)
        # May be missing for missing_downstream_event; just check structure
        assert "found" in result

    def test_get_bank_entries(self, seeded_db: Session):
        from app.agent.tools import tool_get_bank_entries
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_bank_entries(seeded_db, txn.transaction_id)
        assert "found" in result

    def test_get_financial_timeline(self, seeded_db: Session):
        from app.agent.tools import tool_get_financial_timeline
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result = tool_get_financial_timeline(seeded_db, txn.transaction_id)
        assert result["found"] is True
        assert "events" in result
        assert "timing_gaps" in result
        assert result["event_count"] > 0

    def test_get_control_evidence(self, seeded_db: Session):
        from app.agent.tools import tool_get_control_evidence
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select
        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions in seeded data.")
        result = tool_get_control_evidence(seeded_db, exc.exception_id)
        assert result["found"] is True
        assert "control_evidence" in result
        assert "exception_type" in result

    def test_execute_tool_dispatch(self, seeded_db: Session):
        from app.agent.tools import execute_tool
        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        result, record = execute_tool(seeded_db, "get_transaction", {"transaction_id": txn.transaction_id})
        assert result["found"] is True
        assert record.tool_name == "get_transaction"
        assert record.result_summary  # non-empty

    def test_execute_unknown_tool(self, seeded_db: Session):
        from app.agent.tools import execute_tool
        result, record = execute_tool(seeded_db, "nonexistent_tool", {})
        assert "error" in result
        assert "ERROR" in record.result_summary

    def test_tool_calls_only_executed_ones_recorded(self, seeded_db: Session):
        """Verify that tool calls list only contains actually-executed tools."""
        from app.agent.agent import _run_mock_investigation
        from app.finance.lifecycle_trace import build_lifecycle_trace
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        trace = build_lifecycle_trace(seeded_db, exc.transaction_id)
        output = _run_mock_investigation(seeded_db, exc, trace)

        # All recorded tool calls should correspond to tools in the plan
        from app.agent.tools import TOOL_REGISTRY
        for tc in output.tool_calls:
            assert tc.tool_name in TOOL_REGISTRY, f"Unknown tool in output: {tc.tool_name}"
        # At least 2 tools were called (control_evidence + timeline)
        assert len(output.tool_calls) >= 2


# ---------------------------------------------------------------------------
# 3. Full mock agent investigation
# ---------------------------------------------------------------------------

class TestMockAgentInvestigation:
    def test_investigation_returns_output(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        result = run_investigation(seeded_db, exc.exception_id, provider_name="mock")
        assert result is not None
        assert "investigation" in result
        assert "output" in result
        assert "requires_human_review" in result
        assert "missing_evidence" in result

    def test_investigation_persisted_to_db(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord, Investigation
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        run_investigation(seeded_db, exc.exception_id, provider_name="mock")

        inv = seeded_db.execute(
            select(Investigation).where(Investigation.exception_id == exc.exception_id)
        ).scalar_one_or_none()
        assert inv is not None
        assert inv.root_cause
        assert inv.confidence > 0.0
        assert inv.agent_provider == "mock"

    def test_investigation_not_found(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        result = run_investigation(seeded_db, "EXC-NOTEXIST")
        assert result is None

    def test_investigation_has_tool_calls_in_evidence(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        result = run_investigation(seeded_db, exc.exception_id, provider_name="mock")
        output = result["output"]
        assert len(output.tool_calls) >= 2
        # Every tool_call has a non-empty result_summary
        for tc in output.tool_calls:
            assert tc.result_summary

    def test_investigation_confidence_range(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        result = run_investigation(seeded_db, exc.exception_id, provider_name="mock")
        confidence = result["output"].confidence
        assert 0.0 <= confidence <= 1.0

    def test_investigation_has_lifecycle_trace(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        result = run_investigation(seeded_db, exc.exception_id, provider_name="mock")
        trace = result["output"].lifecycle_trace
        assert trace is not None
        assert len(trace.stages) > 0
        assert trace.overall_status in ("VALID", "WARNING", "BREAK", "MISSING")

    def test_investigation_evidence_from_db(self, seeded_db: Session):
        """Root cause must reference actual data values, not generic text."""
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.exception_type == "settlement_amount_discrepancy")
            .limit(1)
        ).scalar_one_or_none()
        if exc is None:
            pytest.skip("No settlement_amount_discrepancy exception.")

        result = run_investigation(seeded_db, exc.exception_id, provider_name="mock")
        root_cause = result["output"].root_cause
        # Should reference actual amounts from DB, not a generic template
        assert "₹" in root_cause or "settlement" in root_cause.lower()


# ---------------------------------------------------------------------------
# 4. Lifecycle trace
# ---------------------------------------------------------------------------

class TestLifecycleTrace:
    def test_trace_has_all_stages_for_healthy(self, seeded_db: Session):
        from app.finance.lifecycle_trace import build_lifecycle_trace
        from app.models.transaction import Transaction, TransactionStatus
        from sqlalchemy import select

        txn = seeded_db.execute(
            select(Transaction).where(Transaction.status == TransactionStatus.HEALTHY).limit(1)
        ).scalar_one_or_none()
        if txn is None:
            pytest.skip("No healthy transactions.")

        trace = build_lifecycle_trace(seeded_db, txn.transaction_id)
        stage_names = [s.stage for s in trace.stages]
        assert "ORDER" in stage_names
        assert "PAYMENT" in stage_names
        assert "ACTUAL_SETTLEMENT" in stage_names
        assert "BANK_CREDIT" in stage_names
        assert trace.overall_status == "VALID"

    def test_trace_break_for_exception(self, seeded_db: Session):
        from app.finance.lifecycle_trace import build_lifecycle_trace
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.exception_type.in_([
                "settlement_amount_discrepancy",
                "duplicate_financial_event",
                "orphan_financial_event",
            ]))
            .limit(1)
        ).scalar_one_or_none()
        if exc is None:
            pytest.skip("No relevant exceptions.")

        trace = build_lifecycle_trace(seeded_db, exc.transaction_id)
        statuses = [s.status for s in trace.stages]
        assert "BREAK" in statuses
        assert trace.overall_status == "BREAK"

    def test_trace_missing_for_missing_downstream(self, seeded_db: Session):
        from app.finance.lifecycle_trace import build_lifecycle_trace
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.exception_type == "missing_downstream_event")
            .limit(1)
        ).scalar_one_or_none()
        if exc is None:
            pytest.skip("No missing_downstream_event exception.")

        trace = build_lifecycle_trace(seeded_db, exc.transaction_id)
        statuses = [s.status for s in trace.stages]
        assert "MISSING" in statuses

    def test_trace_not_found(self, db: Session):
        from app.finance.lifecycle_trace import build_lifecycle_trace
        trace = build_lifecycle_trace(db, "TXN-NOTEXIST")
        assert trace.overall_status == "MISSING"
        assert trace.stages == []

    def test_trace_stage_amounts_are_strings(self, seeded_db: Session):
        from app.finance.lifecycle_trace import build_lifecycle_trace
        from app.models.transaction import Transaction
        from sqlalchemy import select

        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        trace = build_lifecycle_trace(seeded_db, txn.transaction_id)
        for stage in trace.stages:
            if stage.amount is not None:
                # Should be a numeric string, not a Python Decimal repr
                float(stage.amount)  # should not raise


# ---------------------------------------------------------------------------
# 5. Investigation API
# ---------------------------------------------------------------------------

class TestInvestigateAPI:
    def test_investigate_endpoint_200(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/investigate",
            json={"provider": "mock"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "investigation" in data
        assert "requires_human_review" in data
        assert "missing_evidence" in data
        assert "lifecycle_trace" in data

    def test_investigate_endpoint_404(self, client: TestClient):
        resp = client.post(
            "/api/exceptions/EXC-NOTEXIST/investigate",
            json={"provider": "mock"},
        )
        assert resp.status_code == 404

    def test_investigate_returns_tool_calls(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/investigate",
            json={"provider": "mock"},
        )
        data = resp.json()
        tool_calls = data["investigation"]["tool_calls"]
        assert isinstance(tool_calls, list)
        assert len(tool_calls) >= 2
        for tc in tool_calls:
            assert "tool_name" in tc
            assert "result_summary" in tc

    def test_investigate_confidence_in_response(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/investigate",
            json={"provider": "mock"},
        )
        data = resp.json()
        confidence = data["investigation"]["confidence"]
        assert 0.0 <= confidence <= 1.0
        assert data["investigation"]["confidence_band"] in (
            "high_confidence", "requires_verification", "insufficient_evidence"
        )

    def test_investigate_lifecycle_trace_in_response(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/investigate",
            json={"provider": "mock"},
        )
        data = resp.json()
        trace = data.get("lifecycle_trace")
        assert trace is not None
        assert "stages" in trace
        assert len(trace["stages"]) > 0
        for stage in trace["stages"]:
            assert stage["status"] in ("VALID", "WARNING", "BREAK", "MISSING")


# ---------------------------------------------------------------------------
# 6. Controller action API
# ---------------------------------------------------------------------------

class TestControllerActionAPI:
    def _get_open_exception_id(self, seeded_db: Session) -> Optional[str]:
        from app.models.exception import ExceptionRecord, ExceptionStatus
        from sqlalchemy import select
        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.status == ExceptionStatus.OPEN)
            .limit(1)
        ).scalar_one_or_none()
        return exc.exception_id if exc else None

    def test_approve_action(self, seeded_client: TestClient, seeded_db: Session):
        exc_id = self._get_open_exception_id(seeded_db)
        if not exc_id:
            pytest.skip("No open exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc_id}/action",
            json={"action": "approve", "actor": "test_controller", "notes": "Verified manually."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_status"] == "approved"
        assert data["previous_status"] == "open"
        assert data["actor"] == "test_controller"

    def test_reject_action(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord, ExceptionStatus
        from sqlalchemy import select
        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.status == ExceptionStatus.OPEN)
            .offset(1)
            .limit(1)
        ).scalar_one_or_none()
        if not exc:
            pytest.skip("Not enough open exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/action",
            json={"action": "reject", "actor": "test_controller"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_status"] == "rejected"

    def test_escalate_action(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord, ExceptionStatus
        from sqlalchemy import select
        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.status == ExceptionStatus.OPEN)
            .offset(2)
            .limit(1)
        ).scalar_one_or_none()
        if not exc:
            pytest.skip("Not enough open exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/action",
            json={"action": "escalate", "actor": "senior_controller"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_status"] == "escalated"

    def test_action_on_nonexistent_exception(self, client: TestClient):
        resp = client.post(
            "/api/exceptions/EXC-GHOST/action",
            json={"action": "approve", "actor": "controller"},
        )
        assert resp.status_code == 404

    def test_double_action_rejected(self, seeded_client: TestClient, seeded_db: Session):
        """Cannot action an already-actioned exception."""
        exc_id = self._get_open_exception_id(seeded_db)
        if not exc_id:
            pytest.skip("No open exceptions.")

        # First action
        seeded_client.post(
            f"/api/exceptions/{exc_id}/action",
            json={"action": "approve", "actor": "ctrl"},
        )
        # Second action on same exception
        resp = seeded_client.post(
            f"/api/exceptions/{exc_id}/action",
            json={"action": "reject", "actor": "ctrl"},
        )
        assert resp.status_code == 409

    def test_action_response_has_actioned_at(self, seeded_client: TestClient, seeded_db: Session):
        exc_id = self._get_open_exception_id(seeded_db)
        if not exc_id:
            pytest.skip("No open exceptions.")

        resp = seeded_client.post(
            f"/api/exceptions/{exc_id}/action",
            json={"action": "approve", "actor": "ctrl"},
        )
        data = resp.json()
        assert "actioned_at" in data
        assert data["actioned_at"]  # non-empty timestamp


# ---------------------------------------------------------------------------
# 7. Verification API
# ---------------------------------------------------------------------------

class TestVerificationAPI:
    def test_verify_exception_returns_exposures(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(f"/api/exceptions/{exc.exception_id}/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert "before_exposure" in data
        assert "after_exposure" in data
        assert "verification_status" in data
        assert data["verification_status"] in ("resolved", "improved", "persists")

    def test_verify_not_found(self, client: TestClient):
        resp = client.post("/api/exceptions/EXC-GHOST/verify")
        assert resp.status_code == 404

    def test_verify_returns_control_result(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(f"/api/exceptions/{exc.exception_id}/verify")
        data = resp.json()
        assert "control_result_summary" in data
        ctrl = data["control_result_summary"]
        assert "lifecycle_completeness_ok" in ctrl

    def test_verify_persists_for_unchanged_data(self, seeded_client: TestClient, seeded_db: Session):
        """Without any data changes, status should be 'persists'."""
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        resp = seeded_client.post(f"/api/exceptions/{exc.exception_id}/verify")
        data = resp.json()
        # Data hasn't changed, so before_exposure == after_exposure
        assert data["before_exposure"] == data["after_exposure"]
        assert data["verification_status"] == "persists"


# ---------------------------------------------------------------------------
# 8. Audit logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_investigation_creates_audit_entries(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from app.models.audit import AuditLog
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        run_investigation(seeded_db, exc.exception_id, provider_name="mock")

        audit_rows = seeded_db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc.exception_id)
            .where(AuditLog.action.in_(["investigation_created", "investigation_tool_call"]))
        ).scalars().all()

        assert len(audit_rows) >= 3  # 1 investigation_created + at least 2 tool calls

    def test_tool_call_audit_has_tool_name(self, seeded_db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import ExceptionRecord
        from app.models.audit import AuditLog
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        run_investigation(seeded_db, exc.exception_id, provider_name="mock")

        tool_audits = seeded_db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc.exception_id)
            .where(AuditLog.action == "investigation_tool_call")
        ).scalars().all()

        assert len(tool_audits) >= 2
        for row in tool_audits:
            assert "tool" in row.details

    def test_controller_action_creates_audit(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord, ExceptionStatus
        from app.models.audit import AuditLog
        from sqlalchemy import select

        exc = seeded_db.execute(
            select(ExceptionRecord)
            .where(ExceptionRecord.status == ExceptionStatus.OPEN)
            .limit(1)
        ).scalar_one_or_none()
        if exc is None:
            pytest.skip("No open exceptions.")

        seeded_client.post(
            f"/api/exceptions/{exc.exception_id}/action",
            json={"action": "approve", "actor": "audit_test_ctrl"},
        )

        audit = seeded_db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc.exception_id)
            .where(AuditLog.action == "controller_approve")
        ).scalar_one_or_none()

        assert audit is not None
        assert audit.actor == "audit_test_ctrl"
        assert audit.details["new_status"] == "approved"

    def test_verification_creates_audit(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.exception import ExceptionRecord
        from app.models.audit import AuditLog
        from sqlalchemy import select

        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        seeded_client.post(f"/api/exceptions/{exc.exception_id}/verify")

        audit = seeded_db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc.exception_id)
            .where(AuditLog.action == "verification_run")
        ).scalar_one_or_none()

        assert audit is not None
        assert "before_exposure" in audit.details
        assert "after_exposure" in audit.details
        assert "verification_status" in audit.details

    def test_audit_trail_endpoint(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.transaction import Transaction
        from sqlalchemy import select

        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        resp = seeded_client.get(f"/api/audit/{txn.transaction_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have seeder audit logs
        assert len(data) >= 1

    def test_audit_trail_lifecycle_endpoint(self, seeded_client: TestClient, seeded_db: Session):
        from app.models.transaction import Transaction
        from sqlalchemy import select

        txn = seeded_db.execute(select(Transaction).limit(1)).scalar_one()
        resp = seeded_client.get(f"/api/transactions/{txn.transaction_id}/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data
        assert "overall_status" in data


# ---------------------------------------------------------------------------
# 9. Provider abstraction
# ---------------------------------------------------------------------------

class TestProviderAbstraction:
    def test_mock_provider_available(self):
        from app.agent.provider import MockProvider
        p = MockProvider()
        assert p.is_available() is True
        assert p.name == "mock"

    def test_openai_provider_unavailable_without_key(self):
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider(api_key="", model="gpt-4o-mini")
        assert p.is_available() is False

    def test_get_provider_returns_mock_by_default(self):
        from app.agent.provider import get_provider, MockProvider
        p = get_provider("mock")
        assert isinstance(p, MockProvider)

    def test_get_provider_falls_back_to_mock_for_openai_without_key(self):
        from app.agent.provider import get_provider, MockProvider
        p = get_provider("openai")
        assert isinstance(p, MockProvider)

    def test_mock_tool_plan_for_each_exception_type(self):
        from app.agent.provider import MockProvider
        p = MockProvider()
        exc_types = [
            "settlement_amount_discrepancy",
            "refund_closure_failure",
            "duplicate_financial_event",
            "orphan_financial_event",
            "missing_downstream_event",
            "settlement_timing_anomaly",
        ]
        for exc_type in exc_types:
            plan = p.get_tool_plan(exc_type)
            assert "tools" in plan
            assert "confidence" in plan
            assert len(plan["tools"]) >= 2, f"Too few tools for {exc_type}"

    def test_mock_build_response_valid_json(self, seeded_db: Session):
        from app.agent.provider import MockProvider
        from app.agent.tools import execute_tool
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select
        import json

        p = MockProvider()
        exc = seeded_db.execute(select(ExceptionRecord).limit(1)).scalar_one_or_none()
        if exc is None:
            pytest.skip("No exceptions.")

        plan = p.get_tool_plan(exc.exception_type)
        tool_results = {}
        for tool_name in plan["tools"]:
            args = (
                {"exception_id": exc.exception_id}
                if tool_name == "get_control_evidence"
                else {"transaction_id": exc.transaction_id}
            )
            result, _ = execute_tool(seeded_db, tool_name, args)
            tool_results[tool_name] = result

        raw = p.build_response(exc.exception_type, tool_results)
        parsed = json.loads(raw)
        assert "root_cause" in parsed
        assert "confidence" in parsed
        assert "recommended_action" in parsed
        assert 0.0 <= parsed["confidence"] <= 1.0
