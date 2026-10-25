
import os
import secrets
import uuid
from decimal import Decimal, InvalidOperation

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import update, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SmartPayRule, PayoutRecord
from app.services.paypal import create_sandbox_payout, get_payout_details

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



@router.post("/smartpay/{rule_id}/payment-status/refresh")
def refresh_payment_status(
    rule_id: int,
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # 1. Verify the requester
    verify_approval_token(x_approval_token)

    # 2. Find the SmartPay rule
    smart_pay = db.get(SmartPayRule, rule_id)


    if smart_pay is None:
        raise HTTPException(404, "SmartPay rule not found")

    # 3. Find its existing payout
    payout = db.scalar(
        select(PayoutRecord).where(
            PayoutRecord.rule_id == rule_id
        )
    )

    if payout is None:
        raise HTTPException(404, "Payout record not found")

    if not payout.paypal_batch_id:
        raise HTTPException(
            409,
            "PayPal batch ID unavailable. Manual reconciliation required."
        )

    # 4. Check the existing payout with PayPal
    try:
        details = get_payout_details(payout.paypal_batch_id)
    except httpx.HTTPError:
        raise HTTPException(
            502,
            "Unable to retrieve PayPal payout status"
        )

    if not isinstance(details, dict):
        raise HTTPException(502, "Invalid PayPal response")

    header = details.get("batch_header")

    if not isinstance(header, dict):
        raise HTTPException(502, "Missing PayPal batch header")

    sender = header.get("sender_batch_header")

    # 5. Verify this is the correct payout
    if (
        not isinstance(sender, dict)
        or header.get("payout_batch_id") != payout.paypal_batch_id
        or sender.get("sender_batch_id") != payout.sender_batch_id
    ):
        raise HTTPException(
            502,
            "PayPal payout identifiers do not match"
        )

    batch_status = header.get("batch_status")

    if not isinstance(batch_status, str):
        raise HTTPException(502, "Missing batch status")

    # 6. Handle denied/cancelled batches
    if batch_status in {"DENIED", "CANCELED"}:
        new_status = f"PAYOUT_{batch_status}"
        item_status = None

    else:
        items = details.get("items")

        # Our demo creates exactly one payout item
        if not isinstance(items, list) or len(items) != 1:
            raise HTTPException(
                502,
                "Expected exactly one PayPal payout item"
            )

        item = items[0]

        if not isinstance(item, dict):
            raise HTTPException(502, "Invalid payout item")

        payout_item = item.get("payout_item")

        if not isinstance(payout_item, dict):
            raise HTTPException(502, "Missing payout item details")

        money = payout_item.get("amount")

        if not isinstance(money, dict):
            raise HTTPException(502, "Missing payout amount")

        try:
            amount_matches = (
                Decimal(str(money.get("value"))) == payout.amount
            )
        except (InvalidOperation, TypeError, ValueError):
            amount_matches = False

        receiver = payout_item.get("receiver")

        # 7. Validate recipient, amount and identifiers
        if (
            item.get("payout_batch_id") != payout.paypal_batch_id
            or payout_item.get("sender_item_id")
                != payout.sender_batch_id[:63]
            or not isinstance(receiver, str)
            or receiver.casefold() != payout.receiver_email.casefold()
            or payout_item.get("recipient_type") != "EMAIL"
            or money.get("currency") != payout.currency
            or not amount_matches
        ):
            raise HTTPException(
                502,
                "PayPal payout details do not match our record"
            )

        item_status = item.get("transaction_status")

        # 8. Interpret the individual payout result
        if item_status == "SUCCESS" and batch_status == "SUCCESS":
            new_status = "PAID"

        elif item_status in {
            "FAILED", "BLOCKED", "RETURNED",
            "REFUNDED", "REVERSED"
        }:
            new_status = f"PAYOUT_{item_status}"

        elif item_status == "UNCLAIMED":
            new_status = "PAYOUT_UNCLAIMED"

        elif item_status == "ONHOLD":
            new_status = "PAYOUT_ON_HOLD"

        elif item_status in {"PENDING", "SUCCESS"}:
            new_status = "PAYOUT_SUBMITTED"

        else:
            raise HTTPException(
                502,
                "Unrecognized PayPal item status"
            )

    # Avoid downgrading a confirmed payment due to stale data
    if smart_pay.status == "PAID" and new_status == "PAYOUT_SUBMITTED":
        new_status = "PAID"

    # 9. Save the verified PayPal statuses
    payout.paypal_batch_status = batch_status
    payout.paypal_item_status = item_status

    payout.status = (
        "PAYOUT_COMPLETED" if new_status == "PAID"
        else new_status
    )

    smart_pay.status = new_status

    db.commit()

    # 10. Return the updated status
    return {
        "rule_id": rule_id,
        "status": smart_pay.status,
        "paypal_batch_id": payout.paypal_batch_id,
        "paypal_batch_status": batch_status,
        "paypal_item_status": item_status,
        "message": "Existing payout status refreshed"
    }


@router.get("/smartpay/{rule_id}/payment-status")
def get_payment_status(
    rule_id: int,
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    verify_approval_token(x_approval_token)

    smart_pay = db.get(SmartPayRule, rule_id)

    if smart_pay is None:
        raise HTTPException(404, "SmartPay rule not found")

    payout = db.scalar(
        select(PayoutRecord).where(
            PayoutRecord.rule_id == rule_id
        )
    )

    if payout is None:
        raise HTTPException(404, "Payout record not found")

    return {
        "rule_id": rule_id,
        "status": smart_pay.status,
        "payout_status": payout.status,
        "paypal_batch_id": payout.paypal_batch_id,
        "paypal_batch_status": payout.paypal_batch_status,
        "paypal_item_status": payout.paypal_item_status
    }


def verify_approval_token(token: str | None):
    expected_token = os.getenv("APPROVAL_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="Approval token is not configured"
        )

    if not token or not secrets.compare_digest(
        token, expected_token
    ):
        raise HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

