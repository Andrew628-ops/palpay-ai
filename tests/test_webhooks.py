import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers import webhooks, payouts
from decimal import Decimal
import httpx
import json
from unittest.mock import Mock

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import (
    Base,
    SmartPayRule,
    PayoutRecord,
    PayPalWebhookEvent,
)
from app.services import webhook_processing, payout_reconciliation, webhook_retry_worker
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime, timedelta, timezone


def test_webhook_rejects_unsigned_request(monkeypatch):
    # Set a dummy webhook ID for testing
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    # Ensure the test uses Sandbox configuration
    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    # Create a test client
    client = TestClient(app)

    # Send a fake webhook without PayPal signature headers
    response = client.post(
        "/api/webhooks/paypal",
        json={
            "id": "WH-FAKE-123",
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"
        }
    )

    # Verify that FastAPI rejects the request
    assert response.status_code == 400

    # Verify the error message
    assert response.json() == {
        "detail": "Missing PayPal signature headers"
    }


def test_webhook_rejects_invalid_signature(monkeypatch):
    # Set a test webhook ID
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    # Ensure Sandbox configuration
    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    # Simulate PayPal rejecting the signature
    monkeypatch.setattr(
        webhooks,
        "verify_paypal_webhook",
        lambda event, headers, webhook_id: False
    )

    client = TestClient(app)

    # Send a request with fake signature headers
    response = client.post(
        "/api/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.com/cert",
            "paypal-transmission-id": "fake-transmission",
            "paypal-transmission-sig": "invalid-signature",
            "paypal-transmission-time": "2026-10-26T09:00:00Z"
        },
        json={
            "id": "WH-FAKE-456",
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"
        }
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Invalid PayPal signature"
    }


def test_successful_webhook_updates_payment(monkeypatch, tmp_path):
    # 1. Create an isolated test database
    database_path = tmp_path / "test_webhooks.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # 2. Make FastAPI use our test database
    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    # The webhook processor creates its own DB session
    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    # 3. Configure fake PayPal verification
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    monkeypatch.setattr(
        webhooks,
        "verify_paypal_webhook",
        lambda event, headers, webhook_id: True
    )

    sender_batch_id = "palpay-test-123"
    paypal_batch_id = "TEST-BATCH-123"

    try:
        # 4. Create a test SmartPay rule and payout
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Test Developer",
                amount=5.00,
                currency="USD",
                description="Test payment",
                condition="Submit a test verification code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()

            rule_id = rule.id

            payout = PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id=paypal_batch_id
            )

            db.add(payout)
            db.commit()

        # 5. Mock PayPal's payout-details response
        def fake_get_payout_details(batch_id):
            assert batch_id == paypal_batch_id

            return {
                "batch_header": {
                    "payout_batch_id": paypal_batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [
                    {
                        "payout_batch_id": paypal_batch_id,
                        "transaction_status": "SUCCESS",
                        "payout_item": {
                            "sender_item_id": sender_batch_id[:63],
                            "recipient_type": "EMAIL",
                            "receiver": "receiver@example.com",
                            "amount": {
                                "value": "5.00",
                                "currency": "USD"
                            }
                        }
                    }
                ]
            }

        mock_paypal = Mock(side_effect=fake_get_payout_details)

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            mock_paypal
        )

        # 6. Send a simulated verified webhook
        client = TestClient(app)

        response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "test-transmission",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-TEST-SUCCESS-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        # 7. Check the API response
        assert response.status_code == 200
        assert response.json()["status"] == "PROCESSED"

        # 8. Verify the changes were saved
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)

            saved_event = db.get(
                PayPalWebhookEvent,
                "WH-TEST-SUCCESS-123"
            )

            saved_payout = db.get(PayoutRecord, 1)

            assert saved_rule.status == "PAID"
            assert saved_payout.status == "PAYOUT_COMPLETED"
            assert saved_event.status == "PROCESSED"

        
        # Send the SAME webhook for a second time
        duplicate_response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "test-transmission",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-TEST-SUCCESS-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        # Duplicate webhook should be acknowledged
        assert duplicate_response.status_code == 200

        # Already processed event remains processed
        assert duplicate_response.json()["status"] == "PROCESSED"

        # PayPal details should only be checked once
        assert mock_paypal.call_count == 1


    finally:
        # Restore normal FastAPI database behavior
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()



