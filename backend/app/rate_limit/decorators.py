"""
Декораторы для применения рейт лимитов к отдельным маршрутам
"""

import functools
from typing import Callable, Optional
from fastapi import Request, HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from .rate_limiter import get_rate_limiter
from .config import get_rate_limit_config, RateLimitType, RateLimitRule
from .utils import get_client_ip, get_user_id_from_request


def rate_limit(
    route: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None,
    rate_limit_type: Optional[RateLimitType] = None
) -> Callable:
    """
    Декоратор для применения рейт лимита к маршруту
    
    Args:
        route: Название маршрута
        max_requests: Максимальное количество запросов (если не указано, берется из конфига)
        window_seconds: Окно времени в секундах (если не указано, берется из конфига)
        rate_limit_type: Тип рейт лимита (если не указано, берется из конфига)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем объект Request — сначала из args, потом из kwargs
            request = next((a for a in args if isinstance(a, Request)), None) \
                      or kwargs.get('request')
            
            print(f"[Decorator] --- Проверка для маршрута: {route} ---")

            if not isinstance(request, Request):
                # Если Request не найден, пропускаем лимит
                print("[Decorator] Request не найден, пропускаю лимит.")
                return await func(*args, **kwargs)

            if max_requests is None or window_seconds is None:
                # Если параметры не переданы, пропускаем
                print("[Decorator] Лимиты не заданы в декораторе, пропускаю.")
                return await func(*args, **kwargs)

            rule = RateLimitRule(
                max_requests=max_requests,
                window_seconds=window_seconds,
                rate_limit_type=rate_limit_type or RateLimitType.IP
            )
            print(f"[Decorator] Правило: {rule.max_requests} запросов / {rule.window_seconds} сек. Тип: {rule.rate_limit_type.value}")
            
            identifier = None
            # Определяем идентификатор в зависимости от типа лимита
            if rule.rate_limit_type == RateLimitType.IP:
                identifier = get_client_ip(request)
                if identifier is None:
                    # Если IP не найден, пропускаем
                    print("[Decorator] IP не найден, пропускаю.")
                    return await func(*args, **kwargs)
            elif rule.rate_limit_type == RateLimitType.USER:
                user_id = get_user_id_from_request(request)
                if user_id is None:
                    # Если user_id не найден, используем IP
                    identifier = get_client_ip(request)
                    if identifier is None:
                        print("[Decorator] User ID и IP не найдены, пропускаю.")
                        return await func(*args, **kwargs)
                else:
                    identifier = f"user_{user_id}"
            elif rule.rate_limit_type == RateLimitType.COMBINED:
                user_id = get_user_id_from_request(request)
                ip = get_client_ip(request)
                if ip is None:
                    print("[Decorator] IP не найден для комбинированного лимита, пропускаю.")
                    return await func(*args, **kwargs)
                if user_id:
                    identifier = f"combined_{user_id}_{ip}"
                else:
                    identifier = f"ip_{ip}"
            
            if not identifier:
                print("[Decorator] Не удалось определить идентификатор, пропускаю.")
                return await func(*args, **kwargs)

            print(f"[Decorator] Идентификатор для лимита: {identifier}")
            
            # Проверяем лимит
            rate_limiter = get_rate_limiter()
            result = await rate_limiter.check_rate_limit(
                route=route,
                identifier=identifier,
                max_requests=rule.max_requests,
                window_seconds=rule.window_seconds,
                user_id=get_user_id_from_request(request)
            )
            
            # Добавляем заголовки
            headers = {
                "X-RateLimit-Limit": str(result.max_requests),
                "X-RateLimit-Remaining": str(max(0, result.max_requests - result.current_requests)),
                "X-RateLimit-Reset": str(result.reset_time),
                "X-RateLimit-Type": rule.rate_limit_type.value
            }
            
            if not result.allowed:
                # Если лимит превышен, возвращаем 429
                headers["Retry-After"] = str(result.retry_after)
                print(f"[Decorator] ЛИМИТ ПРЕВЫШЕН для {identifier} на маршруте {route}. Осталось {result.retry_after} сек.")
                raise HTTPException(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": f"Превышен лимит запросов. Допустимо {result.max_requests} запросов за {result.window_seconds} секунд",
                        "retry_after": result.retry_after
                    },
                    headers=headers
                )
            
            print(f"[Decorator] Лимит в порядке для {identifier}. Текущие запросы: {result.current_requests}/{result.max_requests}")
            # Выполняем функцию и добавляем заголовки к ответу
            response = await func(*args, **kwargs)
            
            # Если это Response объект, добавляем заголовки
            if hasattr(response, "headers"):
                response.headers.update(headers)
            
            return response
            
        return wrapper
    return decorator

def rate_limit_strict(
    route: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None
) -> Callable:
    """
    Строгий рейт лимит (всегда по IP + User ID)
    """
    return rate_limit(
        route=route,
        max_requests=max_requests,
        window_seconds=window_seconds,
        rate_limit_type=RateLimitType.COMBINED
    )

def rate_limit_ip(
    route: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None
) -> Callable:
    """
    Рейт лимит только по IP
    """
    return rate_limit(
        route=route,
        max_requests=max_requests,
        window_seconds=window_seconds,
        rate_limit_type=RateLimitType.IP
    )

def rate_limit_user(
    route: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None
) -> Callable:
    """
    Рейт лимит по user_id (с фоллбеком на IP)
    """
    return rate_limit(
        route=route,
        max_requests=max_requests,
        window_seconds=window_seconds,
        rate_limit_type=RateLimitType.USER
    ) 