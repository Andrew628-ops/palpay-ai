
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    SmartPayRule,
    PayoutRecord,
    PayPalWebhookEvent,
)
import app.services.webhook_processing as processor


@pytest.fixture
def webhook_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'webhook_safety.db'}"
    )

    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Redirect webhook processing to the test database.
    monkeypatch.setattr(
        processor,
        "SessionLocal",
        SessionLocal,
    )

    yield SessionLocal, monkeypatch

    engine.dispose()


def seed_event(
    SessionLocal,
    *,
    event_type="PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
    event_status="RECEIVED",
    rule_status="PAYOUT_SUBMITTED",
    payout_status="PAYOUT_SUBMITTED",
    started_at=None,
):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Webhook Test",
            amount=10.00,
            currency="USD",
            description="Webhook safety test",
            condition="Complete work",
            status=rule_status,
        )

        db.add(rule)
        db.flush()

        batch_id = f"test-batch-{rule.id}"
        event_id = f"test-event-{rule.id}"

        payout = PayoutRecord(
            rule_id=rule.id,
            sender_batch_id=batch_id,
            receiver_email="sandbox@example.com",
            amount=Decimal("10.00"),
            currency="USD",
            status=payout_status,
        )

        event = PayPalWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_json=json.dumps({
                "resource": {
                    "sender_batch_id": batch_id,
                }
            }),
            status=event_status,
            processing_started_at=started_at,
            processing_token=(
                "previous-worker-token"
                if event_status == "PROCESSING"
                else None
            ),
        )

        db.add_all([payout, event])
        db.commit()

        return event_id, rule.id


def fake_success(db, payout):
    payout.status = "PAYOUT_COMPLETED"

    rule = db.get(SmartPayRule, payout.rule_id)
    rule.status = "PAID"

    return {
        "status": "PAID",
        "item_status": "SUCCESS",
        "batch_status": "SUCCESS",
    }


def test_success_event_is_idempotent(webhook_env):
    SessionLocal, monkeypatch = webhook_env
    event_id, rule_id = seed_event(SessionLocal)

    calls = []

    def reconcile(db, payout):
        calls.append(payout.id)
        return fake_success(db, payout)

    monkeypatch.setattr(
        processor,
        "reconcile_payout",
        reconcile,
    )

    first = processor.process_saved_webhook(event_id)
    second = processor.process_saved_webhook(event_id)

    assert first == "PROCESSED"
    assert second == "PROCESSED"
    assert len(calls) == 1

    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)
        rule = db.get(SmartPayRule, rule_id)

        assert event.status == "PROCESSED"
        assert event.processing_token is None
        assert rule.status == "PAID"


def test_active_worker_claim_is_respected(webhook_env):
    SessionLocal, monkeypatch = webhook_env

    event_id, _ = seed_event(
        SessionLocal,
        event_status="PROCESSING",
        started_at=processor.utc_now(),
    )

    def should_not_reconcile(db, payout):
        raise AssertionError(
            "An active worker already owns this event"
        )

    monkeypatch.setattr(
        processor,
        "reconcile_payout",
        should_not_reconcile,
    )

    result = processor.process_saved_webhook(event_id)

    assert result == "PROCESSING"


def test_expired_worker_claim_can_be_recovered(
    webhook_env,
):
    SessionLocal, monkeypatch = webhook_env

    event_id, rule_id = seed_event(
        SessionLocal,
        event_status="PROCESSING",
        started_at=(
            processor.utc_now() - timedelta(minutes=6)
        ),
    )

    monkeypatch.setattr(
        processor,
        "reconcile_payout",
        fake_success,
    )

    result = processor.process_saved_webhook(event_id)

    assert result == "PROCESSED"

    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)
        rule = db.get(SmartPayRule, rule_id)

        assert event.status == "PROCESSED"
        assert event.processing_token is None
        assert rule.status == "PAID"


def test_mismatched_event_rolls_back_changes(
    webhook_env,
):
    SessionLocal, monkeypatch = webhook_env

    event_id, rule_id = seed_event(
        SessionLocal,
        rule_status="PAID",
        payout_status="PAYOUT_COMPLETED",
    )

    def stale_result(db, payout):
        # Simulate reconciliation attempting to
        # replace confirmed payment with pending.
        payout.status = "PAYOUT_SUBMITTED"

        rule = db.get(SmartPayRule, payout.rule_id)
        rule.status = "PAYOUT_SUBMITTED"

        return {
            "status": "PAYOUT_SUBMITTED",
            "item_status": "PENDING",
            "batch_status": "PENDING",
        }

    monkeypatch.setattr(
        processor,
        "reconcile_payout",
        stale_result,
    )

    with pytest.raises(ValueError):
        processor.process_saved_webhook(event_id)

    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)
        rule = db.get(SmartPayRule, rule_id)
        payout = db.query(PayoutRecord).filter_by(
            rule_id=rule_id
        ).one()

        assert event.status == "RECEIVED"
        assert event.processing_token is None
        assert rule.status == "PAID"
        assert payout.status == "PAYOUT_COMPLETED"


def test_unsupported_event_is_ignored(webhook_env):
    SessionLocal, _ = webhook_env

    event_id, _ = seed_event(
        SessionLocal,
        event_type="PAYMENT.PAYOUTSBATCH.SUCCESS",
    )

    first = processor.process_saved_webhook(event_id)
    second = processor.process_saved_webhook(event_id)

    assert first == "IGNORED"
    assert second == "IGNORED"

    with SessionLocal() as db:
        event = db.get(PayPalWebhookEvent, event_id)
        assert event.status == "IGNORED"


def test_verified_refund_can_update_paid_record(
    webhook_env,
):
    SessionLocal, monkeypatch = webhook_env

    event_id, rule_id = seed_event(
        SessionLocal,
        event_type="PAYMENT.PAYOUTS-ITEM.REFUNDED",
        rule_status="PAID",
        payout_status="PAYOUT_COMPLETED",
    )

    def fake_refund(db, payout):
        payout.status = "PAYOUT_REFUNDED"

        rule = db.get(SmartPayRule, payout.rule_id)
        rule.status = "PAYOUT_REFUNDED"

        return {
            "status": "PAYOUT_REFUNDED",
            "item_status": "REFUNDED",
            "batch_status": "SUCCESS",
        }

    monkeypatch.setattr(
        processor,
        "reconcile_payout",
        fake_refund,
    )

    result = processor.process_saved_webhook(event_id)

    assert result == "PROCESSED"

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)
        assert rule.status == "PAYOUT_REFUNDED"
