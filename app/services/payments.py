import hashlib
import hmac

import requests
from flask import current_app

PAYSTACK_BASE = "https://api.paystack.co"


class PaymentError(Exception):
    pass


def _headers():
    key = current_app.config["PAYSTACK_SECRET_KEY"]
    if not key:
        raise PaymentError("Paystack is not configured (set PAYSTACK_SECRET_KEY).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def initialize_transaction(order, email, callback_url):
    """Returns the Paystack authorization_url to redirect the customer to."""
    payload = {
        "email": email,
        "amount": order.total_minor,  # subunits (pesewas/kobo)
        "currency": order.currency,
        "reference": order.reference,
        "callback_url": callback_url,
    }
    try:
        r = requests.post(f"{PAYSTACK_BASE}/transaction/initialize", json=payload, headers=_headers(), timeout=20)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaymentError("Could not reach the payment provider. Please try again.") from exc
    if not r.ok or not data.get("status"):
        raise PaymentError(data.get("message", "Payment initialization failed."))
    return data["data"]["authorization_url"]


def verify_transaction(reference):
    """Ask Paystack directly whether a reference was paid. Returns Paystack's `data` dict."""
    try:
        r = requests.get(f"{PAYSTACK_BASE}/transaction/verify/{reference}", headers=_headers(), timeout=20)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaymentError("Could not verify payment right now.") from exc
    if not r.ok or not data.get("status"):
        raise PaymentError(data.get("message", "Verification failed."))
    return data["data"]


def valid_webhook_signature(raw_body: bytes, signature: str) -> bool:
    key = current_app.config["PAYSTACK_SECRET_KEY"]
    if not key or not signature:
        return False
    expected = hmac.new(key.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
