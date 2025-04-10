from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class ReferralCreate(BaseModel):
    code: str
    type: str  # "school" или "user"
    owner_user_id: Optional[str] = None
    owner_school_id: Optional[str] = None
    rate: Dict  # {'type': 'percent', 'value': 10}
    description: str
    active: bool = True
    comment: Optional[str] = None
    referred_by: Optional[str] = None  # Реферальный код пригласившего
    referred_use: Optional[bool] = False  # Использовал ли реферальный код
    money: Optional[float] = Field(None, description="Сумма пользователя (ограничена двумя знаками после запятой)")
    created_by: str

    class Config:
        schema_extra = {
            "example": {
                "code": "REF123",
                "type": "user",
                "owner_user_id": "user123",
                "rate": {"type": "percent", "value": 10},
                "description": "Описание рефералки",
                "active": True,
                "created_by": "admin",
                "referred_by": "REF987",
                "referred_use": True,
                "money": 100.00
            }
        }

    @validator("rate")
    def validate_rate(cls, v):
        return Referral.validate_rate(v)
