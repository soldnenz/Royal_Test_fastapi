"""
Конфигурация для рейт лимитов
Определяет правила ограничения для различных маршрутов
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum


class RateLimitType(Enum):
    """Тип рейт лимита"""
    IP = "ip"
    USER = "user"
    COMBINED = "combined"  # И IP, и USER


@dataclass
class RateLimitRule:
    """Правило рейт лимита"""
    max_requests: int
    window_seconds: int
    rate_limit_type: RateLimitType = RateLimitType.IP
    warning_threshold: float = 0.8
    description: str = ""
    
    def __post_init__(self):
        if self.warning_threshold < 0 or self.warning_threshold > 1:
            raise ValueError("warning_threshold должен быть между 0 и 1")


class RateLimitConfig:
    """Конфигурация рейт лимитов для всех маршрутов"""
    
    def __init__(self):
        self.rules: Dict[str, RateLimitRule] = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Настройка правил по умолчанию"""
        
        # Аутентификация - строгие лимиты
        self.rules["auth_login"] = RateLimitRule(
            max_requests=5,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.6,
            description="Попытки входа в систему"
        )
        
        self.rules["auth_register"] = RateLimitRule(
            max_requests=3,
            window_seconds=600,  # 10 минут
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.5,
            description="Регистрация новых пользователей"
        )
        
        self.rules["auth_password_reset"] = RateLimitRule(
            max_requests=3,
            window_seconds=1800,  # 30 минут
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.5,
            description="Сброс пароля"
        )
        
        # API общего назначения
        self.rules["api_general"] = RateLimitRule(
            max_requests=60,
            window_seconds=60,  # 1 минута
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.8,
            description="Общие API запросы"
        )
        
        # Пользовательские данные
        self.rules["user_profile"] = RateLimitRule(
            max_requests=30,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.8,
            description="Обновление профиля пользователя"
        )
        
        # Тестирование
        self.rules["test_start"] = RateLimitRule(
            max_requests=10,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.7,
            description="Начало прохождения теста"
        )
        
        self.rules["test_answer"] = RateLimitRule(
            max_requests=200,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.9,
            description="Отправка ответов на вопросы"
        )
        
        self.rules["test_results"] = RateLimitRule(
            max_requests=20,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.8,
            description="Получение результатов теста"
        )
        
        # Лобби и многопользовательские игры
        self.rules["lobby_create"] = RateLimitRule(
            max_requests=5,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.6,
            description="Создание игрового лобби"
        )
        
        self.rules["lobby_join"] = RateLimitRule(
            max_requests=20,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.8,
            description="Присоединение к лобби"
        )
        
        self.rules["lobby_actions"] = RateLimitRule(
            max_requests=100,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.9,
            description="Действия в лобби"
        )
        
        # WebSocket соединения
        self.rules["websocket_connect"] = RateLimitRule(
            max_requests=10,
            window_seconds=60,
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.7,
            description="Установка WebSocket соединения"
        )
        
        self.rules["websocket_messages"] = RateLimitRule(
            max_requests=300,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.9,
            description="Отправка WebSocket сообщений"
        )
        
        # Медиа файлы
        self.rules["media_upload"] = RateLimitRule(
            max_requests=10,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.7,
            description="Загрузка медиа файлов"
        )
        
        self.rules["media_download"] = RateLimitRule(
            max_requests=100,
            window_seconds=60,
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.8,
            description="Скачивание медиа файлов"
        )
        
        # Платежи и транзакции
        self.rules["payment_create"] = RateLimitRule(
            max_requests=5,
            window_seconds=600,  # 10 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.4,
            description="Создание платежей"
        )
        
        self.rules["subscription_manage"] = RateLimitRule(
            max_requests=10,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.7,
            description="Управление подписками"
        )
        
        # Реферальная система
        self.rules["referral_actions"] = RateLimitRule(
            max_requests=20,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.8,
            description="Действия с реферальной системой"
        )
        
        # Отчеты и жалобы
        self.rules["report_create"] = RateLimitRule(
            max_requests=3,
            window_seconds=1800,  # 30 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.5,
            description="Создание отчетов/жалоб"
        )
        
        # Административные функции
        self.rules["admin_actions"] = RateLimitRule(
            max_requests=100,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.9,
            description="Административные действия"
        )
        
        # Статистика
        self.rules["stats_view"] = RateLimitRule(
            max_requests=60,
            window_seconds=60,
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.8,
            description="Просмотр статистики"
        )
        
        # Поиск и фильтрация
        self.rules["search_requests"] = RateLimitRule(
            max_requests=30,
            window_seconds=60,
            rate_limit_type=RateLimitType.IP,
            warning_threshold=0.8,
            description="Поисковые запросы"
        )
        
        # Экспорт данных
        self.rules["export_data"] = RateLimitRule(
            max_requests=5,
            window_seconds=300,  # 5 минут
            rate_limit_type=RateLimitType.USER,
            warning_threshold=0.6,
            description="Экспорт данных"
        )
    
    def get_rule(self, route: str) -> Optional[RateLimitRule]:
        """Получить правило для маршрута"""
        return self.rules.get(route)
    
    def add_rule(self, route: str, rule: RateLimitRule):
        """Добавить правило для маршрута"""
        self.rules[route] = rule
    
    def remove_rule(self, route: str):
        """Удалить правило для маршрута"""
        if route in self.rules:
            del self.rules[route]
    
    def get_all_routes(self) -> List[str]:
        """Получить все настроенные маршруты"""
        return list(self.rules.keys())
    
    def get_rules_by_type(self, rate_limit_type: RateLimitType) -> Dict[str, RateLimitRule]:
        """Получить все правила определенного типа"""
        return {
            route: rule for route, rule in self.rules.items()
            if rule.rate_limit_type == rate_limit_type
        }
    
    def update_rule(self, route: str, **kwargs):
        """Обновить существующее правило"""
        if route in self.rules:
            rule = self.rules[route]
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
    
    def get_strict_routes(self) -> List[str]:
        """Получить маршруты с наиболее строгими лимитами"""
        strict_routes = []
        for route, rule in self.rules.items():
            # Считаем строгими те, у которых меньше 10 запросов за 5 минут
            requests_per_5min = (rule.max_requests / rule.window_seconds) * 300
            if requests_per_5min < 10:
                strict_routes.append(route)
        return strict_routes
    
    def get_permissive_routes(self) -> List[str]:
        """Получить маршруты с наиболее мягкими лимитами"""
        permissive_routes = []
        for route, rule in self.rules.items():
            # Считаем мягкими те, у которых больше 100 запросов за 5 минут
            requests_per_5min = (rule.max_requests / rule.window_seconds) * 300
            if requests_per_5min > 100:
                permissive_routes.append(route)
        return permissive_routes


# Глобальная конфигурация
_config: Optional[RateLimitConfig] = None


def get_rate_limit_config() -> RateLimitConfig:
    """Получить глобальную конфигурацию рейт лимитов"""
    global _config
    if _config is None:
        _config = RateLimitConfig()
    return _config


def update_rate_limit_config(config: RateLimitConfig):
    """Обновить глобальную конфигурацию рейт лимитов"""
    global _config
    _config = config 