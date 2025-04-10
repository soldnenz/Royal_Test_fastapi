from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class Referral(BaseModel):
    code: str
    type: str  # "school" или "user"
    owner_user_id: Optional[str] = None  # Не обязателен для типа "school"
    owner_school_id: Optional[str] = None  # Не обязателен для типа "user"
    rate: dict  # {'type': 'percent', 'value': 10}
    description: str
    active: bool = True
    comment: Optional[str] = None
    created_by: str
    referred_by: Optional[str] = None  # Реферальный код пригласившего
    referred_use: Optional[bool] = False  # Использовал ли реферальный код
    money: Optional[float] = Field(None, description="Сумма пользователя (ограничена двумя знаками после запятой)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def validate_rate(value: Dict) -> Dict:
        """
        Проверка поля rate {'type': 'percent', 'value': 10}.
        """
        if 'type' not in value or 'value' not in value:
            raise ValueError("Поле rate должно содержать 'type' и 'value'")
        if value['type'] != 'percent':
            raise ValueError("Только тип 'percent' разрешен для 'rate'")
        if not (0 <= value['value'] <= 100):
            raise ValueError("Значение 'value' должно быть в пределах от 0 до 100")
        return value

    class Config:
        orm_mode = True


class ReferralSearchParams(BaseModel):
    code: Optional[str] = None
    type: Optional[str] = None
    owner_user_id: Optional[str] = None
    active: Optional[bool] = None

    class Config:
        orm_mode = True
