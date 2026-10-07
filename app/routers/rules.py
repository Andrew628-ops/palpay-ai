from fastapi import APIRouter, Depends, HTTPException
from app.schemas import SmartPayRuleCreate, SmartPayRuleResponse, SubmissionCreate, SubmissionResponse, AIReviewResponse
from app.database import get_db
from app.models import SmartPayRule, Submission
from typing import List
from sqlalchemy import select

router = APIRouter()

@router.post("/smartpay", response_model=SmartPayRuleResponse, status_code=201)
def create_payment(payment: SmartPayRuleCreate, db = Depends(get_db)):
    new_payment = SmartPayRule(recipient_name=payment.recipient_name, amount=payment.amount, currency=payment.currency, description=payment.description, condition=payment.condition)
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment

@router.get("/smartpay", response_model=List[SmartPayRuleResponse])
def get_payment(db = Depends(get_db)):
    query = select(SmartPayRule)
    payment_record = db.scalars(query).all()
    return payment_record

@router.get("/smartpay/{smartpay_id}", response_model=SmartPayRuleResponse)
def get_smart_pay_id(smartpay_id: int, db = Depends(get_db)):
    query = select(SmartPayRule).where(SmartPayRule.id == smartpay_id)
    payment_id = db.scalar(query)
    if not payment_id:
        raise HTTPException(status_code=404, detail='SmartPay rule not found')
    return payment_id

@router.post("/smartpay/{rule_id}/submit", response_model=SubmissionResponse)
def get_submission(rule_id: int, submission: SubmissionCreate, db=Depends(get_db)):
    query = select(SmartPayRule).where(SmartPayRule.id == rule_id)
    smart_pay = db.scalar(query)
    if smart_pay is None:
        raise HTTPException(status_code=404, detail='SmartPay not found')
    
    print("STATUS:", repr(smart_pay.status))
    if smart_pay.status != "WAITING_FOR_CONDITION":
        raise HTTPException(status_code=400, detail="Submission not allowed for this rule")
    
    new_submission = Submission(rule_id=rule_id, description=submission.description, file_url=submission.file_url)
    db.add(new_submission)
    smart_pay.status = "CONDITION_SUBMITTED"
    db.commit()
    db.refresh(new_submission)
    return new_submission


@router.post("/smartpay/{rule_id}/ai-review", response_model=AIReviewResponse)
def review_submission(rule_id: int, db = Depends(get_db)):
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
    
    analysis = (
    f"The submitted evidence appears to satisfy "
    f"the condition: {smart_pay.condition}"
    )

    recommendation = "APPROVE"
    confidence = 0.92

    submission.ai_analysis = analysis
    submission.ai_recommendation = recommendation

    smart_pay.ai_confidence = confidence

    smart_pay.status = "AI_REVIEWED"

    db.commit()

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "analysis": analysis
    }