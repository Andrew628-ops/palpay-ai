from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, Literal

class SmartPayRuleCreate(BaseModel):
    recipient_name: str
    amount: float = Field(gt=0)
    currency: str
    description: str
    condition: str

class SmartPayRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipient_name: str
    amount: float = Field(gt=0)
    currency: str
    description: str
    condition: str
    status: str
    ai_confidence: Optional[float] = None
    created_at: datetime

class SubmissionCreate(BaseModel):
    description: str
    file_url: str | None = None

class SubmissionResponse(BaseModel):
    id: int
    rule_id: int
    description: str
    file_url: str | None = None
    ai_analysis: str | None = None
    ai_recommendation: str | None = None 
    submitted_at: datetime

class AIReviewResponse(BaseModel):
    recommendation: str
    confidence: float
    analysis: str


class HumanReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "REQUEST_MORE_EVIDENCE",
        "REJECT"
    ]

    reason: str = Field(
        min_length=10,
        max_length=2000
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 10:
            raise ValueError(
                "Review reason must contain at least 10 characters"
            )

        return value


class HumanReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    submission_id: int
    decision: str
    reason: str
    reviewer_id: str
    created_at: datetime