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
    file_url: str

class SubmissionResponse(BaseModel):
    id: int
    rule_id: int
    description: str
    file_url: str
    ai_analysis: str | None
    ai_recommendation: str | None
    submitted_at: datetime