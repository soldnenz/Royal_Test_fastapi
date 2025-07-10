"""
Основной класс для работы с рейт лимитами через Redis
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import redis.asyncio as redis
from redis.asyncio import Redis
from contextlib import asynccontextmanager

from app.core.config import settings


@dataclass
class RateLimitResult:
    """Результат проверки рейт лимита"""
    allowed: bool
    current_requests: int
    max_requests: int
    reset_time: int
    retry_after: int
    window_seconds: int


class RateLimiter:
    """Класс для работы с рейт лимитами через Redis"""
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        key_prefix: str = "rate_limit",
        fail_open: bool = True,
        warning_threshold: float = 0.8
    ):
        """
        Args:
            redis_host: Хост Redis
            redis_port: Порт Redis
            redis_password: Пароль Redis
            redis_db: Номер БД Redis
            key_prefix: Префикс для ключей в Redis
            fail_open: Разрешать запросы при недоступности Redis
            warning_threshold: Порог предупреждения (0.8 = 80%)
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.key_prefix = key_prefix
        self.fail_open = fail_open
        self.warning_threshold = warning_threshold
        
        self.redis: Optional[Redis] = None
        
        # Lua скрипт для атомарной проверки и обновления лимита
        self.lua_script = """
            local key = KEYS[1]
            local window = tonumber(ARGV[1])
            local limit = tonumber(ARGV[2])
            local current_time = tonumber(ARGV[3])
            
            -- Получаем текущий счетчик
            local current = redis.call('GET', key)
            if current == false then
                current = 0
            else
                current = tonumber(current)
            end
            
            -- Проверяем TTL
            local ttl = redis.call('TTL', key)
            if ttl == -1 then
                -- Ключ существует, но без TTL - устанавливаем TTL
                redis.call('EXPIRE', key, window)
                ttl = window
            elseif ttl == -2 then
                -- Ключ не существует - создаем новый
                current = 0
                ttl = window
            end
            
            -- Проверяем лимит
            if current >= limit then
                return {current, limit, ttl, 0}  -- превышен лимит
            else
                -- Увеличиваем счетчик
                current = current + 1
                redis.call('INCR', key)
                redis.call('EXPIRE', key, window)
                return {current, limit, ttl, 1}  -- лимит не превышен
            end
        """
        
        self.script_sha: Optional[str] = None
        
    async def _get_redis_connection(self) -> Optional[Redis]:
        """Получить соединение с Redis"""
        if self.redis is None:
            try:
                self.redis = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    retry_on_timeout=True,
                    health_check_interval=10
                )
                
                # Проверяем соединение
                await self.redis.ping()
                
                # Загружаем Lua скрипт
                self.script_sha = await self.redis.script_load(self.lua_script)
                
                print(f"[RateLimiter] Успешно подключились к Redis: {self.redis_host}:{self.redis_port}/{self.redis_db}")
                
            except Exception as e:
                print(f"[RateLimiter] Ошибка подключения к Redis: {self.redis_host}:{self.redis_port} - {e}")
                if self.redis:
                    await self.redis.close()
                    self.redis = None
                return None
                
        return self.redis
    
    def _get_key(self, route: str, identifier: str) -> str:
        """Генерация ключа для Redis"""
        return f"{self.key_prefix}:{route}:{identifier}"
    
    async def check_rate_limit(
        self,
        route: str,
        identifier: str,
        max_requests: int,
        window_seconds: int,
        user_id: Optional[str] = None
    ) -> RateLimitResult:
        """
        Проверить и обновить рейт лимит
        
        Args:
            route: Название маршрута
            identifier: Идентификатор (IP или user_id)
            max_requests: Максимальное количество запросов
            window_seconds: Окно времени в секундах
            user_id: ID пользователя (для логов)
            
        Returns:
            RateLimitResult с результатом проверки
        """
        redis_conn = await self._get_redis_connection()
        
        if redis_conn is None:
            print(f"[RateLimiter] Redis недоступен. Маршрут: {route}, Идентификатор: {identifier}")
            if self.fail_open:
                print("[RateLimiter] Redis недоступен, разрешаю запрос (fail-open).")
                return RateLimitResult(
                    allowed=True,
                    current_requests=0,
                    max_requests=max_requests,
                    reset_time=int(time.time()) + window_seconds,
                    retry_after=0,
                    window_seconds=window_seconds
                )
            else:
                print("[RateLimiter] Redis недоступен, блокирую запрос (fail-safe).")
                return RateLimitResult(
                    allowed=False,
                    current_requests=max_requests,
                    max_requests=max_requests,
                    reset_time=int(time.time()) + window_seconds,
                    retry_after=window_seconds,
                    window_seconds=window_seconds
                )
        
        try:
            key = self._get_key(route, identifier)
            current_time = int(time.time())
            
            print(f"[RateLimiter] Проверка ключа: {key}")
            print(f"[RateLimiter] Параметры: max_requests={max_requests}, window_seconds={window_seconds}")

            # Выполняем Lua скрипт
            result = await redis_conn.evalsha(
                self.script_sha,
                1,  # количество ключей
                key,  # ключ
                window_seconds,  # окно времени
                max_requests,  # лимит запросов
                current_time  # текущее время
            )
            
            current = int(result[0])  # текущее количество запросов
            limit = int(result[1])    # лимит запросов
            ttl = int(result[2])      # оставшееся время жизни ключа
            allowed = bool(result[3])  # разрешено ли
            
            print(f"[RateLimiter] Результат Redis: current={current}, limit={limit}, ttl={ttl}, allowed={allowed}")

            # Если лимит превышен, логируем предупреждение
            if not allowed:
                print(f"[RateLimiter] ПРЕДУПРЕЖДЕНИЕ: Превышен лимит для {identifier} на маршруте {route}. Запросов: {current}/{limit}")
            
            return RateLimitResult(
                allowed=allowed,
                current_requests=current,
                max_requests=limit,
                reset_time=current_time + ttl,
                retry_after=ttl if not allowed else 0,
                window_seconds=window_seconds
            )
            
        except Exception as e:
            print(f"[RateLimiter] Ошибка при проверке рейт лимита: {e}")
            if self.fail_open:
                return RateLimitResult(
                    allowed=True,
                    current_requests=0,
                    max_requests=max_requests,
                    reset_time=int(time.time()) + window_seconds,
                    retry_after=0,
                    window_seconds=window_seconds
                )
            else:
                return RateLimitResult(
                    allowed=False,
                    current_requests=max_requests,
                    max_requests=max_requests,
                    reset_time=int(time.time()) + window_seconds,
                    retry_after=window_seconds,
                    window_seconds=window_seconds
                )
    
    async def reset_rate_limit(
        self,
        route: str,
        identifier: str,
        user_id: Optional[str] = None,
        admin_action: bool = False
    ) -> bool:
        """Сбросить рейт лимит для конкретного маршрута/идентификатора"""
        redis_conn = await self._get_redis_connection()
        if redis_conn is None:
            print(f"[RateLimiter] Не удалось сбросить лимит, Redis недоступен. Маршрут: {route}, Идентификатор: {identifier}")
            return False
        
        try:
            key = self._get_key(route, identifier)
            await redis_conn.delete(key)
            print(f"[RateLimiter] Лимит сброшен для {key}. Пользователь: {user_id}, Действие админа: {admin_action}")
            return True
        except Exception as e:
            print(f"[RateLimiter] Ошибка при сбросе лимита для {route}/{identifier}: {e}")
            return False
    
    async def get_rate_limit_info(
        self,
        route: str,
        identifier: str,
        max_requests: int,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получить информацию о текущем состоянии рейт лимита"""
        redis_conn = await self._get_redis_connection()
        if redis_conn is None:
            print(f"[RateLimiter] Не удалось получить информацию, Redis недоступен. Маршрут: {route}, Идентификатор: {identifier}")
            return {
                "error": "Redis недоступен",
                "route": route,
                "identifier": identifier,
                "max_requests": max_requests,
                "current_requests": 0,
                "reset_time": int(time.time()) + 3600,
                "ttl": 0
            }
        
        try:
            key = self._get_key(route, identifier)
            
            current_requests = await redis_conn.get(key)
            current_requests = int(current_requests) if current_requests else 0
            
            ttl = await redis_conn.ttl(key)
            
            remaining = max(0, max_requests - current_requests)
            reset_time = int(time.time()) + ttl if ttl > 0 else int(time.time())
            
            return {
                "route": route,
                "identifier": identifier,
                "current_requests": current_requests,
                "max_requests": max_requests,
                "remaining": remaining,
                "reset_time": reset_time,
                "ttl": ttl,
                "user_id": user_id
            }
        except Exception as e:
            print(f"[RateLimiter] Ошибка при получении информации о лимите для {route}/{identifier}: {e}")
            return {
                "error": str(e),
                "route": route,
                "identifier": identifier,
                "max_requests": max_requests,
                "current_requests": 0,
                "reset_time": int(time.time()) + 3600,
                "ttl": 0
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику рейт лимитера
        
        Returns:
            Словарь со статистикой
        """
        redis_conn = await self._get_redis_connection()
        
        if redis_conn is None:
            return {
                "redis_available": False,
                "total_keys": 0,
                "memory_usage": "unknown"
            }
            
        try:
            # Получаем все ключи рейт лимитера
            keys = await redis_conn.keys(f"{self.key_prefix}:*")
            
            # Получаем информацию о памяти
            memory_info = await redis_conn.info("memory")
            memory_used = memory_info.get("used_memory_human", "unknown")
            
            stats = {
                "redis_available": True,
                "total_keys": len(keys),
                "memory_usage": memory_used,
                "key_prefix": self.key_prefix
            }
            
            return stats
            
        except Exception as e:
            print(f"[RateLimiter] Ошибка получения статистики рейт лимитера: {e}")
            return {
                "redis_available": False,
                "total_keys": 0,
                "memory_usage": "unknown"
            }
    
    async def close(self):
        """Закрыть соединение с Redis"""
        if self.redis:
            await self.redis.close()
            self.redis = None
    
    @asynccontextmanager
    async def get_connection(self):
        """Контекстный менеджер для работы с Redis"""
        try:
            yield await self._get_redis_connection()
        finally:
            pass  # Соединение остается открытым для переиспользования


# Глобальный экземпляр RateLimiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Получить глобальный экземпляр RateLimiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_password=settings.REDIS_PASSWORD,
            redis_db=settings.REDIS_DB,
            key_prefix=settings.REDIS_RATE_LIMIT_PREFIX,
            fail_open=settings.REDIS_FAIL_OPEN,
            warning_threshold=settings.REDIS_WARNING_THRESHOLD
        )
    return _rate_limiter


async def close_rate_limiter():
    """Закрыть глобальный рейт лимитер"""
    global _rate_limiter
    if _rate_limiter:
        await _rate_limiter.close()
        _rate_limiter = None 