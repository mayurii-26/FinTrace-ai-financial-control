"""Razorpay integration layer for FinTrace.

This module wraps the Razorpay Python SDK for controlled demo/integration
purposes only. All operations use Test Mode credentials loaded from
environment variables. Real-money write operations (captures, refunds
against live accounts) require explicit opt-in via ``allow_writes=True``
and are disabled by default to prevent accidental charges during demos.

Usage:
    client = get_razorpay_client()
    order = client.fetch_order("order_XXXXXXXX")
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RazorpayClientError(Exception):
    """Raised when the Razorpay API returns an error or is misconfigured."""


class RazorpayClient:
    """Thin wrapper around the razorpay SDK, restricted to read and
    test-mode-safe write operations."""

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        mode: str = "test",
        allow_writes: bool = False,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._mode = mode
        self._allow_writes = allow_writes
        self._client: Any = None

        if not key_id or not key_secret:
            logger.warning(
                "Razorpay credentials not configured. "
                "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env. "
                "All Razorpay API calls will raise RazorpayClientError."
            )
        else:
            self._init_sdk()

    def _init_sdk(self) -> None:
        try:
            import razorpay  # type: ignore[import]
            self._client = razorpay.Client(auth=(self._key_id, self._key_secret))
            logger.info("Razorpay SDK initialised (mode=%s).", self._mode)
        except ImportError:
            logger.error(
                "razorpay package not installed. "
                "Run: pip install razorpay"
            )
            self._client = None

    def _require_client(self) -> Any:
        if self._client is None:
            raise RazorpayClientError(
                "Razorpay client not initialised. "
                "Check that RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set "
                "and the 'razorpay' package is installed."
            )
        return self._client

    def _require_writes(self) -> None:
        if not self._allow_writes:
            raise RazorpayClientError(
                "Write operations are disabled. "
                "Instantiate RazorpayClient with allow_writes=True "
                "only in environments where test-mode writes are safe."
            )

    # ------------------------------------------------------------------
    # Read-only operations (always permitted)
    # ------------------------------------------------------------------

    def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch a single order from Razorpay."""
        client = self._require_client()
        try:
            return dict(client.order.fetch(order_id))
        except Exception as exc:
            raise RazorpayClientError(f"fetch_order failed: {exc}") from exc

    def fetch_payments_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        """Return all payments for a given order."""
        client = self._require_client()
        try:
            result = client.order.payments(order_id)
            items = result.get("items", result) if isinstance(result, dict) else result
            return [dict(p) for p in items]
        except Exception as exc:
            raise RazorpayClientError(f"fetch_payments_for_order failed: {exc}") from exc

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """Fetch a single payment by ID."""
        client = self._require_client()
        try:
            return dict(client.payment.fetch(payment_id))
        except Exception as exc:
            raise RazorpayClientError(f"fetch_payment failed: {exc}") from exc

    def fetch_refunds_for_payment(self, payment_id: str) -> List[Dict[str, Any]]:
        """Return all refunds for a given payment."""
        client = self._require_client()
        try:
            result = client.payment.refunds(payment_id)
            items = result.get("items", result) if isinstance(result, dict) else result
            return [dict(r) for r in items]
        except Exception as exc:
            raise RazorpayClientError(f"fetch_refunds_for_payment failed: {exc}") from exc

    def fetch_settlement(self, settlement_id: str) -> Dict[str, Any]:
        """Fetch a settlement record by ID."""
        client = self._require_client()
        try:
            return dict(client.settlement.fetch(settlement_id))
        except Exception as exc:
            raise RazorpayClientError(f"fetch_settlement failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Test-mode write operations (require allow_writes=True)
    # ------------------------------------------------------------------

    def create_test_order(
        self,
        amount_paise: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a test order. Only available in test mode with allow_writes=True."""
        if self._mode != "test":
            raise RazorpayClientError("create_test_order is only available in test mode.")
        self._require_writes()
        client = self._require_client()
        payload: Dict[str, Any] = {
            "amount": amount_paise,
            "currency": currency,
        }
        if receipt:
            payload["receipt"] = receipt
        if notes:
            payload["notes"] = notes
        try:
            return dict(client.order.create(data=payload))
        except Exception as exc:
            raise RazorpayClientError(f"create_test_order failed: {exc}") from exc

    def create_test_refund(
        self,
        payment_id: str,
        amount_paise: int,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Issue a test-mode refund. Only available in test mode with allow_writes=True."""
        if self._mode != "test":
            raise RazorpayClientError("create_test_refund is only available in test mode.")
        self._require_writes()
        client = self._require_client()
        payload: Dict[str, Any] = {"amount": amount_paise}
        if notes:
            payload["notes"] = notes
        try:
            return dict(client.payment.refund(payment_id, payload))
        except Exception as exc:
            raise RazorpayClientError(f"create_test_refund failed: {exc}") from exc

    def verify_webhook_signature(
        self,
        body: str,
        signature: str,
        webhook_secret: str,
    ) -> bool:
        """Verify a Razorpay webhook signature using HMAC-SHA256."""
        client = self._require_client()
        try:
            client.utility.verify_webhook_signature(body, signature, webhook_secret)
            return True
        except Exception:
            return False


@lru_cache(maxsize=1)
def get_razorpay_client() -> RazorpayClient:
    """Return the cached, configured RazorpayClient instance.
    Write operations are disabled by default (safe for demo use).
    """
    return RazorpayClient(
        key_id=settings.razorpay_key_id,
        key_secret=settings.razorpay_key_secret,
        mode=settings.razorpay_mode,
        allow_writes=False,  # explicitly disabled for safety
    )
