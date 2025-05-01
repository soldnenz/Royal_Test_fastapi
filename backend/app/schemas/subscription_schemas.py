from pydantic import BaseModel, Field, constr
from typing import Optional, Literal
from datetime import datetime

class PaymentInfo(BaseModel):
    payment_id: str
    price: float
    payment_method: str

class IssuedBy(BaseModel):
    admin_iin: Optional[str] = None
    full_name: str

# 👉 Используется при создании подписки (POST /subscriptions)
class SubscriptionCreate(BaseModel):
    user_id: str
    iin: str
    subscription_type: Literal["demo", "economy", "vip", "royal", "school"]
    expires_at: datetime
    activation_method: Literal["manual", "payment", "promocode", "gift"]  # Добавлен "gift"
    note: Optional[str]
    duration_days: int = Field(..., gt=0, le=365)
    payment: Optional[PaymentInfo] = None  # issued_by исключён — вставляется на бэке
    promo_code: Optional[str] = None  # Новый параметр для промокода
    referred_by: Optional[str] = None  # Новый параметр для реферала
    gift: Optional[bool] = False  # Новый параметр для подарочных подписок
    use_balance: bool = True
    amount: Optional[float] = None  # Добавленное поле для суммы
    use_referral: bool = False  # Добавленное поле для использования реферала

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

class GiftSubscriptionCreate(BaseModel):
    gift_iin: constr(strip_whitespace=True, min_length=12, max_length=12, pattern=r'^\d{12}$')
    subscription_type: Literal["economy", "vip", "royal"]
    duration_days: int = Field(..., gt=0, le=365)
    use_balance: bool = True

class SubscriptionUpdate(BaseModel):
    subscription_id: str
    subscription_type: str
    expires_at: datetime
    duration_days: Optional[int] = None
    note: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "subscription_id": "60d21b4667d0d31a9fe3c123",
                "subscription_type": "economy",
                "expires_at": "2023-12-31T23:59:59.999Z",
                "duration_days": 30,
                "note": "Продление подписки администратором"
            }
        }
