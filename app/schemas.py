from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

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