
from decimal import Decimal

import httpx
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import (
    Base,
    SmartPayRule,
    Submission,
    PayoutRecord,
)
from app.routers import payouts


TEST_TOKEN = "payment-security-test-token"
TEST_RECEIVER = "sandbox-security@example.com"

HEADERS = {
    "x-approval-token": TEST_TOKEN,
    "x-expected-receiver": TEST_RECEIVER,
}


@pytest.fixture
def security_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'payment_security.db'}",
        connect_args={"check_same_thread": False},
    )

    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("APPROVAL_TOKEN", TEST_TOKEN)
    monkeypatch.setenv(
        "PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    )
    monkeypatch.setenv(
        "PAYPAL_SANDBOX_RECEIVER_EMAIL",
        TEST_RECEIVER,
    )

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, SessionLocal, monkeypatch
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_rule(SessionLocal, status):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Security Test Developer",
            amount=25.00,
            currency="USD",
            description="Test project",
            condition="Complete the assigned task",
            status=status,
        )
        db.add(rule)
        db.commit()
        return rule.id


def pay(client, rule_id, headers=None):
    if headers is None:
        headers = HEADERS

    return client.post(
        f"/api/rules/smartpay/{rule_id}/pay",
        headers=headers,
    )


def block_paypal(monkeypatch):
    def unexpected_call(**kwargs):
        raise AssertionError(
            "PayPal must not be contacted"
        )

    monkeypatch.setattr(
        payouts,
        "create_sandbox_payout",
        unexpected_call,
    )


@pytest.mark.parametrize(
    "status",
    [
        "CONDITION_SUBMITTED",
        "NEEDS_REVIEW",
        "EVIDENCE_REQUESTED",
        "HUMAN_REJECTED",
        "AWAITING_USER_APPROVAL",
        "PAYOUT_SUBMITTED",
        "PAID",
    ],
)
def test_unapproved_rules_cannot_pay(
    security_env, status
):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, status)
    block_paypal(monkeypatch)

    response = pay(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == status

        count = db.scalar(
            select(func.count(PayoutRecord.id))
        )
        assert count == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"x-expected-receiver": TEST_RECEIVER},
        {
            "x-approval-token": "invalid-token",
            "x-expected-receiver": TEST_RECEIVER,
        },
    ],
)
def test_payout_requires_valid_token(
    security_env, headers
):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, "USER_APPROVED")
    block_paypal(monkeypatch)

    response = pay(client, rule_id, headers)

    assert response.status_code == 403


def test_receiver_mismatch_blocks_payout(security_env):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, "USER_APPROVED")
    block_paypal(monkeypatch)

    response = pay(
        client,
        rule_id,
        {
            "x-approval-token": TEST_TOKEN,
            "x-expected-receiver": "wrong@example.com",
        },
    )

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "USER_APPROVED"
        )


def test_live_paypal_url_is_blocked(security_env):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, "USER_APPROVED")

    monkeypatch.setenv(
        "PAYPAL_BASE_URL",
        "https://api-m.paypal.com",
    )
    block_paypal(monkeypatch)

    response = pay(client, rule_id)

    assert response.status_code == 503


def test_duplicate_payout_is_prevented(security_env):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, "USER_APPROVED")
    paypal_calls = []

    def fake_paypal(**kwargs):
        paypal_calls.append(kwargs)

        return {
            "batch_header": {
                "payout_batch_id": "TEST-BATCH-001",
                "batch_status": "PENDING",
            }
        }

    monkeypatch.setattr(
        payouts,
        "create_sandbox_payout",
        fake_paypal,
    )

    first = pay(client, rule_id)
    second = pay(client, rule_id)

    assert first.status_code == 202, first.text
    assert second.status_code == 409
    assert len(paypal_calls) == 1

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        payout_count = db.scalar(
            select(func.count(PayoutRecord.id))
        )

        assert rule.status == "PAYOUT_SUBMITTED"
        assert payout_count == 1


def test_unknown_payout_is_not_retried(security_env):
    client, SessionLocal, monkeypatch = security_env

    rule_id = create_rule(SessionLocal, "USER_APPROVED")
    paypal_calls = []

    def fake_timeout(**kwargs):
        paypal_calls.append(kwargs)
        raise httpx.ReadTimeout("Simulated network timeout")

    monkeypatch.setattr(
        payouts,
        "create_sandbox_payout",
        fake_timeout,
    )

    first = pay(client, rule_id)
    second = pay(client, rule_id)

    assert first.status_code == 502
    assert second.status_code == 409
    assert len(paypal_calls) == 1

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        payout = db.scalar(
            select(PayoutRecord)
            .where(PayoutRecord.rule_id == rule_id)
        )

        assert rule.status == "PAYOUT_UNKNOWN"
        assert payout is not None
        assert payout.status == "PAYOUT_UNKNOWN"


def create_approval_rule(SessionLocal, recommendations):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Approval Test Developer",
            amount=25.00,
            currency="USD",
            description="Test approval workflow",
            condition="Submit evidence",
            status="AWAITING_USER_APPROVAL",
        )

        db.add(rule)
        db.flush()
        rule_id = rule.id

        for recommendation in recommendations:
            db.add(
                Submission(
                    rule_id=rule_id,
                    description="Test evidence",
                    ai_analysis="AI test result",
                    ai_recommendation=recommendation,
                )
            )

        db.commit()
        return rule_id


def approve(client, rule_id):
    return client.post(
        f"/api/rules/smartpay/{rule_id}/approve",
        headers={"x-approval-token": TEST_TOKEN},
    )


def test_old_approval_cannot_override_new_rejection(
    security_env,
):
    client, SessionLocal, _ = security_env

    rule_id = create_approval_rule(
        SessionLocal,
        ["APPROVE", "REJECT"],
    )

    response = approve(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "AWAITING_USER_APPROVAL"
        )


def test_approval_uses_latest_submission(security_env):
    client, SessionLocal, _ = security_env

    rule_id = create_approval_rule(
        SessionLocal,
        ["REJECT", "APPROVE"],
    )

    response = approve(client, rule_id)

    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "USER_APPROVED"
        )

        assert db.scalar(
            select(func.count(PayoutRecord.id))
        ) == 0


def test_ai_review_requires_operator_token(security_env):
    client, SessionLocal, _ = security_env

    rule_id = create_rule(
        SessionLocal,
        "CONDITION_SUBMITTED",
    )

    response = client.post(
        f"/api/rules/smartpay/{rule_id}/ai-review"
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "CONDITION_SUBMITTED"
        )
