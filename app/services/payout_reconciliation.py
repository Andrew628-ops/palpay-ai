
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

    
    # Preserve the previous states before making changes.
    previous_rule_status = rule.status
    previous_payout_status = payout.status

    reversal_statuses = {
        "PAYOUT_REFUNDED",
        "PAYOUT_RETURNED",
        "PAYOUT_REVERSED",
    }

    # A confirmed reversal cannot be overwritten
    # by an outdated successful-payment response.
    if batch_status == "SUCCESS" and item_status == "SUCCESS":
        if (
            previous_rule_status in reversal_statuses
            or previous_payout_status in reversal_statuses
        ):
            raise ValueError(
                "Cannot overwrite a recorded payment reversal"
            )

        payout.status = "PAYOUT_COMPLETED"
        rule.status = "PAID"

    elif item_status == "REFUNDED":
        payout.status = "PAYOUT_REFUNDED"
        rule.status = "PAYOUT_REFUNDED"

    elif item_status == "RETURNED":
        payout.status = "PAYOUT_RETURNED"
        rule.status = "PAYOUT_RETURNED"

    elif item_status == "FAILED":
        protected_statuses = {
            "PAID",
            "PAYOUT_COMPLETED",
            *reversal_statuses,
        }

        if (
            previous_rule_status in protected_statuses
            or previous_payout_status in protected_statuses
        ):
            raise ValueError(
                "Unexpected failed status for a confirmed payment"
            )

        payout.status = "PAYOUT_FAILED"
        rule.status = "PAYOUT_FAILED"

    elif item_status in {
        "PENDING",
        "UNCLAIMED",
        "ONHOLD",
        "SUCCESS",
    }:
        # Intermediate status: do not overwrite
        # an already confirmed or reversed payment.
        pass

    else:
        raise ValueError(
            f"Unsupported PayPal item status: {item_status}"
        )

    # Save verified PayPal details after validation.
    payout.paypal_batch_status = batch_status
    payout.paypal_item_status = item_status

    return {
        "rule_id": rule.id,
        "status": rule.status,
        "payout_status": payout.status,
        "batch_status": batch_status,
        "item_status": item_status
    }
