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

import asyncio
import json
import os
import textwrap
from typing import Final, Optional

import aio_pika
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

BOT_TOKEN: Final[str] = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "7664299581:AAFkROG8TXF0wkL6-nrL7G_8Y5v0J_V5lYI",  # токен по умолчанию — как попросил пользователь
)

CHAT_ID: Final[int] = int(os.getenv("TELEGRAM_CHAT_ID", "-1002793640921"))
WARNING_TOPIC_ID: Final[int] = int(os.getenv("TELEGRAM_WARNING_TOPIC", "2"))
ERROR_TOPIC_ID: Final[int] = int(os.getenv("TELEGRAM_ERROR_TOPIC", "3"))

if CHAT_ID == 0:
    raise RuntimeError(
        "Неверный CHAT_ID. Проверьте TELEGRAM_CHAT_ID или задайте корректный ID."  # noqa: E501
    )

RABBITMQ_URL: Final[str] = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME: Final[str] = os.getenv("RABBITMQ_EXCHANGE", "logs")
ROUTING_KEY: Final[str] = os.getenv("RABBITMQ_ROUTING_KEY", "application.logs")
QUEUE_NAME: Final[str] = os.getenv("RABBITMQ_QUEUE", "telegram_log_bot_queue")

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

LEVEL_EMOJI: Final[dict[str, str]] = {
    "WARNING": "🟠",
    "ERROR": "🔴",
    "CRITICAL": "🔥",
}


def _format_log_message(data: dict[str, object]) -> str:
    """Преобразуем словарь лога в красивое HTML-сообщение."""

    timestamp = data.get("timestamp", "—")
    log_id = data.get("log_id", "—")
    level = str(data.get("level", "")).upper()
    section = data.get("section", "—")
    subsection = data.get("subsection", "—")
    message = data.get("message", "—")

    # Обрезаем сообщение, если оно слишком длинное
    if isinstance(message, str) and len(message) > 1000:
        message = message[:1000] + "…"

    extra = data.get("extra_data", {}) or {}

    extra_text = ""
    if extra:
        pretty_json = json.dumps(extra, ensure_ascii=False, indent=2)
        # ограничим размер extra, чтобы не превысить лимит 4096 символов
        if len(pretty_json) > 1500:
            pretty_json = pretty_json[:1500] + "…"
        extra_text = f"\n<pre>{pretty_json}</pre>"

    return textwrap.dedent(
        f"""
        {LEVEL_EMOJI.get(level, '')} <b>{level.title()}</b>
        <b>Time:</b> {timestamp}
        <b>ID:</b> {log_id}
        <b>Section:</b> {section}/{subsection}
        <b>Message:</b> {message}{extra_text}
        """
    ).strip()


async def _send_with_retry(bot: Bot, *, chat_id: int, thread_id: int, text: str) -> None:
    """Отправка с обработкой Flood-wait ошибки Telegram."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            message_thread_id=thread_id,
            disable_web_page_preview=True,
        )
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            message_thread_id=thread_id,
            disable_web_page_preview=True,
        )


# ---------------------------------------------------------------------------
# Уведомление о запуске
# ---------------------------------------------------------------------------

async def _notify_startup(bot: Bot) -> None:
    """Отправляет сообщение в WARNING_TOPIC_ID о запуске бота."""
    text = "🟢 <b>Log bot запущен и слушает RabbitMQ.</b>"
    try:
        await _send_with_retry(bot, chat_id=CHAT_ID, thread_id=WARNING_TOPIC_ID, text=text)
    except Exception as exc:
        # Пишем в консоль, но не прерываем работу
        print(f"Cannot send startup notification: {exc}")


# ---------------------------------------------------------------------------
# Основная логика: потребитель RabbitMQ + Telegram
# ---------------------------------------------------------------------------

async def _consume_and_forward(bot: Bot) -> None:
    """Слушаем очередь RabbitMQ и пересылаем логи в Telegram."""

    connection: aio_pika.RobustConnection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel: aio_pika.abc.AbstractChannel = await connection.channel()

    exchange: aio_pika.Exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue: aio_pika.Queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
    )
    await queue.bind(exchange, ROUTING_KEY)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                except json.JSONDecodeError:
                    # Плохое сообщение — пропускаем
                    continue

                # Убираем нежелательные поля
                data.pop("user_id", None)
                data.pop("ip_address", None)
                data.pop("user_agent", None)
                data.pop("source", None)

                level = str(data.get("level", "")).upper()
                thread_id = WARNING_TOPIC_ID if level == "WARNING" else ERROR_TOPIC_ID

                text = _format_log_message(data)
                await _send_with_retry(bot, chat_id=CHAT_ID, thread_id=thread_id, text=text)

    await connection.close()


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

async def main() -> None:
    bot_default_props = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(BOT_TOKEN, default=bot_default_props)
    try:
        # Уведомляем о запуске
        await _notify_startup(bot)
        await _consume_and_forward(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 