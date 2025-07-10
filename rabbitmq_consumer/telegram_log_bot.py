"""telegram_log_bot.py

Асинхронный бот для пересылки структурированных логов из RabbitMQ в Telegram-группу
с форумом (топиками). Логи уровня WARNING отправляются в топик WARNING, а ERROR
и CRITICAL — в топик ERROR.

Перед запуском задайте переменные окружения (значения можно взять из «Copy Link»
топика в Telegram: номер после слеша — это `message_thread_id`):

  TELEGRAM_BOT_TOKEN       — токен бота (если не задан, берём встроенный токен)
  TELEGRAM_CHAT_ID         — ID группы/форума
  TELEGRAM_WARNING_TOPIC   — `message_thread_id` топика для предупреждений
  TELEGRAM_ERROR_TOPIC     — `message_thread_id` топика для ошибок

RabbitMQ параметры берутся так же, как в log_consumer.py:
  RABBITMQ_URL, RABBITMQ_EXCHANGE, RABBITMQ_ROUTING_KEY, RABBITMQ_QUEUE
"""

from __future__ import annotations

import os
import json
import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

import aio_pika
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

try:
    from dotenv import load_dotenv
    # Пытаемся загрузить .env файл из текущей директории или родительской
    env_paths = ['.env', '../.env']
    for env_path in env_paths:
        if Path(env_path).exists():
            load_dotenv(env_path)
            break
except ImportError:
    print("⚠️ python-dotenv не установлен. Переменные окружения должны быть установлены вручную.")

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Конфигурация
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_WARNING_TOPIC = os.getenv("TELEGRAM_WARNING_TOPIC")
TELEGRAM_ERROR_TOPIC = os.getenv("TELEGRAM_ERROR_TOPIC")
EXCHANGE_NAME = os.getenv("RABBITMQ_EXCHANGE", "logs_exchange")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "telegram_logs")

# Максимальное количество попыток переподключения
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # секунд
RETRY_BASE_DELAY = 1  # базовая задержка для повторных попыток

