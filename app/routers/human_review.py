
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    SmartPayRule,
    Submission,
    PayoutRecord,
    HumanReviewDecision,
)
from app.schemas import (
    HumanReviewDecisionCreate,
    HumanReviewDecisionResponse,
)
from app.routers.payouts import verify_approval_token


router = APIRouter()


DECISION_STATUSES = {
    "REQUEST_MORE_EVIDENCE": "EVIDENCE_REQUESTED",
    "REJECT": "HUMAN_REJECTED",
}


@router.post(
    "/{rule_id}/human-decision",
    response_model=HumanReviewDecisionResponse,
    status_code=201,
)
def record_human_review(
    rule_id: int,
    decision_data: HumanReviewDecisionCreate,
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # 1. Verify demo operator authorization.
    verify_approval_token(x_approval_token)

    new_status = DECISION_STATUSES[decision_data.decision]

    # 2. Atomically claim a rule requiring human attention.
    result = db.execute(
        update(SmartPayRule)
        .where(
            SmartPayRule.id == rule_id,
            SmartPayRule.status == "NEEDS_REVIEW",
        )
        .values(status=new_status)
    )

    if result.rowcount != 1:
        db.rollback()

        rule = db.get(SmartPayRule, rule_id)

        if rule is None:
            raise HTTPException(
                status_code=404,
                detail="SmartPay rule not found",
            )

        raise HTTPException(
            status_code=409,
            detail="Rule is not awaiting human review",
        )

    # 3. Identify the newest evidence submission.
    submission = db.scalar(
        select(Submission)
        .where(Submission.rule_id == rule_id)
        .order_by(Submission.id.desc())
        .limit(1)
    )

    if (
        submission is None
        or not submission.ai_recommendation
    ):
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="No completed AI review found",
        )

    # 4. Never reopen a rule with an existing payout.
    existing_payout = db.scalar(
        select(PayoutRecord.id).where(
            PayoutRecord.rule_id == rule_id
        )
    )

    if existing_payout is not None:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Rule already has a payout record",
        )

    # 5. Save an audit record.
    review = HumanReviewDecision(
        rule_id=rule_id,
        submission_id=submission.id,
        decision=decision_data.decision,
        reason=decision_data.reason,
        reviewer_id="sandbox-operator",
    )

    db.add(review)

    # 6. Commit the decision and status change together.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Human review decision already recorded or conflicts with existing data",
        )

    db.refresh(review)

    return review
