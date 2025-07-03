# app/logging/__init__.py

from .logger_setup import setup_application_logging, get_structured_logger, close_all_rabbitmq_connections
from .log_models import LogLevel, LogSection, LogSubsection
from .rabbitmq_handler import get_rabbitmq_publisher, close_rabbitmq_publisher

# Алиас для обратной совместимости
get_logger = get_structured_logger

__all__ = [
    'setup_application_logging',
    'get_structured_logger',
    'get_logger',
    'LogLevel',
    'LogSection',
    'LogSubsection',
    'get_rabbitmq_publisher',
    'close_rabbitmq_publisher',
    'close_all_rabbitmq_connections'
] 