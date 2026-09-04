"""Synthetic transaction lifecycle generator.

Generates N end-to-end financial lifecycles (order -> payment -> refund ->
fee/tax -> settlement -> bank credit) as plain Python objects (not ORM
rows yet - see ``app.data.seeder`` for persistence). Every lifecycle is
stamped with a ground-truth label drawn from
``app.data.ground_truth.GroundTruthType`` and, for anomaly scenarios, is
deliberately mutated to inject exactly the control break that label
implies. All monetary math uses ``Decimal``.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from faker import Faker

from app.data.ground_truth import GROUND_TRUTH_WEIGHTS, GroundTruthType
from app.finance.constants import DEFAULT_FEE_RATE, DEFAULT_TAX_RATE
from app.finance.money import quantize, to_decimal

BASE_DATE = datetime(2025, 1, 1, 9, 0, 0)

# ---------------------------------------------------------------------------
# Realistic data pools (module-level constants)
# ---------------------------------------------------------------------------

MERCHANTS: list[tuple[str, str]] = [
    ("MER-AMZN001", "Amazon India"),
    ("MER-FLIP001", "Flipkart"),
    ("MER-SWGY001", "Swiggy"),
    ("MER-ZOMY001", "Zomato"),
    ("MER-OLAC001", "OLACabs"),
    ("MER-NYKAA01", "Nykaa"),
    ("MER-MNTR001", "Myntra"),
    ("MER-MESO001", "MakeMyTrip"),
    ("MER-GPAY001", "Google Play"),
    ("MER-PHRM001", "PharmEasy"),
    ("MER-BKMY001", "BookMyShow"),
    ("MER-URBN001", "Urban Company"),
    ("MER-JUSK001", "JuSke"),
    ("MER-TATA001", "Tata CLiQ"),
    ("MER-AJIO001", "AJIO"),
    ("MER-BOAT001", "boAt Store"),
    ("MER-LENS001", "Lenskart"),
    ("MER-CULT001", "Cult.fit"),
    ("MER-BYJU001", "BYJU'S"),
    ("MER-CRED001", "CRED"),
]

_PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet"]
_PAYMENT_WEIGHTS = [42, 28, 18, 12]

_UPI_SUFFIXES = ["okicici", "oksbi", "okhdfcbank", "axl", "ybl", "paytm", "ibl"]
_CARD_BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YES", "IDFC"]
_WALLET_PROVIDERS = ["Paytm", "PhonePe", "Amazon Pay", "MobiKwik", "Freecharge"]


# ---------------------------------------------------------------------------
# Helper: build payment method detail
# ---------------------------------------------------------------------------

def _payment_detail(method: str, rng: random.Random, customer_first: str) -> str:
    """Return a realistic payment method detail string."""
    if method == "upi":
        # e.g. priya@okicici
        handle = customer_first.lower().replace(" ", "")
        suffix = rng.choice(_UPI_SUFFIXES)
        return f"{handle}@{suffix}"
    elif method == "card":
        bank = rng.choice(_CARD_BANKS)
        digits = f"{rng.randint(1000, 9999)}"
        return f"{bank}****{digits}"
    elif method == "netbanking":
        bank = rng.choice(_CARD_BANKS)
        return f"{bank} NetBanking"
    else:  # wallet
        return rng.choice(_WALLET_PROVIDERS)


def _bank_reference(order_ts: datetime, rng: random.Random, seq: int) -> str:
    """Return a NEFT-style bank reference string."""
    date_str = order_ts.strftime("%Y%m%d")
    seq_str = f"{seq:06d}"
    return f"NEFT{date_str}{seq_str}"


# ---------------------------------------------------------------------------
# Dataclasses (fields added; existing fields untouched)
# ---------------------------------------------------------------------------

@dataclass
class SyntheticEvent:
    kind: str  # order/payment/refund/settlement/bank_entry
    id: str
    amount: Decimal
    timestamp: datetime
    extra: dict = field(default_factory=dict)
    is_orphan: bool = False
    reference_id: str = ""  # bank reference / gateway ref for each event


@dataclass
class SyntheticLifecycle:
    transaction_id: str
    ground_truth_type: str
    ground_truth_is_anomaly: bool
    order: SyntheticEvent
    payments: List[SyntheticEvent]
    refunds: List[SyntheticEvent]
    settlements: List[SyntheticEvent]
    bank_entries: List[SyntheticEvent]
    # --- NEW enrichment fields ---
    merchant_id: str = ""
    merchant_name: str = ""
    customer_id: str = ""
    customer_name: str = ""
    payment_method: str = ""
    payment_method_detail: str = ""
    bank_reference: str = ""


def _weighted_choice(rng: random.Random) -> GroundTruthType:
    types = list(GROUND_TRUTH_WEIGHTS.keys())
    weights = list(GROUND_TRUTH_WEIGHTS.values())
    return rng.choices(types, weights=weights, k=1)[0]


def _compute_settlement(amount: Decimal, refund: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Return (fee, tax, expected_settlement) for a clean, healthy flow."""
    net_base = amount - refund
    if net_base < Decimal("0.00"):
        net_base = Decimal("0.00")
    fee = quantize(net_base * DEFAULT_FEE_RATE)
    tax = quantize(fee * DEFAULT_TAX_RATE)
    settlement = quantize(net_base - fee - tax)
    return fee, tax, settlement


