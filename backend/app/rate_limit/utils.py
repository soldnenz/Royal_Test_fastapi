"""
Утилиты для работы с rate limit
"""

from typing import Optional
from fastapi import Request

def get_client_ip(request: Request) -> Optional[str]:
    """Получить IP клиента из запроса"""
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    elif "x-forwarded-for" in request.headers:
        # Берем первый IP из списка
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    elif request.client:
        return request.client.host
    return None

def get_user_id_from_request(request: Request) -> Optional[str]:
    """Получить ID пользователя из запроса"""
    if hasattr(request.state, "user_id"):
        return str(request.state.user_id)
    return None 