def test_webhook_paypal_api_failure(monkeypatch, tmp_path):
    # Create a separate test database
    database_path = tmp_path / "failure_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    # Simulate successful signature verification
    monkeypatch.setattr(
        webhooks,
        "verify_paypal_webhook",
        lambda event, headers, webhook_id: True
    )

    sender_batch_id = "palpay-failure-test-123"

    try:
        # Create an approved payout that was submitted
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Test Developer",
                amount=5.00,
                currency="USD",
                description="API failure test",
                condition="Submit test code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()

            rule_id = rule.id

            payout = PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id="FAILED-CONNECTION-BATCH"
            )

            db.add(payout)
            db.commit()

        # Simulate PayPal being temporarily unavailable
        def fake_paypal_failure(batch_id):
            raise httpx.ConnectError(
                "PayPal API temporarily unavailable"
            )

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            fake_paypal_failure
        )

        client = TestClient(app)

        response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "failure-test",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-TEST-FAILURE-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        # The endpoint should report temporary failure
        assert response.status_code == 503

        assert response.json() == {
            "detail": "Webhook saved, but reconciliation is pending"
        }

        # Verify no incorrect payment update occurred
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)

            saved_event = db.get(
                PayPalWebhookEvent,
                "WH-TEST-FAILURE-123"
            )

            saved_payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert saved_event is not None
            assert saved_event.status == "RECEIVED"
            assert saved_rule.status == "PAYOUT_SUBMITTED"
            assert saved_payout.status == "PAYOUT_SUBMITTED"

        
        # Simulate PayPal recovering
        def fake_paypal_recovery(batch_id):
            assert batch_id == "FAILED-CONNECTION-BATCH"

            return {
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [
                    {
                        "payout_batch_id": batch_id,
                        "transaction_status": "SUCCESS",
                        "payout_item": {
                            "sender_item_id": sender_batch_id[:63],
                            "recipient_type": "EMAIL",
                            "receiver": "receiver@example.com",
                            "amount": {
                                "value": "5.00",
                                "currency": "USD"
                            }
                        }
                    }
                ]
            }

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            fake_paypal_recovery
        )

        # PayPal retries the SAME webhook
        retry_response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "failure-test",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-TEST-FAILURE-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        assert retry_response.status_code == 200
        assert retry_response.json()["status"] == "PROCESSED"

        # Verify database recovery
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)
            saved_event = db.get(
                PayPalWebhookEvent,
                "WH-TEST-FAILURE-123"
            )

            saved_payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert saved_rule.status == "PAID"
            assert saved_payout.status == "PAYOUT_COMPLETED"
            assert saved_event.status == "PROCESSED"


    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()



def test_concurrent_duplicate_webhooks(monkeypatch, tmp_path):
    database_path = tmp_path / "concurrent_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    sender_batch_id = "palpay-concurrent-test"
    paypal_batch_id = "CONCURRENT-BATCH-123"
    event_id = "WH-CONCURRENT-123"

    # Use the test database in our processor
    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    try:
        # Prepare test records
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Concurrency Tester",
                amount=5.00,
                currency="USD",
                description="Concurrent webhook test",
                condition="Test code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()
            rule_id = rule.id

            db.add(PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id=paypal_batch_id
            ))

            db.add(PayPalWebhookEvent(
                event_id=event_id,
                event_type="PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                payload_json=json.dumps({
                    "resource": {
                        "sender_batch_id": sender_batch_id
                    }
                }),
                status="RECEIVED"
            ))

            db.commit()

        started = Event()
        release = Event()

        # Pause the first worker during PayPal verification
        def fake_get_payout_details(batch_id):
            assert batch_id == paypal_batch_id

            started.set()

            if not release.wait(timeout=10):
                raise TimeoutError("Test worker timed out")

            return {
                "batch_header": {
                    "payout_batch_id": paypal_batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [{
                    "payout_batch_id": paypal_batch_id,
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "sender_item_id": sender_batch_id[:63],
                        "recipient_type": "EMAIL",
                        "receiver": "receiver@example.com",
                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        mock_paypal = Mock(side_effect=fake_get_payout_details)

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            mock_paypal
        )

        # Start two workers at nearly the same time
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                webhook_processing.process_saved_webhook,
                event_id
            )

            try:
                # Ensure the first worker has claimed the event
                assert started.wait(timeout=5)

                second = executor.submit(
                    webhook_processing.process_saved_webhook,
                    event_id
                )

                # The second worker must not reconcile it
                second_result = second.result(timeout=5)

                assert second_result == "PROCESSING"

            finally:
                release.set()

            first_result = first.result(timeout=10)

        assert first_result == "PROCESSED"
        assert mock_paypal.call_count == 1

        # Verify the final database states
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)
            saved_event = db.get(PayPalWebhookEvent, event_id)

            saved_payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert saved_rule.status == "PAID"
            assert saved_payout.status == "PAYOUT_COMPLETED"
            assert saved_event.status == "PROCESSED"

    finally:
        test_engine.dispose()



def test_stale_webhook_claim_recovery(monkeypatch, tmp_path):
    database_path = tmp_path / "stale_claim_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    sender_batch_id = "palpay-stale-test"
    paypal_batch_id = "STALE-BATCH-123"
    event_id = "WH-STALE-TEST-123"

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Create test payment and webhook records.
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Test Developer",
                amount=5.00,
                currency="USD",
                description="Stale webhook recovery",
                condition="Submit test code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()
            rule_id = rule.id

            db.add(PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id=paypal_batch_id
            ))

            db.add(PayPalWebhookEvent(
                event_id=event_id,
                event_type="PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                payload_json=json.dumps({
                    "resource": {
                        "sender_batch_id": sender_batch_id
                    }
                }),
                status="PROCESSING",
                processing_started_at=now,
                processing_token="active-worker"
            ))

            db.commit()

        paypal_calls = Mock()

        def fake_get_payout_details(batch_id):
            paypal_calls()
            assert batch_id == paypal_batch_id

            return {
                "batch_header": {
                    "payout_batch_id": paypal_batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [{
                    "payout_batch_id": paypal_batch_id,
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "sender_item_id": sender_batch_id[:63],
                        "recipient_type": "EMAIL",
                        "receiver": "receiver@example.com",
                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            fake_get_payout_details
        )

        # 1. A fresh PROCESSING claim must not be stolen.
        result = webhook_processing.process_saved_webhook(event_id)

        assert result == "PROCESSING"
        assert paypal_calls.call_count == 0

        # 2. Simulate a worker abandoned 10 minutes ago.
        with TestSessionLocal() as db:
            event = db.get(PayPalWebhookEvent, event_id)
            event.processing_started_at = (
                now - timedelta(minutes=10)
            )
            db.commit()

        # 3. Recover and process the stale event.
        result = webhook_processing.process_saved_webhook(event_id)

        assert result == "PROCESSED"
        assert paypal_calls.call_count == 1

        # 4. Verify all changes are saved.
        with TestSessionLocal() as db:
            event = db.get(PayPalWebhookEvent, event_id)
            rule = db.get(SmartPayRule, rule_id)

            payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert event.status == "PROCESSED"
            assert event.processing_token is None
            assert event.processing_started_at is None

            assert rule.status == "PAID"
            assert payout.status == "PAYOUT_COMPLETED"

        # 5. Reprocessing a completed event does nothing.
        result = webhook_processing.process_saved_webhook(event_id)

        assert result == "PROCESSED"
        assert paypal_calls.call_count == 1

    finally:
        test_engine.dispose()


def test_old_worker_cannot_overwrite_new_worker(monkeypatch, tmp_path):
    database_path = tmp_path / "worker_takeover.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    event_id = "WH-WORKER-TAKEOVER"
    sender_batch_id = "palpay-takeover-test"

    first_started = Event()
    release_old_worker = Event()
    calls = []

    try:
        # Create isolated test records
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Test Recipient",
                amount=5.00,
                currency="USD",
                description="Worker takeover test",
                condition="Submit verification code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()
            rule_id = rule.id

            db.add(PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id="TAKEOVER-BATCH"
            ))

            db.add(PayPalWebhookEvent(
                event_id=event_id,
                event_type="PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                payload_json=json.dumps({
                    "resource": {
                        "sender_batch_id": sender_batch_id
                    }
                }),
                status="RECEIVED"
            ))

            db.commit()

        # Mock reconciliation without contacting PayPal
        def fake_reconcile(db, payout):
            calls.append(1)

            if len(calls) == 1:
                first_started.set()

                if not release_old_worker.wait(timeout=10):
                    raise TimeoutError("Old worker timed out")

            rule = db.get(SmartPayRule, payout.rule_id)
            rule.status = "PAID"
            payout.status = "PAYOUT_COMPLETED"

            return {
                "status": "PAID",
                "batch_status": "SUCCESS",
                "item_status": "SUCCESS"
            }

        monkeypatch.setattr(
            webhook_processing,
            "reconcile_payout",
            fake_reconcile
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Worker A starts processing
            first = executor.submit(
                webhook_processing.process_saved_webhook,
                event_id
            )

            try:
                assert first_started.wait(timeout=5)

                # Simulate the first worker's lease expiring
                old_time = (
                    datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(minutes=10)
                )

                with TestSessionLocal() as db:
                    db.execute(
                        update(PayPalWebhookEvent)
                        .where(
                            PayPalWebhookEvent.event_id == event_id
                        )
                        .values(processing_started_at=old_time)
                    )
                    db.commit()

                # Worker B reclaims and completes processing
                second_result = (
                    webhook_processing.process_saved_webhook(event_id)
                )

                assert second_result == "PROCESSED"

            finally:
                release_old_worker.set()

            # Worker A must reject its expired claim
            with pytest.raises(
                ValueError,
                match="claim was lost"
            ):
                first.result(timeout=10)

        # Check the final database state
        with TestSessionLocal() as db:
            event = db.get(PayPalWebhookEvent, event_id)
            rule = db.get(SmartPayRule, rule_id)

            payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert event.status == "PROCESSED"
            assert event.processing_token is None
            assert rule.status == "PAID"
            assert payout.status == "PAYOUT_COMPLETED"

        assert len(calls) == 2

    finally:
        test_engine.dispose()


def test_automatic_retry_of_abandoned_webhooks(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "retry_worker_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # Point both services to our isolated database
    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    monkeypatch.setattr(
        webhook_retry_worker,
        "SessionLocal",
        TestSessionLocal
    )

    now = webhook_processing.utc_now()
    names = ["waiting", "stale", "active"]
    rule_ids = {}

    try:
        with TestSessionLocal() as db:
            for name in names:
                rule = SmartPayRule(
                    recipient_name="Test Recipient",
                    amount=5.00,
                    currency="USD",
                    description="Retry worker test",
                    condition="Submit test code",
                    status="PAYOUT_SUBMITTED"
                )

                db.add(rule)
                db.flush()
                rule_ids[name] = rule.id

                sender_batch_id = f"palpay-retry-{name}"

                db.add(PayoutRecord(
                    rule_id=rule.id,
                    sender_batch_id=sender_batch_id,
                    receiver_email="receiver@example.com",
                    amount=Decimal("5.00"),
                    currency="USD",
                    status="PAYOUT_SUBMITTED",
                    paypal_batch_id=f"RETRY-BATCH-{name}"
                ))

                status = (
                    "RECEIVED" if name == "waiting"
                    else "PROCESSING"
                )

                started_at = (
                    now - timedelta(minutes=10)
                    if name == "stale"
                    else now if name == "active"
                    else None
                )

                db.add(PayPalWebhookEvent(
                    event_id=f"WH-RETRY-{name}",
                    event_type="PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                    payload_json=json.dumps({
                        "resource": {
                            "sender_batch_id": sender_batch_id
                        }
                    }),
                    status=status,
                    processing_started_at=started_at,
                    processing_token=(
                        None if name == "waiting"
                        else f"worker-{name}"
                    )
                ))

            db.commit()

        # Mock PayPal's read-only payout details API
        def fake_get_payout_details(batch_id):
            name = batch_id.removeprefix("RETRY-BATCH-")
            sender_batch_id = f"palpay-retry-{name}"

            return {
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [{
                    "payout_batch_id": batch_id,
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "sender_item_id": sender_batch_id[:63],
                        "recipient_type": "EMAIL",
                        "receiver": "receiver@example.com",
                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        mock_paypal = Mock(side_effect=fake_get_payout_details)

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            mock_paypal
        )

        # Run one retry cycle
        result = webhook_retry_worker.retry_pending_webhooks()

        assert result == {
            "found": 2,
            "processed": 2,
            "deferred": 0,
            "failed": 0
        }

        assert mock_paypal.call_count == 2

        # Verify database changes
        with TestSessionLocal() as db:
            for name in ["waiting", "stale"]:
                event = db.get(
                    PayPalWebhookEvent,
                    f"WH-RETRY-{name}"
                )

                rule = db.get(
                    SmartPayRule,
                    rule_ids[name]
                )

                payout = db.scalar(
                    select(PayoutRecord).where(
                        PayoutRecord.rule_id == rule_ids[name]
                    )
                )

                assert event.status == "PROCESSED"
                assert event.processing_token is None
                assert rule.status == "PAID"
                assert payout.status == "PAYOUT_COMPLETED"

            # Active worker must not be interrupted
            active = db.get(
                PayPalWebhookEvent,
                "WH-RETRY-active"
            )

            assert active.status == "PROCESSING"
            assert active.processing_token == "worker-active"

        # Completed events should not be retried
        second_result = (
            webhook_retry_worker.retry_pending_webhooks()
        )

        assert second_result["found"] == 0
        assert mock_paypal.call_count == 2

    finally:
        test_engine.dispose()


def test_failed_webhook_updates_payment(monkeypatch, tmp_path):
    database_path = tmp_path / "failed_payout_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    monkeypatch.setattr(
        webhooks,
        "verify_paypal_webhook",
        lambda event, headers, webhook_id: True
    )

    sender_batch_id = "palpay-failed-test"
    paypal_batch_id = "FAILED-TEST-BATCH"

    try:
        # Create an isolated SmartPay rule
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Failed Test Recipient",
                amount=5.00,
                currency="USD",
                description="Failed payout test",
                condition="Submit verification code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()
            rule_id = rule.id

            db.add(PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="receiver@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id=paypal_batch_id
            ))

            db.commit()

        # Mock a failed PayPal payout
        def fake_failed_payout(batch_id):
            assert batch_id == paypal_batch_id

            return {
                "batch_header": {
                    "payout_batch_id": paypal_batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [{
                    "payout_batch_id": paypal_batch_id,
                    "transaction_status": "FAILED",
                    "payout_item": {
                        "sender_item_id": sender_batch_id[:63],
                        "recipient_type": "EMAIL",
                        "receiver": "receiver@example.com",
                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        mock_paypal = Mock(side_effect=fake_failed_payout)

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            mock_paypal
        )

        # Send a mocked, successfully verified webhook
        client = TestClient(app)

        response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "failed-test",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-FAILED-TEST-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.FAILED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "PROCESSED"

        # Confirm database records
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)

            saved_event = db.get(
                PayPalWebhookEvent,
                "WH-FAILED-TEST-123"
            )

            saved_payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert saved_rule.status == "PAYOUT_FAILED"
            assert saved_payout.status == "PAYOUT_FAILED"
            assert saved_payout.paypal_item_status == "FAILED"
            assert saved_event.status == "PROCESSED"

        assert mock_paypal.call_count == 1

    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


def test_returned_and_refunded_payouts(monkeypatch, tmp_path):
    database_path = tmp_path / "reversal_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        webhook_processing, "SessionLocal", TestSessionLocal
    )
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")
    monkeypatch.setattr(
        webhooks, "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )
    monkeypatch.setattr(
        webhooks, "verify_paypal_webhook",
        lambda event, headers, webhook_id: True
    )

    cases = {
        "RETURNED": ("PAYOUT_SUBMITTED", "PAYOUT_RETURNED"),
        "REFUNDED": ("PAID", "PAYOUT_REFUNDED"),
    }

    rule_ids = {}

    try:
        with TestSessionLocal() as db:
            for paypal_status, (initial, expected) in cases.items():
                rule = SmartPayRule(
                    recipient_name="Test Recipient",
                    amount=5.00,
                    currency="USD",
                    description="Reversal test",
                    condition="Submit code",
                    status=initial
                )

                db.add(rule)
                db.flush()
                rule_ids[paypal_status] = rule.id

                db.add(PayoutRecord(
                    rule_id=rule.id,
                    sender_batch_id=f"palpay-{paypal_status.lower()}",
                    receiver_email="receiver@example.com",
                    amount=Decimal("5.00"),
                    currency="USD",
                    status=(
                        "PAYOUT_COMPLETED"
                        if initial == "PAID"
                        else "PAYOUT_SUBMITTED"
                    ),
                    paypal_batch_id=f"BATCH-{paypal_status}"
                ))

            db.commit()

        def fake_paypal_details(batch_id):
            paypal_status = batch_id.removeprefix("BATCH-")
            sender_id = f"palpay-{paypal_status.lower()}"

            return {
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_id
                    }
                },
                "items": [{
                    "payout_batch_id": batch_id,
                    "transaction_status": paypal_status,
                    "payout_item": {
                        "sender_item_id": sender_id[:63],
                        "recipient_type": "EMAIL",
                        "receiver": "receiver@example.com",
                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        mock_paypal = Mock(side_effect=fake_paypal_details)

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            mock_paypal
        )

        client = TestClient(app)

        for paypal_status, (_, expected) in cases.items():
            event_id = f"WH-TEST-{paypal_status}"

            response = client.post(
                "/api/webhooks/paypal",
                headers={
                    "paypal-auth-algo": "SHA256withRSA",
                    "paypal-cert-url": "https://example.com/cert",
                    "paypal-transmission-id": f"test-{paypal_status}",
                    "paypal-transmission-sig": "mock-signature",
                    "paypal-transmission-time": "2026-10-26T09:00:00Z"
                },
                json={
                    "id": event_id,
                    "event_type": (
                        f"PAYMENT.PAYOUTS-ITEM.{paypal_status}"
                    ),
                    "resource": {
                        "sender_batch_id":
                            f"palpay-{paypal_status.lower()}"
                    }
                }
            )

            assert response.status_code == 200, response.text
            assert response.json()["status"] == "PROCESSED"

            with TestSessionLocal() as db:
                rule = db.get(
                    SmartPayRule, rule_ids[paypal_status]
                )
                event = db.get(PayPalWebhookEvent, event_id)

                payout = db.scalar(
                    select(PayoutRecord).where(
                        PayoutRecord.rule_id == rule.id
                    )
                )

                assert rule.status == expected
                assert payout.status == expected
                assert payout.paypal_item_status == paypal_status
                assert event.status == "PROCESSED"

        assert mock_paypal.call_count == 2

    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()



def test_webhook_rejects_mismatched_payout(monkeypatch, tmp_path):
    database_path = tmp_path / "mismatch_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestSessionLocal
    )

    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-123")

    monkeypatch.setattr(
        webhooks,
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    # Simulate a verified webhook
    monkeypatch.setattr(
        webhooks,
        "verify_paypal_webhook",
        lambda event, headers, webhook_id: True
    )

    sender_batch_id = "palpay-mismatch-test"
    paypal_batch_id = "MISMATCH-BATCH-123"

    try:
        # 1. Create a test payment
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="John Developer",
                amount=5.00,
                currency="USD",
                description="Mismatch verification test",
                condition="Submit verification code",
                status="PAYOUT_SUBMITTED"
            )

            db.add(rule)
            db.flush()
            rule_id = rule.id

            db.add(PayoutRecord(
                rule_id=rule_id,
                sender_batch_id=sender_batch_id,
                receiver_email="john@example.com",
                amount=Decimal("5.00"),
                currency="USD",
                status="PAYOUT_SUBMITTED",
                paypal_batch_id=paypal_batch_id
            ))

            db.commit()

        # 2. Simulate PayPal returning a different recipient
        def fake_paypal_details(batch_id):
            assert batch_id == paypal_batch_id

            return {
                "batch_header": {
                    "payout_batch_id": paypal_batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": {
                        "sender_batch_id": sender_batch_id
                    }
                },
                "items": [{
                    "payout_batch_id": paypal_batch_id,
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "sender_item_id": sender_batch_id[:63],
                        "recipient_type": "EMAIL",

                        # Deliberately wrong recipient
                        "receiver": "attacker@example.com",

                        "amount": {
                            "value": "5.00",
                            "currency": "USD"
                        }
                    }
                }]
            }

        monkeypatch.setattr(
            payout_reconciliation,
            "get_payout_details",
            fake_paypal_details
        )

        # 3. Send the simulated webhook
        client = TestClient(app)

        response = client.post(
            "/api/webhooks/paypal",
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://example.com/cert",
                "paypal-transmission-id": "mismatch-test",
                "paypal-transmission-sig": "mock-signature",
                "paypal-transmission-time": "2026-10-26T09:00:00Z"
            },
            json={
                "id": "WH-MISMATCH-TEST-123",
                "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "resource": {
                    "sender_batch_id": sender_batch_id
                }
            }
        )

        # 4. Reconciliation must be rejected
        assert response.status_code == 503

        assert response.json()["detail"] == (
            "Webhook saved, but reconciliation is pending"
        )

        # 5. Confirm database was not incorrectly updated
        with TestSessionLocal() as db:
            saved_rule = db.get(SmartPayRule, rule_id)

            saved_event = db.get(
                PayPalWebhookEvent,
                "WH-MISMATCH-TEST-123"
            )

            saved_payout = db.scalar(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            )

            assert saved_rule.status == "PAYOUT_SUBMITTED"
            assert saved_payout.status == "PAYOUT_SUBMITTED"
            assert saved_payout.paypal_item_status is None

            # Event remains available for investigation/retry
            assert saved_event.status == "RECEIVED"

    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()



