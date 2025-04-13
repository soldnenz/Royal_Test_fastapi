from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re

# Регулярное выражение для проверки кода при создании (админский вариант)
CODE_PATTERN = re.compile(r'^[a-zA-Zа-яА-Я0-9_\-+=]+$')


class Rate(BaseModel):
    type: str = Field(..., description="Тип ставки (должен быть 'percent')")
    value: float = Field(..., description="Значение в процентах (от 0 до 100)")

    @field_validator("type")
    @classmethod
    def validate_rate_type(cls, v: str) -> str:
        if v != "percent":
            raise ValueError("Только тип 'percent' разрешён для rate")
        return v

    @field_validator("value")
    @classmethod
    def validate_rate_value(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("Значение 'value' должно быть от 0 до 100")
        return v


class Referral(BaseModel):
    code: str = Field(..., description="Уникальный реферальный код")
    type: str = Field(..., description="Тип рефералки: 'school' или 'user'")
    owner_user_id: str = Field(..., description="ID владельца (пользователь)")
    rate: Rate = Field(..., description="Параметры ставки, например {'type': 'percent', 'value': 10}")
    description: str = Field(..., description="Описание рефералки")
    active: bool = Field(default=True, description="Флаг активности рефералки")
    comment: Optional[str] = Field(None, description="Комментарий (опционально)")
    created_by: str = Field(..., description="Кто создал рефералку (полное имя)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата и время создания рефералки")

    class Config:
        from_attributes = True  # Для Pydantic V2 вместо orm_mode


class ReferralSearchParams(BaseModel):
    code: Optional[str] = Field(None, description="Фильтр по реферальному коду")
    type: Optional[str] = Field(None, description="Фильтр по типу ('school' или 'user')")
    owner_user_id: Optional[str] = Field(None, description="Фильтр по ID владельца")
    active: Optional[bool] = Field(None, description="Фильтр по активности рефералки")

    class Config:
        from_attributes = True


class ReferralCreate(BaseModel):
    """
    Схема для создания реферального кода.
    Если создаёт обычный пользователь — поле code не передаётся (генерируется автоматически),
    а ставка берётся из настроек (DEFAULT_REFERRAL_RATE).
    Если создаёт админ, поле code может быть задано и проверено.
    """
    code: Optional[str] = Field(None, description="Уникальный реферальный код (только для админа)")
    type: str = Field(..., description="Тип рефералки: 'school' или 'user'")
    owner_user_id: str = Field(..., description="ID владельца (пользователь)")
    rate: Optional[Rate] = Field(None, description="Параметры ставки (если не передано, берётся из настроек)")
    description: Optional[str] = Field("", description="Описание рефералки")
    active: bool = Field(default=True, description="Флаг активности")
    comment: Optional[str] = Field(None, description="Комментарий (опционально)")
    created_by: Optional[str] = Field(None, description="Кто создал рефералку (будет заполнено автоматически)")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Дата создания")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not CODE_PATTERN.fullmatch(v):
            raise ValueError("Код может содержать только буквы, цифры и символы _-+=.")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("user", "school"):
            raise ValueError("Тип должен быть 'user' или 'school'.")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "code": "REF123ABC",  # передается только для админа
                "type": "user",
                "owner_user_id": "609d1d2e3a4b5c6d7e8f9a0b",
                "rate": {"type": "percent", "value": 10},
                "description": "Описание рефералки",
                "active": True,
                "comment": "Комментарий",
                "created_by": "Иван Иванов",
                "created_at": "2025-04-11T12:00:00"
            }
        }
class ReferralCreateUser(BaseModel):
    """
    Схема для создания реферального кода обычным пользователем.
    Пользователь указывает только описание.
    Остальные поля (type, owner_user_id, rate, code) будут заполнены сервером.
    """
    description: Optional[str] = Field("", description="Описание реферальной ссылки (до 256 символов)")

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return ""
        v = v.strip()
        if len(v) > 256:
            raise ValueError("Описание не должно превышать 256 символов")
        # Допустимые символы: латинские и кириллические буквы, цифры, пробел, '_' и '-'
        if not re.fullmatch(r'^[A-Za-zА-Яа-яЁё0-9_\- ]*$', v):
            raise ValueError("Описание может содержать только буквы, цифры, пробел, '_' и '-'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "description": "Моя реферальная ссылка"
            }
        }

class ReferralUpdateAdmin(BaseModel):
    """
    Схема для обновления реферального кода (только администраторы).
    Все поля опциональны.
    """
    code: Optional[str] = Field(None, description="Новый код (если нужно изменить)")
    type: Optional[str] = Field(None, description="Новый тип ('user' или 'school')")
    owner_user_id: Optional[str] = Field(None, description="Новый ID владельца")
    rate: Optional[Rate] = Field(None, description="Новая ставка")
    description: Optional[str] = Field(None, description="Новое описание")
    active: Optional[bool] = Field(None, description="Активность (True/False)")
    comment: Optional[str] = Field(None, description="Новый комментарий")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not CODE_PATTERN.fullmatch(v):
            raise ValueError("Код может содержать только буквы, цифры и символы _-+=.")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("user", "school"):
            raise ValueError("Тип должен быть 'user' или 'school'.")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()
