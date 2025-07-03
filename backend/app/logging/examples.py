# app/logging/examples.py

"""
Примеры использования новой структурированной системы логирования
"""

from fastapi import Request
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection
from app.logging.utils import log_auth_event, log_security_event, log_websocket_event, log_api_request


# ===== БАЗОВОЕ ИСПОЛЬЗОВАНИЕ =====

def example_basic_logging():
    """Базовый пример использования структурированного логгера"""
    
    # Получаем логгер для модуля аутентификации
    auth_logger = get_structured_logger("auth.login")
    
    # Логируем успешный вход
    auth_logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.LOGIN,
        message="Пользователь успешно вошел в систему",
        user_id="507f1f77bcf86cd799439011",
        ip_address="192.168.1.100",
        extra_data={
            "login_method": "email",
            "session_duration": 3600
        }
    )
    
    # Логируем ошибку
    auth_logger.error(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.LOGIN,
        message="Неудачная попытка входа - неверный пароль",
        ip_address="192.168.1.100",
        extra_data={
            "attempted_email": "user@example.com",
            "reason": "invalid_password"
        }
    )


# ===== ИСПОЛЬЗОВАНИЕ УТИЛИТАРНЫХ ФУНКЦИЙ =====

def example_auth_logging(request: Request, user_id: str):
    """Пример логирования событий аутентификации"""
    
    # Успешный вход
    log_auth_event(
        subsection=LogSubsection.AUTH.LOGIN,
        message="Аутентификация пользователя прошла успешно",
        user_id=user_id,
        request=request,
        success=True,
        extra_data={"auth_method": "password"}
    )
    
    # Неуспешный вход
    log_auth_event(
        subsection=LogSubsection.AUTH.LOGIN,
        message="Предоставлены неверные учетные данные",
        request=request,
        success=False,
        extra_data={"attempted_email": "user@example.com"}
    )


def example_security_logging(request: Request):
    """Пример логирования событий безопасности"""
    
    # Подозрительная активность
    log_security_event(
        subsection=LogSubsection.SECURITY.INJECTION_ATTEMPT,
        message="Обнаружена попытка SQL инъекции",
        severity="critical",
        request=request,
        threat_data={
            "payload": "'; DROP TABLE users; --",
            "parameter": "username",
            "detected_by": "input_validation"
        }
    )
    
    # Превышение лимита запросов
    log_security_event(
        subsection=LogSubsection.SECURITY.RATE_LIMIT,
        message="Превышен лимит запросов",
        severity="warning", 
        request=request,
        threat_data={
            "requests_count": 150,
            "time_window": "60s",
            "limit": 100
        }
    )


def example_websocket_logging(user_id: str, lobby_id: str):
    """Пример логирования WebSocket событий"""
    
    # Подключение к лобби
    log_websocket_event(
        subsection=LogSubsection.WEBSOCKET.CONNECTION,
        message="Пользователь подключился к лобби",
        lobby_id=lobby_id,
        user_id=user_id,
        connection_info={
            "connection_type": "websocket",
            "protocol": "wss",
            "total_connections": 5
        }
    )
    
    # Отключение
    log_websocket_event(
        subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
        message="Пользователь отключился от лобби",
        lobby_id=lobby_id,
        user_id=user_id,
        connection_info={
            "reason": "user_request",
            "duration_seconds": 1800
        }
    )


def example_api_request_logging(request: Request, user_id: str):
    """Пример логирования API запросов"""
    
    # Успешный запрос
    log_api_request(
        request=request,
        response_status=200,
        processing_time_ms=45.2,
        user_id=user_id,
        extra_data={
            "endpoint_type": "protected",
            "data_size_bytes": 1024
        }
    )
    
    # Ошибка сервера
    log_api_request(
        request=request,
        response_status=500,
        processing_time_ms=125.8,
        user_id=user_id,
        extra_data={
            "error_type": "database_connection",
            "retry_count": 3
        }
    )


# ===== СПЕЦИАЛИЗИРОВАННЫЕ ЛОГГЕРЫ =====

def example_specialized_loggers():
    """Пример использования специализированных логгеров"""
    
    # Логгер для WebSocket
    ws_logger = get_structured_logger("websocket.lobby")
    ws_logger.info(
        section=LogSection.WEBSOCKET,
        subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
        message="Тест в лобби запущен",
        extra_data={
            "lobby_id": "lobby_123", 
            "participants_count": 5,
            "test_type": "multiplayer"
        }
    )
    
    # Логгер для файлов
    files_logger = get_structured_logger("files.access")
    files_logger.warning(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS_CHECK,
        message="Попытка несанкционированного доступа к файлу",
        user_id="user_456",
        extra_data={
            "file_id": "file_789",
            "access_type": "download",
            "reason": "user_not_in_lobby"
        }
    )


# ===== ДЕКОРАТОР ЛОГИРОВАНИЯ =====

from app.logging.utils import log_function_call

@log_function_call(LogSection.TEST, LogSubsection.TEST.VALIDATION)
def example_decorated_function(test_id: str, answers: dict):
    """Пример функции с автоматическим логированием"""
    # Логика валидации теста
    if not answers:
        raise ValueError("No answers provided")
    
    return {"valid": True, "score": 85}


# ===== ПРИМЕР ЛОГИРОВАНИЯ ОШИБОК =====

def example_error_logging():
    """Пример логирования ошибок и исключений"""
    
    logger = get_structured_logger("database.operations")
    
    try:
        # Некая операция с базой данных
        result = perform_database_operation()
    except ConnectionError as e:
        logger.error(
            section=LogSection.DATABASE,
            subsection="connection",
            message=f"Database connection failed: {str(e)}",
            extra_data={
                "error_type": "ConnectionError",
                "retry_count": 3,
                "database_host": "mongodb://localhost:27017"
            }
        )
        raise
    except Exception as e:
        logger.critical(
            section=LogSection.DATABASE,
            subsection="unknown_error", 
            message=f"Unexpected database error: {str(e)}",
            extra_data={
                "error_type": type(e).__name__,
                "operation": "find_user",
                "stack_trace": str(e)
            }
        )
        raise


def perform_database_operation():
    """Заглушка для примера"""
    pass


# ===== НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====

"""
Для использования системы логирования настройте переменные окружения:

# .env файл
LOG_LEVEL=INFO
LOG_FILE=logs/application.log
SECURITY_LOG_FILE=logs/security.log
CONSOLE_LOGGING=true
LOG_MAX_BYTES=10485760  # 10 MB
LOG_BACKUP_COUNT=5

# Опционально - отключить консольное логирование в продакшене
CONSOLE_LOGGING=false
"""


# ===== ПРИМЕР СТРУКТУРЫ ЛОГА =====

"""
Пример лога в JSON формате:

{
    "timestamp": "2024-01-15 14:30:45 +05",
    "log_id": "a7b3c5d1",
    "level": "INFO",
    "section": "auth",
    "subsection": "login",
    "message": "User logged in successfully",
    "user_id": "507f1f77bcf86cd799439011",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "extra_data": {
        "login_method": "email",
        "session_duration": 3600,
        "method": "POST",
        "endpoint": "/auth/login"
    }
}
""" 