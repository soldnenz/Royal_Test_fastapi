# app/logging/logger_setup.py

import logging
import json
import os
import inspect
import asyncio
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger
from logging.handlers import RotatingFileHandler

from .log_models import StructuredLogEntry, LogLevel, LogSection
from .rabbitmq_handler import RabbitMQHandler, get_rabbitmq_publisher


class StructuredFormatter(logging.Formatter):
    """Кастомный форматтер для структурированных логов"""
    
    def format(self, record):
        # Если в record есть structured_data, используем его
        if hasattr(record, 'structured_data'):
            return record.structured_data.to_json_string()
        
        # Иначе создаем базовую структуру
        entry = StructuredLogEntry(
            level=LogLevel(record.levelname),
            section=LogSection.SYSTEM,
            subsection="general",
            message=record.getMessage(),
            extra_data={"module": record.name}
        )
        return entry.to_json_string()


class StructuredLogger:
    """Обертка для создания структурированных логов"""
    
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
        self._rabbitmq_tasks = set()  # Для отслеживания задач RabbitMQ
    
    def _get_caller_info(self) -> Dict[str, str]:
        """
        Автоматически определяет файл и функцию, откуда был вызван лог
        
        Returns:
            Dict с информацией о файле и функции
        """
        try:
            # Получаем стек вызовов
            # [0] - _get_caller_info
            # [1] - _log 
            # [2] - info/debug/warning/error/critical
            # [3] - реальная функция, которая вызвала лог
            frame = inspect.currentframe()
            caller_frame = frame.f_back.f_back.f_back
            
            if caller_frame:
                # Получаем информацию о файле
                filename = caller_frame.f_code.co_filename
                # Извлекаем только имя файла без пути
                file_name = filename.split('/')[-1].split('\\')[-1]
                
                # Получаем имя функции
                function_name = caller_frame.f_code.co_name
                
                # Получаем номер строки
                line_number = caller_frame.f_lineno
                
                return {
                    "source_file": file_name,
                    "source_function": function_name,
                    "source_line": line_number
                }
            else:
                return {
                    "source_file": "unknown",
                    "source_function": "unknown", 
                    "source_line": 0
                }
        except Exception:
            # В случае ошибки возвращаем базовую информацию
            return {
                "source_file": "unknown",
                "source_function": "unknown", 
                "source_line": 0
            }
    
    def _log(
        self,
        level: LogLevel,
        section: LogSection,
        subsection: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Внутренний метод для логирования"""
        # Автоматически получаем информацию о вызывающем коде
        caller_info = self._get_caller_info()
        
        # Объединяем caller_info с переданными extra_data
        combined_extra_data = {**(extra_data or {}), **caller_info}
        
        entry = StructuredLogEntry(
            level=level,
            section=section,
            subsection=subsection,
            message=message,
            extra_data=combined_extra_data,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Создаем LogRecord с нашими структурированными данными
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=getattr(logging, level.value),
            fn="",
            lno=0,
            msg="",
            args=(),
            exc_info=None
        )
        log_record.structured_data = entry
        
        self.logger.handle(log_record)
        
        # Отправляем логи выше INFO в RabbitMQ с правильным управлением задачами
        if level in [LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]:
            self._schedule_rabbitmq_send(entry)
    
    def _schedule_rabbitmq_send(self, entry: StructuredLogEntry):
        """Планирует отправку лога в RabbitMQ с правильным управлением задачами"""
        try:
            # Проверяем, есть ли активный event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Нет активного event loop, пропускаем отправку
                return
            
            # Создаем задачу с обработкой исключений
            task = asyncio.create_task(self._send_to_rabbitmq(entry))
            
            # Добавляем задачу в отслеживание
            self._rabbitmq_tasks.add(task)
            
            # Добавляем callback для удаления задачи из отслеживания
            def cleanup_task(t):
                try:
                    self._rabbitmq_tasks.discard(t)
                except Exception:
                    pass
            
            task.add_done_callback(cleanup_task)
            
        except Exception as e:
            # В случае ошибки логируем в stderr
            print(f"Error scheduling RabbitMQ send: {e}")
    
    async def _send_to_rabbitmq(self, entry: StructuredLogEntry):
        """Отправляет лог в RabbitMQ"""
        try:
            publisher = get_rabbitmq_publisher()
            await publisher.publish_log(entry)
        except Exception as e:
            # В случае ошибки логируем в stderr
            print(f"Error sending log to RabbitMQ: {e}")
    
    async def wait_for_rabbitmq_tasks(self):
        """Ждет завершения всех задач RabbitMQ"""
        if self._rabbitmq_tasks:
            await asyncio.gather(*self._rabbitmq_tasks, return_exceptions=True)
            self._rabbitmq_tasks.clear()
    
    def debug(self, section: LogSection, subsection: str, message: str, **kwargs):
        """DEBUG уровень"""
        self._log(LogLevel.DEBUG, section, subsection, message, **kwargs)
    
    def info(self, section: LogSection, subsection: str, message: str, **kwargs):
        """INFO уровень"""
        self._log(LogLevel.INFO, section, subsection, message, **kwargs)
    
    def warning(self, section: LogSection, subsection: str, message: str, **kwargs):
        """WARNING уровень"""
        self._log(LogLevel.WARNING, section, subsection, message, **kwargs)
    
    def error(self, section: LogSection, subsection: str, message: str, **kwargs):
        """ERROR уровень"""
        self._log(LogLevel.ERROR, section, subsection, message, **kwargs)
    
    def critical(self, section: LogSection, subsection: str, message: str, **kwargs):
        """CRITICAL уровень"""
        self._log(LogLevel.CRITICAL, section, subsection, message, **kwargs)


def setup_application_logging():
    """
    Настройка централизованного логирования приложения
    
    Особенности:
    - Структурированные JSON логи с GMT+5 временем
    - Уникальный ID для каждого лога
    - Стандартизированные разделы и подразделы
    - Ротация файлов логов
    - Настройка через переменные окружения
    - Отправка логов выше INFO в RabbitMQ через FastStream
    """
    
    # Получаем настройки из переменных окружения
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "logs/application.log")
    console_logging = os.getenv("CONSOLE_LOGGING", "true").lower() == "true"
    rabbitmq_enabled = os.getenv("RABBITMQ_LOGGING", "true").lower() == "true"
    
    # Создаем директорию для логов если её нет
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Получаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Удаляем все существующие хендлеры
    while root_logger.hasHandlers():
        root_logger.removeHandler(root_logger.handlers[0])
    
    # Создаем наш кастомный форматтер
    formatter = StructuredFormatter()
    
    # ===== КОНСОЛЬНЫЙ ХЕНДЛЕР =====
    if console_logging:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
    
    # ===== ФАЙЛОВЫЙ ХЕНДЛЕР С РОТАЦИЕЙ =====
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10 MB по умолчанию
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "50"))   # 50 файлов
    
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    # ===== RABBITMQ ХЕНДЛЕР =====
    rabbitmq_handlers = []
    if rabbitmq_enabled:
        try:
            rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs")
            exchange_name = os.getenv("RABBITMQ_EXCHANGE", "logs")
            routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "application.logs")
            
            rabbitmq_handler = RabbitMQHandler(
                rabbitmq_url=rabbitmq_url,
                exchange_name=exchange_name,
                routing_key=routing_key,
                level=logging.WARNING  # Только WARNING и выше
            )
            rabbitmq_handler.setFormatter(formatter)
            root_logger.addHandler(rabbitmq_handler)
            rabbitmq_handlers.append(rabbitmq_handler)
            
        except Exception as e:
            print(f"Failed to setup RabbitMQ handler: {e}")
    
    # Сохраняем ссылки на хендлеры для правильного закрытия
    root_logger.rabbitmq_handlers = rabbitmq_handlers
    
    # ===== ОТДЕЛЬНЫЙ ФАЙЛ ДЛЯ БЕЗОПАСНОСТИ =====
    security_log_file = os.getenv("SECURITY_LOG_FILE", "logs/security.log")
    security_dir = os.path.dirname(security_log_file)
    if security_dir and not os.path.exists(security_dir):
        os.makedirs(security_dir)
    
    security_handler = RotatingFileHandler(
        filename=security_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    security_handler.setFormatter(formatter)
    security_handler.setLevel("WARNING")  # Только важные события безопасности
    
    # Создаем специальный логгер для безопасности
    security_logger = logging.getLogger("security_events")
    security_logger.setLevel("WARNING")
    security_logger.addHandler(security_handler)
    security_logger.propagate = False  # Не передаем в корневой логгер
    
    # ===== НАСТРОЙКА UVICORN ЛОГГЕРА =====
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_logger.addHandler(console_handler if console_logging else file_handler)
    uvicorn_logger.setLevel(log_level)
    uvicorn_logger.propagate = False
    
    # Логируем успешную инициализацию
    init_logger = get_structured_logger("system.init")
    init_logger.info(
        section=LogSection.SYSTEM,
        subsection="startup",
        message="Система структурированного логирования успешно инициализирована",
        extra_data={
            "log_level": log_level,
            "log_file": log_file,
            "console_logging": console_logging,
            "rabbitmq_enabled": rabbitmq_enabled,
            "max_file_size_mb": max_bytes / 1024 / 1024,
            "backup_files": backup_count
        }
    )


def get_structured_logger(name: str) -> StructuredLogger:
    """
    Получить структурированный логгер для модуля
    
    Args:
        name: Имя модуля/компонента (например: "auth.login", "websocket.connection")
    
    Returns:
        StructuredLogger: Настроенный структурированный логгер
    """
    return StructuredLogger(name)


# Удобные алиасы для быстрого получения логгеров по разделам
def get_auth_logger() -> StructuredLogger:
    """Логгер для аутентификации"""
    return get_structured_logger("auth")

def get_websocket_logger() -> StructuredLogger:
    """Логгер для WebSocket"""
    return get_structured_logger("websocket")

def get_security_logger() -> StructuredLogger:
    """Логгер для безопасности"""
    return StructuredLogger("security_events")

def get_api_logger() -> StructuredLogger:
    """Логгер для API"""
    return get_structured_logger("api")

def get_admin_logger() -> StructuredLogger:
    """Логгер для админки"""
    return get_structured_logger("admin")


async def close_all_rabbitmq_connections():
    """Закрывает все RabbitMQ соединения"""
    import logging
    
    # Закрываем хендлеры в корневом логгере
    root_logger = logging.getLogger()
    if hasattr(root_logger, 'rabbitmq_handlers'):
        for handler in root_logger.rabbitmq_handlers:
            if hasattr(handler, 'close'):
                try:
                    await handler.close()
                except Exception as e:
                    print(f"Error closing RabbitMQ handler: {e}")
    
    # Закрываем глобальный издатель
    from .rabbitmq_handler import close_rabbitmq_publisher
    await close_rabbitmq_publisher() 