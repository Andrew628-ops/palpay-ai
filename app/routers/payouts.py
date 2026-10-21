
import os
import secrets
import uuid
from decimal import Decimal

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SmartPayRule, PayoutRecord
from app.services.paypal import create_sandbox_payout

load_dotenv()

router = APIRouter()


@router.post(
    "/smartpay/{rule_id}/pay",
    status_code=202,
    responses={409: {"description": "Payout not permitted or already requested"}}
)
def pay_smartpay(
    rule_id: int,
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # 1. Verify authorization
    expected_token = os.getenv("APPROVAL_TOKEN")

    if not expected_token:
        raise HTTPException(503, "Approval token is not configured")

    if not x_approval_token or not secrets.compare_digest(
        x_approval_token, expected_token
    ):
        raise HTTPException(403, "Unauthorized")

    # 2. Enforce Sandbox only
    base_url = os.getenv(
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    ).rstrip("/")

    if base_url != "https://api-m.sandbox.paypal.com":
        raise HTTPException(503, "Sandbox payments only")

    receiver = os.getenv("PAYPAL_SANDBOX_RECEIVER_EMAIL")

    if not receiver:
        raise HTTPException(503, "Sandbox receiver is missing")

    # 3. Find and validate the rule
    smart_pay = db.get(SmartPayRule, rule_id)

    if smart_pay is None:
        raise HTTPException(404, "SmartPay rule not found")

    if smart_pay.status != "USER_APPROVED":
        raise HTTPException(409, "Rule is not approved for payout")

    amount = Decimal(str(smart_pay.amount))

    if smart_pay.currency != "USD":
        raise HTTPException(400, "Only USD is supported in this demo")

    if (
        not amount.is_finite()
        or amount <= 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise HTTPException(400, "Invalid payment amount")

    # 4. Generate a unique batch ID
    batch_id = f"palpay-{rule_id}-{uuid.uuid4().hex}"

    # 5. Reserve the payout BEFORE contacting PayPal
    try:
        statement = (
            update(SmartPayRule)
            .where(
                SmartPayRule.id == rule_id,
                SmartPayRule.status == "USER_APPROVED"
            )
            .values(status="PAYOUT_REQUESTED")
        )

        result = db.execute(statement)

        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Payout already requested")

        payout = PayoutRecord(
            rule_id=rule_id,
            sender_batch_id=batch_id,
            receiver_email=receiver,
            amount=amount,
            currency="USD",
            status="PAYOUT_REQUESTED"
        )

        db.add(payout)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Payout record already exists")

    # 6. Send Sandbox payout
    try:
        response = create_sandbox_payout(
            receiver_email=receiver,
            amount=float(amount),
            currency="USD",
            sender_batch_id=batch_id
        )

    except (httpx.HTTPError, ValueError, KeyError):
        # Outcome may be unknown. Never create a new payout ID.
        payout.status = "PAYOUT_UNKNOWN"
        smart_pay.status = "PAYOUT_UNKNOWN"
        db.commit()

        raise HTTPException(
            502,
            "Payout outcome unconfirmed. Reconcile before retrying."
        )

    # 7. Save PayPal's batch response
    header = response.get("batch_header") or {}

    paypal_batch_id = header.get("payout_batch_id")
    batch_status = header.get("batch_status")

    payout.paypal_batch_id = paypal_batch_id
    payout.paypal_batch_status = batch_status

    if not paypal_batch_id or not batch_status:
        payout.status = "PAYOUT_UNKNOWN"
        smart_pay.status = "PAYOUT_UNKNOWN"

    elif batch_status == "DENIED":
        payout.status = "PAYOUT_DENIED"
        smart_pay.status = "PAYOUT_DENIED"

    else:
        payout.status = "PAYOUT_SUBMITTED"
        smart_pay.status = "PAYOUT_SUBMITTED"

    db.commit()

    if not paypal_batch_id or not batch_status:
        raise HTTPException(
            502,
            "Incomplete PayPal response. Reconciliation required."
        )

    return {
        "rule_id": rule_id,
        "status": payout.status,
        "sender_batch_id": batch_id,
        "paypal_batch_id": paypal_batch_id,
        "paypal_batch_status": batch_status,
        "message": "Sandbox payout request recorded. Recipient payment not yet confirmed."
    }
