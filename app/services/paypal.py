
import os
import httpx
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

PAYPAL_BASE_URL = os.getenv(
    "PAYPAL_BASE_URL",
    "https://api-m.sandbox.paypal.com"
)


def get_paypal_access_token():
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("PayPal credentials are missing")

    response = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=15.0
    )

    response.raise_for_status()

    return response.json()["access_token"]



def create_sandbox_payout(receiver_email: str, amount: float, currency: str, sender_batch_id: str):
    if PAYPAL_BASE_URL.rstrip("/") != "https://api-m.sandbox.paypal.com":
        raise ValueError("Sandbox payouts only")

    if currency != "USD":
        raise ValueError("Demo payouts support USD only")

    money = Decimal(str(amount))

    if money <= 0 or money != money.quantize(Decimal("0.01")):
        raise ValueError("Amount must be a positive USD amount")

    if not receiver_email or not sender_batch_id:
        raise ValueError("Recipient and batch ID are required")

    access_token = get_paypal_access_token()

    payload = {
        "sender_batch_header": {
            "sender_batch_id": sender_batch_id,
            "email_subject": "PalPay AI Sandbox Payment"
        },
        "items": [
            {
                "recipient_type": "EMAIL",
                "amount": {
                    "value": f"{money:.2f}",
                    "currency": currency
                },
                "receiver": receiver_email,
                "sender_item_id": sender_batch_id[:63]
            }
        ]
    }

    response = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/payments/payouts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30.0
    )

    try:
        response.raise_for_status()

    except httpx.HTTPStatusError as error:
        print("\n--- PAYPAL SANDBOX PAYOUT ERROR ---")
        print("HTTP Status:", error.response.status_code)

        try:
            details = error.response.json()
        except ValueError:
            details = {}

        if not isinstance(details, dict):
            details = {}

        print("Error Name:", details.get("name", "Unknown"))
        print("Debug ID:", details.get("debug_id", "Unavailable"))

        issues = details.get("details", [])
        if isinstance(issues, list):
            for item in issues:
                if isinstance(item, dict):
                    print("Issue:", item.get("issue", "Unknown"))

        print("---------------------------------\n")
        raise

    return response.json()


def get_payout_details(paypal_batch_id: str):
    access_token = get_paypal_access_token()

    response = httpx.get(
        f"{PAYPAL_BASE_URL}/v1/payments/payouts/{paypal_batch_id}",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=30.0
    )

    response.raise_for_status()

    return response.json()
