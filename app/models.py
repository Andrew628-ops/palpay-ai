from datetime import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column

class SmartPayRule(Base):
    __tablename__ = "smartpay_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    condition: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    ai_confidence: Mapped[float] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)