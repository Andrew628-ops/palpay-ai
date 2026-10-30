
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SmartPayRule
from app.routers.payouts import verify_approval_token

router = APIRouter()

REVIEW_STATUSES = (
    "CONDITION_SUBMITTED",
    "NEEDS_REVIEW",
    "AI_REJECTED",
    "AWAITING_USER_APPROVAL",
)

REVIEW_STAGES = {
    "CONDITION_SUBMITTED": "READY_FOR_AI_REVIEW",
    "NEEDS_REVIEW": "NEEDS_HUMAN_ATTENTION",
    "AI_REJECTED": "EVIDENCE_REJECTED",
    "AWAITING_USER_APPROVAL": "AWAITING_HUMAN_APPROVAL",
}

@router.get("/queue")
def get_review_queue(
    limit: int = Query(default=20, ge=1, le=100),
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Demo operator authorization
    verify_approval_token(x_approval_token)

    statement = (
        select(SmartPayRule)
        .where(SmartPayRule.status.in_(REVIEW_STATUSES))
        .order_by(
            SmartPayRule.created_at.desc(),
            SmartPayRule.id.desc()
        )
        .limit(limit)
    )

    rules = db.scalars(statement).all()

    reviews = []

    for rule in rules:
        review_stage = REVIEW_STAGES[rule.status]

        reviews.append({
            "rule_id": rule.id,
            "recipient_name": rule.recipient_name,
            "amount": rule.amount,
            "currency": rule.currency,
            "status": rule.status,
            "review_stage": review_stage,
            "created_at": (
                rule.created_at.isoformat()
                if rule.created_at else None
            ),
        })

    return {
        "count": len(reviews),
        "reviews": reviews,
    }
