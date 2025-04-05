from typing import Optional
from pydantic import BaseModel, Field, EmailStr, constr, validator
import re
import idna
from datetime import datetime

def sanitize_input(value: str) -> str:
    """
    Разрешает только:
      - Русские буквы (включая ё/Ё),
      - Английские буквы (a-z, A-Z),
      - Цифры (0-9),
      - Пробел,
      - Символ равенства (=),
      - Подчёркивание (_),
      - Собачку (@),
      - Круглые скобки ((), ),
      - Дефис/минус (-),
      - Точку (.),
      - Плюс (+).

    При обнаружении любого другого символа выбрасывает исключение ValueError.

    :param value: Строка для проверки
    :return: Исходная строка, если она проходит проверку
    :raises ValueError: Если в строке обнаружены недопустимые символы
    """
    pattern = r'^[0-9a-zA-Zа-яА-ЯёЁ =_@().+\-]+$'
    if not re.match(pattern, value):
        raise ValueError(
            "Недопустимые символы. Разрешены только русские и английские буквы, цифры, пробел, "
            "символ равенства (=), подчёркивание (_), @, круглые скобки (), дефис (-), точка (.) и плюс (+)."
        )
    return value

def validate_ascii_email(value: str) -> str:
    value = value.strip().lower()

    if len(value) > 123:
        raise ValueError("Email не должен превышать 123 символа")

    if 'xn--' in value:
        raise ValueError("Разрешены только латинские email-домены. Кириллица недопустима.")

    if not re.fullmatch(r"[a-z0-9@._+\-]+", value):
        raise ValueError("Email может содержать только латинские буквы, цифры и символы '@', '.', '_', '-', '+'")

    return value


class UserBase(BaseModel):
    """
    Общие поля для пользователя.
    """
    iin: str = Field(..., description="ИИН должен состоять ровно из 12 цифр. Может начинаться с нуля.")
    phone: str = Field(..., description="Телефон в международном формате, например: +77011234567")
    email: str = Field(..., description="Email с латинскими символами")

    @validator("iin")
    def validate_iin(cls, v):
        if not re.fullmatch(r"^\d{12}$", v):
            raise ValueError("ИИН должен состоять ровно из 12 цифр")
        return sanitize_input(v)

    @validator("phone")
    def validate_phone(cls, v):
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.fullmatch(pattern, v):
            raise ValueError("Телефон должен быть в международном формате, например: +77011234567")
        return sanitize_input(v)

    @validator("email")
    def validate_email(cls, v: str):
        return validate_ascii_email(v)


class UserCreate(UserBase):
    """
    Схема при регистрации нового пользователя.
    """
    password: str = Field(..., description="Пароль. От 6 до 123 символов")
    confirm_password: str = Field(..., description="Подтверждение пароля. Должно совпадать с паролем")

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        if len(v) > 123:
            raise ValueError("Пароль не должен превышать 123 символа")
        return sanitize_input(v)

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError("Пароли не совпадают")
        return sanitize_input(v)

    class Config:
        schema_extra = {
            "example": {
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        }


class UserOut(BaseModel):
    """
    Схема для отображения информации о пользователе.
    """
    id: Optional[str]
    iin: str
    phone: str
    email: str
    role: str
    created_at: datetime  # ✅ теперь datetime, а не str

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()  # ✅ сериализация для ответа
        }
        schema_extra = {
            "example": {
                "_id": "603d83d6c89a72d8f751b9ab",
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "role": "user",
                "created_at": "2025-03-26T12:34:56"
            }
        }


class UserUpdate(BaseModel):
    """
    (Опционально) Схема для обновления существующего пользователя.
    Указывайте только поля, которые хотите изменить.
    """
    phone: Optional[str] = None
    email: Optional[str] = None

    @validator("phone")
    def validate_phone(cls, v):
        if v is None:
            return v
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.fullmatch(pattern, v):
            raise ValueError("Телефон должен быть в международном формате, например: +77011234567")
        return sanitize_input(v)

    @validator("email")
    def validate_email(cls, v):
        if v is None:
            return v
        return sanitize_input(v)

    class Config:
        schema_extra = {
            "example": {
                "phone": "+77019876543",
                "email": "new_email@example.com",
            }
        }