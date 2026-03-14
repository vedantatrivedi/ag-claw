from __future__ import annotations

from typing import Any, Dict, List, Tuple
from unittest import mock

import requests

from shopping_agent.app.tools.pinelabs import (
    PineLabsClient,
    PineLabsCustomer,
    PineLabsSettings,
    capture_preauth,
    create_budget_preauth,
    get_preauth_status,
    list_pinelabs_tool_functions,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"Content-Type": "application/json"}
        self.text = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Dict[str, Any]:
        return self._payload


class FakeSession(requests.Session):
    def __init__(self, scripted: List[Tuple[str, str, Dict[str, Any]]]) -> None:
        super().__init__()
        self.scripted = scripted

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:  # type: ignore[override]
        expected_method, expected_url, payload = self.scripted.pop(0)
        assert method == expected_method
        assert url == expected_url
        return FakeResponse(200, payload)


def test_create_budget_preauth_returns_redirect_url() -> None:
    settings = PineLabsSettings(
        client_id="id",
        client_secret="secret",
        environment="uat",
        callback_url="https://example.com/callback",
        failure_callback_url=None,
        notes="Agent shopping pre-auth",
        timeout_seconds=300.0,
        poll_interval_seconds=5.0,
        http_timeout_seconds=30.0,
        default_budget_paisa=10000,
        default_capture_paisa=6000,
        merchant_metadata_flow="shopping-agent",
    )
    session = FakeSession(
        [
            (
                "POST",
                "https://pluraluat.v2.pinepg.in/api/auth/v1/token",
                {"access_token": "token-123"},
            ),
            (
                "POST",
                "https://pluraluat.v2.pinepg.in/api/checkout/v1/orders",
                {
                    "data": {
                        "order_id": "ord_123",
                        "redirect_url": "https://checkout.example.com/ord_123",
                        "status": "CREATED",
                    }
                },
            ),
        ]
    )

    with mock.patch(
        "shopping_agent.app.tools.pinelabs.PineLabsSettings.from_env",
        return_value=settings,
    ), mock.patch(
        "shopping_agent.app.tools.pinelabs.PineLabsCustomer.from_env",
        return_value=PineLabsCustomer(
            email="test@example.com",
            first_name="Test",
            customer_id="cust-1",
            mobile_number="9876543210",
        ),
    ), mock.patch(
        "shopping_agent.app.tools.pinelabs.requests.Session",
        return_value=session,
    ):
        result = create_budget_preauth()

    assert result["order_id"] == "ord_123"
    assert result["redirect_url"] == "https://checkout.example.com/ord_123"


def test_capture_preauth_waits_for_authorized_and_returns_final_status() -> None:
    settings = PineLabsSettings(
        client_id="id",
        client_secret="secret",
        environment="uat",
        callback_url="https://example.com/callback",
        failure_callback_url=None,
        notes="Agent shopping pre-auth",
        timeout_seconds=300.0,
        poll_interval_seconds=0.0,
        http_timeout_seconds=30.0,
        default_budget_paisa=10000,
        default_capture_paisa=6000,
        merchant_metadata_flow="shopping-agent",
    )
    session = FakeSession(
        [
            (
                "POST",
                "https://pluraluat.v2.pinepg.in/api/auth/v1/token",
                {"access_token": "token-123"},
            ),
            (
                "GET",
                "https://pluraluat.v2.pinepg.in/api/pay/v1/orders/ord_123",
                {"data": {"order_id": "ord_123", "status": "AUTHORIZED"}},
            ),
            (
                "PUT",
                "https://pluraluat.v2.pinepg.in/api/pay/v1/orders/ord_123/capture",
                {"data": {"order_id": "ord_123", "status": "PARTIALLY_CAPTURED"}},
            ),
            (
                "GET",
                "https://pluraluat.v2.pinepg.in/api/pay/v1/orders/ord_123",
                {"data": {"order_id": "ord_123", "status": "PARTIALLY_CAPTURED"}},
            ),
        ]
    )

    with mock.patch(
        "shopping_agent.app.tools.pinelabs.PineLabsSettings.from_env",
        return_value=settings,
    ), mock.patch(
        "shopping_agent.app.tools.pinelabs.requests.Session",
        return_value=session,
    ):
        result = capture_preauth("ord_123")

    assert result["final_order_status"] == "PARTIALLY_CAPTURED"
    assert result["captured_amount_paisa"] == 6000


def test_get_preauth_status_can_poll_for_authorized() -> None:
    settings = PineLabsSettings(
        client_id="id",
        client_secret="secret",
        environment="uat",
        callback_url="https://example.com/callback",
        failure_callback_url=None,
        notes="Agent shopping pre-auth",
        timeout_seconds=300.0,
        poll_interval_seconds=0.0,
        http_timeout_seconds=30.0,
        default_budget_paisa=10000,
        default_capture_paisa=6000,
        merchant_metadata_flow="shopping-agent",
    )
    session = FakeSession(
        [
            (
                "POST",
                "https://pluraluat.v2.pinepg.in/api/auth/v1/token",
                {"access_token": "token-123"},
            ),
            (
                "GET",
                "https://pluraluat.v2.pinepg.in/api/pay/v1/orders/ord_123",
                {"data": {"order_id": "ord_123", "status": "PENDING"}},
            ),
            (
                "GET",
                "https://pluraluat.v2.pinepg.in/api/pay/v1/orders/ord_123",
                {"data": {"order_id": "ord_123", "status": "AUTHORIZED"}},
            ),
        ]
    )

    with mock.patch(
        "shopping_agent.app.tools.pinelabs.PineLabsSettings.from_env",
        return_value=settings,
    ), mock.patch(
        "shopping_agent.app.tools.pinelabs.requests.Session",
        return_value=session,
    ):
        result = get_preauth_status("ord_123", wait_for_status="AUTHORIZED")

    assert result["status"] == "AUTHORIZED"


def test_list_pinelabs_tool_functions_reports_polling_support() -> None:
    settings = PineLabsSettings(
        client_id="id",
        client_secret="secret",
        environment="uat",
        callback_url="https://example.com/callback",
        failure_callback_url=None,
        notes="Agent shopping pre-auth",
        timeout_seconds=300.0,
        poll_interval_seconds=5.0,
        http_timeout_seconds=30.0,
        default_budget_paisa=10000,
        default_capture_paisa=6000,
        merchant_metadata_flow="shopping-agent",
    )

    with mock.patch(
        "shopping_agent.app.tools.pinelabs.PineLabsSettings.from_env",
        return_value=settings,
    ):
        result = list_pinelabs_tool_functions()

    assert result["polling_supported"] is True
    assert result["webhook_required"] is False
