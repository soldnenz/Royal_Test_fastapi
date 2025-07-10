"""
Модели для логирования Rate Limiter
Специализированные структуры для детального логирования rate limiting событий
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
import pytz

from .log_models import StructuredLogEntry, LogLevel, LogSection, LogSubsection


@dataclass
class RateLimitEvent:
    """Базовая модель события rate limit"""
    route: str
    ip_address: str
    user_id: Optional[str] = None
    current_requests: int = 0
    max_requests: int = 0
    window_seconds: int = 0
    ttl: int = 0
    description: str = ""


@dataclass
class RateLimitWarningEvent(RateLimitEvent):
    """Модель предупреждения о приближении к лимиту"""
    usage_percentage: float = 0.0
    threshold: float = 0.8


@dataclass
class RateLimitExceededEvent(RateLimitEvent):
    """Модель превышения rate limit"""
    retry_after: int = 0
    block_reason: str = ""


@dataclass
class RateLimitHighActivityEvent:
    """Модель высокой активности rate limiting"""
    blocked_requests: int
    total_requests: int
    block_rate: float
    current_route: str
    ip_address: str
    detection_threshold: int = 10


@dataclass
class RateLimitStatsEvent:
    """Модель статистики rate limiter"""
    total_requests: int
    blocked_requests: int
    block_rate: float
    redis_memory_used: str
    available_routes: list
    uptime_seconds: Optional[int] = None


class RateLimitLogger:
    """Специализированный логгер для Rate Limiter"""
    
    def __init__(self, base_logger):
        """
        Args:
            base_logger: Базовый логгер из системы логирования проекта
        """
        self.logger = base_logger
    
    def log_warning(self, event: RateLimitWarningEvent):
        """Логирование предупреждения о приближении к лимиту"""
        user_info = f", user_id: {event.user_id}" if event.user_id else ""
        self.logger.warning(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_WARNING,
            message=f"Предупреждение rate limit для {event.route}: использовано {event.current_requests}/{event.max_requests} запросов ({event.usage_percentage:.1f}%), TTL: {event.ttl}с, IP: {event.ip_address}{user_info}"
        )
    
    def log_exceeded(self, event: RateLimitExceededEvent):
        """Логирование превышения rate limit"""
        user_info = f", user_id: {event.user_id}" if event.user_id else ""
        self.logger.warning(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_EXCEEDED,
            message=f"Превышен rate limit для {event.route}: {event.current_requests}/{event.max_requests} запросов, повторить через {event.retry_after}с, IP: {event.ip_address}{user_info} - {event.description}"
        )
    
    def log_blocked(self, event: RateLimitExceededEvent):
        """Логирование блокировки запроса"""
        severity = "критично" if event.current_requests > event.max_requests * 2 else "высоко"
        user_info = f", user_id: {event.user_id}" if event.user_id else ""
        self.logger.error(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_BLOCKED,
            message=f"Запрос заблокирован rate limiter для {event.route}, серьезность: {severity}, IP: {event.ip_address}{user_info}"
        )
    
    def log_high_activity(self, event: RateLimitHighActivityEvent):
        """Логирование высокой активности блокировок"""
        severity = "критическая" if event.block_rate > 50 else "высокая"
        alert = "требует немедленного внимания" if event.block_rate > 80 else "требует мониторинга"
        self.logger.error(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_HIGH_ACTIVITY,
            message=f"Обнаружена {severity} активность блокировок rate limit: {event.blocked_requests}/{event.total_requests} ({event.block_rate:.1f}%), текущий route: {event.current_route}, IP: {event.ip_address}, {alert}"
        )
    
    def log_stats(self, event: RateLimitStatsEvent):
        """Логирование статистики rate limiter"""
        health = "здоровое" if event.block_rate < 10 else "тревожное" if event.block_rate < 50 else "критическое"
        self.logger.info(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_STATS,
            message=f"Статистика rate limiter: {event.total_requests} запросов, {event.blocked_requests} заблокировано ({event.block_rate:.1f}%), память Redis: {event.redis_memory_used}, состояние: {health}, доступно routes: {len(event.available_routes)}"
        )
    
    def log_reset(self, route: str, ip: str, user_id: Optional[str] = None, admin_action: bool = False):
        """Логирование сброса rate limit"""
        reset_type = "административный" if admin_action else "автоматический"
        user_info = f", user_id: {user_id}" if user_id else ""
        self.logger.info(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_RESET,
            message=f"Сброс rate limit для {route}: {reset_type} сброс, IP: {ip}{user_info}"
        )
    
    def log_info_request(self, route: str, ip: str, info_data: Dict[str, Any], user_id: Optional[str] = None):
        """Логирование запроса информации о rate limit"""
        current_reqs = info_data.get('current_requests', 0)
        max_reqs = info_data.get('max_requests', 0)
        user_info = f", user_id: {user_id}" if user_id else ""
        self.logger.debug(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_INFO,
            message=f"Запрос информации о rate limit для {route}: {current_reqs}/{max_reqs} запросов, IP: {ip}{user_info}"
        )
    
    def log_fail_open(self, route: str, ip: str, error: str, user_id: Optional[str] = None):
        """Логирование fail-open режима"""
        user_info = f", user_id: {user_id}" if user_id else ""
        self.logger.warning(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.RATE_LIMIT_FAIL_OPEN,
            message=f"Rate limiter переходит в режим fail-open для {route} из-за ошибки Redis: {error}, IP: {ip}{user_info} - требуется проверка подключения к Redis"
        )
    
    def log_connection_established(self, redis_host: str, redis_port: int, redis_db: int):
        """Логирование установки соединения с Redis"""
        self.logger.info(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.CONNECTION,
            message=f"Установлено соединение Redis для rate limiter: {redis_host}:{redis_port}, БД: {redis_db}"
        )
    
    def log_connection_error(self, redis_host: str, redis_port: int, error: str):
        """Логирование ошибки соединения с Redis"""
        self.logger.error(
            section=LogSection.REDIS,
            subsection=LogSubsection.REDIS.ERROR,
            message=f"Ошибка подключения к Redis для rate limiter: {redis_host}:{redis_port}, ошибка: {error} - rate limiting недоступен"
        )


def create_rate_limit_warning_event(
    route: str,
    ip: str,
    current_requests: int,
    max_requests: int,
    window_seconds: int,
    ttl: int,
    threshold: float = 0.8,
    user_id: Optional[str] = None,
    description: str = ""
) -> RateLimitWarningEvent:
    """Создание события предупреждения rate limit"""
    usage_percentage = (current_requests / max_requests) * 100 if max_requests > 0 else 0
    
    return RateLimitWarningEvent(
        route=route,
        ip_address=ip,
        user_id=user_id,
        current_requests=current_requests,
        max_requests=max_requests,
        window_seconds=window_seconds,
        ttl=ttl,
        description=description,
        usage_percentage=usage_percentage,
        threshold=threshold
    )


def create_rate_limit_exceeded_event(
    route: str,
    ip: str,
    current_requests: int,
    max_requests: int,
    window_seconds: int,
    ttl: int,
    retry_after: int,
    user_id: Optional[str] = None,
    description: str = "",
    block_reason: str = ""
) -> RateLimitExceededEvent:
    """Создание события превышения rate limit"""
    return RateLimitExceededEvent(
        route=route,
        ip_address=ip,
        user_id=user_id,
        current_requests=current_requests,
        max_requests=max_requests,
        window_seconds=window_seconds,
        ttl=ttl,
        retry_after=retry_after,
        description=description,
        block_reason=block_reason
    )


def create_rate_limit_high_activity_event(
    blocked_requests: int,
    total_requests: int,
    current_route: str,
    ip: str,
    detection_threshold: int = 10
) -> RateLimitHighActivityEvent:
    """Создание события высокой активности блокировок"""
    block_rate = (blocked_requests / total_requests * 100) if total_requests > 0 else 0
    
    return RateLimitHighActivityEvent(
        blocked_requests=blocked_requests,
        total_requests=total_requests,
        block_rate=block_rate,
        current_route=current_route,
        ip_address=ip,
        detection_threshold=detection_threshold
    ) 