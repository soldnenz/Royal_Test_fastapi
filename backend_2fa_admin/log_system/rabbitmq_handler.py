import logging
import asyncio
import json
from typing import Optional, Dict, Any
from faststream import FastStream
from faststream.rabbit import RabbitBroker
import aio_pika
from .log_models import StructuredLogEntry, LogLevel
from config import settings


class RabbitMQHandler(logging.Handler):
    """
    Кастомный хендлер для отправки логов в RabbitMQ через FastStream
    Отправляет только логи выше уровня INFO (WARNING, ERROR, CRITICAL)
    """
    
    def __init__(
        self,
        rabbitmq_url: str = settings.rabbitmq_url,
        exchange_name: str = settings.rabbitmq_exchange,
        routing_key: str = settings.rabbitmq_routing_key,
        level: int = logging.WARNING,
        **kwargs
    ):
        super().__init__(level)
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self.broker: Optional[RabbitBroker] = None
        self.app: Optional[FastStream] = None
        self._lock = asyncio.Lock()
        self._initialized = False
        self._tasks = set()  # Для отслеживания асинхронных задач
        
    async def _ensure_broker_initialized(self):
        """Инициализирует брокер если он еще не инициализирован"""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    try:
                        # Создаем брокер
                        self.broker = RabbitBroker(self.rabbitmq_url)
                        
                        # Создаем FastStream приложение
                        self.app = FastStream(self.broker)
                        
                        # Подключаемся к RabbitMQ
                        await self.broker.connect()
                        
                        # Создаем exchange через aio-pika
                        connection = await aio_pika.connect_robust(self.rabbitmq_url)
                        channel = await connection.channel()
                        await channel.declare_exchange(
                            self.exchange_name,
                            aio_pika.ExchangeType.TOPIC,
                            durable=True
                        )
                        await connection.close()
                        
                        self._initialized = True
                        
                    except Exception as e:
                        # Логируем ошибку инициализации в stderr
                        print(f"Failed to initialize RabbitMQ handler: {e}")
                        self._initialized = False
    
    def emit(self, record: logging.LogRecord):
        """Отправляет лог в RabbitMQ"""
        try:
            # Проверяем уровень лога - отправляем WARNING и выше
            if record.levelno < logging.WARNING:
                return
            
            # Проверяем, есть ли активный event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Нет активного event loop, пропускаем отправку
                return
                
            # Создаем асинхронную задачу для отправки
            task = asyncio.create_task(self._async_emit(record))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            
        except Exception as e:
            # В случае ошибки логируем в stderr
            print(f"Error in RabbitMQ handler emit: {e}")
    
    async def _async_emit(self, record: logging.LogRecord):
        """Асинхронная отправка лога в RabbitMQ"""
        try:
            await self._ensure_broker_initialized()
            
            if not self._initialized or not self.broker:
                return
            
            # Подготавливаем данные для отправки
            log_data = self._prepare_log_data(record)
            
            # Используем настроенный routing key вместо динамического формирования
            routing_key = self.routing_key
            
            # Отправляем в RabbitMQ
            await self.broker.publish(
                message=log_data,
                exchange=self.exchange_name,
                routing_key=routing_key
            )
            
        except Exception as e:
            # В случае ошибки логируем в stderr
            print(f"Error sending log to RabbitMQ: {e}")
    
    def _prepare_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Подготавливает данные лога для отправки в RabbitMQ"""
        
        # Если у нас есть структурированные данные, используем их
        if hasattr(record, 'structured_data'):
            structured_entry: StructuredLogEntry = record.structured_data
            return {
                "timestamp": structured_entry.timestamp.isoformat(),
                "log_id": structured_entry.log_id,
                "level": structured_entry.level.value,
                "section": structured_entry.section.value,
                "subsection": structured_entry.subsection,
                "message": structured_entry.message,
                "extra_data": structured_entry.extra_data,
                "user_id": structured_entry.user_id,
                "ip_address": structured_entry.ip_address,
                "user_agent": structured_entry.user_agent,
                "source": "2fa_structured_logger"
            }
        
        # Иначе создаем базовую структуру из обычного лога
        return {
            "timestamp": self.formatter.formatTime(record) if self.formatter else "",
            "log_id": str(record.created),
            "level": record.levelname,
            "section": "system",
            "subsection": "general",
            "message": record.getMessage(),
            "extra_data": {
                "module": record.name,
                "function": record.funcName,
                "line": record.lineno,
                "filename": record.filename
            },
            "user_id": getattr(record, 'user_id', None),
            "ip_address": getattr(record, 'ip_address', None),
            "user_agent": getattr(record, 'user_agent', None),
            "source": "2fa_standard_logger"
        }
    
    async def _async_close(self):
        """Асинхронно закрывает соединение с RabbitMQ и все задачи"""
        # Отменяем все pending задачи
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Ждем завершения всех задач
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self.broker:
            try:
                await self.broker.close()
            except Exception as e:
                print(f"Error closing RabbitMQ connection: {e}")

    # ------------------------------------------------------------------
    #  Новый синхронный close — требуется logging.Handler.close
    # ------------------------------------------------------------------
    def close(self):
        """Синхронно вызываемый логгером метод close.

        logging.shutdown() вызывает Handler.close как обычную функцию,
        поэтому здесь оборачиваем асинхронное закрытие, чтобы избежать
        предупреждения "coroutine was never awaited".
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running() and not loop.is_closed():
                # Если цикл уже запущен – просто планируем корутину
                loop.create_task(self._async_close())
            elif not loop.is_closed():
                # Если цикл ещё не запущен – запускаем временный
                loop.run_until_complete(self._async_close())
        except RuntimeError:
            # Нет текущего цикла или цикл закрыт – создаём новый
            try:
                asyncio.run(self._async_close())
            except Exception as e:
                # Игнорируем ошибки закрытия если event loop уже недоступен
                print(f"Info: RabbitMQ connection cleanup skipped: {e}")
        except Exception as e:
            # Игнорируем ошибки закрытия
            print(f"Info: RabbitMQ connection cleanup skipped: {e}")


