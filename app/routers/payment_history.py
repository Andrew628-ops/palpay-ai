from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select, func
from decimal import Decimal
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


@router.get("/summary")
def get_payment_summary(
    x_approval_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Protect analytics with our demo operator token.
    verify_approval_token(x_approval_token)

    # Count all SmartPay rules.
    total_rules = db.scalar(
        select(func.count(SmartPayRule.id))
    ) or 0

    # Count rules awaiting human approval.
    awaiting_approval = db.scalar(
        select(func.count(SmartPayRule.id)).where(
            SmartPayRule.status == "AWAITING_USER_APPROVAL"
        )
    ) or 0

    # Only include payouts confirmed as completed.
    completed_conditions = (
        PayoutRecord.status == "PAYOUT_COMPLETED",
        SmartPayRule.status == "PAID",
    )

    completed_payouts = db.scalar(
        select(func.count(PayoutRecord.id))
        .join(
            SmartPayRule,
            PayoutRecord.rule_id == SmartPayRule.id
        )
        .where(*completed_conditions)
    ) or 0

    # Sum completed USD payments only.
    # Never mix currencies in a single monetary total.
    total_usd = db.scalar(
        select(func.sum(PayoutRecord.amount))
        .join(
            SmartPayRule,
            PayoutRecord.rule_id == SmartPayRule.id
        )
        .where(
            *completed_conditions,
            PayoutRecord.currency == "USD"
        )
    )

    completed_volume_usd = Decimal(
        str(total_usd if total_usd is not None else "0")
    ).quantize(Decimal("0.01"))

    return {
        "total_rules": total_rules,
        "completed_payouts": completed_payouts,
        "awaiting_approval": awaiting_approval,
        "completed_volume_usd": str(completed_volume_usd),
        "environment": "SANDBOX",
    }
