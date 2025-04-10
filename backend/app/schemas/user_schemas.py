from pydantic import BaseModel, Field, EmailStr, constr, validator
from typing import Optional
from datetime import datetime
import re

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
    """
    if value is None:
        return value

    pattern = r'^[0-9a-zA-Zа-яА-ЯёЁ =_@().+\-]+$'
    if not re.match(pattern, value):
        raise ValueError(
            "Недопустимые символы. Разрешены только русские и английские буквы, цифры, пробел, "
            "символ равенства (=), подчёркивание (_), @, круглые скобки (), дефис (-), точка (.) и плюс (+)."
        )
    return value

def validate_full_name(value: str) -> str:
    value = value.strip()
    # Только кириллические буквы, пробел и дефис
    pattern = r"^[А-Яа-яЁё\- ]{2,120}$"
    if not re.fullmatch(pattern, value):
        raise ValueError("ФИО должно содержать только кириллические буквы, пробелы и дефис. От 2 до 120 символов.")
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

def validate_money(value: float) -> float:
    """
    Проверяет, что число в поле 'money' имеет не более 2 знаков после запятой.
    """
    if round(value, 2) != value:
        raise ValueError("Сумма должна быть ограничена до двух знаков после запятой")
    return value


class UserBase(BaseModel):
    """
    Общие поля для пользователя.
    """
    full_name: str = Field(..., description="Фамилия Имя Отчество (только кириллица)")
    iin: str = Field(..., description="ИИН должен состоять ровно из 12 цифр. Может начинаться с нуля.")
    phone: str = Field(..., description="Телефон в международном формате, например: +77011234567")
    email: str = Field(..., description="Email с латинскими символами")
    referred_by: Optional[str] = Field(None, description="Реферальный код пригласившего (если есть)")
    referred_use: Optional[bool] = Field(False, description="Использовал ли реферальный код")  # Добавляем поле
    money: Optional[float] = Field(None, description="Сумма пользователя (ограничена двумя знаками после запятой)")

    @validator("referred_by")
    def validate_referred_by(cls, v):
        if v is None:
            return v
        return sanitize_input(v)

    @validator("full_name")
    def validate_full_name_field(cls, v):
        return validate_full_name(v)

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

    @validator("money")
    def validate_money_field(cls, v):
        if v is not None:
            return validate_money(v)
        return v


class UserCreate(BaseModel):
    full_name: str = Field(..., description="Фамилия Имя Отчество")
    iin: str = Field(..., description="ИИН должен состоять ровно из 12 цифр")
    phone: str = Field(..., description="Телефон в международном формате")
    email: str = Field(..., description="Email с латинскими символами")
    password: str = Field(..., description="Пароль")
    confirm_password: str = Field(..., description="Подтверждение пароля")
    referred_by: Optional[str] = Field(None, description="Реферальный код пригласившего (если есть)")
    referred_use: Optional[bool] = Field(False, description="Использовал ли реферальный код")  # Поле для использования реферального кода
    money: Optional[float] = Field(None, description="Сумма пользователя (ограничена двумя знаками после запятой)")

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v

    @validator("confirm_password")
    def validate_confirm_password(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError("Пароли не совпадают")
        return v

    @validator("money")
    def validate_money_field(cls, v):
        if v is not None:
            return validate_money(v)
        return v

    class Config:
        schema_extra = {
            "example": {
                "full_name": "Иванов Иван Иванович",
                "iin": "050292491234",
                "phone": "+77072242123",
                "email": "none@mail.ru",
                "password": "qwer123",
                "confirm_password": "qwer123",
                "referred_by": "XYZ123",
                "referred_use": True,  # Пример использования рефералки
                "money": 1000.99  # Пример с суммой
            }
        }

class UserOut(BaseModel):
    """
    Схема для отображения информации о пользователе.
    """
    id: Optional[str]
    full_name: str
    iin: str
    phone: str
    email: str
    role: str
    created_at: datetime
    referred_by: Optional[str] = Field(None, description="Код пригласившего пользователя (если был)")
    referred_use: Optional[bool] = Field(False, description="Использовал ли реферальный код")  # Поле для отображения
    money: Optional[float] = Field(None, description="Сумма пользователя (ограничена двумя знаками после запятой)")  # Добавляем поле

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "_id": "603d83d6c89a72d8f751b9ab",
                "full_name": "Иванов Иван Иванович",
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "role": "user",
                "created_at": "2025-03-26T12:34:56",
                "referred_by": "REF987KLM",
                "referred_use": True,  # Пример использования рефералки
                "money": 1000.99  # Пример с суммой
            }
        }

class UserUpdate(BaseModel):
    """
    Схема для обновления существующего пользователя.
    Указывайте только поля, которые хотите изменить.
    """
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    referred_by: Optional[str] = None  # Можно обновить реферальный код
    referred_use: Optional[bool] = None  # Можно обновить использование реферального кода
    money: Optional[float] = None  # Можно обновить сумму

    @validator("full_name")
    def validate_full_name_field(cls, v):
        if v is None:
            return v
        return validate_full_name(v)

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

    @validator("money")
    def validate_money_field(cls, v):
        if v is not None:
            return validate_money(v)
        return v

    class Config:
        schema_extra = {
            "example": {
                "full_name": "Сергеев Сергей Сергеевич",
                "phone": "+77019876543",
                "email": "new_email@example.com",
                "referred_by": "XYZ123",
                "referred_use": True,  # Пример использования реферального кода
                "money": 500.75  # Пример с суммой
            }
        }
