
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.models import PayPalWebhookEvent
from app.services.paypal import (
    PAYPAL_BASE_URL,
    get_paypal_access_token
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter()


def verify_paypal_webhook(event, headers, webhook_id):
    access_token = get_paypal_access_token()

    payload = {
        "auth_algo": headers["paypal-auth-algo"],
        "cert_url": headers["paypal-cert-url"],
        "transmission_id": headers["paypal-transmission-id"],
        "transmission_sig": headers["paypal-transmission-sig"],
        "transmission_time": headers["paypal-transmission-time"],
        "webhook_id": webhook_id,
        "webhook_event": event
    }

    response = httpx.post(
        f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=20.0
    )

    response.raise_for_status()

    return (
        response.json().get("verification_status")
        == "SUCCESS"
    )


@router.post("/paypal")
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    # 1. Check webhook configuration
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")

    if not webhook_id:
        raise HTTPException(503, "Webhook ID not configured")

    if PAYPAL_BASE_URL.rstrip("/") != "https://api-m.sandbox.paypal.com":
        raise HTTPException(503, "Sandbox only")

    # 2. Read the incoming event
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid JSON")

    if not isinstance(event, dict):
        raise HTTPException(400, "Invalid webhook event")

    # 3. Check required PayPal headers
    required_headers = [
        "paypal-auth-algo",
        "paypal-cert-url",
        "paypal-transmission-id",
        "paypal-transmission-sig",
        "paypal-transmission-time"
    ]

    headers = {
        name: request.headers.get(name)
        for name in required_headers
    }

    if not all(headers.values()):
        raise HTTPException(400, "Missing PayPal signature headers")

    # 4. Verify the signature with PayPal
    try:
        verified = await run_in_threadpool(
            verify_paypal_webhook,
            event,
            headers,
            webhook_id
        )
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(
            503,
            "PayPal signature verification unavailable"
        )

    if not verified:
        raise HTTPException(401, "Invalid PayPal signature")

    # 5. Validate event identifiers
    event_id = event.get("id")
    event_type = event.get("event_type")

    if not isinstance(event_id, str) or not event_id:
        raise HTTPException(400, "Missing event ID")

    if not isinstance(event_type, str) or not event_type:
        raise HTTPException(400, "Missing event type")

    # 6. Save verified event to database
    try:
        db.add(
            PayPalWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload_json=json.dumps(event),
                status="RECEIVED"
            )
        )
        db.commit()

    except IntegrityError:
        db.rollback()
        return {
            "received": True,
            "duplicate": True
        }

    return {
        "received": True,
        "verified": True,
        "event_id": event_id,
        "event_type": event_type,
        "status": "RECEIVED"
    }
