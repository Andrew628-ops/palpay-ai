from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class SmartPayRuleCreate(BaseModel):
    reciepient_name: str
    amount: float = Field(gt=0)
    currency: str
    description: str
    condition: str

class SmartPayRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reciepient_name: str
    amount: float = Field(gt=0)
    currency: str
    description: str
    condition: str
    status: str
    ai_confidence: float
    created_at: datetime