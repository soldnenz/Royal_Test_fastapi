from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class PaymentInfo(BaseModel):
    payment_id: Optional[str]
    price: Optional[int]
    payment_method: Optional[Literal["cash", "card", "online", "promo"]] = None

class IssuedBy(BaseModel):
    admin_iin: str
    full_name: str

# 👉 Используется при создании подписки (POST /subscriptions)
class SubscriptionCreate(BaseModel):
    user_id: str
    iin: str
    subscription_type: Literal["basic", "pro", "trial"]
    expires_at: datetime
    activation_method: Literal["manual", "payment", "promocode"]
    note: Optional[str]
    duration_days: int
    payment: Optional[PaymentInfo] = None  # issued_by исключён — вставляется на бэке

# 👉 Используется для вывода подписки
class SubscriptionOut(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    iin: str
    subscription_type: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    is_active: bool
    issued_by: IssuedBy
    activation_method: str
    note: Optional[str]
    duration_days: int
    cancelled_at: Optional[datetime]
    cancelled_by: Optional[str]
    cancel_reason: Optional[str]
    payment: Optional[PaymentInfo]

# 👉 Используется для отмены подписки (PUT /subscriptions/cancel)
class SubscriptionCancel(BaseModel):
    subscription_id: str
    cancel_reason: str  # cancelled_by больше не нужен — вставляется на бэке
