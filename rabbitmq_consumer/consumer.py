import asyncio
import json
import os
from datetime import datetime
import pytz
from faststream import FastStream
from faststream.rabbit import RabbitBroker
import aio_pika
from typing import Dict, Any

# Настройки RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = os.getenv("RABBITMQ_EXCHANGE", "logs")
ROUTING_KEY = os.getenv("RABBITMQ_ROUTING_KEY", "application.logs")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "log_processing_queue")

# Timezone для форматирования времени
KZ_TIMEZONE = pytz.timezone('Asia/Almaty')

class LogProcessor:
    def __init__(self):
        self.broker: RabbitBroker = None
        self.app: FastStream = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация подключения к RabbitMQ"""
        if not self._initialized:
            try:
                print(f"[CONSUMER] Подключение к RabbitMQ: {RABBITMQ_URL}")
                
                # Создаем брокер
                self.broker = RabbitBroker(RABBITMQ_URL)
                
                # Создаем FastStream приложение
                self.app = FastStream(broker=self.broker)
                
                # Подключаемся к RabbitMQ
                await self.broker.connect()
                print("[CONSUMER] Подключение установлено")
                
                # Объявляем exchange и очередь
                channel = await self.broker.channel()
                
                # Объявляем exchange
                exchange = await channel.declare_exchange(
                    EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                print(f"[CONSUMER] Exchange '{EXCHANGE_NAME}' объявлен")
                
                # Объявляем очередь с нужными параметрами
                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    auto_delete=False
                )
                
                # Привязываем очередь к exchange
                await queue.bind(
                    exchange=exchange,
                    routing_key=ROUTING_KEY
                )
                print(f"[CONSUMER] Очередь привязана к exchange с routing_key: {ROUTING_KEY}")
                
                self._initialized = True
                
            except Exception as e:
                print(f"[CONSUMER] Ошибка инициализации: {e}")
                raise
    
    def format_log_message(self, log_data: Dict[str, Any]) -> str:
        """Форматирует лог для вывода"""
        try:
            # Парсим timestamp если он есть
            timestamp = log_data.get("timestamp", "")
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                dt_kz = dt.astimezone(KZ_TIMEZONE)
                formatted_time = dt_kz.strftime("%Y-%m-%d %H:%M:%S %z")
            else:
                formatted_time = datetime.now(KZ_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %z")
            
            # Форматируем основную информацию
            level = log_data.get("level", "UNKNOWN")
            section = log_data.get("section", "unknown")
            subsection = log_data.get("subsection", "unknown")
            message = log_data.get("message", "")
            
            # Форматируем дополнительные данные
            extra_data = log_data.get("extra_data", {})
            extra_str = json.dumps(extra_data, ensure_ascii=False, indent=2)
            
            return (
                f"\n{'='*80}\n"
                f"Время: {formatted_time}\n"
                f"ID: {log_data.get('log_id', 'N/A')}\n"
                f"Уровень: {level}\n"
                f"Раздел: {section}/{subsection}\n"
                f"Сообщение: {message}\n"
                f"Доп. данные:\n{extra_str}\n"
                f"{'='*80}\n"
            )
            
        except Exception as e:
            return f"Ошибка форматирования лога: {e}\nСырые данные: {log_data}"
    
    async def process_log(self, message: Dict[str, Any]):
        """Обработка полученного лога"""
        try:
            formatted_message = self.format_log_message(message)
            print(formatted_message)
            
            # Здесь можно добавить дополнительную обработку
            # Например, сохранение в базу данных, отправку уведомлений и т.д.
            
        except Exception as e:
            print(f"[CONSUMER] Ошибка обработки сообщения: {e}")
    
    async def start_consuming(self):
        """Запуск приема сообщений"""
        try:
            await self.initialize()
            
            @self.broker.subscriber(QUEUE_NAME)
            async def handle_log(message: Dict[str, Any]):
                await self.process_log(message)
            
            print(f"[CONSUMER] Начинаем прослушивание очереди {QUEUE_NAME}")
            await self.broker.start()
            
        except Exception as e:
            print(f"[CONSUMER] Ошибка запуска консьюмера: {e}")
            raise

async def main():
    processor = LogProcessor()
    try:
        await processor.start_consuming()
        # Держим приложение запущенным
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[CONSUMER] Получен сигнал завершения")
    finally:
        if processor.broker:
            await processor.broker.close()
            print("[CONSUMER] Соединение с RabbitMQ закрыто")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[CONSUMER] Программа завершена пользователем") 