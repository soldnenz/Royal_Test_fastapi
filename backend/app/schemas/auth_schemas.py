from pydantic import BaseModel, Field, validator, constr
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
      - Круглые скобки (),
      - Дефис/минус (-),
      - Точку (.),
      - Плюс (+).

    Если встречаются недопустимые символы – выбрасывается ValueError.
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
    Удаляет пробелы по краям и приводит email к нижнему регистру.
    Проверяет, что:
      - Длина не превышает 123 символа,
      - Email соответствует формату:
            локальная_часть@домен,
        где локальная часть может содержать цифры, латинские буквы, точки, подчёркивания, плюсы и дефисы,
        а домен – буквы, цифры, дефисы и содержит как минимум одну точку.

    Если формат некорректен, выбрасывается ValueError.
    """
    value = value.strip().lower()

    if len(value) > 123:
        raise ValueError("Email не должен превышать 123 символа")

    pattern = r'^[a-z0-9._+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)+$'
    if not re.fullmatch(pattern, value):
        raise ValueError("Email должен быть валидного формата и содержать доменное имя с точкой.")

    return value


class AuthRequest(BaseModel):
    """
    Схема для входа (логин).
    В качестве username можно использовать IIN или email.
    """
    username: str
    password: str

    @validator("username")
    def validate_username(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Имя пользователя должно содержать минимум 3 символа")
        if len(v) > 256:
            raise ValueError("Имя пользователя не должно превышать 256 символов")
        return sanitize_input(v)

    @validator("password")
    def validate_password(cls, v):
        v = v.strip()
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        if len(v) > 256:
            raise ValueError("Пароль не должен превышать 256 символов")
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
