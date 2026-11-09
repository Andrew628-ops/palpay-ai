
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
    HumanReviewDecision,
    PayoutRecord,
)
from app.routers import (
    human_review,
    review_queue,
    rules,
)


TEST_TOKEN = "review-flow-test-token"
HEADERS = {"x-approval-token": TEST_TOKEN}


@pytest.fixture
def flow_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'review_flow.db'}",
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

    for module in (human_review, review_queue, rules):
        monkeypatch.setattr(
            module,
            "verify_approval_token",
            fake_verify_token,
        )

    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def seed_rule(SessionLocal, status="NEEDS_REVIEW"):
    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Test Developer",
            amount=25.00,
            currency="USD",
            description="Create a responsive homepage",
            condition="Submit completed homepage evidence",
            status=status,
        )

        db.add(rule)
        db.flush()

        submission = Submission(
            rule_id=rule.id,
            description="Initial homepage evidence",
            file_url="https://example.com/initial",
            ai_analysis="Manual inspection required",
            ai_recommendation="NEEDS_REVIEW",
        )

        db.add(submission)
        db.flush()

        rule_id = rule.id
        submission_id = submission.id

        db.commit()

        return rule_id, submission_id


def send_decision(client, rule_id, decision):
    return client.post(
        f"/api/reviews/{rule_id}/human-decision",
        headers=HEADERS,
        json={
            "decision": decision,
            "reason": (
                "The submitted evidence requires "
                "additional verification."
            ),
        },
    )


def send_resubmission(client, rule_id, headers=HEADERS):
    return client.post(
        f"/api/rules/smartpay/{rule_id}/resubmit",
        headers=headers,
        json={
            "description": "Improved homepage evidence",
            "file_url": "https://example.com/improved",
        },
    )


def get_queue(client, headers=HEADERS):
    return client.get(
        "/api/reviews/queue",
        headers=headers,
    )


def test_queue_classifies_review_statuses(flow_env):
    client, SessionLocal = flow_env

    needs_review_id, _ = seed_rule(
        SessionLocal, "NEEDS_REVIEW"
    )
    requested_id, _ = seed_rule(
        SessionLocal, "EVIDENCE_REQUESTED"
    )
    rejected_id, _ = seed_rule(
        SessionLocal, "HUMAN_REJECTED"
    )

    response = get_queue(client)

    assert response.status_code == 200, response.text

    reviews = {
        item["rule_id"]: item
        for item in response.json()["reviews"]
    }

    assert reviews[needs_review_id]["review_stage"] == (
        "NEEDS_HUMAN_ATTENTION"
    )

    assert reviews[requested_id]["review_stage"] == (
        "AWAITING_RESUBMISSION"
    )

    assert rejected_id not in reviews


def test_request_more_evidence_then_resubmit(flow_env):
    client, SessionLocal = flow_env

    rule_id, original_submission_id = seed_rule(
        SessionLocal
    )

    decision = send_decision(
        client, rule_id, "REQUEST_MORE_EVIDENCE"
    )

    assert decision.status_code == 201, decision.text
    assert decision.json()["submission_id"] == (
        original_submission_id
    )

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "EVIDENCE_REQUESTED"
        )

    queue = get_queue(client)
    assert queue.status_code == 200

    item = next(
        item
        for item in queue.json()["reviews"]
        if item["rule_id"] == rule_id
    )

    assert item["review_stage"] == "AWAITING_RESUBMISSION"

    resubmit = send_resubmission(client, rule_id)

    assert resubmit.status_code in (200, 201), (
        resubmit.text
    )

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)

        submissions = db.scalars(
            select(Submission)
            .where(Submission.rule_id == rule_id)
            .order_by(Submission.id)
        ).all()

        assert rule.status == "CONDITION_SUBMITTED"
        assert len(submissions) == 2

        assert submissions[0].id == original_submission_id
        assert submissions[0].ai_recommendation == (
            "NEEDS_REVIEW"
        )

        assert submissions[1].description == (
            "Improved homepage evidence"
        )

        assert submissions[1].ai_recommendation is None

        audit_count = db.scalar(
            select(func.count(HumanReviewDecision.id))
            .where(HumanReviewDecision.rule_id == rule_id)
        )

        payout_count = db.scalar(
            select(func.count(PayoutRecord.id))
            .where(PayoutRecord.rule_id == rule_id)
        )

        assert audit_count == 1
        assert payout_count == 0

    queue = get_queue(client)

    item = next(
        item
        for item in queue.json()["reviews"]
        if item["rule_id"] == rule_id
    )

    assert item["review_stage"] == "READY_FOR_AI_REVIEW"


def test_human_rejection_closes_review_cycle(flow_env):
    client, SessionLocal = flow_env

    rule_id, _ = seed_rule(SessionLocal)

    decision = send_decision(
        client, rule_id, "REJECT"
    )

    assert decision.status_code == 201, decision.text

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "HUMAN_REJECTED"
        )

    queue = get_queue(client)
    assert queue.status_code == 200

    queued_ids = {
        item["rule_id"]
        for item in queue.json()["reviews"]
    }

    assert rule_id not in queued_ids

    resubmit = send_resubmission(client, rule_id)

    assert resubmit.status_code == 409

    history = client.get(
        f"/api/reviews/{rule_id}/human-decisions",
        headers=HEADERS,
    )

    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["decisions"][0]["decision"] == (
        "REJECT"
    )

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "HUMAN_REJECTED"
        )


def test_second_resubmission_is_blocked(flow_env):
    client, SessionLocal = flow_env

    rule_id, _ = seed_rule(SessionLocal)

    decision = send_decision(
        client, rule_id, "REQUEST_MORE_EVIDENCE"
    )

    assert decision.status_code == 201

    first = send_resubmission(client, rule_id)
    second = send_resubmission(client, rule_id)

    assert first.status_code in (200, 201)
    assert second.status_code == 409

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count(Submission.id))
            .where(Submission.rule_id == rule_id)
        )

        assert count == 2


def test_unauthorized_requests_do_not_change_state(
    flow_env,
):
    client, SessionLocal = flow_env

    rule_id, _ = seed_rule(SessionLocal)

    queue = get_queue(client, headers={})

    decision = client.post(
        f"/api/reviews/{rule_id}/human-decision",
        json={
            "decision": "REJECT",
            "reason": "This is an unauthorized request.",
        },
    )

    resubmit = send_resubmission(
        client, rule_id, headers={}
    )

    assert queue.status_code == 403
    assert decision.status_code == 403
    assert resubmit.status_code == 403

    with SessionLocal() as db:
        assert db.get(SmartPayRule, rule_id).status == (
            "NEEDS_REVIEW"
        )

        count = db.scalar(
            select(func.count(HumanReviewDecision.id))
            .where(HumanReviewDecision.rule_id == rule_id)
        )

        assert count == 0