class RabbitMQLogPublisher:
    """
    Класс для публикации логов в RabbitMQ через FastStream
    Используется для отправки логов выше уровня INFO
    """
    
    def __init__(
        self,
        rabbitmq_url: str = "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs",
        exchange_name: str = "logs",
        routing_key: str = "2fa.logs"
    ):
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self.broker: Optional[RabbitBroker] = None
        self.app: Optional[FastStream] = None
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Инициализирует соединение с RabbitMQ"""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    try:
                        self.broker = RabbitBroker(self.rabbitmq_url)
                        self.app = FastStream(self.broker)
                        
                        await self.broker.connect()
                        
                        # Создаем exchange через aio-pika
                        connection = await aio_pika.connect_robust(self.rabbitmq_url)
                        channel = await connection.channel()
                        await channel.declare_exchange(
                            self.exchange_name,
                            aio_pika.ExchangeType.TOPIC,
                            durable=True
                        )
                        await connection.close()
                        
                        self._initialized = True
                        
                    except Exception as e:
                        print(f"Failed to initialize RabbitMQ publisher: {e}")
                        self._initialized = False
    
    async def publish_log(self, log_entry: StructuredLogEntry):
        """Публикует структурированный лог в RabbitMQ"""
        try:
            await self.initialize()
            
            if not self._initialized or not self.broker:
                return
            
            # Подготавливаем данные для отправки
            log_data = {
                "timestamp": log_entry.timestamp.isoformat(),
                "log_id": log_entry.log_id,
                "level": log_entry.level.value,
                "section": log_entry.section.value,
                "subsection": log_entry.subsection,
                "message": log_entry.message,
                "extra_data": log_entry.extra_data,
                "user_id": log_entry.user_id,
                "ip_address": log_entry.ip_address,
                "user_agent": log_entry.user_agent,
                "source": "2fa_structured_logger"
            }
            
            # Используем настроенный routing key вместо динамического формирования
            routing_key = self.routing_key
            
            # Отправляем в RabbitMQ
            await self.broker.publish(
                message=log_data,
                exchange=self.exchange_name,
                routing_key=routing_key
            )
            
        except Exception as e:
            print(f"Error publishing log to RabbitMQ: {e}")
    
    async def close(self):
        """Закрывает соединение с RabbitMQ"""
        if self.broker:
            try:
                await self.broker.close()
            except Exception as e:
                print(f"Error closing RabbitMQ publisher: {e}")


# Глобальный экземпляр publisher
_rabbitmq_publisher: Optional[RabbitMQLogPublisher] = None


def get_rabbitmq_publisher() -> RabbitMQLogPublisher:
    """Получает глобальный экземпляр RabbitMQ publisher"""
    global _rabbitmq_publisher
    if _rabbitmq_publisher is None:
        import os
        from config import settings
        
        # Используем переменную окружения или настройки, или fallback значение
        rabbitmq_url = os.getenv("RABBITMQ_URL") or settings.rabbitmq_url or "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs"
        
        _rabbitmq_publisher = RabbitMQLogPublisher(
            rabbitmq_url=rabbitmq_url,
            exchange_name=getattr(settings, 'rabbitmq_exchange', 'logs'),
            routing_key=getattr(settings, 'rabbitmq_routing_key', '2fa.logs')
        )
    return _rabbitmq_publisher


async def close_rabbitmq_publisher():
    """Закрывает глобальный RabbitMQ publisher"""
    global _rabbitmq_publisher
    if _rabbitmq_publisher:
        await _rabbitmq_publisher.close()
        _rabbitmq_publisher = None 