"""
Middleware для автоматического применения рейт лимитов
"""

import time
from typing import Callable, Dict, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .rate_limiter import get_rate_limiter
from .config import get_rate_limit_config, RateLimitType
from .utils import get_client_ip, get_user_id_from_request
from app.core.response import error


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического применения рейт лимитов
    """
    
    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        global_rate_limit: Optional[Dict] = None,
        exclude_paths: Optional[list] = None,
        include_paths: Optional[list] = None
    ):
        """
        Args:
            app: ASGI приложение
            enabled: Включить/отключить middleware
            global_rate_limit: Глобальный рейт лимит в формате {"max_requests": 100, "window_seconds": 60}
            exclude_paths: Список путей для исключения из рейт лимитов
            include_paths: Список путей для включения в рейт лимиты (если указан, то только эти пути будут проверяться)
        """
        super().__init__(app)
        self.enabled = enabled
        self.global_rate_limit = global_rate_limit
        self.exclude_paths = exclude_paths or []
        self.include_paths = include_paths
        
        # Добавляем стандартные исключения
        self.exclude_paths.extend([
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/static/"
        ])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Обработка запроса"""
        if not self.enabled:
            return await call_next(request)
        
        # Проверяем, нужно ли применять рейт лимит к этому пути
        if not self._should_apply_rate_limit(request.url.path):
            return await call_next(request)
        
        # Сначала проверяем глобальный рейт лимит
        if self.global_rate_limit:
            global_result = await self._check_global_rate_limit(request)
            if global_result:
                return global_result
        
        # Затем проверяем специфичные рейт лимиты
        route_result = await self._check_route_rate_limit(request)
        if route_result:
            return route_result
        
        # Если лимиты не превышены, продолжаем обработку
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Добавляем заголовки производительности
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    def _should_apply_rate_limit(self, path: str) -> bool:
        """Проверить, нужно ли применять рейт лимит к пути"""
        # Если указан список включений, проверяем только его
        if self.include_paths:
            return any(path.startswith(include_path) for include_path in self.include_paths)
        
        # Иначе проверяем исключения
        return not any(path.startswith(exclude_path) for exclude_path in self.exclude_paths)
    
    async def _check_global_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """Проверить глобальный рейт лимит"""
        if not self.global_rate_limit:
            return None
        
        max_requests = self.global_rate_limit.get("max_requests", 100)
        window_seconds = self.global_rate_limit.get("window_seconds", 60)
        
        # Используем IP для глобального лимита
        identifier = get_client_ip(request)
        if identifier is None:
            # Если IP не найден, логируем и пропускаем
            print(f"[Middleware] IP не найден для глобального рейт лимита. Путь: {request.url.path}")
            return None

        user_id = get_user_id_from_request(request)
        
        rate_limiter = get_rate_limiter()
        result = await rate_limiter.check_rate_limit(
            route="global",
            identifier=identifier,
            max_requests=max_requests,
            window_seconds=window_seconds,
            user_id=user_id
        )
        
        if not result.allowed:
            error_details = {
                "current_requests": result.current_requests,
                "max_requests": result.max_requests,
                "reset_time": result.reset_time,
                "retry_after": result.retry_after,
                "type": "global"
            }
            
            response = error(
                code=429,
                message=f"Превышен глобальный лимит запросов. Допустимо {result.max_requests} запросов за {result.window_seconds} секунд",
                details=error_details
            )
            
            # Добавляем специальные заголовки для рейт лимитов
            response.headers.update({
                "X-RateLimit-Limit": str(result.max_requests),
                "X-RateLimit-Remaining": str(max(0, result.max_requests - result.current_requests)),
                "X-RateLimit-Reset": str(result.reset_time),
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Type": "global"
            })
            
            return response
        
        return None
    
    async def _check_route_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """Проверить рейт лимит для конкретного маршрута"""
        # Пытаемся определить маршрут из URL
        route_name = self._get_route_name_from_path(request.url.path, request.method)
        
        if not route_name:
            return None
        
        config = get_rate_limit_config()
        rule = config.get_rule(route_name)
        
        if not rule:
            return None
        
        # Определяем идентификатор в зависимости от типа лимита
        if rule.rate_limit_type == RateLimitType.IP:
            identifier = get_client_ip(request)
            if identifier is None:
                # Если IP не найден, логируем и пропускаем
                print(f"[Middleware] IP не найден для рейт лимита маршрута {route_name}. Путь: {request.url.path}")
                return None
        elif rule.rate_limit_type == RateLimitType.USER:
            user_id = get_user_id_from_request(request)
            if user_id is None:
                # Если user_id не найден, используем IP
                identifier = get_client_ip(request)
                if identifier is None:
                    # Если IP не найден, логируем и пропускаем
                    print(f"[Middleware] IP и User ID не найдены для рейт лимита пользователя {route_name}. Путь: {request.url.path}")
                    return None
            else:
                identifier = f"user_{user_id}"
        elif rule.rate_limit_type == RateLimitType.COMBINED:
            user_id = get_user_id_from_request(request)
            ip = get_client_ip(request)
            if ip is None:
                # Если IP не найден, логируем и пропускаем
                print(f"[Middleware] IP не найден для комбинированного рейт лимита {route_name}. Путь: {request.url.path}")
                return None
            identifier = f"combined_{ip}_{user_id or 'anonymous'}"
        else:
            identifier = get_client_ip(request)
            if identifier is None:
                # Если IP не найден, логируем и пропускаем
                print(f"[Middleware] IP не найден для рейт лимита по умолчанию {route_name}. Путь: {request.url.path}")
                return None
        
        # Проверяем лимит
        rate_limiter = get_rate_limiter()
        user_id = get_user_id_from_request(request)
        
        result = await rate_limiter.check_rate_limit(
            route=route_name,
            identifier=identifier,
            max_requests=rule.max_requests,
            window_seconds=rule.window_seconds,
            user_id=user_id
        )
        
        if not result.allowed:
            error_details = {
                "current_requests": result.current_requests,
                "max_requests": result.max_requests,
                "reset_time": result.reset_time,
                "retry_after": result.retry_after,
                "route": route_name,
                "type": "route"
            }
            
            response = error(
                code=429,
                message=f"Превышен лимит запросов для {route_name}. Допустимо {result.max_requests} запросов за {result.window_seconds} секунд",
                details=error_details
            )
            
            # Добавляем специальные заголовки для рейт лимитов
            response.headers.update({
                "X-RateLimit-Limit": str(result.max_requests),
                "X-RateLimit-Remaining": str(max(0, result.max_requests - result.current_requests)),
                "X-RateLimit-Reset": str(result.reset_time),
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Type": "route",
                "X-RateLimit-Route": route_name
            })
            
            return response
        
        return None
    
    def _get_route_name_from_path(self, path: str, method: str) -> Optional[str]:
        """Получить имя маршрута из пути"""
        # Мапинг путей к именам маршрутов
        route_mappings = {
            # Аутентификация
            ("POST", "/auth/login"): "auth_login",
            ("POST", "/auth/register"): "auth_register",
            ("POST", "/auth/password-reset"): "auth_password_reset",
            ("POST", "/auth/logout"): "auth_logout",
            
            # Пользовательские данные
            ("GET", "/user/profile"): "user_profile",
            ("PUT", "/user/profile"): "user_profile",
            ("POST", "/user/profile"): "user_profile",
            
            # Тестирование
            ("POST", "/test/start"): "test_start",
            ("POST", "/test/answer"): "test_answer",
            ("GET", "/test/results"): "test_results",
            
            # Лобби
            ("POST", "/lobby/create"): "lobby_create",
            ("POST", "/lobby/join"): "lobby_join",
            ("GET", "/lobby"): "lobby_actions",
            ("PUT", "/lobby"): "lobby_actions",
            ("DELETE", "/lobby"): "lobby_actions",
            
            # WebSocket
            ("GET", "/ws"): "websocket_connect",
            
            # Медиа
            ("POST", "/media/upload"): "media_upload",
            ("GET", "/media"): "media_download",
            
            # Платежи
            ("POST", "/payment"): "payment_create",
            ("GET", "/subscription"): "subscription_manage",
            ("POST", "/subscription"): "subscription_manage",
            ("PUT", "/subscription"): "subscription_manage",
            
            # Рефералы
            ("GET", "/referral"): "referral_actions",
            ("POST", "/referral"): "referral_actions",
            
            # Отчеты
            ("POST", "/report"): "report_create",
            
            # Административные функции
            ("GET", "/admin"): "admin_actions",
            ("POST", "/admin"): "admin_actions",
            ("PUT", "/admin"): "admin_actions",
            ("DELETE", "/admin"): "admin_actions",
            
            # Статистика
            ("GET", "/stats"): "stats_view",
            
            # Поиск
            ("GET", "/search"): "search_requests",
            ("POST", "/search"): "search_requests",
            
            # Экспорт
            ("GET", "/export"): "export_data",
            ("POST", "/export"): "export_data",
        }
        
        # Прямое совпадение
        direct_match = route_mappings.get((method, path))
        if direct_match:
            return direct_match
        
        # Совпадение по префиксу
        for (route_method, route_path), route_name in route_mappings.items():
            if method == route_method and path.startswith(route_path):
                return route_name
        
        # Общие правила по префиксу
        if path.startswith("/auth/"):
            return "auth_login"  # Общий лимит для аутентификации
        elif path.startswith("/user/"):
            return "user_profile"
        elif path.startswith("/test/"):
            return "test_start"
        elif path.startswith("/lobby/"):
            return "lobby_actions"
        elif path.startswith("/media/"):
            return "media_download"
        elif path.startswith("/admin/"):
            return "admin_actions"
        elif path.startswith("/api/"):
            return "api_general"
        
        return None


