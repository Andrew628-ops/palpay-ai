from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SmartPayRule, PayoutRecord
from app.routers.payouts import verify_approval_token


router = APIRouter()


@router.get("/history")
def get_payment_history(
    limit: int = Query(default=20, ge=1, le=100),
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Demo operator authorization
    verify_approval_token(x_approval_token)

    statement = (
        select(PayoutRecord, SmartPayRule)
        .join(
            SmartPayRule,
            PayoutRecord.rule_id == SmartPayRule.id
        )
        .order_by(
            PayoutRecord.created_at.desc(),
            PayoutRecord.id.desc()
        )
        .limit(limit)
    )

    records = db.execute(statement).all()

    payments = []

    for payout, rule in records:
        payments.append({
            "rule_id": rule.id,
            "recipient_name": rule.recipient_name,
            "amount": str(payout.amount),
            "currency": payout.currency,
            "rule_status": rule.status,
            "payout_status": payout.status,
            "created_at": (
                payout.created_at.isoformat()
                if payout.created_at else None
            )
        })

    return {
        "count": len(payments),
        "payments": payments
    }