def test_duplicate_payment_execution(monkeypatch, tmp_path):
    # 1. Create a separate test database
    database_path = tmp_path / "duplicate_payment_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # 2. Override FastAPI's database dependency
    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    # 3. Configure fake credentials
    monkeypatch.setenv(
        "APPROVAL_TOKEN",
        "test-approval-token"
    )

    monkeypatch.setenv(
        "PAYPAL_SANDBOX_RECEIVER_EMAIL",
        "receiver@example.com"
    )

    monkeypatch.setenv(
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com"
    )

    # 4. Mock PayPal so no real API request is made
    mock_paypal = Mock(return_value={
        "batch_header": {
            "payout_batch_id": "TEST-BATCH-123",
            "batch_status": "PENDING"
        }
    })

    monkeypatch.setattr(
        payouts,
        "create_sandbox_payout",
        mock_paypal
    )

    try:
        # 5. Create a human-approved SmartPay rule
        with TestSessionLocal() as db:
            rule = SmartPayRule(
                recipient_name="Test Developer",
                amount=5.00,
                currency="USD",
                description="Duplicate payment test",
                condition="Submit verification code",
                status="USER_APPROVED"
            )

            db.add(rule)
            db.commit()
            db.refresh(rule)

            rule_id = rule.id

        client = TestClient(app)

        url = f"/api/rules/smartpay/{rule_id}/pay"

        headers = {
            "x-approval-token": "test-approval-token"
        }

        # 6. First payment request
        first_response = client.post(
            url,
            headers=headers
        )

        assert first_response.status_code == 202
        assert first_response.json()["status"] == "PAYOUT_SUBMITTED"

        # PayPal should have been called once
        assert mock_paypal.call_count == 1

        # 7. Second payment request for the SAME rule
        second_response = client.post(
            url,
            headers=headers
        )

        # Duplicate payment must be rejected
        assert second_response.status_code == 409

        # PayPal must NOT be called again
        assert mock_paypal.call_count == 1

        # 8. Verify database records
        with TestSessionLocal() as db:
            saved_rule = db.get(
                SmartPayRule,
                rule_id
            )

            payout_records = db.scalars(
                select(PayoutRecord).where(
                    PayoutRecord.rule_id == rule_id
                )
            ).all()

            assert saved_rule.status == "PAYOUT_SUBMITTED"

            # Only one payout record must exist
            assert len(payout_records) == 1

            payout = payout_records[0]

            assert payout.status == "PAYOUT_SUBMITTED"
            assert payout.paypal_batch_id == "TEST-BATCH-123"

            assert (
                payout.sender_batch_id
                == mock_paypal.call_args.kwargs["sender_batch_id"]
            )

    finally:
        # Restore the original database dependency
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()
