"""
Pine Labs / Plural payment tools for budget pre-authorization and later capture.

Designed for agent workflows:
1. Pre-authorize a maximum approved budget.
2. Curate products asynchronously.
3. Capture the final amount after user confirmation.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency at runtime
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

try:
    from agents import function_tool
except ImportError:  # pragma: no cover - optional integration
    function_tool = None


class PineLabsError(RuntimeError):
    """Raised when Pine Labs configuration or API interactions fail."""


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_required(name: str) -> str:
    value = os.getenv(name)
    if value in (None, ""):
        raise PineLabsError(f"Required environment variable is missing: {name}")
    return value


def _env_optional_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise PineLabsError(f"Environment variable {name} must be an integer.") from exc


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise PineLabsError(f"Environment variable {name} must be numeric.") from exc


@dataclass(frozen=True)
class PineLabsCustomer:
    email: str
    first_name: str
    customer_id: str
    mobile_number: str

    @classmethod
    def from_env(cls) -> "PineLabsCustomer":
        return cls(
            email=_env_required("PLURAL_TEST_EMAIL"),
            first_name=_env_required("PLURAL_TEST_FIRST_NAME"),
            customer_id=_env_required("PLURAL_TEST_CUSTOMER_ID"),
            mobile_number=_env_required("PLURAL_TEST_MOBILE"),
        )


@dataclass(frozen=True)
class PineLabsSettings:
    client_id: str
    client_secret: str
    environment: str
    callback_url: str
    failure_callback_url: Optional[str]
    notes: str
    timeout_seconds: float
    poll_interval_seconds: float
    http_timeout_seconds: float
    default_budget_paisa: Optional[int]
    default_capture_paisa: Optional[int]
    merchant_metadata_flow: str

    @classmethod
    def from_env(cls) -> "PineLabsSettings":
        load_dotenv()
        environment = os.getenv("PLURAL_ENV", "uat").strip().lower()
        if environment not in {"uat", "prod"}:
            raise PineLabsError("PLURAL_ENV must be either 'uat' or 'prod'.")
        return cls(
            client_id=_env_required("PLURAL_CLIENT_ID"),
            client_secret=_env_required("PLURAL_CLIENT_SECRET"),
            environment=environment,
            callback_url=_env_required("PLURAL_CALLBACK_URL"),
            failure_callback_url=os.getenv("PLURAL_FAILURE_CALLBACK_URL") or None,
            notes=os.getenv("PLURAL_TEST_NOTES", "Agent shopping pre-auth"),
            timeout_seconds=_env_float("PLURAL_TEST_TIMEOUT_SECONDS", 300.0),
            poll_interval_seconds=_env_float("PLURAL_TEST_POLL_SECONDS", 5.0),
            http_timeout_seconds=_env_float("PLURAL_HTTP_TIMEOUT_SECONDS", 30.0),
            default_budget_paisa=_env_optional_int("PLURAL_TEST_AMOUNT_PAISA"),
            default_capture_paisa=_env_optional_int("PLURAL_TEST_CAPTURE_PAISA"),
            merchant_metadata_flow=os.getenv("PLURAL_TOOL_FLOW", "shopping-agent"),
        )

    @property
    def base_url(self) -> str:
        return (
            "https://pluraluat.v2.pinepg.in"
        )


class PineLabsClient:
    """Minimal production-oriented client for preauth and later capture."""

    AUTHORIZED_STATUS = "AUTHORIZED"
    TERMINAL_STATUSES = frozenset(
        {"CAPTURED", "PARTIALLY_CAPTURED", "CANCELLED", "FAILED", "DECLINED", "EXPIRED"}
    )

    def __init__(
        self,
        settings: Optional[PineLabsSettings] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or PineLabsSettings.from_env()
        self.session = session or requests.Session()
        self._access_token: Optional[str] = None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @staticmethod
    def _request_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _reference(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _headers(self, include_auth: bool = True) -> MutableMapping[str, str]:
        headers: MutableMapping[str, str] = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Request-ID": self._request_id(),
            "Request-Timestamp": self._timestamp(),
        }
        if include_auth:
            if not self._access_token:
                raise PineLabsError("Access token is missing. Call generate_token() first.")
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
        include_auth: bool = True,
    ) -> Dict[str, Any]:
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self._headers(include_auth=include_auth),
                json=json_body,
                timeout=self.settings.http_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise PineLabsError(f"{method} {url} failed before receiving a response: {exc}") from exc

        content_type = response.headers.get("Content-Type", "")
        try:
            payload: Dict[str, Any] = response.json() if "json" in content_type or response.text else {}
        except ValueError:
            payload = {"raw_text": response.text}

        if not response.ok:
            raise PineLabsError(
                f"{method} {url} failed with HTTP {response.status_code}: {payload}"
            )
        return payload

    def generate_token(self, *, force: bool = False) -> Dict[str, Any]:
        if self._access_token and not force:
            return {"access_token": self._access_token, "cached": True}

        payload = {
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "grant_type": "client_credentials",
        }
        data = self._request(
            "POST",
            f"{self.settings.base_url}/api/auth/v1/token",
            json_body=payload,
            include_auth=False,
        )
        token = data.get("access_token") or data.get("data", {}).get("access_token")
        if not token:
            raise PineLabsError(f"Token response did not include access_token: {data}")
        self._access_token = str(token)
        return data

    def create_preauth_order(
        self,
        *,
        amount_paisa: int,
        customer: PineLabsCustomer,
        merchant_order_reference: Optional[str] = None,
        notes: Optional[str] = None,
        merchant_metadata: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        self.generate_token()
        payload: Dict[str, Any] = {
            "merchant_order_reference": merchant_order_reference or self._reference("preauth"),
            "order_amount": {"value": amount_paisa, "currency": "INR"},
            "pre_auth": True,
            "allowed_payment_methods": ["CARD"],
            "callback_url": self.settings.callback_url,
            "purchase_details": {
                "customer": {
                    "email_id": customer.email,
                    "first_name": customer.first_name,
                    "customer_id": customer.customer_id,
                    "mobile_number": customer.mobile_number,
                },
                "merchant_metadata": {
                    "flow": self.settings.merchant_metadata_flow,
                },
            },
        }
        if notes or self.settings.notes:
            payload["notes"] = notes or self.settings.notes
        if self.settings.failure_callback_url:
            payload["failure_callback_url"] = self.settings.failure_callback_url
        if merchant_metadata:
            payload["purchase_details"]["merchant_metadata"].update(dict(merchant_metadata))

        return self._request(
            "POST",
            f"{self.settings.base_url}/api/checkout/v1/orders",
            json_body=payload,
        )

    def get_order(self, order_id: str) -> Dict[str, Any]:
        self.generate_token()
        return self._request("GET", f"{self.settings.base_url}/api/pay/v1/orders/{order_id}")

    def capture_order(
        self,
        *,
        order_id: str,
        capture_amount_paisa: int,
        merchant_capture_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.generate_token()
        payload = {
            "merchant_capture_reference": merchant_capture_reference or self._reference("cap"),
            "capture_amount": {"value": capture_amount_paisa, "currency": "INR"},
        }
        return self._request(
            "PUT",
            f"{self.settings.base_url}/api/pay/v1/orders/{order_id}/capture",
            json_body=payload,
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        self.generate_token()
        return self._request("PUT", f"{self.settings.base_url}/api/pay/v1/orders/{order_id}/cancel")

    @staticmethod
    def extract_order_data(response: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(response.get("data"), Mapping):
            return response["data"]  # type: ignore[index]
        return response

    @classmethod
    def extract_order_id(cls, response: Mapping[str, Any]) -> str:
        order_id = cls.extract_order_data(response).get("order_id")
        if not order_id:
            raise PineLabsError(f"order_id not found in response: {response}")
        return str(order_id)

    @classmethod
    def extract_status(cls, response: Mapping[str, Any]) -> Optional[str]:
        status = cls.extract_order_data(response).get("status")
        return str(status) if status is not None else None

    @classmethod
    def extract_redirect_url(cls, response: Mapping[str, Any]) -> Optional[str]:
        data = cls.extract_order_data(response)
        return data.get("redirect_url") or data.get("challenge_url")

    def wait_for_status(
        self,
        *,
        order_id: str,
        target_status: str,
        timeout_seconds: Optional[float] = None,
        poll_interval_seconds: Optional[float] = None,
        fail_on_terminal_status: bool = True,
    ) -> Dict[str, Any]:
        import logging
        _logger = logging.getLogger(__name__)

        timeout = timeout_seconds or self.settings.timeout_seconds
        interval = poll_interval_seconds or self.settings.poll_interval_seconds
        deadline = time.monotonic() + timeout
        last_response: Optional[Dict[str, Any]] = None
        poll_count = 0
        t_start = time.monotonic()

        while time.monotonic() < deadline:
            poll_count += 1
            last_response = self.get_order(order_id)
            current_status = self.extract_status(last_response)
            _logger.info("[perf] Pine Labs poll #%d — status=%s (%.1fs elapsed)", poll_count, current_status, time.monotonic() - t_start)
            if current_status == target_status:
                _logger.info("[perf] Pine Labs reached '%s' after %d polls in %.1fs", target_status, poll_count, time.monotonic() - t_start)
                return last_response
            if fail_on_terminal_status and current_status in self.TERMINAL_STATUSES:
                raise PineLabsError(
                    f"Order {order_id} reached terminal status {current_status} "
                    f"before target status {target_status}."
                )
            time.sleep(interval)

        raise PineLabsError(
            f"Timed out waiting for order {order_id} to reach status {target_status}. "
            f"Last response: {last_response}"
        )


def _resolve_budget(amount_paisa: Optional[int], settings: PineLabsSettings) -> int:
    if amount_paisa is not None:
        return amount_paisa
    if settings.default_budget_paisa is not None:
        return settings.default_budget_paisa
    raise PineLabsError("amount_paisa must be provided or PLURAL_TEST_AMOUNT_PAISA must be set.")


def _resolve_capture_amount(capture_amount_paisa: Optional[int], settings: PineLabsSettings) -> int:
    if capture_amount_paisa is not None:
        return capture_amount_paisa
    if settings.default_capture_paisa is not None:
        return settings.default_capture_paisa
    raise PineLabsError(
        "capture_amount_paisa must be provided or PLURAL_TEST_CAPTURE_PAISA must be set."
    )


def create_budget_preauth(
    budget_paisa: Optional[int] = None,
    *,
    merchant_order_reference: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a card pre-authorization for the approved shopping budget."""

    settings = PineLabsSettings.from_env()
    client = PineLabsClient(settings=settings)
    customer = PineLabsCustomer.from_env()
    amount_paisa = _resolve_budget(budget_paisa, settings)
    response = client.create_preauth_order(
        amount_paisa=amount_paisa,
        customer=customer,
        merchant_order_reference=merchant_order_reference,
        notes=notes,
        merchant_metadata=metadata,
    )
    return {
        "success": True,
        "environment": settings.environment,
        "order_id": client.extract_order_id(response),
        "status": client.extract_status(response),
        "redirect_url": client.extract_redirect_url(response),
        "budget_paisa": amount_paisa,
        "response": response,
    }


