from fastapi import APIRouter, Depends, HTTPException, Header
from app.schemas import SmartPayRuleCreate, SmartPayRuleResponse, SubmissionCreate, SubmissionResponse, AIReviewResponse
from app.database import get_db
from app.models import SmartPayRule, Submission
from typing import List
from app.routers.payouts import verify_approval_token
from sqlalchemy import select, update

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


@router.post(
    "/smartpay/{rule_id}/resubmit",
    response_model=SubmissionResponse,
    status_code=201
)
def resubmit_evidence(
    rule_id: int,
    submission: SubmissionCreate,
    x_approval_token: str | None = Header(default=None),
    db=Depends(get_db)
):
    # Temporary operator authentication for our Sandbox demo.
    verify_approval_token(x_approval_token)

    description = submission.description.strip()

    if not description:
        raise HTTPException(
            status_code=422,
            detail="Evidence description cannot be empty"
        )

    # Change the status only if the rule is eligible.
    # The conditional update helps prevent duplicate resubmissions.
    statement = (
        update(SmartPayRule)
        .where(
            SmartPayRule.id == rule_id,
            SmartPayRule.status.in_(
                (
                    "NEEDS_REVIEW",
                    "AI_REJECTED",
                    "EVIDENCE_REQUESTED",
                )
            )
        )
        .values(status="CONDITION_SUBMITTED")
    )

    result = db.execute(statement)

    if result.rowcount != 1:
        db.rollback()

        rule = db.get(SmartPayRule, rule_id)

        if rule is None:
            raise HTTPException(
                status_code=404,
                detail="SmartPay rule not found"
            )

        raise HTTPException(
            status_code=409,
            detail="Rule is not eligible for resubmission"
        )

    # Create a NEW submission instead of overwriting the old one.
    new_submission = Submission(
        rule_id=rule_id,
        description=description,
        file_url=submission.file_url
    )

    db.add(new_submission)

    # Both changes commit together.
    db.commit()
    db.refresh(new_submission)

    return new_submission

