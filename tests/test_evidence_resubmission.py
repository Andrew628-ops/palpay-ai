
import pytest
import os
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base, SmartPayRule, Submission
from app.routers import rules, ai_review


TEST_TOKEN = "resubmission-test-token"


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'resubmission.db'}",
        connect_args={"check_same_thread": False}
    )

    TestSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestSessionLocal() as db:
            yield db

    def fake_verify_token(token):
        if token != TEST_TOKEN:
            raise HTTPException(403, "Not authorized")

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        rules,
        "verify_approval_token",
        fake_verify_token
    )

    try:
        with TestClient(app) as client:
            yield client, TestSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_existing_rule(SessionLocal, status):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Test Developer",
            amount=100.00,
            currency="USD",
            description="Build a website",
            condition="Submit completed website",
            status=status
        )

        db.add(rule)
        db.flush()

        rule_id = rule.id

        db.add(
            Submission(
                rule_id=rule_id,
                description="Original evidence",
                file_url="",
                ai_analysis="Original AI analysis",
                ai_recommendation="NEEDS_REVIEW"
            )
        )

        db.commit()
        return rule_id


def resubmit(client, rule_id, token=TEST_TOKEN):
    headers = (
        {"x-approval-token": token}
        if token is not None else {}
    )

    return client.post(
        f"/api/rules/smartpay/{rule_id}/resubmit",
        headers=headers,
        json={
            "description": "Improved evidence",
            "file_url": ""
        }
    )


@pytest.mark.parametrize(
    "initial_status",
    ["NEEDS_REVIEW", "AI_REJECTED"]
)
def test_resubmission_preserves_history(
    test_env, initial_status
):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal, initial_status
    )

    response = resubmit(client, rule_id)

    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        submissions = db.scalars(
            select(Submission)
            .where(Submission.rule_id == rule_id)
            .order_by(Submission.id)
        ).all()

        assert rule.status == "CONDITION_SUBMITTED"
        assert len(submissions) == 2

        assert submissions[0].description == "Original evidence"
        assert submissions[0].ai_analysis == "Original AI analysis"

        assert submissions[1].description == "Improved evidence"
        assert submissions[1].ai_analysis is None


def test_duplicate_resubmission_rejected(test_env):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal, "NEEDS_REVIEW"
    )

    assert resubmit(client, rule_id).status_code == 201

    second_response = resubmit(client, rule_id)

    assert second_response.status_code == 409

    with SessionLocal() as db:
        submissions = db.scalars(
            select(Submission).where(
                Submission.rule_id == rule_id
            )
        ).all()

        assert len(submissions) == 2


def test_resubmission_requires_authorization(test_env):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal, "NEEDS_REVIEW"
    )

    response = resubmit(client, rule_id, token=None)

    assert response.status_code == 403

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)
        assert rule.status == "NEEDS_REVIEW"


def test_paid_rule_cannot_be_resubmitted(test_env):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal, "PAID"
    )

    response = resubmit(client, rule_id)

    assert response.status_code == 409

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)
        assert rule.status == "PAID"


def test_ai_reviews_latest_submission(test_env, monkeypatch):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal, "NEEDS_REVIEW"
    )

    response = resubmit(client, rule_id)
    assert response.status_code == 201

    received = {}

    # Gemini is mocked: no external AI request.
    def fake_ai_review(
        condition,
        submission_description,
        file_url
    ):
        received["description"] = submission_description

        return {
            "recommendation": "APPROVE",
            "confidence": 95.0,
            "analysis": "Updated evidence meets the condition"
        }

    monkeypatch.setattr(
        ai_review,
        "ai_review_submission",
        fake_ai_review
    )

    response = client.post(
        f"/api/rules/smartpay/{rule_id}/ai-review",
        headers={
            "x-approval-token": os.environ["APPROVAL_TOKEN"]
        }
    )

    assert response.status_code == 200, response.text

    assert received["description"] == "Improved evidence"

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        submissions = db.scalars(
            select(Submission)
            .where(Submission.rule_id == rule_id)
            .order_by(Submission.id)
        ).all()

        assert rule.status == "AWAITING_USER_APPROVAL"

        assert submissions[0].ai_analysis == "Original AI analysis"
        assert submissions[1].ai_recommendation == "APPROVE"


def test_ai_review_rejects_outdated_result(
    test_env, monkeypatch
):
    client, SessionLocal = test_env

    rule_id = create_existing_rule(
        SessionLocal,
        "NEEDS_REVIEW"
    )

    response = resubmit(client, rule_id)
    assert response.status_code == 201

    with SessionLocal() as db:

        def fake_ai_review(
            condition,
            submission_description,
            file_url
        ):
            # Simulate another review changing
            # the rule while Gemini is processing.
            changed = db.execute(
                update(SmartPayRule)
                .where(
                    SmartPayRule.id == rule_id,
                    SmartPayRule.status == "CONDITION_SUBMITTED"
                )
                .values(status="NEEDS_REVIEW")
            )

            assert changed.rowcount == 1
            db.commit()

            return {
                "recommendation": "APPROVE",
                "confidence": 0.95,
                "analysis": "Outdated AI result"
            }

        monkeypatch.setattr(
            ai_review,
            "ai_review_submission",
            fake_ai_review
        )

        with pytest.raises(HTTPException) as error:
            ai_review.review_smartpay_submission(
                rule_id=rule_id,
                x_approval_token=os.environ["APPROVAL_TOKEN"],
                db=db
            )

        assert error.value.status_code == 409

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        latest_submission = db.scalar(
            select(Submission)
            .where(Submission.rule_id == rule_id)
            .order_by(Submission.id.desc())
            .limit(1)
        )

        assert rule.status == "NEEDS_REVIEW"
        assert latest_submission.ai_recommendation is None
