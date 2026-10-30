from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from app.schemas import AIReviewResponse
from app.models import SmartPayRule, Submission
from app.database import get_db
from app.services.ai import review_submission as ai_review_submission
import os
import secrets
from dotenv import load_dotenv
from fastapi import Header
from sqlalchemy import update

load_dotenv()

router = APIRouter()


@router.post("/smartpay/{rule_id}/ai-review", response_model=AIReviewResponse)
def review_smartpay_submission(rule_id: int, db=Depends(get_db)):
    query = select(SmartPayRule).where(SmartPayRule.id == rule_id)
    smart_pay = db.scalar(query)

    if smart_pay is None:
        raise HTTPException(status_code=404, detail="SmartPay not found")

    if smart_pay.status != "CONDITION_SUBMITTED":
        raise HTTPException(status_code=400, detail="Rule not ready for review")

    submission_query = (
    select(Submission)
    .where(Submission.rule_id == rule_id)
    .order_by(Submission.id.desc())
    .limit(1)
    )

    submission = db.scalar(submission_query)

    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    result = ai_review_submission(
        condition=smart_pay.condition,
        submission_description=submission.description,
        file_url=submission.file_url
    )

    submission.ai_analysis = result["analysis"]
    submission.ai_recommendation = result["recommendation"]

    smart_pay.ai_confidence = result["confidence"]

    if result["recommendation"] == "APPROVE":
        smart_pay.status = "AWAITING_USER_APPROVAL"

    elif result["recommendation"] == "REJECT":
        smart_pay.status = "AI_REJECTED"

    else:
        smart_pay.status = "NEEDS_REVIEW"

    db.commit()

    return {
        "recommendation": result["recommendation"],
        "confidence": result["confidence"],
        "analysis": result["analysis"]
    }



@router.post("/smartpay/{rule_id}/approve")
def approve_smartpay(rule_id: int, x_approval_token: str | None = Header(default=None), db=Depends(get_db)):

    expected_token = os.getenv("APPROVAL_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="Approval is not configured"
        )

    if not x_approval_token or not secrets.compare_digest(
        x_approval_token, expected_token
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to approve"
        )

    smart_pay = db.get(SmartPayRule, rule_id)

    if smart_pay is None:
        raise HTTPException(
            status_code=404,
            detail="SmartPay rule not found"
        )

    if smart_pay.status != "AWAITING_USER_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail="SmartPay rule is not awaiting approval"
        )

    submission_query = (
        select(Submission)
        .where(Submission.rule_id == rule_id)
    )

    submission = db.scalar(submission_query)

    if submission is None or submission.ai_recommendation != "APPROVE":
        raise HTTPException(
            status_code=409,
            detail="No AI approval recommendation found"
        )

    statement = (
        update(SmartPayRule)
        .where(
            SmartPayRule.id == rule_id,
            SmartPayRule.status == "AWAITING_USER_APPROVAL"
        )
        .values(status="USER_APPROVED")
    )

    result = db.execute(statement)

    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Approval already processed or status changed"
        )

    db.commit()

    return {
        "rule_id": rule_id,
        "status": "USER_APPROVED",
        "message": "Human approval recorded. No payment has been sent."
    }
