
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select

from app.database import get_db
from app.models import SmartPayRule, Submission
from app.routers.payouts import verify_approval_token

router = APIRouter()


@router.get("/smartpay/{rule_id}/submissions")
def get_submission_history(
    rule_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    x_approval_token: str | None = Header(default=None),
    db=Depends(get_db),
):
    verify_approval_token(x_approval_token)

    rule = db.get(SmartPayRule, rule_id)

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="SmartPay rule not found"
        )

    statement = (
        select(Submission)
        .where(Submission.rule_id == rule_id)
        .order_by(Submission.id.desc())
        .limit(limit)
    )

    submissions = db.scalars(statement).all()

    history = []

    for submission in submissions:
        history.append({
            "submission_id": submission.id,
            "description": submission.description,
            "file_url": submission.file_url,
            "ai_analysis": submission.ai_analysis,
            "ai_recommendation": submission.ai_recommendation,
            "submitted_at": (
                submission.submitted_at.isoformat()
                if submission.submitted_at else None
            ),
        })

    return {
        "rule_id": rule_id,
        "count": len(history),
        "submissions": history,
    }
