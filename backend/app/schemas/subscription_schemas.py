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
    subscription_type: Literal["Demo", "economy", "Vip", "Royal"]
    expires_at: datetime
    activation_method: Literal["manual", "payment", "promocode", "gift"]  # Добавлен "gift"
    note: Optional[str]
    duration_days: int
    payment: Optional[PaymentInfo] = None  # issued_by исключён — вставляется на бэке
    promo_code: Optional[str] = None  # Новый параметр для промокода
    referred_by: Optional[str] = None  # Новый параметр для реферала
    gift: Optional[bool] = False  # Новый параметр для подарочных подписок

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
    promo_code: Optional[str]  # Для вывода промокода, если он был использован
    referred_by: Optional[str]  # Для вывода реферала, если он был использован
    gift: Optional[bool]  # Для вывода, если подписка была подарочной

# 👉 Используется для отмены подписки (PUT /subscriptions/cancel)
class SubscriptionCancel(BaseModel):
    subscription_id: str
    cancel_reason: str  # cancelled_by больше не нужен — вставляется на бэке
