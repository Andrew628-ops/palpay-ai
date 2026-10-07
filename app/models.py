from sqlalchemy import Column, Integer, String, Float, DateTime
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