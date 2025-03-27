# app/models/user_model.py

from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class UserModel(BaseModel):
    """
    Базовая модель пользователя для хранения в MongoDB.
    Служит для преобразований "dict <-> объект" и удобства валидации данных.
    """
    # Поле _id из MongoDB
    id: Optional[str] = Field(None, alias="_id")

    # ИИН: ровно 12 цифр
    iin: str = Field(..., min_length=12, max_length=12, regex=r"^\d{12}$")

    # Телефон
    phone: str = Field(..., description="Номер телефона (проверка на фронте/бэке)")

    # Email
    email: EmailStr = Field(..., description="Адрес e-mail пользователя")

    # Хэш пароля (bcrypt и т.д.)
    hashed_password: str = Field(..., description="Захешированный пароль")

    # Роль (по умолчанию user)
    role: str = Field(default="user", description="Роль пользователя")

    # Дата создания в формате UTC+5 (строкой или ISO-форматом)
    created_at: str = Field(..., description="Дата/время создания (UTC+5)")

    class Config:
        # Разрешаем использовать alias (например, _id) при создании объекта
        allow_population_by_field_name = True
        # Пример для документации
        schema_extra = {
            "example": {
                "_id": "603d83d6c89a72d8f751b9ab",
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "created_at": "2025-03-26 12:34:56"
            }
        }