def _random_amount(rng: random.Random) -> Decimal:
    # Realistic e-commerce order sizes: INR 100 - 75,000.
    cents = rng.randint(10000, 7500000)
    return quantize(Decimal(cents) / Decimal(100))


def generate_lifecycles(count: int, seed: int = 42) -> List[SyntheticLifecycle]:
    """Generate ``count`` synthetic transaction lifecycles."""
    rng = random.Random(seed)
    Faker.seed(seed)
    fake = Faker("en_IN")

    lifecycles: List[SyntheticLifecycle] = []

    for i in range(count):
        txn_id = f"TXN-{i + 1:06d}"
        gt_type = _weighted_choice(rng)
        order_amount = _random_amount(rng)

        day_offset = rng.randint(0, 300)
        order_ts = BASE_DATE + timedelta(days=day_offset, minutes=rng.randint(0, 1440))

        lifecycle = _build_scenario(txn_id, gt_type, order_amount, order_ts, rng, fake)

        # ------------------------------------------------------------------
        # Enrich lifecycle with merchant / customer / payment / bank-ref data
        # ------------------------------------------------------------------

        # Merchant
        merchant_id, merchant_name = rng.choice(MERCHANTS)

        # Customer
        customer_name = fake.name()
        customer_id = "CUST-" + uuid.uuid4().hex[:6].upper()

        # Payment method
        payment_method = rng.choices(_PAYMENT_METHODS, weights=_PAYMENT_WEIGHTS, k=1)[0]
        first_name = customer_name.split()[0]
        payment_method_detail = _payment_detail(payment_method, rng, first_name)

        # Bank reference (sequence number based on loop index, 1-based)
        bank_reference = _bank_reference(order_ts, rng, i + 1)

        # Assign enrichment fields to the lifecycle
        lifecycle.merchant_id = merchant_id
        lifecycle.merchant_name = merchant_name
        lifecycle.customer_id = customer_id
        lifecycle.customer_name = customer_name
        lifecycle.payment_method = payment_method
        lifecycle.payment_method_detail = payment_method_detail
        lifecycle.bank_reference = bank_reference

        # ------------------------------------------------------------------
        # Assign reference_id to every event in this lifecycle
        # ------------------------------------------------------------------
        lifecycle.order.reference_id = f"ORD-REF-{uuid.uuid4().hex[:5].upper()}"
        for ev in lifecycle.payments:
            ev.reference_id = f"PAY-REF-{uuid.uuid4().hex[:5].upper()}"
        for ev in lifecycle.refunds:
            ev.reference_id = f"REF-REF-{uuid.uuid4().hex[:5].upper()}"
        for ev in lifecycle.settlements:
            ev.reference_id = f"SET-REF-{uuid.uuid4().hex[:5].upper()}"
        for ev in lifecycle.bank_entries:
            ev.reference_id = f"BANK-REF-{uuid.uuid4().hex[:5].upper()}"

        lifecycles.append(lifecycle)

    return lifecycles


