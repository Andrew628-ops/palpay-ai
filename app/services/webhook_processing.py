
import json

from sqlalchemy import select

from app.database import SessionLocal
from app.models import PayPalWebhookEvent, PayoutRecord
from app.services.payout_reconciliation import reconcile_payout


def process_saved_webhook(event_id: str):
    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)

        if event is None:
            raise ValueError("Webhook event not found")

        # Avoid processing an event twice
        if event.status == "PROCESSED":
            return "PROCESSED"

        # Handle item success events first
        if event.event_type != "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
            return "STORED"

        payload = json.loads(event.payload_json)
        resource = payload.get("resource")

        if not isinstance(resource, dict):
            raise ValueError("Invalid webhook resource")

        sender_batch_id = resource.get("sender_batch_id")

        if not isinstance(sender_batch_id, str) or not sender_batch_id:
            raise ValueError("Missing sender batch ID")

        # Find the existing payout
        payout = db.scalar(
            select(PayoutRecord).where(
                PayoutRecord.sender_batch_id == sender_batch_id
            )
        )

        if payout is None:
            raise ValueError("Matching payout not found")

        # Verify payment details directly with PayPal
        result = reconcile_payout(db, payout)

        if result["status"] != "PAID":
            raise ValueError("Payment not yet confirmed")

        # Save both updates in one transaction
        event.status = "PROCESSED"
        db.commit()

        return "PROCESSED"
