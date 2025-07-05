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
from config import settings


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


def setup_logging():
    """Настройка системы логирования"""
    # Создаем директорию для логов если её нет
    log_dir = os.path.dirname(settings.log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Очищаем существующие хендлеры
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем форматтер
    formatter = StructuredFormatter()
    
    # Файловый хендлер с ротацией
    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # RabbitMQ хендлер (если настроен)
    if settings.rabbitmq_url:
        try:
            rabbitmq_handler = RabbitMQHandler(
                rabbitmq_url=settings.rabbitmq_url,
                exchange_name=settings.rabbitmq_exchange,
                routing_key=settings.rabbitmq_routing_key,
                level=logging.WARNING
            )
            rabbitmq_handler.setFormatter(formatter)
            root_logger.addHandler(rabbitmq_handler)
        except Exception as e:
            print(f"Failed to setup RabbitMQ handler: {e}")
    
    # Настройка логгеров для внешних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_structured_logger(name: str) -> StructuredLogger:
    """Получить структурированный логгер"""
    return StructuredLogger(name)


def get_2fa_logger() -> StructuredLogger:
    """Получить специализированный логгер для 2FA"""
    return StructuredLogger("2fa_service")


async def close_all_rabbitmq_connections():
    """Закрывает все соединения с RabbitMQ"""
    from .rabbitmq_handler import close_rabbitmq_publisher
    await close_rabbitmq_publisher()


# Инициализируем логирование при импорте
setup_logging() 