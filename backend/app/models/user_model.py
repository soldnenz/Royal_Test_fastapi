from typing import Optional
from pydantic import BaseModel, Field, EmailStr, validator
import re

class UserModel(BaseModel):
    """
    Базовая модель пользователя для хранения в MongoDB.
    Служит для преобразований "dict <-> объект" и удобства валидации данных.
    """
    # Поле _id из MongoDB
    id: Optional[str] = Field(None, alias="_id")

    # ФИО
    full_name: str = Field(..., description="Фамилия Имя Отчество пользователя")

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

    # Код пригласившего
    referred_by: Optional[str] = Field(None, description="Код пригласившего пользователя")

    referred_use: Optional[bool] = Field(False, description="Использовал ли реферальный код")

    # Сумма пользователя
    money: float = Field(0.0, description="Сумма пользователя (по умолчанию 0.0)")

    # Статус бана пользователя
    is_banned: bool = Field(False, description="Флаг блокировки пользователя")
    
    # Информация о бане, если пользователь заблокирован
    ban_info: Optional[dict] = Field(None, description="Информация о блокировке")

    # Дата создания в формате UTC+5 (строкой или ISO-форматом)
    created_at: str = Field(..., description="Дата/время создания (UTC+5)")

    @validator("money")
    def validate_money(cls, v):
        """
        Проверяет, что число в поле 'money' имеет не более 2 знаков после запятой.
        """
        if v is not None and round(v, 2) != v:
            raise ValueError("Сумма должна быть ограничена до двух знаков после запятой")
        return v

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "_id": "603d83d6c89a72d8f751b9ab",
                "full_name": "Иванов Иван Иванович",
                "iin": "012345678901",
                "phone": "+77011234567",
                "email": "user@example.com",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "referred_by": "INVITE456",
                "referred_use": True,
                "money": 1000.99,  # Пример с суммой
                "is_banned": False,  # По умолчанию не заблокирован
                "ban_info": None,    # Нет информации о блокировке
                "created_at": "2025-03-26 12:34:56"
            }
        }
