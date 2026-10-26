
import json

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import PayPalWebhookEvent, PayoutRecord
from app.services.payout_reconciliation import reconcile_payout


def process_saved_webhook(event_id: str):
    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)

        if event is None:
            raise ValueError("Webhook event not found")

        # We currently process successful payout-item events
        if event.event_type != "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
            return "STORED"

        # Atomically claim the event
        statement = (
            update(PayPalWebhookEvent)
            .where(
                PayPalWebhookEvent.event_id == event_id,
                PayPalWebhookEvent.status == "RECEIVED"
            )
            .values(status="PROCESSING")
        )

        claim = db.execute(statement)
        db.commit()

        # Another worker has already claimed or processed it
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
            # Retrieve the stored webhook payload
            event = db.get(PayPalWebhookEvent, event_id)

            payload = json.loads(event.payload_json)
            resource = payload.get("resource")

            if not isinstance(resource, dict):
                raise ValueError("Invalid webhook resource")

            sender_batch_id = resource.get("sender_batch_id")

            if not isinstance(sender_batch_id, str) or not sender_batch_id:
                raise ValueError("Missing sender batch ID")

            # Find the corresponding payout
            payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.sender_batch_id == sender_batch_id
                )
            )

            if payout is None:
                raise ValueError("Matching payout not found")

            # Verify the existing transaction with PayPal
            result = reconcile_payout(db, payout)

            if (
                result["status"] != "PAID"
                or result["batch_status"] != "SUCCESS"
                or result["item_status"] != "SUCCESS"
            ):
                raise ValueError("Payment not yet confirmed")

            # Commit reconciliation and event completion together
            event.status = "PROCESSED"
            db.commit()

            return "PROCESSED"

        except Exception:
            db.rollback()

            # Release the claim so the event can be retried
            with SessionLocal() as recovery_db:
                recovery_db.execute(
                    update(PayPalWebhookEvent)
                    .where(
                        PayPalWebhookEvent.event_id == event_id,
                        PayPalWebhookEvent.status == "PROCESSING"
                    )
                    .values(status="RECEIVED")
                )
                recovery_db.commit()

            raise
