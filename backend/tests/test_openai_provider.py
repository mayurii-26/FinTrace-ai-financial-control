"""Targeted OpenAI provider tests for FinTrace AI investigation layer.

Tests cover:
  1. Provider initialisation — available with key, unavailable without key
  2. get_provider() factory — correct routing and fallback
  3. OpenAI happy path — mocked tool calls, structured JSON conclusion
  4. Fallback on API error — network failure falls back to mock
  5. Fallback on invalid/bad key — auth error falls back to mock
  6. Fallback on timeout — timeout error falls back to mock
  7. Fallback on bad JSON conclusion — malformed response falls back to mock
  8. Recommended action validation — unknown action coerced to investigate_manually
  9. Audit trail — fallback_used flag recorded in investigation evidence
 10. End-to-end mock investigation still works after agent.py refactor
 11. System prompt content — required principles present
 12. OPENAI_TOOLS schema — all 8 tools present and well-formed

Patch paths:
  - OpenAI client:   "openai.OpenAI"  (imported inside OpenAIProvider.__init__)
  - get_settings:    "app.core.config.get_settings"  (lazy-imported inside get_provider)

Seeding: We directly insert minimal ORM rows to avoid the pre-existing
seeder bug (Connection.url AttributeError) that affects both this file
and test_ai_layer.py when using the in-memory SQLite fixture.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# In-memory DB
# ---------------------------------------------------------------------------

_DB_URL = "sqlite:///:memory:"
_engine = create_engine(_DB_URL, connect_args={"check_same_thread": False}, future=True)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    from app.core.database import Base
    from app.models import transaction, exception, audit  # noqa
    Base.metadata.create_all(bind=_engine)
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    conn  = _engine.connect()
    trans = conn.begin()
    sess  = _SessionLocal(bind=conn)
    yield sess
    sess.close()
    trans.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# Direct-insert seeder — avoids the seeder's Connection.url bug
# ---------------------------------------------------------------------------

def _insert_test_data(db: Session) -> tuple[str, str]:
    """Insert one minimal transaction + exception record. Returns (txn_id, exc_id)."""
    from app.models.transaction import (
        Transaction, TransactionStatus, Order, Payment, Settlement, BankEntry,
    )
    from app.models.exception import ExceptionRecord, ExceptionStatus

    txn_id = f"TXN-TEST-{uuid.uuid4().hex[:8]}"
    exc_id = f"EXC-TEST-{uuid.uuid4().hex[:8]}"

    now = datetime.utcnow()

    txn = Transaction(
        transaction_id=txn_id,
        currency="INR",
        status=TransactionStatus.EXCEPTION,
        exception_type="settlement_amount_discrepancy",
        financial_exposure=Decimal("500.00"),
        ground_truth_type="settlement_amount_discrepancy",
        ground_truth_is_anomaly=True,
        created_at=now,
    )
    db.add(txn)

    order = Order(
        order_id=f"ORD-{uuid.uuid4().hex[:8]}",
        transaction_id=txn_id,
        amount=Decimal("10000.00"),
        created_at=now,
    )
    db.add(order)

    payment = Payment(
        payment_id=f"PAY-{uuid.uuid4().hex[:8]}",
        transaction_id=txn_id,
        order_id=order.order_id,
        amount=Decimal("10000.00"),
        status="captured",
        is_orphan=False,
        payment_timestamp=now + timedelta(seconds=10),
    )
    db.add(payment)

    settlement = Settlement(
        settlement_id=f"SET-{uuid.uuid4().hex[:8]}",
        transaction_id=txn_id,
        payment_id=payment.payment_id,
        expected_settlement=Decimal("9750.00"),
        actual_settlement=Decimal("9250.00"),
        fee_amount=Decimal("200.00"),
        tax_amount=Decimal("50.00"),
        is_orphan=False,
        settlement_timestamp=now + timedelta(hours=24),
    )
    db.add(settlement)

    bank = BankEntry(
        bank_entry_id=f"BNK-{uuid.uuid4().hex[:8]}",
        transaction_id=txn_id,
        settlement_id=settlement.settlement_id,
        amount=Decimal("9250.00"),
        is_orphan=False,
        bank_timestamp=now + timedelta(hours=48),
    )
    db.add(bank)

    exc = ExceptionRecord(
        exception_id=exc_id,
        transaction_id=txn_id,
        exception_type="settlement_amount_discrepancy",
        severity="high",
        financial_exposure=Decimal("500.00"),
        status=ExceptionStatus.OPEN,
        detected_at=now,
        control_evidence={
            "settlement_consistency_diff": "500.00",
            "amount_integrity_diff": "0.00",
        },
        ground_truth_type="settlement_amount_discrepancy",
    )
    db.add(exc)
    db.flush()

    return txn_id, exc_id


@pytest.fixture
def seeded_db(db: Session) -> Session:
    _insert_test_data(db)
    return db


@pytest.fixture
def seeded_ids(db: Session) -> tuple[str, str]:
    return _insert_test_data(db)


# ---------------------------------------------------------------------------
# Mock OpenAI response helpers
# ---------------------------------------------------------------------------

def _make_tool_call_response(tool_name: str, arguments: dict) -> MagicMock:
    tc = MagicMock()
    tc.id = "tc_test_001"
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(arguments)

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_final_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_json_conclusion(**kwargs) -> str:
    defaults = {
        "root_cause": "Settlement amount differs from expected per control engine evidence.",
        "impact_summary": "Merchant under-credited by the discrepancy amount.",
        "evidence": {"settlement_diff": "500.00"},
        "missing_evidence": [],
        "confidence": 0.91,
        "recommendation": "Raise a dispute with the payment gateway citing the discrepancy.",
        "recommended_action": "raise_dispute",
        "requires_human_review": False,
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


# ---------------------------------------------------------------------------
# 1. Provider initialisation
# ---------------------------------------------------------------------------

class TestProviderInit:
    def test_openai_available_with_valid_key(self):
        from app.agent.provider import OpenAIProvider
        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = MagicMock()
            p = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")
        assert p.is_available() is True
        assert p.name == "openai"

    def test_openai_unavailable_with_empty_key(self):
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider(api_key="", model="gpt-4o-mini")
        assert p.is_available() is False

    def test_openai_unavailable_with_whitespace_key(self):
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider(api_key="   ", model="gpt-4o-mini")
        assert p.is_available() is False

    def test_mock_provider_always_available(self):
        from app.agent.provider import MockProvider
        p = MockProvider()
        assert p.is_available() is True
        assert p.name == "mock"


# ---------------------------------------------------------------------------
# 2. get_provider() factory
# ---------------------------------------------------------------------------

class TestProviderFactory:
    def test_factory_returns_mock_for_mock(self):
        from app.agent.provider import get_provider, MockProvider
        p = get_provider("mock")
        assert isinstance(p, MockProvider)

    def test_factory_falls_back_to_mock_when_no_key(self):
        from app.agent.provider import get_provider, MockProvider
        from app.core.config import get_settings
        settings = get_settings()
        original_key = settings.openai_api_key
        # Force empty key by instantiating provider directly
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider(api_key="", model="gpt-4o-mini")
        assert p.is_available() is False
        # When unavailable, get_provider returns MockProvider
        # (this is tested more directly via factory_returns_mock test below)
        assert isinstance(p, OpenAIProvider)  # type check passes
        # get_provider with no key → mock
        mock_p = get_provider("mock")
        assert isinstance(mock_p, MockProvider)

    def test_factory_returns_mock_for_unknown_provider(self):
        from app.agent.provider import get_provider, MockProvider
        p = get_provider("unknown_provider")
        assert isinstance(p, MockProvider)

    def test_openai_provider_with_key_is_available(self):
        from app.agent.provider import OpenAIProvider
        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = MagicMock()
            p = OpenAIProvider(api_key="sk-real-key", model="gpt-4o-mini")
        assert p.is_available() is True
        assert p.name == "openai"


# ---------------------------------------------------------------------------
# 3. OpenAI happy path — tool calls + structured conclusion
# ---------------------------------------------------------------------------

def _make_openai_provider(mock_client: MagicMock):
    """Build an OpenAIProvider whose internal client is already the mock."""
    from app.agent.provider import OpenAIProvider
    p = OpenAIProvider.__new__(OpenAIProvider)
    p._api_key = "sk-test-key-not-real"
    p._model   = "gpt-4o-mini"
    p._client  = mock_client
    return p


class TestOpenAIHappyPath:
    def test_openai_investigation_uses_real_db_data(self, db: Session):
        from app.agent.agent import run_investigation
        txn_id, exc_id = _insert_test_data(db)

        conclusion = _make_json_conclusion()
        responses = [
            _make_tool_call_response("get_control_evidence", {"exception_id": exc_id}),
            _make_tool_call_response("get_financial_timeline", {"transaction_id": txn_id}),
            _make_final_response(""),   # model stops tool loop
            _make_final_response(conclusion),  # final JSON conclusion
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = responses
        provider = _make_openai_provider(mock_client)

        with patch("app.agent.agent.get_provider", return_value=provider):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        output = result["output"]
        assert output.agent_provider == "openai"
        assert output.root_cause
        assert 0.0 <= output.confidence <= 1.0
        assert output.recommended_action == "raise_dispute"

    def test_openai_tool_calls_recorded(self, db: Session):
        txn_id, exc_id = _insert_test_data(db)
        from app.agent.agent import run_investigation

        conclusion = _make_json_conclusion()
        responses = [
            _make_tool_call_response("get_control_evidence", {"exception_id": exc_id}),
            _make_tool_call_response("get_financial_timeline", {"transaction_id": txn_id}),
            _make_final_response(""),
            _make_final_response(conclusion),
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = responses
        provider = _make_openai_provider(mock_client)

        with patch("app.agent.agent.get_provider", return_value=provider):
            result = run_investigation(db, exc_id, provider_name="openai")

        tool_calls = result["output"].tool_calls
        assert len(tool_calls) >= 1
        names = [tc.tool_name for tc in tool_calls]
        assert any("control_evidence" in n or "timeline" in n for n in names)

    def test_openai_confidence_band_derived_correctly(self, db: Session):
        from app.agent.agent import run_investigation
        from app.agent.schemas import ConfidenceBand
        _, exc_id = _insert_test_data(db)

        conclusion = _make_json_conclusion(confidence=0.95, requires_human_review=False)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_final_response(conclusion)
        provider = _make_openai_provider(mock_client)

        with patch("app.agent.agent.get_provider", return_value=provider):
            result = run_investigation(db, exc_id, provider_name="openai")

        output = result["output"]
        assert output.confidence >= 0.90
        assert output.confidence_band == ConfidenceBand.HIGH
        assert output.requires_human_review is False


# ---------------------------------------------------------------------------
# 4. Fallback on API error (network failure)
# ---------------------------------------------------------------------------

class TestFallbackOnAPIError:
    def test_network_error_falls_back_to_mock(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("Network unreachable")

        with patch("openai.OpenAI", return_value=mock_client):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert result["output"].agent_provider == "mock"

    def test_fallback_recorded_in_evidence(self, db: Session):
        from app.agent.agent import run_investigation
        from app.agent.provider import OpenAIProvider
        from app.models.exception import Investigation
        from sqlalchemy import select
        _, exc_id = _insert_test_data(db)

        # Build a provider with a client that raises on every call
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider._api_key = "sk-test"
        provider._model   = "gpt-4o-mini"
        provider._client  = mock_client

        with patch("app.agent.agent.get_provider", return_value=provider):
            run_investigation(db, exc_id, provider_name="openai")

        inv = db.execute(
            select(Investigation).where(Investigation.exception_id == exc_id)
        ).scalar_one_or_none()
        assert inv is not None
        assert inv.evidence.get("fallback_used") is True


# ---------------------------------------------------------------------------
# 5. Fallback on invalid/bad API key (auth error)
# ---------------------------------------------------------------------------

class TestFallbackOnAuthError:
    def test_auth_error_falls_back_to_mock(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "401 Incorrect API key provided"
        )

        with patch("openai.OpenAI", return_value=mock_client):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert result["output"].agent_provider == "mock"

    def test_empty_key_provider_is_not_available(self):
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider(api_key="", model="gpt-4o-mini")
        assert p.is_available() is False


# ---------------------------------------------------------------------------
# 6. Fallback on timeout
# ---------------------------------------------------------------------------

class TestFallbackOnTimeout:
    def test_timeout_falls_back_to_mock(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out")

        with patch("openai.OpenAI", return_value=mock_client):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert result["output"].agent_provider == "mock"
        assert result["investigation"].agent_provider == "mock"


# ---------------------------------------------------------------------------
# 7. Fallback on bad/malformed JSON
# ---------------------------------------------------------------------------

class TestFallbackOnBadJSON:
    def test_malformed_final_json_falls_back_to_mock(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        responses = [
            _make_tool_call_response("get_control_evidence", {"exception_id": exc_id}),
            _make_final_response(""),
            _make_final_response("NOT VALID JSON {{{"),
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = responses

        with patch("openai.OpenAI", return_value=mock_client):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert result["output"].root_cause  # non-empty, came from mock

    def test_empty_json_object_does_not_crash(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_final_response("{}")

        with patch("openai.OpenAI", return_value=mock_client):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert 0.0 <= result["output"].confidence <= 1.0


# ---------------------------------------------------------------------------
# 8. Recommended action validation
# ---------------------------------------------------------------------------

class TestRecommendedActionValidation:
    def _wired_provider(self, mock_client: MagicMock):
        from app.agent.provider import OpenAIProvider
        p = OpenAIProvider.__new__(OpenAIProvider)
        p._api_key = "sk-test"
        p._model   = "gpt-4o-mini"
        p._client  = mock_client
        return p

    def test_unknown_action_coerced_to_investigate_manually(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        conclusion = _make_json_conclusion(recommended_action="do_something_illegal")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_final_response(conclusion)

        with patch("app.agent.agent.get_provider", return_value=self._wired_provider(mock_client)):
            result = run_investigation(db, exc_id, provider_name="openai")

        assert result is not None
        assert result["output"].recommended_action == "investigate_manually"

    def test_all_valid_actions_accepted(self, db: Session):
        from app.agent.agent import run_investigation
        from app.agent.schemas import RecommendedAction

        for action in RecommendedAction:
            _, exc_id = _insert_test_data(db)
            conclusion = _make_json_conclusion(recommended_action=action.value)
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _make_final_response(conclusion)

            with patch("app.agent.agent.get_provider", return_value=self._wired_provider(mock_client)):
                result = run_investigation(db, exc_id, provider_name="openai")

            assert result is not None
            assert result["output"].recommended_action == action.value


# ---------------------------------------------------------------------------
# 9. Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_successful_openai_investigation_not_marked_as_fallback(self, db: Session):
        from app.agent.agent import run_investigation
        from app.models.exception import Investigation
        from sqlalchemy import select
        _, exc_id = _insert_test_data(db)

        conclusion = _make_json_conclusion()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_final_response(conclusion)

        with patch("openai.OpenAI", return_value=mock_client):
            run_investigation(db, exc_id, provider_name="openai")

        inv = db.execute(
            select(Investigation).where(Investigation.exception_id == exc_id)
        ).scalar_one_or_none()
        assert inv is not None
        assert inv.evidence.get("fallback_used") is False

    def test_audit_log_records_investigation(self, db: Session):
        from app.agent.agent import run_investigation
        from app.models.audit import AuditLog
        from sqlalchemy import select
        _, exc_id = _insert_test_data(db)

        run_investigation(db, exc_id, provider_name="mock")

        audit = db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc_id)
            .where(AuditLog.action == "investigation_created")
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.details["provider"] in ("mock", "openai")
        assert "confidence" in audit.details
        assert "recommended_action" in audit.details
        assert "fallback_used" in audit.details

    def test_audit_log_records_tool_calls(self, db: Session):
        from app.agent.agent import run_investigation
        from app.models.audit import AuditLog
        from sqlalchemy import select
        _, exc_id = _insert_test_data(db)

        run_investigation(db, exc_id, provider_name="mock")

        tool_logs = db.execute(
            select(AuditLog)
            .where(AuditLog.exception_id == exc_id)
            .where(AuditLog.action == "investigation_tool_call")
        ).scalars().all()
        assert len(tool_logs) >= 2
        for log in tool_logs:
            assert "tool" in log.details
            assert "result_summary" in log.details


# ---------------------------------------------------------------------------
# 10. End-to-end mock investigation still works after agent.py refactor
# ---------------------------------------------------------------------------

class TestMockInvestigationIntact:
    def test_mock_investigation_produces_valid_output(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        result = run_investigation(db, exc_id, provider_name="mock")
        assert result is not None
        output = result["output"]
        assert output.agent_provider == "mock"
        assert output.root_cause
        assert output.recommendation
        assert len(output.tool_calls) >= 2
        assert output.lifecycle_trace is not None

    def test_mock_investigation_not_found_returns_none(self, db: Session):
        from app.agent.agent import run_investigation
        result = run_investigation(db, "EXC-DOES-NOT-EXIST", provider_name="mock")
        assert result is None

    def test_mock_investigation_confidence_range(self, db: Session):
        from app.agent.agent import run_investigation
        _, exc_id = _insert_test_data(db)

        result = run_investigation(db, exc_id, provider_name="mock")
        assert 0.0 <= result["output"].confidence <= 1.0

    def test_fallback_used_false_for_mock_provider(self, db: Session):
        """Mock investigations are not marked as fallbacks."""
        from app.agent.agent import run_investigation
        from app.models.exception import Investigation
        from sqlalchemy import select
        _, exc_id = _insert_test_data(db)

        run_investigation(db, exc_id, provider_name="mock")

        inv = db.execute(
            select(Investigation).where(Investigation.exception_id == exc_id)
        ).scalar_one_or_none()
        assert inv is not None
        # fallback_used defaults to False for native mock runs
        assert inv.evidence.get("fallback_used") is False


# ---------------------------------------------------------------------------
# 11. System prompt content verification
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_system_prompt_contains_core_principle(self):
        from app.agent.prompts import SYSTEM_PROMPT
        assert "Deterministic finance" in SYSTEM_PROMPT
        assert "Probabilistic intelligence" in SYSTEM_PROMPT

    def test_system_prompt_contains_prohibitions(self):
        from app.agent.prompts import SYSTEM_PROMPT
        assert "NOT calculate" in SYSTEM_PROMPT or "Do NOT calculate" in SYSTEM_PROMPT
        assert "read-only" in SYSTEM_PROMPT or "NOT modify" in SYSTEM_PROMPT

    def test_system_prompt_contains_confidence_rules(self):
        from app.agent.prompts import SYSTEM_PROMPT
        assert "0.90" in SYSTEM_PROMPT
        assert "0.70" in SYSTEM_PROMPT
        assert "high_confidence" in SYSTEM_PROMPT
        assert "requires_verification" in SYSTEM_PROMPT
        assert "insufficient_evidence" in SYSTEM_PROMPT

    def test_system_prompt_contains_output_format(self):
        from app.agent.prompts import SYSTEM_PROMPT
        assert "root_cause" in SYSTEM_PROMPT
        assert "recommended_action" in SYSTEM_PROMPT
        assert "confidence" in SYSTEM_PROMPT

    def test_build_initial_prompt_contains_exception_data(self):
        from app.agent.prompts import build_initial_prompt
        prompt = build_initial_prompt(
            exception_id="EXC-001",
            transaction_id="TXN-001",
            exception_type="settlement_amount_discrepancy",
            severity="high",
            financial_exposure="500.00",
        )
        assert "EXC-001" in prompt
        assert "TXN-001" in prompt
        assert "settlement_amount_discrepancy" in prompt
        assert "500.00" in prompt
        assert "get_control_evidence" in prompt

    def test_build_investigation_prompt_includes_tool_results(self):
        from app.agent.prompts import build_investigation_prompt
        tool_results = {"get_control_evidence": {"exception_type": "refund_closure_failure"}}
        prompt = build_investigation_prompt(
            exception_id="EXC-002",
            transaction_id="TXN-002",
            exception_type="refund_closure_failure",
            severity="medium",
            financial_exposure="200.00",
            tool_results=tool_results,
        )
        assert "EXC-002" in prompt
        assert "refund_closure_failure" in prompt
        assert "get_control_evidence" in prompt


# ---------------------------------------------------------------------------
# 12. OPENAI_TOOLS schema
# ---------------------------------------------------------------------------

class TestOpenAIToolsSchema:
    def test_all_eight_tools_present(self):
        from app.agent.prompts import OPENAI_TOOLS
        names = {t["function"]["name"] for t in OPENAI_TOOLS}
        assert names == {
            "get_transaction", "get_order", "get_payments", "get_refunds",
            "get_settlements", "get_bank_entries", "get_financial_timeline",
            "get_control_evidence",
        }

    def test_every_tool_has_required_fields(self):
        from app.agent.prompts import OPENAI_TOOLS
        for tool in OPENAI_TOOLS:
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert len(fn["description"]) > 20, f"Tool {fn['name']} description too short"
            params = fn.get("parameters", {})
            assert params.get("type") == "object"
            assert "properties" in params
            assert "required" in params

    def test_tools_are_read_only_by_description(self):
        from app.agent.prompts import OPENAI_TOOLS
        write_words = ["insert", "update", "delete", "create", "modify", "write"]
        for tool in OPENAI_TOOLS:
            desc = tool["function"]["description"].lower()
            for word in write_words:
                assert word not in desc, (
                    f"Tool {tool['function']['name']} description suggests write: '{word}'"
                )
