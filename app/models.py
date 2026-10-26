from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Numeric, Text
from datetime import datetime, timezone

from app.database import Base


class SmartPayRule(Base):
    __tablename__ = "smart_pay_rules"

    id = Column(Integer, primary_key=True, index=True)
    recipient_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    description = Column(String, nullable=False)
    condition = Column(String, nullable=False)

    status = Column(
        String,
        default="WAITING_FOR_CONDITION",
        nullable=False
    )

    ai_confidence = Column(Float, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class Submission(Base):
    __tablename__ = "smart_pay_submissions"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("smart_pay_rules.id"), index=True, nullable=False)
    description = Column(String, nullable=False)
    file_url = Column(String, nullable=True)
    ai_analysis = Column(String, nullable=True)
    ai_recommendation = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)



class PayoutRecord(Base):
    __tablename__ = "smart_pay_payouts"

    id = Column(Integer, primary_key=True, index=True)

    rule_id = Column(
        Integer,
        ForeignKey("smart_pay_rules.id"),
        nullable=False,
        unique=True
    )

    sender_batch_id = Column(
        String,
        nullable=False,
        unique=True
    )

    receiver_email = Column(String, nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)

    currency = Column(String(3), nullable=False)

    status = Column(
        String,
        default="PAYOUT_REQUESTED",
        nullable=False
    )

    paypal_batch_id = Column(String, nullable=True)

    paypal_batch_status = Column(String, nullable=True)

    paypal_item_status = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )



class PayPalWebhookEvent(Base):
    __tablename__ = "paypal_webhook_events"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)

    status = Column(
        String,
        default="RECEIVED",
        nullable=False
    )

    received_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
