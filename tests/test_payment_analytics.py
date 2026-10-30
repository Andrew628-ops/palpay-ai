
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, SmartPayRule, PayoutRecord
from app.routers import payment_history


TEST_TOKEN = "test-only-analytics-token"


@pytest.fixture
def analytics_env(tmp_path, monkeypatch):
    # Create a separate SQLite database for each test.
    database_path = tmp_path / "analytics_test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )

    TestSessionLocal = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # Redirect FastAPI database access to the test database.
    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    # Stub the token checker so we never need real secrets.
    def fake_verify_approval_token(token):
        if token != TEST_TOKEN:
            raise HTTPException(
                status_code=403,
                detail="Invalid test token",
            )

    monkeypatch.setattr(
        payment_history,
        "verify_approval_token",
        fake_verify_approval_token,
    )

    try:
        with TestClient(app) as client:
            yield client, TestSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


def create_test_rule(
    db,
    *,
    amount,
    status,
    currency="USD",
    payout_status=None,
):
    rule = SmartPayRule(
        recipient_name="Analytics Test Recipient",
        amount=float(amount),
        currency=currency,
        description="Automated analytics test",
        condition="Complete the test task",
        status=status,
    )

    db.add(rule)
    db.flush()

    if payout_status is not None:
        payout = PayoutRecord(
            rule_id=rule.id,
            sender_batch_id=f"analytics-batch-{rule.id}",
            receiver_email="sandbox@example.com",
            amount=Decimal(str(amount)),
            currency=currency,
            status=payout_status,
            paypal_batch_id=f"paypal-test-{rule.id}",
            paypal_batch_status="SUCCESS",
            paypal_item_status="SUCCESS",
        )
        db.add(payout)

    return rule


def get_summary(client):
    return client.get(
        "/api/payments/summary",
        headers={"x-approval-token": TEST_TOKEN},
    )


def test_summary_requires_authorization(analytics_env):
    client, _ = analytics_env

    missing_token = client.get("/api/payments/summary")

    invalid_token = client.get(
        "/api/payments/summary",
        headers={"x-approval-token": "wrong-token"},
    )

    assert missing_token.status_code == 403
    assert invalid_token.status_code == 403


def test_summary_empty_database(analytics_env):
    client, _ = analytics_env

    response = get_summary(client)

    assert response.status_code == 200

    data = response.json()

    assert data["total_rules"] == 0
    assert data["completed_payouts"] == 0
    assert data["awaiting_approval"] == 0
    assert data["completed_volume_usd"] == "0.00"
    assert data["environment"] == "SANDBOX"


def test_summary_excludes_incomplete_payments(analytics_env):
    client, TestSessionLocal = analytics_env

    with TestSessionLocal() as db:
        # Two successfully completed payouts.
        create_test_rule(
            db,
            amount="15.00",
            status="PAID",
            payout_status="PAYOUT_COMPLETED",
        )

        create_test_rule(
            db,
            amount="10.00",
            status="PAID",
            payout_status="PAYOUT_COMPLETED",
        )

        # Still processing: should not count as completed.
        create_test_rule(
            db,
            amount="100.00",
            status="PAYOUT_SUBMITTED",
            payout_status="PAYOUT_SUBMITTED",
        )

        # Reversed payout: should not count as completed.
        create_test_rule(
            db,
            amount="50.00",
            status="PAYOUT_RETURNED",
            payout_status="PAYOUT_RETURNED",
        )

        # Waiting for human approval.
        create_test_rule(
            db,
            amount="20.00",
            status="AWAITING_USER_APPROVAL",
        )

        # Inconsistent states should not count as completed.
        create_test_rule(
            db,
            amount="200.00",
            status="PAID",
            payout_status="PAYOUT_SUBMITTED",
        )

        db.commit()

    response = get_summary(client)

    assert response.status_code == 200

    data = response.json()

    assert data["total_rules"] == 6
    assert data["completed_payouts"] == 2
    assert data["awaiting_approval"] == 1
    assert data["completed_volume_usd"] == "25.00"


def test_summary_separates_currencies(analytics_env):
    client, TestSessionLocal = analytics_env

    with TestSessionLocal() as db:
        create_test_rule(
            db,
            amount="0.01",
            currency="USD",
            status="PAID",
            payout_status="PAYOUT_COMPLETED",
        )

        create_test_rule(
            db,
            amount="8.50",
            currency="EUR",
            status="PAID",
            payout_status="PAYOUT_COMPLETED",
        )

        db.commit()

    response = get_summary(client)

    assert response.status_code == 200

    data = response.json()

    # Both payments are completed.
    assert data["completed_payouts"] == 2

    # Only USD contributes to the USD volume.
    assert data["completed_volume_usd"] == "0.01"
