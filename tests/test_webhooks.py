
from fastapi.testclient import TestClient
from app.main import app
from app.routers import webhooks
from decimal import Decimal
import httpx
import json
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import (
    Base,
    SmartPayRule,
    PayoutRecord,
    PayPalWebhookEvent,
)
from app.services import webhook_processing, payout_reconciliation
from concurrent.futures import ThreadPoolExecutor
from threading import Event


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
