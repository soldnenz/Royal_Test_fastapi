# app/logging/utils.py

from typing import Optional, Dict, Any
from fastapi import Request

from .logger_setup import get_structured_logger
from .log_models import LogSection, LogSubsection


def extract_request_info(request: Request) -> Dict[str, str]:
    """Извлекает информацию из FastAPI Request для логирования"""
    return {
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "method": request.method,
        "url": str(request.url),
        "endpoint": request.url.path
    }


def log_user_action(
    section: LogSection,
    subsection: str,
    message: str,
    user_id: Optional[str] = None,
    request: Optional[Request] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    level: str = "info"
):
    """
    Удобная функция для логирования действий пользователя
    
    Args:
        section: Раздел системы
        subsection: Подраздел
        message: Сообщение лога
        user_id: ID пользователя
        request: FastAPI Request объект
        extra_data: Дополнительные данные
        level: Уровень лога (info, warning, error)
    """
    logger = get_structured_logger(f"{section.value}.{subsection}")
    
    log_kwargs = {}
    if user_id:
        log_kwargs["user_id"] = user_id
    if extra_data:
        log_kwargs["extra_data"] = extra_data
    
    if request:
        request_info = extract_request_info(request)
        log_kwargs["ip_address"] = request_info["ip_address"]
        log_kwargs["user_agent"] = request_info["user_agent"]
        if not extra_data:
            log_kwargs["extra_data"] = {}
        log_kwargs["extra_data"].update({
            "method": request_info["method"],
            "endpoint": request_info["endpoint"]
        })
    
    # Вызываем соответствующий метод логгера
    log_method = getattr(logger, level.lower())
    log_method(section, subsection, message, **log_kwargs)


def log_auth_event(
    subsection: str,
    message: str,
    user_id: Optional[str] = None,
    request: Optional[Request] = None,
    success: bool = True,
    extra_data: Optional[Dict[str, Any]] = None
):
    """Специализированная функция для событий аутентификации"""
    level = "info" if success else "warning"
    
    if not extra_data:
        extra_data = {}
    extra_data["success"] = success
    
    log_user_action(
        section=LogSection.AUTH,
        subsection=subsection,
        message=message,
        user_id=user_id,
        request=request,
        extra_data=extra_data,
        level=level
    )


def log_security_event(
    subsection: str,
    message: str,
    severity: str = "warning",
    request: Optional[Request] = None,
    user_id: Optional[str] = None,
    threat_data: Optional[Dict[str, Any]] = None
):
    """Специализированная функция для событий безопасности"""
    logger = get_structured_logger("security_events")
    
    log_kwargs = {}
    if user_id:
        log_kwargs["user_id"] = user_id
    if threat_data:
        log_kwargs["extra_data"] = threat_data
    
    if request:
        request_info = extract_request_info(request)
        log_kwargs["ip_address"] = request_info["ip_address"]
        log_kwargs["user_agent"] = request_info["user_agent"]
        if not log_kwargs.get("extra_data"):
            log_kwargs["extra_data"] = {}
        log_kwargs["extra_data"].update(request_info)
    
    # Все события безопасности как минимум WARNING уровня
    if severity.lower() in ["debug", "info"]:
        severity = "warning"
    
    log_method = getattr(logger, severity.lower())
    log_method(LogSection.SECURITY, subsection, message, **log_kwargs)


def log_websocket_event(
    subsection: str,
    message: str,
    lobby_id: Optional[str] = None,
    user_id: Optional[str] = None,
    connection_info: Optional[Dict[str, Any]] = None,
    level: str = "info"
):
    """Специализированная функция для WebSocket событий"""
    extra_data = {}
    if lobby_id:
        extra_data["lobby_id"] = lobby_id
    if connection_info:
        extra_data.update(connection_info)
    
    log_user_action(
        section=LogSection.WEBSOCKET,
        subsection=subsection,
        message=message,
        user_id=user_id,
        extra_data=extra_data if extra_data else None,
        level=level
    )


def log_api_request(
    request: Request,
    response_status: int,
    processing_time_ms: Optional[float] = None,
    user_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
):
    """Логирование API запросов"""
    request_info = extract_request_info(request)
    
    # Определяем уровень лога по статусу ответа
    if response_status < 400:
        level = "info"
    elif response_status < 500:
        level = "warning"
    else:
        level = "error"
    
    log_data = {
        "status_code": response_status,
        **request_info
    }
    
    if processing_time_ms is not None:
        log_data["processing_time_ms"] = processing_time_ms
    
    if extra_data:
        log_data.update(extra_data)
    
    message = f"{request_info['method']} {request_info['endpoint']} - {response_status}"
    
    log_user_action(
        section=LogSection.API,
        subsection="request",
        message=message,
        user_id=user_id,
        extra_data=log_data,
        level=level
    )


# Декораторы для автоматического логирования
def log_function_call(section: LogSection, subsection: str):
    """Декоратор для автоматического логирования вызовов функций"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_structured_logger(f"{section.value}.{subsection}")
            
            try:
                logger.debug(
                    section, 
                    subsection, 
                    f"Function {func.__name__} called",
                    extra_data={"function": func.__name__}
                )
                
                result = func(*args, **kwargs)
                
                logger.debug(
                    section,
                    subsection,
                    f"Function {func.__name__} completed successfully",
                    extra_data={"function": func.__name__}
                )
                
                return result
            except Exception as e:
                logger.error(
                    section,
                    subsection,
                    f"Function {func.__name__} failed: {str(e)}",
                    extra_data={
                        "function": func.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise
        return wrapper
    return decorator 