class RateLimitStatsMiddleware(BaseHTTPMiddleware):
    """
    Middleware для сбора статистики по рейт лимитам
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "routes_stats": {}
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Обработка запроса с подсчетом статистики"""
        self.stats["total_requests"] += 1
        
        # Получаем маршрут для статистики
        route_name = self._get_route_name_from_path(request.url.path, request.method)
        if route_name:
            if route_name not in self.stats["routes_stats"]:
                self.stats["routes_stats"][route_name] = {
                    "requests": 0,
                    "blocked": 0
                }
            self.stats["routes_stats"][route_name]["requests"] += 1
        
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Проверяем, был ли запрос заблокирован
        if response.status_code == 429:
            self.stats["blocked_requests"] += 1
            if route_name:
                self.stats["routes_stats"][route_name]["blocked"] += 1
        
        # Добавляем заголовки со статистикой
        response.headers["X-RateLimit-Stats-Total"] = str(self.stats["total_requests"])
        response.headers["X-RateLimit-Stats-Blocked"] = str(self.stats["blocked_requests"])
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    def _get_route_name_from_path(self, path: str, method: str) -> Optional[str]:
        """Получить имя маршрута из пути (упрощенная версия)"""
        if path.startswith("/auth/"):
            return "auth"
        elif path.startswith("/user/"):
            return "user"
        elif path.startswith("/test/"):
            return "test"
        elif path.startswith("/lobby/"):
            return "lobby"
        elif path.startswith("/media/"):
            return "media"
        elif path.startswith("/admin/"):
            return "admin"
        elif path.startswith("/api/"):
            return "api"
        
        return "other"
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        total = self.stats["total_requests"]
        blocked = self.stats["blocked_requests"]
        
        return {
            "total_requests": total,
            "blocked_requests": blocked,
            "block_rate": (blocked / total * 100) if total > 0 else 0,
            "routes_stats": self.stats["routes_stats"]
        }
    
    def reset_stats(self):
        """Сбросить статистику"""
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "routes_stats": {}
        }


# Глобальный экземпляр статистики
_stats_middleware: Optional[RateLimitStatsMiddleware] = None


def get_rate_limit_stats() -> Dict:
    """Получить статистику рейт лимитов"""
    global _stats_middleware
    if _stats_middleware:
        return _stats_middleware.get_stats()
    return {
        "total_requests": 0,
        "blocked_requests": 0,
        "block_rate": 0,
        "routes_stats": {}
    }


def reset_rate_limit_stats():
    """Сбросить статистику рейт лимитов"""
    global _stats_middleware
    if _stats_middleware:
        _stats_middleware.reset_stats()


def set_stats_middleware(middleware: RateLimitStatsMiddleware):
    """Установить middleware для статистики"""
    global _stats_middleware
    _stats_middleware = middleware 