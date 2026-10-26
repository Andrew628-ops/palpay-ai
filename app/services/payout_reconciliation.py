
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import SmartPayRule, PayoutRecord
from app.services.paypal import get_payout_details


def reconcile_payout(db: Session, payout: PayoutRecord):
    rule = db.get(SmartPayRule, payout.rule_id)

    if rule is None or not payout.paypal_batch_id:
        raise ValueError("Missing payment record")

    # Retrieve the existing payment from PayPal
    details = get_payout_details(payout.paypal_batch_id)

    header = details.get("batch_header") or {}
    sender = header.get("sender_batch_header") or {}
    items = details.get("items") or []

    # Verify batch identity
    if (
        header.get("payout_batch_id") != payout.paypal_batch_id
        or sender.get("sender_batch_id") != payout.sender_batch_id
    ):
        raise ValueError("PayPal batch mismatch")

    # Our demo supports exactly one recipient per payout
    if len(items) != 1:
        raise ValueError("Unexpected payout item count")

    item = items[0]
    payment = item.get("payout_item") or {}
    money = payment.get("amount") or {}

    try:
        amount = Decimal(str(money["value"]))
    except (KeyError, InvalidOperation, ValueError):
        raise ValueError("Invalid PayPal payout amount")

    # Verify recipient and payment details
    receiver = payment.get("receiver")

    if (
        item.get("payout_batch_id") != payout.paypal_batch_id
        or payment.get("sender_item_id")
            != payout.sender_batch_id[:63]
        or payment.get("recipient_type") != "EMAIL"
        or not isinstance(receiver, str)
        or receiver.casefold() != payout.receiver_email.casefold()
        or money.get("currency") != payout.currency
        or amount != payout.amount
    ):
        raise ValueError("PayPal payout details mismatch")

    batch_status = header.get("batch_status")
    item_status = item.get("transaction_status")

    if not isinstance(batch_status, str) or not isinstance(item_status, str):
        raise ValueError("Missing PayPal payout status")

    payout.paypal_batch_status = batch_status
    payout.paypal_item_status = item_status

    # Mark paid only when both statuses confirm success
    if batch_status == "SUCCESS" and item_status == "SUCCESS":
        payout.status = "PAYOUT_COMPLETED"
        rule.status = "PAID"

    # Do not commit here. The caller owns the transaction.
    return {
        "rule_id": rule.id,
        "status": rule.status,
        "payout_status": payout.status,
        "batch_status": batch_status,
        "item_status": item_status
    }
