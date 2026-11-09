
from decimal import Decimal

import pytest
from fastapi import HTTPException
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
    HumanReviewDecision,
)
from app.routers import human_review


TEST_TOKEN = "human-review-test-only"


@pytest.fixture
def review_env(tmp_path, monkeypatch):
    # Each test gets its own temporary database.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'human_review.db'}",
        connect_args={"check_same_thread": False},
    )

    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as db:
            yield db

    # Use a fake token checker during tests.
    def fake_verify_token(token):
        if token != TEST_TOKEN:
            raise HTTPException(
                status_code=403,
                detail="Not authorized",
            )

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        human_review,
        "verify_approval_token",
        fake_verify_token,
    )

    try:
        with TestClient(app) as client:
            yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_review_rule(
    SessionLocal,
    *,
    status="NEEDS_REVIEW",
    with_submission=True,
    with_ai_review=True,
    with_payout=False,
):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Test Developer",
            amount=100.00,
            currency="USD",
            description="Build a responsive website",
            condition="Submit a completed homepage",
            status=status,
        )

        db.add(rule)
        db.flush()

        rule_id = rule.id
        submission_id = None

        if with_submission:
            submission = Submission(
                rule_id=rule_id,
                description="Website evidence",
                file_url="",
                ai_analysis=(
                    "Manual inspection required"
                    if with_ai_review else None
                ),
                ai_recommendation=(
                    "NEEDS_REVIEW"
                    if with_ai_review else None
                ),
            )

            db.add(submission)
            db.flush()
            submission_id = submission.id

        if with_payout:
            db.add(
                PayoutRecord(
                    rule_id=rule_id,
                    sender_batch_id=f"human-review-{rule_id}",
                    receiver_email="sandbox@example.com",
                    amount=Decimal("100.00"),
                    currency="USD",
                    status="PAYOUT_SUBMITTED",
                )
            )

        db.commit()

        return rule_id, submission_id


def send_decision(
    client,
    rule_id,
    *,
    decision="REQUEST_MORE_EVIDENCE",
    reason="The submitted website needs further verification.",
    token=TEST_TOKEN,
):
    headers = (
        {"x-approval-token": token}
        if token is not None else {}
    )

    return client.post(
        f"/api/reviews/{rule_id}/human-decision",
        headers=headers,
        json={
            "decision": decision,
            "reason": reason,
        },
    )


@pytest.mark.parametrize(
    "decision,expected_status",
    [
        ("REQUEST_MORE_EVIDENCE", "EVIDENCE_REQUESTED"),
        ("REJECT", "HUMAN_REJECTED"),
    ],
)
def test_human_decision_records_audit(
    review_env, decision, expected_status
):
    client, SessionLocal = review_env

    rule_id, submission_id = create_review_rule(
        SessionLocal
    )

    response = send_decision(
        client,
        rule_id,
        decision=decision,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["rule_id"] == rule_id
    assert data["submission_id"] == submission_id
    assert data["decision"] == decision
    assert data["reviewer_id"] == "sandbox-operator"
    assert data["created_at"] is not None

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        reviews = db.scalars(
            select(HumanReviewDecision).where(
                HumanReviewDecision.rule_id == rule_id
            )
        ).all()

        assert rule.status == expected_status
        assert len(reviews) == 1

        # A human review must never create a payout.
        assert db.scalar(
            select(PayoutRecord).where(
                PayoutRecord.rule_id == rule_id
            )
        ) is None


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_human_review_requires_authorization(
    review_env, token
):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(SessionLocal)

    response = send_decision(
        client,
        rule_id,
        token=token,
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "NEEDS_REVIEW"
        )


def test_duplicate_human_decision_is_rejected(review_env):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(SessionLocal)

    first = send_decision(client, rule_id)
    second = send_decision(client, rule_id)

    assert first.status_code == 201
    assert second.status_code == 409

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count(HumanReviewDecision.id))
        )

        assert count == 1


def test_paid_rule_cannot_be_reviewed(review_env):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(
        SessionLocal,
        status="PAID",
    )

    response = send_decision(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == "PAID"


@pytest.mark.parametrize(
    "options",
    [
        {"with_submission": False},
        {"with_ai_review": False},
    ],
)
def test_requires_completed_ai_review(review_env, options):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(
        SessionLocal,
        **options,
    )

    response = send_decision(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "NEEDS_REVIEW"
        )


def test_existing_payout_blocks_human_decision(review_env):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(
        SessionLocal,
        with_payout=True,
    )

    response = send_decision(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "NEEDS_REVIEW"
        )

        count = db.scalar(
            select(func.count(HumanReviewDecision.id))
        )

        assert count == 0


@pytest.mark.parametrize(
    "decision,reason",
    [
        ("APPROVE_PAYMENT", "This should not be allowed."),
        ("REJECT", "  "),
    ],
)
def test_invalid_human_decision_is_rejected(
    review_env, decision, reason
):
    client, SessionLocal = review_env

    rule_id, _ = create_review_rule(SessionLocal)

    response = send_decision(
        client,
        rule_id,
        decision=decision,
        reason=reason,
    )

    assert response.status_code == 422

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "NEEDS_REVIEW"
        )


def test_nonexistent_rule_returns_404(review_env):
    client, _ = review_env

    response = send_decision(client, 99999)

    assert response.status_code == 404
