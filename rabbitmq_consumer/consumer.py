import asyncio
import json
import os
from datetime import datetime
import pytz
import aio_pika
from typing import Dict, Any

# Настройки RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
EXCHANGE_NAME = os.getenv("RABBITMQ_EXCHANGE")

# Поддерживаемые routing keys для разных сервисов
ROUTING_KEYS = [
    "logs.info.*",           # Все информационные логи
    "logs.error.*",          # Все логи ошибок
]

QUEUE_NAME = os.getenv("RABBITMQ_QUEUE")

# Timezone для форматирования времени
KZ_TIMEZONE = pytz.timezone('Asia/Almaty')

class LogProcessor:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self._running = False
    
    async def initialize(self):
        """Инициализация подключения к RabbitMQ"""
        try:
            print(f"[CONSUMER] Подключение к RabbitMQ: {RABBITMQ_URL}")
            
            # Создаем соединение
            self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self.channel = await self.connection.channel()
            
            print("[CONSUMER] Подключение установлено")
            
            # Объявляем exchange
            exchange = await self.channel.declare_exchange(
                EXCHANGE_NAME,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            print(f"[CONSUMER] Exchange '{EXCHANGE_NAME}' объявлен")
            
            # Объявляем очередь с нужными параметрами
            self.queue = await self.channel.declare_queue(
                QUEUE_NAME,
                durable=True,
                auto_delete=False
            )
            
            # Привязываем очередь к exchange для всех routing keys
            for routing_key in ROUTING_KEYS:
                await self.queue.bind(
                    exchange=exchange,
                    routing_key=routing_key
                )
                print(f"[CONSUMER] Очередь привязана к exchange с routing_key: {routing_key}")
            
            print(f"[CONSUMER] Начинаем прослушивание очереди {QUEUE_NAME}")
            print(f"[CONSUMER] Поддерживаемые routing keys: {', '.join(ROUTING_KEYS)}")
            
        except Exception as e:
            print(f"[CONSUMER] Ошибка инициализации: {e}")
            raise
    
    def format_log_message(self, log_data: Dict[str, Any]) -> str:
        """Форматирует лог для вывода"""
        try:
            # Парсим timestamp если он есть
            timestamp = log_data.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    dt_kz = dt.astimezone(KZ_TIMEZONE)
                    formatted_time = dt_kz.strftime("%Y-%m-%d %H:%M:%S %z")
                except ValueError:
                    formatted_time = timestamp
            else:
                formatted_time = datetime.now(KZ_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %z")
            
            # Форматируем основную информацию
            level = log_data.get("level", "UNKNOWN")
            section = log_data.get("section", "unknown")
            subsection = log_data.get("subsection", "unknown")
            message = log_data.get("message", "")
            source = log_data.get("source", "unknown")
            
            # Форматируем дополнительные данные
            extra_data = log_data.get("extra_data", {})
            extra_str = json.dumps(extra_data, ensure_ascii=False, indent=2)
            
            # Определяем эмодзи для уровня (используем ASCII символы для Windows)
            level_emoji = {
                "DEBUG": "[DEBUG]",
                "INFO": "[INFO]",
                "WARNING": "[WARN]",
                "ERROR": "[ERROR]",
                "CRITICAL": "[CRIT]"
            }.get(level, "[UNKN]")
            
            # Определяем цвета для разных уровней (ANSI escape codes)
            color_codes = {
                "DEBUG": "\033[36m",     # Cyan
                "INFO": "\033[32m",      # Green
                "WARNING": "\033[33m",   # Yellow
                "ERROR": "\033[31m",     # Red
                "CRITICAL": "\033[91m"   # Bright Red
            }
            reset_color = "\033[0m"
            color = color_codes.get(level, "")
            
            # Получаем дополнительную информацию
            user_id = log_data.get("user_id", "N/A")
            ip_address = log_data.get("ip_address", "N/A")
            
            return (
                f"\n{color}{'='*80}{reset_color}\n"
                f"{color}{level_emoji} {level}{reset_color} | Источник: {source}\n"
                f"Время: {formatted_time}\n"
                f"ID: {log_data.get('log_id', 'N/A')}\n"
                f"Раздел: {section}/{subsection}\n"
                f"Пользователь: {user_id} | IP: {ip_address}\n"
                f"Сообщение: {message}\n"
                f"Доп. данные:\n{extra_str}\n"
                f"{color}{'='*80}{reset_color}\n"
            )
            
        except Exception as e:
            return f"Ошибка форматирования лога: {e}\nСырые данные: {log_data}"
    
    async def process_log(self, log_data: Dict[str, Any]):
        """Обработка полученного лога"""
        try:
            formatted_message = self.format_log_message(log_data)
            print(formatted_message)
            
            # Здесь можно добавить дополнительную обработку
            # Например, сохранение в базу данных, отправку уведомлений и т.д.
            
        except Exception as e:
            print(f"[CONSUMER] Ошибка обработки сообщения: {e}")
    
    async def message_handler(self, message: aio_pika.IncomingMessage):
        """Обработчик входящих сообщений"""
        async with message.process():
            try:
                # Декодируем сообщение
                body = message.body.decode('utf-8')
                log_data = json.loads(body)
                
                # Обрабатываем лог
                await self.process_log(log_data)
                
            except json.JSONDecodeError as e:
                print(f"[CONSUMER] Ошибка декодирования JSON: {e}")
                print(f"[CONSUMER] Сырое сообщение: {message.body}")
            except Exception as e:
                print(f"[CONSUMER] Ошибка обработки сообщения: {e}")
    
    async def start_consuming(self):
        """Запуск приема сообщений"""
        try:
            await self.initialize()
            
            # Начинаем прослушивание очереди
            self._running = True
            await self.queue.consume(self.message_handler)
            
            print(f"[CONSUMER] Ожидаем сообщения в очереди {QUEUE_NAME}")
            
            # Держим соединение активным
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"[CONSUMER] Ошибка запуска консьюмера: {e}")
            raise
    
    async def stop(self):
        """Остановка потребителя"""
        self._running = False
        if self.connection:
            await self.connection.close()
            print("[CONSUMER] Соединение с RabbitMQ закрыто")

async def main():
    processor = LogProcessor()
    try:
        await processor.start_consuming()
    except KeyboardInterrupt:
        print("\n[CONSUMER] Получен сигнал завершения")
    finally:
        await processor.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[CONSUMER] Программа завершена пользователем") 