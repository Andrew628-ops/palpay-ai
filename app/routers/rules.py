from fastapi import APIRouter, Depends
from app.schemas import SmartPayRuleCreate, SmartPayRuleResponse
from app.database import get_db
from app.models import SmartPayRule

router = APIRouter()

@router.post("/smartpay", response_model=SmartPayRuleResponse)
def create_payment(payment: SmartPayRuleCreate, db = Depends(get_db)):
    new_payment = SmartPayRule(recipient_name=payment.recipient_name, amount=payment.amount, currency=payment.currency, description=payment.description, condition=payment.condition)
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment