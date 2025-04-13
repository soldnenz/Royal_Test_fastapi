# ✅ validators + модели (доработанный полный код для Pydantic v2)
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re

def sanitize_input(value: str) -> str:
    if value is None:
        return value
    pattern = r'^[0-9a-zA-Zа-яА-ЯёЁ =_@().+\-]+$'
    if not re.fullmatch(pattern, value):
        raise ValueError("Недопустимые символы: разрешены только буквы, цифры, пробел, = _ @ ( ) . + -")
    return value.strip()

def validate_full_name(value: str) -> str:
    value = value.strip()
    # Добавлены казахские символы: Іі, Әә, Ғғ, Ққ, Ңң, Өө, Ұұ, Үү, Һһ
    pattern = r"^[А-Яа-яЁёІіӘәҒғҚқҢңӨөҰұҮүҺһ\- ]{2,120}$"
    if not re.fullmatch(pattern, value):
        raise ValueError(
            "ФИО должно содержать только кириллические (в том числе казахские) буквы, пробелы и дефис. От 2 до 120 символов."
        )
    return value

def validate_ascii_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 123:
        raise ValueError("Email не должен превышать 123 символа")
    if 'xn--' in value:
        raise ValueError("Разрешены только латинские email-домены. Кириллица недопустима.")
    # Шаблон проверяет: локальная часть (буквы, цифры, точки, подчёркивания, плюсы, дефисы),
    # затем символ '@', затем доменное имя с хотя бы одной точкой.
    pattern = r'^[a-z0-9._+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)+$'
    if not re.fullmatch(pattern, value):
        raise ValueError("Email должен быть валидного формата и может содержать только латинские буквы, цифры и символы '@', '.', '_', '-', '+'")
    return value

def validate_money(value: float) -> float:
    if round(value, 2) != value:
        raise ValueError("Сумма должна быть ограничена до двух знаков после запятой")
    return value

def validate_iin(value: str) -> str:
    if not re.fullmatch(r"^\d{12}$", value):
        raise ValueError("ИИН должен состоять ровно из 12 цифр")
    return value

def validate_phone(value: str) -> str:
    value = value.strip()
    # Строгая проверка: номер должен начинаться с +7 и содержать ровно 10 цифр после него.
    if not re.fullmatch(r'^\+7\d{10}$', value):
        raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX (ровно 12 символов: +7 и 10 цифр)")
    return value



# --- СХЕМЫ ---
class UserBase(BaseModel):
    full_name: str
    iin: str
    phone: str
    email: str
    referred_by: Optional[str] = None
    referred_use: Optional[bool] = False
    money: float = 0.0

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v): return validate_full_name(v)

    @field_validator("iin")
    @classmethod
    def validate_iin_field(cls, v): return validate_iin(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v): return validate_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v): return validate_ascii_email(v)

    @field_validator("referred_by")
    @classmethod
    def validate_referred(cls, v): return sanitize_input(v) if v else v

    @field_validator("money")
    @classmethod
    def validate_money_value(cls, v): return validate_money(v)


class UserCreate(UserBase):
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, v, info):
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Пароли не совпадают")
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "full_name": "Иванов Иван Иванович",
                "iin": "050292491234",
                "phone": "+77072242123",
                "email": "none@mail.ru",
                "password": "qwer123",
                "confirm_password": "qwer123",
                "referred_by": "XYZ123",
                "referred_use": True,
                "money": 1000.99
            }
        }


class UserOut(BaseModel):
    id: Optional[str]
    full_name: str
    iin: str
    phone: str
    email: str
    role: str
    created_at: datetime
    referred_by: Optional[str] = None
    referred_use: Optional[bool] = False
    money: Optional[float] = 0.0

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "_id": "603d83d6c89a72d8f751b9ab",
                "full_name": "Иванов Иван Иванович",
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "role": "user",
                "created_at": "2025-03-26T12:34:56",
                "referred_by": "REF987KLM",
                "referred_use": True,
                "money": 1000.99
            }
        }


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    referred_by: Optional[str] = None
    referred_use: Optional[bool] = None
    money: Optional[float] = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v): return validate_full_name(v)

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, v): return validate_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v): return validate_ascii_email(v)

    @field_validator("referred_by")
    @classmethod
    def validate_referred(cls, v): return sanitize_input(v) if v else v

    @field_validator("money")
    @classmethod
    def validate_money_value(cls, v): return validate_money(v) if v is not None else v

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Сергеев Сергей Сергеевич",
                "phone": "+77019876543",
                "email": "new_email@example.com",
                "referred_by": "XYZ123",
                "referred_use": True,
                "money": 500.75
            }
        }