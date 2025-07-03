"""
Пример использования RabbitMQ логирования

Этот файл демонстрирует, как настроить и использовать отправку логов в RabbitMQ
через FastStream для логов выше уровня INFO (WARNING, ERROR, CRITICAL).
"""

import asyncio
import os
from .logger_setup import get_structured_logger
from .log_models import LogSection, LogSubsection
from .rabbitmq_handler import get_rabbitmq_publisher, close_rabbitmq_publisher


async def example_rabbitmq_logging():
    """Пример отправки логов в RabbitMQ"""
    
    # Получаем логгер
    logger = get_structured_logger("example.rabbitmq")
    
    print("=== Пример RabbitMQ логирования ===")
    
    # INFO лог - НЕ будет отправлен в RabbitMQ
    logger.info(
        section=LogSection.SYSTEM,
        subsection="example",
        message="Это INFO сообщение - не будет отправлено в RabbitMQ",
        extra_data={"example": True}
    )
    
    # WARNING лог - БУДЕТ отправлен в RabbitMQ
    logger.warning(
        section=LogSection.SYSTEM,
        subsection="example",
        message="Это WARNING сообщение - будет отправлено в RabbitMQ",
        extra_data={"example": True, "level": "warning"}
    )
    
    # ERROR лог - БУДЕТ отправлен в RabbitMQ
    logger.error(
        section=LogSection.SYSTEM,
        subsection="example",
        message="Это ERROR сообщение - будет отправлено в RabbitMQ",
        extra_data={"example": True, "level": "error", "error_code": 500}
    )
    
    # CRITICAL лог - БУДЕТ отправлен в RabbitMQ
    logger.critical(
        section=LogSection.SECURITY,
        subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
        message="Это CRITICAL сообщение - будет отправлено в RabbitMQ",
        extra_data={
            "example": True,
            "level": "critical",
            "security_alert": True,
            "ip_address": "192.168.1.100"
        },
        ip_address="192.168.1.100"
    )
    
    print("Логи отправлены. Проверьте RabbitMQ для получения сообщений.")


async def example_direct_publisher():
    """Пример прямого использования издателя RabbitMQ"""
    
    print("\n=== Пример прямого издателя RabbitMQ ===")
    
    # Получаем издателя
    publisher = get_rabbitmq_publisher()
    
    # Создаем тестовые логи
    from .log_models import StructuredLogEntry, LogLevel
    
    test_logs = [
        StructuredLogEntry(
            level=LogLevel.WARNING,
            section=LogSection.API,
            subsection="rate_limit",
            message="Превышен лимит запросов",
            extra_data={"user_id": "123", "requests_per_minute": 150}
        ),
        StructuredLogEntry(
            level=LogLevel.ERROR,
            section=LogSection.DATABASE,
            subsection="connection",
            message="Ошибка подключения к базе данных",
            extra_data={"database": "mongodb", "error": "Connection timeout"}
        ),
        StructuredLogEntry(
            level=LogLevel.CRITICAL,
            section=LogSection.SECURITY,
            subsection="injection_attempt",
            message="Попытка SQL инъекции",
            extra_data={"query": "SELECT * FROM users; DROP TABLE users;", "ip": "10.0.0.1"},
            ip_address="10.0.0.1"
        )
    ]
    
    # Отправляем логи
    for log_entry in test_logs:
        success = await publisher.publish_log(log_entry)
        print(f"Лог {log_entry.level} отправлен: {'Успешно' if success else 'Ошибка'}")
    
    print("Прямая отправка завершена.")


def setup_environment_variables():
    """Настройка переменных окружения для примера"""
    
    # Настройки RabbitMQ (замените на ваши)
    os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    os.environ.setdefault("RABBITMQ_EXCHANGE", "logs")
    os.environ.setdefault("RABBITMQ_ROUTING_KEY", "application.logs")
    os.environ.setdefault("RABBITMQ_LOGGING", "true")
    
    # Настройки логирования
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("CONSOLE_LOGGING", "true")


async def main():
    """Главная функция для запуска примеров"""
    
    # Настраиваем переменные окружения
    setup_environment_variables()
    
    # Инициализируем логирование
    from .logger_setup import setup_application_logging
    setup_application_logging()
    
    try:
        # Запускаем примеры
        await example_rabbitmq_logging()
        await example_direct_publisher()
        
        # Ждем немного для отправки всех сообщений
        await asyncio.sleep(2)
        
    finally:
        # Закрываем соединение с RabbitMQ
        await close_rabbitmq_publisher()
        print("\nСоединение с RabbitMQ закрыто.")


if __name__ == "__main__":
    # Запускаем пример
    asyncio.run(main()) 