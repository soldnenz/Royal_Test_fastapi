from pydantic import BaseModel, Field, constr
from typing import Optional, Literal, List
from datetime import datetime

class PromoCodeBase(BaseModel):
    code: Optional[constr(strip_whitespace=True, min_length=3, max_length=32)] = None
    subscription_type: Literal["economy", "vip", "royal", "school", "demo"]
    duration_days: int = Field(..., gt=0, le=365)
    is_active: bool = True
    created_by_user_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    usage_limit: int = Field(1, gt=0)

class PromoCodeCreate(PromoCodeBase):
    amount: Optional[float] = Field(0, ge=0, le=1_000_000)

class PromoCodeActivate(BaseModel):
    promo_code: constr(strip_whitespace=True, min_length=3, max_length=32)

class PromoCodeOut(PromoCodeBase):
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    used_by: Optional[List[str]] = None
    purchase_amount: Optional[float] = None

class PromoCodeAdminUpdate(BaseModel):
    subscription_type: Optional[Literal["economy", "vip", "royal", "school", "demo"]]
    duration_days: Optional[int] = Field(None, gt=0, le=365)
    is_active: Optional[bool]
    expires_at: Optional[datetime]
    usage_limit: Optional[int] = Field(None, gt=0)