class TelegramLogBot:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
        if not TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID не установлен")
            
        self.bot = None  # Инициализируем бота в методе start
        self.chat_id = TELEGRAM_CHAT_ID
        self.warning_topic = TELEGRAM_WARNING_TOPIC
        self.error_topic = TELEGRAM_ERROR_TOPIC
        self.connection = None
        self.channel = None
        self.exchange = None
        self.queue = None
        self.should_stop = False
        
    async def start(self):
        """Инициализация бота при старте"""
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
    async def connect_to_rabbitmq(self) -> bool:
        """Устанавливает подключение к RabbitMQ с повторными попытками"""
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            try:
                if self.connection and not self.connection.is_closed:
                    await self.connection.close()
                    
                self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
                self.channel = await self.connection.channel()
                
                # Объявляем exchange
                self.exchange = await self.channel.declare_exchange(
                    EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                
                # Объявляем очередь
                self.queue = await self.channel.declare_queue(
                    QUEUE_NAME,
                    durable=True
                )
                
                return True
                
            except Exception as e:
                print(f"❌ Попытка подключения {attempt + 1}/{MAX_RECONNECT_ATTEMPTS} не удалась: {e}")
                if attempt < MAX_RECONNECT_ATTEMPTS - 1:
                    print(f"⏳ Ожидание {RECONNECT_DELAY} секунд перед следующей попыткой...")
                    await asyncio.sleep(RECONNECT_DELAY)
                    
        return False
        
    async def setup_queue(self) -> bool:
        """Настраивает очередь и привязки"""
        try:
            # Привязываем очередь к exchange для разных типов логов
            routing_keys = [
                # Общие паттерны для всех уровней
                "logs.warning.*",     # Все предупреждения
                "logs.error.*",       # Все ошибки
                "logs.critical.*",    # Все критические ошибки
                
                # Специфичные сервисы
                "logs.*.api",         # API логи
                "logs.*.security",    # Логи безопасности
                "logs.*.2fa",         # Логи 2FA
                "logs.*.auth",        # Логи авторизации
                "logs.*.application", # Логи приложения
                "logs.*.system",      # Системные логи
                
                # Специфичные комбинации
                "logs.warning.api",
                "logs.error.api",
                "logs.warning.security",
                "logs.error.security"
            ]
            
            for key in routing_keys:
                await self.queue.bind(self.exchange, key)
                print(f"[TELEGRAM BOT] Очередь привязана к exchange с routing_key: {key}")
                
            return True
            
        except Exception as e:
            print(f"❌ Ошибка настройки очереди: {e}")
            return False
            
    async def send_telegram_message(self, text: str, level: str = "INFO", retry_count: int = 0) -> bool:
        """Отправляет сообщение в Telegram с обработкой ошибок и экспоненциальной задержкой"""
        try:
            # Определяем topic_id на основе уровня лога
            topic_id = None
            if level in ["WARNING"]:
                topic_id = int(self.warning_topic) if self.warning_topic else None
            elif level in ["ERROR", "CRITICAL"]:
                topic_id = int(self.error_topic) if self.error_topic else None
            
            print(f"[TELEGRAM BOT] Отправка сообщения уровня {level}" + 
                  (f" в топик {topic_id}" if topic_id else ""))
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                message_thread_id=topic_id
            )
            print(f"[TELEGRAM BOT] ✅ Сообщение успешно отправлено")
            return True
        except TelegramRetryAfter as e:
            # Получаем значение retry_after из разных возможных атрибутов
            retry_after = getattr(e, 'retry_after', None) or getattr(e, 'value', None) or RETRY_BASE_DELAY
            retry_delay = retry_after * (2 ** retry_count)  # Экспоненциальная задержка
            print(f"⚠️ Превышен лимит сообщений, ожидание {retry_delay} секунд")
            await asyncio.sleep(retry_delay)
            # Повторная попытка с увеличенным счетчиком
            return await self.send_telegram_message(text, level, retry_count + 1)
        except TelegramAPIError as e:
            print(f"❌ Ошибка Telegram API: {e}")
            if retry_count < 3:  # Максимум 3 попытки для других ошибок API
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** retry_count))
                return await self.send_telegram_message(text, level, retry_count + 1)
            return False
        except Exception as e:
            print(f"❌ Неожиданная ошибка при отправке в Telegram: {e}")
            return False
            
    async def process_message(self, message: aio_pika.IncomingMessage) -> None:
        """Обрабатывает входящее сообщение"""
        try:
            async with message.process():
                print(f"[TELEGRAM BOT] 📨 Получено новое сообщение:")
                print(f"[TELEGRAM BOT] 🔑 Routing key: {message.routing_key}")
                print(f"[TELEGRAM BOT] 📦 Exchange: {message.exchange}")
                
                body = message.body.decode()
                print(f"[TELEGRAM BOT] 📄 Тело сообщения: {body}")
                
                data = json.loads(body)
                
                # Форматируем сообщение для Telegram
                level = data.get("level", "UNKNOWN")
                section = data.get("section", "unknown")
                subsection = data.get("subsection", "unknown")
                msg = data.get("message", "Нет сообщения")
                source = data.get("source", "unknown")
                
                print(f"[TELEGRAM BOT] 📝 Обработка сообщения:")
                print(f"[TELEGRAM BOT] - Уровень: {level}")
                print(f"[TELEGRAM BOT] - Раздел: {section}/{subsection}")
                print(f"[TELEGRAM BOT] - Источник: {source}")
                
                # Получаем дополнительную информацию
                extra_data = data.get("extra_data", {})
                source_file = extra_data.get("source_file", "unknown")
                source_function = extra_data.get("source_function", "unknown")
                source_line = extra_data.get("source_line", "?")
                user_id = data.get("user_id", "N/A")
                ip_address = data.get("ip_address", "N/A")
                
                # Определяем эмодзи для уровня
                level_emoji = {
                    "DEBUG": "🔍",
                    "INFO": "ℹ️",
                    "WARNING": "⚠️",
                    "ERROR": "❌",
                    "CRITICAL": "🔥"
                }.get(level, "❓")
                
                # Определяем эмодзи для источника
                source_emoji = {
                    "2fa": "🔐",
                    "application": "📱",
                    "auth": "🔑",
                    "security": "🛡️",
                    "system": "⚙️",
                    "websocket": "🔌",
                    "files": "📁",
                    "lobby": "🎮",
                    "test": "📝",
                    "payment": "💰",
                    "database": "💾",
                    "redis": "📦",
                    "api": "🌐"
                }.get(section.lower(), "📋")
                
                # Формируем текст сообщения
                text = (
                    f"{level_emoji} <b>{level}</b> от {source}\n"
                    f"{source_emoji} <b>Раздел:</b> {section}/{subsection}\n"
                    f"📝 <b>Сообщение:</b> {msg}\n"
                )
                
                # Добавляем информацию об источнике для WARNING, ERROR и CRITICAL
                if level in ["WARNING", "ERROR", "CRITICAL"]:
                    text += (
                        f"\n📍 <b>Источник:</b>\n"
                        f"Файл: {source_file}\n"
                        f"Функция: {source_function}\n"
                        f"Строка: {source_line}\n"
                    )
                
                # Добавляем информацию о пользователе если есть
                if user_id != "N/A" or ip_address != "N/A":
                    text += (
                        f"\n👤 <b>Инициатор:</b>\n"
                        f"ID: {user_id}\n"
                        f"IP: {ip_address}\n"
                    )
                
                # Добавляем дополнительные данные если есть
                if extra_data and extra_data != {"source_file": source_file, "source_function": source_function, "source_line": source_line}:
                    other_data = {k: v for k, v in extra_data.items() 
                                if k not in ["source_file", "source_function", "source_line"]}
                    if other_data:
                        text += f"\n🔍 <b>Дополнительно:</b>\n"
                        for key, value in other_data.items():
                            text += f"{key}: {value}\n"
                
                # Добавляем timestamp если есть
                if "timestamp" in data:
                    text += f"\n🕒 <b>Время:</b> {data['timestamp']}"
                
                # Добавляем ID лога если есть
                if "log_id" in data:
                    text += f"\n🔑 <b>ID лога:</b> {data['log_id']}"
                
                print(f"[TELEGRAM BOT] 📤 Подготовлено сообщение для отправки в Telegram")
                
                # Отправляем сообщение
                await self.send_telegram_message(text, level)
                
        except json.JSONDecodeError as e:
            print(f"[TELEGRAM BOT] ❌ Ошибка декодирования JSON: {e}")
            print(f"[TELEGRAM BOT] Сырое сообщение: {message.body}")
        except Exception as e:
            print(f"[TELEGRAM BOT] ❌ Ошибка обработки сообщения: {e}")
            
    async def run(self) -> None:
        """Основной цикл работы бота"""
        try:
            await self.start()
            
            if not await self.connect_to_rabbitmq():
                print("❌ Не удалось подключиться к RabbitMQ после всех попыток")
                return
                
            if not await self.setup_queue():
                print("❌ Не удалось настроить очередь")
                return
                
            print("✅ Бот запущен и готов к работе")
            
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if self.should_stop:
                        break
                    await self.process_message(message)
                        
        except Exception as e:
            print(f"❌ Ошибка в основном цикле: {e}")
        finally:
            await self.cleanup()
            
    async def cleanup(self) -> None:
        """Очистка ресурсов при завершении работы"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        if self.bot:
            await self.bot.session.close()

async def main() -> None:
    """Основная функция"""
    bot = TelegramLogBot()
    
    def signal_handler(signum, frame):
        print("\n⏳ Получен сигнал завершения, graceful shutdown...")
        bot.should_stop = True
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main()) 