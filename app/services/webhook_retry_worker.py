
import logging
import os
import time
from datetime import timedelta

from sqlalchemy import and_, or_, select

from app.database import SessionLocal
from app.models import PayPalWebhookEvent
from app.services import webhook_processing


logger = logging.getLogger(__name__)


def retry_pending_webhooks(limit=20):
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")

    cutoff = (
        webhook_processing.utc_now()
        - timedelta(minutes=webhook_processing.LEASE_MINUTES)
    )

    # Find events eligible for another processing attempt
    with SessionLocal() as db:
        event_ids = db.scalars(
            select(PayPalWebhookEvent.event_id)
            .where(
                PayPalWebhookEvent.event_type.in_(
                    tuple(webhook_processing.EVENT_EXPECTATIONS)
                ),
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
            .order_by(
                PayPalWebhookEvent.received_at,
                PayPalWebhookEvent.event_id
            )
            .limit(limit)
        ).all()

    results = {
        "found": len(event_ids),
        "processed": 0,
        "deferred": 0,
        "failed": 0
    }

    # Process each event using the existing safe processor
    for event_id in event_ids:
        try:
            status = webhook_processing.process_saved_webhook(
                event_id
            )

            if status == "PROCESSED":
                results["processed"] += 1
            else:
                results["deferred"] += 1

        except Exception:
            results["failed"] += 1
            logger.exception(
                "Unable to reconcile webhook %s",
                event_id
            )

    return results


def run_worker():
    interval = int(
        os.getenv("WEBHOOK_RETRY_INTERVAL_SECONDS", "60")
    )

    if interval < 30:
        raise ValueError(
            "Retry interval must be at least 30 seconds"
        )

    logger.info("Webhook retry worker started")

    while True:
        results = retry_pending_webhooks()
        logger.info("Webhook retry results: %s", results)
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
