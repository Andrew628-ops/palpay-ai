
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import (
    Base,
    SmartPayRule,
    Submission,
    HumanReviewDecision,
)
from app.routers import human_review


TEST_TOKEN = "history-test-token"


@pytest.fixture
def history_env(tmp_path, monkeypatch):
    # An isolated database for each test.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'history.db'}",
        connect_args={"check_same_thread": False},
    )

    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

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
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_rule(db):
    rule = SmartPayRule(
        recipient_name="Test Developer",
        amount=50.00,
        currency="USD",
        description="Test human review history",
        condition="Submit completed work",
        status="NEEDS_REVIEW",
    )

    db.add(rule)
    db.flush()

    return rule


def create_decision(db, rule, decision, created_at):
    submission = Submission(
        rule_id=rule.id,
        description="Evidence for human review",
        file_url="",
        ai_analysis="Manual review required",
        ai_recommendation="NEEDS_REVIEW",
    )

    db.add(submission)
    db.flush()

    review = HumanReviewDecision(
        rule_id=rule.id,
        submission_id=submission.id,
        decision=decision,
        reason="The evidence requires manual verification.",
        reviewer_id="sandbox-operator",
        created_at=created_at,
    )

    db.add(review)
    db.flush()

    return review.id


def load_history(client, rule_id, token=TEST_TOKEN, limit=20):
    headers = (
        {"x-approval-token": token}
        if token is not None else {}
    )

    return client.get(
        f"/api/reviews/{rule_id}/human-decisions",
        headers=headers,
        params={"limit": limit},
    )


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_history_requires_authorization(history_env, token):
    client, TestingSession = history_env

    with TestingSession() as db:
        rule_id = create_rule(db).id
        db.commit()

    response = load_history(client, rule_id, token=token)

    assert response.status_code == 403


def test_empty_history(history_env):
    client, TestingSession = history_env

    with TestingSession() as db:
        rule_id = create_rule(db).id
        db.commit()

    response = load_history(client, rule_id)

    assert response.status_code == 200
    assert response.json() == {
        "rule_id": rule_id,
        "count": 0,
        "decisions": [],
    }


def test_history_is_ordered_and_rule_scoped(history_env):
    client, TestingSession = history_env

    with TestingSession() as db:
        first_rule = create_rule(db)
        first_rule_id = first_rule.id

        old_id = create_decision(
            db,
            first_rule,
            "REQUEST_MORE_EVIDENCE",
            datetime(2026, 10, 20, 10, 0),
        )

        new_id = create_decision(
            db,
            first_rule,
            "REJECT",
            datetime(2026, 10, 22, 10, 0),
        )

        # This decision belongs to another rule.
        other_rule = create_rule(db)

        create_decision(
            db,
            other_rule,
            "REJECT",
            datetime(2026, 10, 23, 10, 0),
        )

        db.commit()

    response = load_history(client, first_rule_id)

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2

    # Newest decision first.
    assert [
        item["decision_id"]
        for item in data["decisions"]
    ] == [new_id, old_id]

    assert all(
        item["reviewer_id"] == "sandbox-operator"
        for item in data["decisions"]
    )

    # A history read must not change the rule.
    with TestingSession() as db:
        assert db.get(
            SmartPayRule,
            first_rule_id,
        ).status == "NEEDS_REVIEW"


def test_missing_rule_returns_404(history_env):
    client, _ = history_env

    response = load_history(client, 99999)

    assert response.status_code == 404


@pytest.mark.parametrize("limit", [0, 101])
def test_invalid_history_limit(history_env, limit):
    client, TestingSession = history_env

    with TestingSession() as db:
        rule_id = create_rule(db).id
        db.commit()

    response = load_history(
        client,
        rule_id,
        limit=limit,
    )

    assert response.status_code == 422
