from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TwoFARequest(BaseModel):
    """Схема запроса на 2FA"""
    admin_id: str = Field(..., description="ID администратора")
    admin_name: str = Field(..., description="Имя администратора")
    admin_email: Optional[str] = Field(None, description="Email администратора")
    telegram_id: str = Field(..., description="Telegram ID администратора")
    ip_address: str = Field(..., description="IP адрес")
    user_agent: str = Field(..., description="User Agent")
    location: Optional[str] = Field(None, description="Геолокация IP")


class TwoFAResponse(BaseModel):
    """Схема ответа 2FA"""
    success: bool = Field(..., description="Успешность операции")
    message: str = Field(..., description="Сообщение")
    request_id: Optional[str] = Field(None, description="ID запроса")
    expires_at: Optional[datetime] = Field(None, description="Время истечения")


class TwoFACallback(BaseModel):
    """Схема callback для 2FA"""
    request_id: str = Field(..., description="ID запроса")
    action: str = Field(..., description="Действие (allow/deny)")
    admin_id: str = Field(..., description="ID администратора")


class TwoFAStatus(BaseModel):
    """Схема статуса 2FA"""
    request_id: str = Field(..., description="ID запроса")
    status: str = Field(..., description="Статус (pending/allowed/denied/expired)")
    admin_id: str = Field(..., description="ID администратора")
    created_at: datetime = Field(..., description="Время создания")
    expires_at: datetime = Field(..., description="Время истечения")
    ip_address: str = Field(..., description="IP адрес")
    user_agent: str = Field(..., description="User Agent")


class HealthCheck(BaseModel):
    """Схема проверки здоровья сервиса"""
    status: str = Field(..., description="Статус сервиса")
    timestamp: datetime = Field(..., description="Время проверки")
    version: str = Field(..., description="Версия сервиса")
    database: str = Field(..., description="Статус базы данных")
    telegram_bot: str = Field(..., description="Статус Telegram бота") 