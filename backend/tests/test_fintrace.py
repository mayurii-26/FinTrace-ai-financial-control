"""Comprehensive pytest test suite for FinTrace backend.

Tests are organized into sections:
  1. Finance primitives (money, constants)
  2. Control engine
  3. Synthetic data generator (all 7 scenarios)
  4. Benchmark runner
  5. API endpoints (via TestClient)

All tests use an in-memory SQLite database. No external services required.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, future=True)


def _init_test_db() -> None:
    from app.core.database import Base
    from app.models import transaction, exception, audit  # noqa: F401
    Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    _init_test_db()
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    trans = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    from app.main import app
    from app.core.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Finance primitives
# ---------------------------------------------------------------------------

class TestMoneyHelpers:
    def test_to_decimal_from_int(self):
        from app.finance.money import to_decimal
        assert to_decimal(100) == Decimal("100.00")

    def test_to_decimal_from_string(self):
        from app.finance.money import to_decimal
        assert to_decimal("12.345") == Decimal("12.35")  # quantized

    def test_to_decimal_none(self):
        from app.finance.money import to_decimal
        assert to_decimal(None) == Decimal("0.00")

    def test_quantize_rounding(self):
        from app.finance.money import quantize
        assert quantize(Decimal("1.555")) == Decimal("1.56")
        assert quantize(Decimal("1.554")) == Decimal("1.55")

    def test_sum_decimals(self):
        from app.finance.money import sum_decimals
        assert sum_decimals([10, 20, Decimal("5.50")]) == Decimal("35.50")

    def test_abs_diff(self):
        from app.finance.money import abs_diff
        assert abs_diff(100, 97) == Decimal("3.00")
        assert abs_diff(97, 100) == Decimal("3.00")

    def test_within_tolerance(self):
        from app.finance.money import within_tolerance
        assert within_tolerance(100, 100)
        assert within_tolerance(100, 100.005)
        assert not within_tolerance(100, 101)


class TestConstants:
    def test_fee_rate(self):
        from app.finance.constants import DEFAULT_FEE_RATE
        assert DEFAULT_FEE_RATE == Decimal("0.02")

    def test_tax_rate(self):
        from app.finance.constants import DEFAULT_TAX_RATE
        assert DEFAULT_TAX_RATE == Decimal("0.18")

    def test_sla_values(self):
        from app.finance.constants import SETTLEMENT_SLA_DAYS, BANK_CREDIT_SLA_DAYS
        assert SETTLEMENT_SLA_DAYS == 3
        assert BANK_CREDIT_SLA_DAYS == 2


# ---------------------------------------------------------------------------
# 2. Control engine
# ---------------------------------------------------------------------------

def _make_bundle(
    payment_amount: Decimal = Decimal("1000.00"),
    order_amount: Decimal = Decimal("1000.00"),
    refund_amount: Decimal = Decimal("0.00"),
    settlement_amount: Decimal | None = None,
    settlement_days: int = 2,
    bank_days: int = 1,
    is_orphan_payment: bool = False,
    duplicate_payment: bool = False,
    missing_settlement: bool = False,
    missing_bank: bool = False,
):
    """Build a minimal in-memory LifecycleBundle for control engine tests."""
    from app.finance.constants import DEFAULT_FEE_RATE, DEFAULT_TAX_RATE
    from app.finance.money import quantize
    from app.finance.lifecycle_builder import LifecycleBundle
    from app.finance.lifecycle import TransactionLifecycle
    from app.models.transaction import (
        Transaction, Order, Payment, Refund, Settlement, BankEntry, TransactionStatus
    )

    net = payment_amount - refund_amount
    if net < Decimal("0.00"):
        net = Decimal("0.00")
    fee = quantize(net * DEFAULT_FEE_RATE)
    tax = quantize(fee * DEFAULT_TAX_RATE)
    expected = quantize(net - fee - tax)

    if settlement_amount is None:
        settlement_amount = expected

    now = datetime(2025, 3, 1, 10, 0, 0)
    pay_ts = now + timedelta(minutes=5)
    set_ts = pay_ts + timedelta(days=settlement_days)
    bank_ts = set_ts + timedelta(days=bank_days)

    txn = Transaction(
        transaction_id="TEST-0001",
        currency="INR",
        ground_truth_type="healthy",
        ground_truth_is_anomaly=False,
        status=TransactionStatus.PENDING,
    )
    txn.order = Order(
        order_id="ORD-TEST",
        transaction_id="TEST-0001",
        amount=order_amount,
        created_at=now,
    )
    payments = [
        Payment(
            payment_id="PAY-TEST-1",
            transaction_id="TEST-0001",
            amount=payment_amount,
            status="captured",
            payment_timestamp=pay_ts,
            is_orphan=is_orphan_payment,
        )
    ]
    if duplicate_payment:
        payments.append(
            Payment(
                payment_id="PAY-TEST-2",
                transaction_id="TEST-0001",
                amount=payment_amount,
                status="captured",
                payment_timestamp=pay_ts + timedelta(minutes=1),
                is_orphan=False,
            )
        )
    txn.payments = payments
    txn.refunds = []
    if refund_amount > Decimal("0.00"):
        txn.refunds = [
            Refund(
                refund_id="REF-TEST",
                transaction_id="TEST-0001",
                amount=refund_amount,
                status="processed",
                refund_timestamp=pay_ts + timedelta(hours=2),
            )
        ]
    txn.settlements = [] if missing_settlement else [
        Settlement(
            settlement_id="SET-TEST",
            transaction_id="TEST-0001",
            fee_amount=fee,
            tax_amount=tax,
            expected_settlement=expected,
            actual_settlement=settlement_amount,
            settlement_timestamp=set_ts,
            is_orphan=False,
        )
    ]
    txn.bank_entries = [] if missing_bank else [
        BankEntry(
            bank_entry_id="BANK-TEST",
            transaction_id="TEST-0001",
            amount=settlement_amount,
            bank_timestamp=bank_ts,
            is_orphan=False,
        )
    ]

    lc = TransactionLifecycle(
        transaction_id="TEST-0001",
        order_amount=order_amount,
        payment_amount=payment_amount,
        refund_amount=refund_amount,
        fee_amount=fee,
        tax_amount=tax,
        expected_settlement=expected,
        actual_settlement=settlement_amount,
        bank_credit=settlement_amount if not missing_bank else Decimal("0.00"),
        payment_timestamp=pay_ts,
        settlement_timestamp=set_ts if not missing_settlement else None,
        bank_timestamp=bank_ts if not missing_bank else None,
        has_order=True,
        has_payment=True,
        has_refund=refund_amount > Decimal("0.00"),
        has_settlement=not missing_settlement,
        has_bank_entry=not missing_bank,
    )
    return LifecycleBundle(
        transaction=txn,
        lifecycle=lc,
        payments=txn.payments,
        refunds=txn.refunds,
        settlements=txn.settlements,
        bank_entries=txn.bank_entries,
    )


class TestControlEngine:
    def test_healthy_transaction(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle()
        result = run_controls(bundle)
        assert result.is_fully_healthy()

    def test_amount_integrity_fail(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(payment_amount=Decimal("900.00"), order_amount=Decimal("1000.00"))
        result = run_controls(bundle)
        assert not result.amount_integrity_ok
        assert result.amount_integrity_diff == Decimal("100.00")

    def test_settlement_discrepancy(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(settlement_amount=Decimal("850.00"))
        result = run_controls(bundle)
        assert not result.settlement_consistency_ok
        assert result.settlement_consistency_diff > Decimal("0.00")

    def test_timing_anomaly_settlement(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(settlement_days=7)  # exceeds 3-day SLA
        result = run_controls(bundle)
        assert not result.settlement_timing_ok
        assert result.settlement_days_late == 7

    def test_duplicate_payment(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(duplicate_payment=True)
        result = run_controls(bundle)
        assert result.duplicate_detected

    def test_orphan_payment(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(is_orphan_payment=True)
        result = run_controls(bundle)
        assert result.orphan_detected

    def test_missing_settlement(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(missing_settlement=True, missing_bank=True)
        result = run_controls(bundle)
        assert not result.lifecycle_completeness_ok
        assert "settlement" in result.missing_stages

    def test_missing_bank_entry(self):
        from app.finance.control_engine import run_controls
        bundle = _make_bundle(missing_bank=True)
        result = run_controls(bundle)
        assert not result.lifecycle_completeness_ok
        assert "bank_entry" in result.missing_stages


class TestAnomalyClassifier:
    def test_classify_healthy(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle()
        result = run_controls(bundle)
        assert classify_exception(result) is None

    def test_classify_discrepancy(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle(settlement_amount=Decimal("800.00"))
        result = run_controls(bundle)
        assert classify_exception(result) == "settlement_amount_discrepancy"

    def test_classify_duplicate(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle(duplicate_payment=True)
        result = run_controls(bundle)
        assert classify_exception(result) == "duplicate_financial_event"

    def test_classify_orphan(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle(is_orphan_payment=True)
        result = run_controls(bundle)
        assert classify_exception(result) == "orphan_financial_event"

    def test_classify_timing(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle(settlement_days=10)
        result = run_controls(bundle)
        assert classify_exception(result) == "settlement_timing_anomaly"

    def test_classify_missing_downstream(self):
        from app.finance.control_engine import run_controls
        from app.anomaly.classifier import classify_exception
        bundle = _make_bundle(missing_settlement=True, missing_bank=True)
        result = run_controls(bundle)
        assert classify_exception(result) == "missing_downstream_event"


class TestSeverity:
    def test_critical_exposure(self):
        from app.anomaly.severity import classify_severity
        assert classify_severity("settlement_amount_discrepancy", Decimal("100000.00")) == "critical"

    def test_high_exposure(self):
        from app.anomaly.severity import classify_severity
        assert classify_severity("settlement_amount_discrepancy", Decimal("15000.00")) == "high"

    def test_medium_floor(self):
        from app.anomaly.severity import classify_severity
        # Low exposure but type has "medium" floor
        assert classify_severity("duplicate_financial_event", Decimal("1.00")) == "medium"

    def test_low_exposure(self):
        from app.anomaly.severity import classify_severity
        assert classify_severity("settlement_timing_anomaly", Decimal("10.00")) == "low"


# ---------------------------------------------------------------------------
# 3. Synthetic data generator - all 7 scenarios
# ---------------------------------------------------------------------------

class TestSyntheticGenerator:
    @pytest.fixture(scope="class")
    def all_lifecycles(self):
        from app.data.generator import generate_lifecycles
        # Generate enough to likely hit all 7 scenario types
        return generate_lifecycles(300, seed=42)

    def _get_by_type(self, lifecycles, gt_type):
        return [lc for lc in lifecycles if lc.ground_truth_type == gt_type]

    def test_generates_expected_count(self, all_lifecycles):
        assert len(all_lifecycles) == 300

    def test_healthy_scenario(self, all_lifecycles):
        healthy = self._get_by_type(all_lifecycles, "healthy")
        assert len(healthy) > 0
        for lc in healthy[:3]:
            assert len(lc.payments) == 1
            assert len(lc.settlements) == 1
            assert len(lc.bank_entries) == 1
            assert not lc.ground_truth_is_anomaly

    def test_settlement_discrepancy_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "settlement_amount_discrepancy")
        assert len(items) > 0
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            assert len(lc.settlements) == 1
            # actual settlement should differ from expected
            s = lc.settlements[0]
            assert s.amount != s.extra.get("expected")

    def test_refund_closure_failure_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "refund_closure_failure")
        assert len(items) > 0
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            assert len(lc.refunds) == 1
            assert len(lc.settlements) == 1

    def test_duplicate_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "duplicate_financial_event")
        assert len(items) > 0
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            assert len(lc.payments) == 2  # original + duplicate

    def test_orphan_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "orphan_financial_event")
        assert len(items) > 0
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            orphan_pays = [p for p in lc.payments if p.is_orphan]
            assert len(orphan_pays) == 1

    def test_timing_anomaly_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "settlement_timing_anomaly")
        assert len(items) > 0
        from app.finance.constants import SETTLEMENT_SLA_DAYS
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            pay_ts = lc.payments[0].timestamp
            set_ts = lc.settlements[0].timestamp
            days_diff = (set_ts - pay_ts).days
            assert days_diff > SETTLEMENT_SLA_DAYS

    def test_missing_downstream_scenario(self, all_lifecycles):
        items = self._get_by_type(all_lifecycles, "missing_downstream_event")
        assert len(items) > 0
        for lc in items[:3]:
            assert lc.ground_truth_is_anomaly
            assert len(lc.settlements) == 0
            assert len(lc.bank_entries) == 0

    def test_all_lifecycles_have_order_and_payment(self, all_lifecycles):
        for lc in all_lifecycles:
            assert lc.order is not None
            assert len(lc.payments) >= 1

    def test_ground_truth_weights_roughly_respected(self, all_lifecycles):
        from collections import Counter
        counts = Counter(lc.ground_truth_type for lc in all_lifecycles)
        # Healthy should be the majority
        assert counts["healthy"] > counts["settlement_amount_discrepancy"]
        assert counts["healthy"] > counts["duplicate_financial_event"]


# ---------------------------------------------------------------------------
# 4. Benchmark runner
# ---------------------------------------------------------------------------

class TestBenchmarkRunner:
    @pytest.fixture(scope="class")
    def seeded_db_session(self):
        """Create a fresh in-memory DB and seed it with 100 transactions."""
        from app.core.database import Base
        from app.models import transaction, exception, audit  # noqa
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            future=True,
        )
        Base.metadata.create_all(bind=engine)
        Sess = sessionmaker(bind=engine, future=True)
        s = Sess()
        from app.data.seeder import seed_database
        seed_database(s, count=100, seed=99, force=True)
        yield s
        s.close()

    def test_benchmark_returns_all_keys(self, seeded_db_session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(seeded_db_session)
        required = [
            "total_records", "healthy_count", "exception_count",
            "precision", "recall", "f1_score", "match_rate_pct",
            "throughput_records_per_sec", "duration_seconds",
            "total_financial_value", "total_financial_exposure",
            "per_type_stats",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_benchmark_total_records(self, seeded_db_session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(seeded_db_session)
        assert result["total_records"] == 100

    def test_benchmark_precision_recall_range(self, seeded_db_session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(seeded_db_session)
        assert 0.0 <= result["precision"] <= 1.0
        assert 0.0 <= result["recall"] <= 1.0
        assert 0.0 <= result["f1_score"] <= 1.0

    def test_benchmark_throughput_positive(self, seeded_db_session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(seeded_db_session)
        assert result["throughput_records_per_sec"] > 0

    def test_benchmark_counts_sum(self, seeded_db_session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(seeded_db_session)
        assert result["healthy_count"] + result["exception_count"] == result["total_records"]

    def test_empty_db_benchmark(self, db: Session):
        from app.benchmark.runner import run_benchmark
        result = run_benchmark(db)
        assert result["total_records"] == 0
        assert result["f1_score"] == 0.0


# ---------------------------------------------------------------------------
# 5. API endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "docs" in data


class TestDashboardEndpoint:
    def test_dashboard_empty(self, client: TestClient):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["total_transactions"] == 0
        assert data["healthy_count"] == 0
        assert "exception_rate_pct" in data
        assert "top_exception_types" in data


class TestExceptionsEndpoint:
    def test_list_exceptions_empty(self, client: TestClient):
        response = client.get("/api/exceptions")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_exception_not_found(self, client: TestClient):
        response = client.get("/api/exceptions/EXC-DOESNOTEXIST")
        assert response.status_code == 404


class TestReconciliationEndpoint:
    def test_reconciliation_no_pending(self, client: TestClient):
        response = client.post("/api/reconciliation", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0

    def test_reconciliation_with_seeded_data(self, client: TestClient, db: Session):
        # Seed a small batch
        from app.data.seeder import seed_database
        seed_database(db, count=30, seed=7, force=True)
        # Force rerun on all
        response = client.post("/api/reconciliation", json={"force_rerun": True})
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 30
        assert data["healthy"] + data["exceptions_raised"] == 30


class TestBenchmarkEndpoint:
    def test_benchmark_empty_db(self, client: TestClient):
        response = client.get("/api/benchmark")
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] == 0


class TestSeedEndpoint:
    def test_seed_endpoint(self, client: TestClient, db: Session):
        response = client.post("/api/seed", json={"count": 20, "seed": 1, "force": True})
        assert response.status_code == 200
        data = response.json()
        assert data["inserted"] == 20

    def test_seed_no_double_seed(self, client: TestClient, db: Session):
        # First seed
        client.post("/api/seed", json={"count": 10, "seed": 2, "force": True})
        # Second seed without force should be a no-op
        response = client.post("/api/seed", json={"count": 10, "seed": 2, "force": False})
        assert response.status_code == 200
        data = response.json()
        assert data["inserted"] == 0


class TestInvestigationEndpoint:
    def test_investigation_not_found(self, client: TestClient):
        response = client.post(
            "/api/investigation",
            json={"exception_id": "EXC-NOTEXIST", "provider": "mock"},
        )
        assert response.status_code == 404

    def test_investigation_mock_provider(self, client: TestClient, db: Session):
        # Seed and reconcile to create at least one exception
        from app.data.seeder import seed_database
        seed_database(db, count=50, seed=55, force=True)

        # Find an open exception
        from app.models.exception import ExceptionRecord
        from sqlalchemy import select
        exc = db.execute(
            select(ExceptionRecord).limit(1)
        ).scalar_one_or_none()

        if exc is None:
            pytest.skip("No exceptions created in this seed - adjust seed value.")

        response = client.post(
            "/api/investigation",
            json={"exception_id": exc.exception_id, "provider": "mock"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "investigation" in data
        assert "requires_human_review" in data
        assert "missing_evidence" in data
        assert data["investigation"]["agent_provider"] == "mock"
        assert data["investigation"]["confidence"] > 0.0


class TestTransactionLifecycleEndpoint:
    def test_lifecycle_not_found(self, client: TestClient):
        response = client.get("/api/transactions/TXN-NOTEXIST/lifecycle")
        assert response.status_code == 404

    def test_lifecycle_found(self, client: TestClient, db: Session):
        from app.data.seeder import seed_database
        seed_database(db, count=5, seed=33, force=True)

        from app.models.transaction import Transaction
        from sqlalchemy import select
        txn = db.execute(select(Transaction).limit(1)).scalar_one()

        response = client.get(f"/api/transactions/{txn.transaction_id}/lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == txn.transaction_id
        assert "order_amount" in data
        assert "has_order" in data
