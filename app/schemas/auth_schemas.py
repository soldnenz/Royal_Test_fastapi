from pydantic import BaseModel, EmailStr, Field, constr, validator
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
    """
    Разрешены только:
    - латинские буквы (a-z)
    - цифры (0-9)
    - символы '@', '.', '_', '-', '+'

    Пробелы по краям удаляются, всё приводится к нижнему регистру.
    """
    value = value.strip().lower()

    if len(value) > 123:
        raise ValueError("Email не должен превышать 123 символа")

    if not re.fullmatch(r"[a-z0-9@._+\-]+", value):
        raise ValueError("Email может содержать только латинские буквы, цифры и символы '@', '.', '_', '-', '+'")

    return value

class AuthRequest(BaseModel):
    """
    Схема для входа (логин).
    Можно использовать iin или email в качестве username.
    """
    username: constr(min_length=3, max_length=256)
    password: constr(min_length=6, max_length=256)

    @validator("username")
    def validate_username(cls, v):
        return sanitize_input(v)

    @validator("password")
    def validate_password(cls, v):
        return sanitize_input(v)

    class Config:
        schema_extra = {
            "example": {
                "username": "012345678901",  # или "user@example.com"
                "password": "strong_password_123"
            }
        }


class TokenResponse(BaseModel):
    """
    Схема ответа при успешной аутентификации.
    """
    access_token: str = Field(..., description="JWT-токен для авторизации")
    token_type: str = Field(default="bearer", description="Тип токена (bearer)")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class PasswordResetRequest(BaseModel):
    """
    Схема для запроса сброса пароля (передаём email).
    """
    email: str = Field(..., description="Email с латинскими символами")

    @validator("email")
    def validate_email(cls, v: str):
        return validate_ascii_email(v)

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class PasswordResetConfirm(BaseModel):
    """
    Схема для подтверждения сброса пароля.
    """
    email: str = Field(..., description="Email с латинскими символами")
    code: constr(max_length=6)
    new_password: constr(min_length=6, max_length=256)

    @validator("email")
    def validate_email(cls, v: str):
        return validate_ascii_email(v)

    @validator("code")
    def validate_code(cls, v):
        return sanitize_input(v)

    @validator("new_password")
    def validate_new_password(cls, v):
        return sanitize_input(v)

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "code": "123456",
                "new_password": "new_strong_password_123"
            }
        }
