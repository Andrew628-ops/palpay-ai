from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from app.schemas import AIReviewResponse
from app.models import SmartPayRule, Submission
from app.database import get_db
from app.services.ai import review_submission as ai_review_submission

router = APIRouter()


@router.post("/smartpay/{rule_id}/ai-review", response_model=AIReviewResponse)
def review_smartpay_submission(rule_id: int, db = Depends(get_db)):
    query = select(SmartPayRule).where(SmartPayRule.id == rule_id)
    smart_pay = db.scalar(query)
    if smart_pay is None:
        raise HTTPException(status_code=404, detail='SmartPay not found')
    
    if smart_pay.status != "CONDITION_SUBMITTED":
        raise HTTPException(status_code=400, detail='Rule not ready for review')
    
    submission_query = select(Submission).where(Submission.rule_id == rule_id)
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

    smart_pay.status = "AI_REVIEWED"

    db.commit()

    return {
        "recommendation": result["recommendation"],
        "confidence": result["confidence"],
        "analysis": result["analysis"]
    }