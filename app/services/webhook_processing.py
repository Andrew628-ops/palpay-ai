
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from app.database import SessionLocal
from app.models import PayPalWebhookEvent, PayoutRecord
from app.services.payout_reconciliation import reconcile_payout

EVENT_EXPECTATIONS = {
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED": ("PAID", "SUCCESS"),
    "PAYMENT.PAYOUTS-ITEM.FAILED": ("PAYOUT_FAILED", "FAILED"),
    "PAYMENT.PAYOUTS-ITEM.RETURNED": ("PAYOUT_RETURNED", "RETURNED"),
    "PAYMENT.PAYOUTS-ITEM.REFUNDED": ("PAYOUT_REFUNDED", "REFUNDED"),
}
LEASE_MINUTES = 5


def utc_now():
    # SQLite stores our DateTime values without timezone info.
    # We consistently use naive UTC for processing timestamps.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def process_saved_webhook(event_id: str):
    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)

        if event is None:
            raise ValueError("Webhook event not found")

        if event.event_type not in EVENT_EXPECTATIONS:
            return "STORED"

        now = utc_now()
        cutoff = now - timedelta(minutes=LEASE_MINUTES)
        token = uuid4().hex

        # Claim a new event or reclaim an abandoned one.
        claim_statement = (
            update(PayPalWebhookEvent)
            .where(
                PayPalWebhookEvent.event_id == event_id,
                or_(
                    PayPalWebhookEvent.status == "RECEIVED",
                    and_(
                        PayPalWebhookEvent.status == "PROCESSING",
                        or_(
                            PayPalWebhookEvent.processing_started_at.is_(None),
                            PayPalWebhookEvent.processing_started_at < cutoff
                        )
                    )
                )
            )
            .values(
                status="PROCESSING",
                processing_started_at=now,
                processing_token=token
            )
        )

        claim = db.execute(claim_statement)
        db.commit()

        if claim.rowcount != 1:
            db.expire_all()
            current = db.get(PayPalWebhookEvent, event_id)

            if current is None:
                raise ValueError("Webhook event disappeared")

            if current.status == "PROCESSED":
                return "PROCESSED"

            if current.status == "PROCESSING":
                return "PROCESSING"

            raise ValueError("Unexpected webhook state")

        try:
            event = db.get(PayPalWebhookEvent, event_id)

            payload = json.loads(event.payload_json)
            resource = payload.get("resource")

            if not isinstance(resource, dict):
                raise ValueError("Invalid webhook resource")

            sender_batch_id = resource.get("sender_batch_id")

            if not isinstance(sender_batch_id, str) or not sender_batch_id:
                raise ValueError("Missing sender batch ID")

            payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.sender_batch_id == sender_batch_id
                )
            )

            if payout is None:
                raise ValueError("Matching payout not found")

            # Recheck the existing payout with PayPal.
            result = reconcile_payout(db, payout)

            
            expected_status, expected_item_status = EVENT_EXPECTATIONS[
                event.event_type
            ]

            if (
                result["status"] != expected_status
                or result["item_status"] != expected_item_status
            ):
                raise ValueError(
                    "PayPal payout status does not match webhook event"
            )

            if (
                expected_status == "PAID"
                and result["batch_status"] != "SUCCESS"
            ):
                raise ValueError(
                    "Payment batch is not confirmed successful"
            )


            # Only the current token owner may finish processing.
            finish = db.execute(
                update(PayPalWebhookEvent)
                .where(
                    PayPalWebhookEvent.event_id == event_id,
                    PayPalWebhookEvent.status == "PROCESSING",
                    PayPalWebhookEvent.processing_token == token
                )
                .values(
                    status="PROCESSED",
                    processing_started_at=None,
                    processing_token=None
                )
            )

            if finish.rowcount != 1:
                raise ValueError("Webhook processing claim was lost")

            # Payment and webhook completion commit together.
            db.commit()

            return "PROCESSED"

        except Exception:
            # Discard uncommitted payment changes.
            db.rollback()

            # Release the claim only if we still own it.
            with SessionLocal() as recovery_db:
                recovery_db.execute(
                    update(PayPalWebhookEvent)
                    .where(
                        PayPalWebhookEvent.event_id == event_id,
                        PayPalWebhookEvent.status == "PROCESSING",
                        PayPalWebhookEvent.processing_token == token
                    )
                    .values(
                        status="RECEIVED",
                        processing_started_at=None,
                        processing_token=None
                    )
                )
                recovery_db.commit()

            raise