def get_preauth_status(
    order_id: str,
    *,
    wait_for_status: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    poll_interval_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch the current status of a preauth order, optionally polling to a target status."""

    settings = PineLabsSettings.from_env()
    client = PineLabsClient(settings=settings)
    if wait_for_status:
        response = client.wait_for_status(
            order_id=order_id,
            target_status=wait_for_status,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    else:
        response = client.get_order(order_id)
    return {
        "success": True,
        "order_id": order_id,
        "status": client.extract_status(response),
        "response": response,
    }


def capture_preauth(
    order_id: str,
    capture_amount_paisa: Optional[int] = None,
    *,
    merchant_capture_reference: Optional[str] = None,
    wait_for_authorized: bool = True,
    timeout_seconds: Optional[float] = None,
    poll_interval_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Capture an authorized preauth order for the final curated cart total."""

    settings = PineLabsSettings.from_env()
    client = PineLabsClient(settings=settings)
    final_capture_amount = _resolve_capture_amount(capture_amount_paisa, settings)

    if wait_for_authorized:
        client.wait_for_status(
            order_id=order_id,
            target_status=client.AUTHORIZED_STATUS,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    capture_response = client.capture_order(
        order_id=order_id,
        capture_amount_paisa=final_capture_amount,
        merchant_capture_reference=merchant_capture_reference,
    )
    latest_order = client.get_order(order_id)
    return {
        "success": True,
        "order_id": order_id,
        "captured_amount_paisa": final_capture_amount,
        "capture_status": client.extract_status(capture_response),
        "final_order_status": client.extract_status(latest_order),
        "capture_response": capture_response,
        "latest_order": latest_order,
    }


def cancel_preauth(order_id: str) -> Dict[str, Any]:
    """Cancel an authorized or pending preauth order."""

    settings = PineLabsSettings.from_env()
    client = PineLabsClient(settings=settings)
    response = client.cancel_order(order_id)
    latest_order = client.get_order(order_id)
    return {
        "success": True,
        "order_id": order_id,
        "cancel_status": client.extract_status(response),
        "final_order_status": client.extract_status(latest_order),
        "cancel_response": response,
        "latest_order": latest_order,
    }


def list_pinelabs_tool_functions() -> Dict[str, Any]:
    """Return a machine-readable description of the PineLabs payment tools."""

    settings = PineLabsSettings.from_env()
    return {
        "success": True,
        "environment": settings.environment,
        "tools": [
            {
                "name": "create_budget_preauth",
                "purpose": "Reserve the user-approved maximum budget on card before curation.",
            },
            {
                "name": "get_preauth_status",
                "purpose": "Fetch or poll the status of the preauth order.",
            },
            {
                "name": "capture_preauth",
                "purpose": "Capture the final curated total after user confirmation.",
            },
            {
                "name": "cancel_preauth",
                "purpose": "Cancel an unused preauth if the user rejects the curated cart.",
            },
        ],
        "polling_supported": True,
        "webhook_required": False,
    }


if function_tool is not None:  # pragma: no branch
    try:
        create_budget_preauth_tool = function_tool(create_budget_preauth)
        get_preauth_status_tool = function_tool(get_preauth_status)
        capture_preauth_tool = function_tool(capture_preauth)
        cancel_preauth_tool = function_tool(cancel_preauth)
        list_pinelabs_tool_functions_tool = function_tool(list_pinelabs_tool_functions)
    except Exception:  # pragma: no cover - optional integration compatibility
        create_budget_preauth_tool = None
        get_preauth_status_tool = None
        capture_preauth_tool = None
        cancel_preauth_tool = None
        list_pinelabs_tool_functions_tool = None
else:  # pragma: no cover - optional integration
    create_budget_preauth_tool = None
    get_preauth_status_tool = None
    capture_preauth_tool = None
    cancel_preauth_tool = None
    list_pinelabs_tool_functions_tool = None


def get_agents_sdk_tools() -> list[Any]:
    """Return OpenAI Agents SDK-compatible function tools."""

    tools = [
        create_budget_preauth_tool,
        get_preauth_status_tool,
        capture_preauth_tool,
        cancel_preauth_tool,
        list_pinelabs_tool_functions_tool,
    ]
    available_tools = [tool for tool in tools if tool is not None]
    if not available_tools:
        raise PineLabsError(
            "OpenAI Agents SDK is not installed. Install it with `pip install openai-agents`."
        )
    return available_tools


def tool_summary_json() -> str:
    """Serialize the PineLabs tool registry for logging or debugging."""

    return json.dumps(list_pinelabs_tool_functions(), indent=2, sort_keys=True)