def _build_scenario(
    txn_id: str,
    gt_type: GroundTruthType,
    order_amount: Decimal,
    order_ts: datetime,
    rng: random.Random,
    fake: Faker,
) -> SyntheticLifecycle:
    """Construct one lifecycle, deliberately injecting the control break
    implied by ``gt_type``. Every branch below is fully deterministic
    given the rng seed - no randomness leaks into the ground-truth label
    itself, only into amounts/timings/ids."""

    order = SyntheticEvent(kind="order", id=f"ORD-{uuid.uuid4().hex[:10].upper()}", amount=order_amount, timestamp=order_ts)

    payment_ts = order_ts + timedelta(minutes=rng.randint(1, 30))
    payment_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"
    payments = [SyntheticEvent(kind="payment", id=payment_id, amount=order_amount, timestamp=payment_ts)]

    refunds: List[SyntheticEvent] = []
    settlements: List[SyntheticEvent] = []
    bank_entries: List[SyntheticEvent] = []

    refund_amount = Decimal("0.00")

    if gt_type == GroundTruthType.HEALTHY:
        # 20% of healthy transactions include a legitimate, fully-honoured
        # partial refund to keep the refund-consistency check meaningful.
        if rng.random() < 0.2:
            refund_amount = quantize(order_amount * Decimal(str(rng.uniform(0.1, 0.5))))
            refunds.append(
                SyntheticEvent(
                    kind="refund",
                    id=f"REF-{uuid.uuid4().hex[:10].upper()}",
                    amount=refund_amount,
                    timestamp=payment_ts + timedelta(hours=rng.randint(1, 48)),
                )
            )
        fee, tax, settlement_amount = _compute_settlement(order_amount, refund_amount)
        settlement_ts = payment_ts + timedelta(days=rng.randint(1, 2), hours=rng.randint(0, 12))
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=settlement_amount,
                timestamp=settlement_ts,
                extra={"fee": fee, "tax": tax, "expected": settlement_amount},
            )
        )
        bank_ts = settlement_ts + timedelta(days=rng.randint(0, 1), hours=rng.randint(0, 8))
        bank_entries.append(
            SyntheticEvent(
                kind="bank_entry",
                id=f"BANK-{uuid.uuid4().hex[:10].upper()}",
                amount=settlement_amount,
                timestamp=bank_ts,
            )
        )

    elif gt_type == GroundTruthType.SETTLEMENT_AMOUNT_DISCREPANCY:
        fee, tax, expected_settlement = _compute_settlement(order_amount, refund_amount)
        # Inject a material discrepancy: settlement short-pays the merchant.
        discrepancy = quantize(order_amount * Decimal(str(rng.uniform(0.03, 0.15))))
        actual_settlement = quantize(expected_settlement - discrepancy)
        settlement_ts = payment_ts + timedelta(days=rng.randint(1, 2))
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=actual_settlement,
                timestamp=settlement_ts,
                extra={"fee": fee, "tax": tax, "expected": expected_settlement},
            )
        )
        bank_ts = settlement_ts + timedelta(days=1)
        bank_entries.append(
            SyntheticEvent(kind="bank_entry", id=f"BANK-{uuid.uuid4().hex[:10].upper()}", amount=actual_settlement, timestamp=bank_ts)
        )

    elif gt_type == GroundTruthType.REFUND_CLOSURE_FAILURE:
        refund_amount = quantize(order_amount * Decimal(str(rng.uniform(0.2, 0.6))))
        refunds.append(
            SyntheticEvent(
                kind="refund",
                id=f"REF-{uuid.uuid4().hex[:10].upper()}",
                amount=refund_amount,
                timestamp=payment_ts + timedelta(hours=rng.randint(1, 24)),
            )
        )
        fee, tax, expected_settlement = _compute_settlement(order_amount, refund_amount)
        # Settlement was computed on the GROSS amount, ignoring the refund
        # entirely - the classic "refund closure failure".
        gross_fee, gross_tax, gross_settlement = _compute_settlement(order_amount, Decimal("0.00"))
        settlement_ts = payment_ts + timedelta(days=rng.randint(1, 2))
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=gross_settlement,
                timestamp=settlement_ts,
                extra={"fee": gross_fee, "tax": gross_tax, "expected": expected_settlement},
            )
        )
        bank_ts = settlement_ts + timedelta(days=1)
        bank_entries.append(
            SyntheticEvent(kind="bank_entry", id=f"BANK-{uuid.uuid4().hex[:10].upper()}", amount=gross_settlement, timestamp=bank_ts)
        )

    elif gt_type == GroundTruthType.DUPLICATE_FINANCIAL_EVENT:
        # Primary (legitimate) payment + settlement + bank entry.
        fee, tax, settlement_amount = _compute_settlement(order_amount, Decimal("0.00"))
        settlement_ts = payment_ts + timedelta(days=rng.randint(1, 2))
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=settlement_amount,
                timestamp=settlement_ts,
                extra={"fee": fee, "tax": tax, "expected": settlement_amount},
            )
        )
        bank_ts = settlement_ts + timedelta(days=1)
        bank_entries.append(
            SyntheticEvent(kind="bank_entry", id=f"BANK-{uuid.uuid4().hex[:10].upper()}", amount=settlement_amount, timestamp=bank_ts)
        )
        # Inject a duplicate payment (same amount, slightly later timestamp).
        dup_pay_ts = payment_ts + timedelta(minutes=rng.randint(1, 10))
        payments.append(
            SyntheticEvent(
                kind="payment",
                id=f"PAY-{uuid.uuid4().hex[:10].upper()}",
                amount=order_amount,
                timestamp=dup_pay_ts,
                is_orphan=False,
            )
        )

    elif gt_type == GroundTruthType.ORPHAN_FINANCIAL_EVENT:
        # Complete legitimate lifecycle…
        fee, tax, settlement_amount = _compute_settlement(order_amount, Decimal("0.00"))
        settlement_ts = payment_ts + timedelta(days=rng.randint(1, 2))
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=settlement_amount,
                timestamp=settlement_ts,
                extra={"fee": fee, "tax": tax, "expected": settlement_amount},
            )
        )
        bank_ts = settlement_ts + timedelta(days=1)
        bank_entries.append(
            SyntheticEvent(kind="bank_entry", id=f"BANK-{uuid.uuid4().hex[:10].upper()}", amount=settlement_amount, timestamp=bank_ts)
        )
        # …plus one orphan payment that has no matching order/settlement.
        orphan_amount = quantize(order_amount * Decimal(str(rng.uniform(0.5, 1.5))))
        orphan_pay_ts = payment_ts + timedelta(hours=rng.randint(2, 72))
        payments.append(
            SyntheticEvent(
                kind="payment",
                id=f"PAY-{uuid.uuid4().hex[:10].upper()}",
                amount=orphan_amount,
                timestamp=orphan_pay_ts,
                is_orphan=True,
            )
        )

    elif gt_type == GroundTruthType.SETTLEMENT_TIMING_ANOMALY:
        fee, tax, settlement_amount = _compute_settlement(order_amount, Decimal("0.00"))
        # SLA breach: settlement arrives well past SETTLEMENT_SLA_DAYS (3).
        settlement_delay_days = rng.randint(5, 14)
        settlement_ts = payment_ts + timedelta(days=settlement_delay_days)
        settlements.append(
            SyntheticEvent(
                kind="settlement",
                id=f"SET-{uuid.uuid4().hex[:10].upper()}",
                amount=settlement_amount,
                timestamp=settlement_ts,
                extra={"fee": fee, "tax": tax, "expected": settlement_amount},
            )
        )
        # Bank credit also arrives late (but within its own SLA relative to settlement).
        bank_ts = settlement_ts + timedelta(days=rng.randint(0, 1))
        bank_entries.append(
            SyntheticEvent(kind="bank_entry", id=f"BANK-{uuid.uuid4().hex[:10].upper()}", amount=settlement_amount, timestamp=bank_ts)
        )

    elif gt_type == GroundTruthType.MISSING_DOWNSTREAM_EVENT:
        # Payment captured but neither settlement nor bank credit ever arrived.
        # The order and payment are present; settlement + bank_entry are absent
        # so the lifecycle-completeness check fires "missing_downstream_event".
        pass  # settlements and bank_entries remain empty lists

    return SyntheticLifecycle(
        transaction_id=txn_id,
        ground_truth_type=gt_type.value,
        ground_truth_is_anomaly=(gt_type != GroundTruthType.HEALTHY),
        order=order,
        payments=payments,
        refunds=refunds,
        settlements=settlements,
        bank_entries=bank_entries,
    )
