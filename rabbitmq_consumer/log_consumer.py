import os
import json
import asyncio
import signal
import sys
from typing import Optional

import aio_pika

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ---------------------------------------------------------------------------
# Конфигурация из переменных окружения с разумными значениями по умолчанию
# ---------------------------------------------------------------------------
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL")
EXCHANGE_NAME: str = os.getenv("RABBITMQ_EXCHANGE")

# Поддерживаемые routing keys для разных сервисов
ROUTING_KEYS = [
    "logs.info.application", # Основное приложение
    "logs.info.2fa",         # Микросервис 2FA
    "logs.info.redis",       # Redis и rate limiter
    "logs.error.application", # Ошибки приложения
    "logs.error.2fa",        # Ошибки 2FA
    "logs.error.redis"       # Ошибки Redis
]

QUEUE_NAME: str = os.getenv("RABBITMQ_QUEUE")


async def _consume() -> None:
    """Подключается к RabbitMQ, настраивает очередь и начинает слушать сообщения."""

    # Устанавливаем соединение и открываем канал
    connection: aio_pika.RobustConnection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel: aio_pika.abc.AbstractChannel = await connection.channel()

    # Объявляем exchange (тип topic) — такие же параметры, как и у издателя
    exchange: aio_pika.Exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    # Объявляем durable-очередь
    queue: aio_pika.Queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
    )

    # Биндим очередь к exchange для всех routing keys
    for routing_key in ROUTING_KEYS:
        await queue.bind(exchange, routing_key)
        print(f"[CONSUMER] Очередь привязана к exchange с routing_key: {routing_key}")

    print(
        f" [*] Waiting for messages on exchange '{EXCHANGE_NAME}' with routing keys "
        f"{', '.join(ROUTING_KEYS)}. To exit press CTRL+C"
    )

    # Итератор очереди обеспечивает удобное получение и ack сообщений
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                _handle_message(message.body)

    # Если вышли из цикла — закрываем соединение
    await connection.close()


def _handle_message(body: bytes) -> None:
    """Разбирает тело сообщения как JSON и выводит в консоль."""
    try:
        data = json.loads(body.decode())
        
        # Добавляем информацию о источнике
        source = data.get("source", "unknown")
        level = data.get("level", "UNKNOWN")
        
        # Определяем эмодзи для уровня (используем ASCII символы для Windows)
        level_emoji = {
            "DEBUG": "[DEBUG]",
            "INFO": "[INFO]",
            "WARNING": "[WARN]",
            "ERROR": "[ERROR]",
            "CRITICAL": "[CRIT]"
        }.get(level, "[UNKN]")
        
        print(f"\n{level_emoji} [{source}] {level}")
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        print(f"Received log message:\n{pretty}\n")
        
    except json.JSONDecodeError:
        # Если сообщение не JSON, выводим как строку
        print(f"\nReceived non-JSON message: {body!r}\n")


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def _setup_signal_handlers(loop: asyncio.AbstractEventLoop, task: asyncio.Task) -> None:
    """Регистрация graceful-shutdown через сигналы ОС.

    На Windows метод `loop.add_signal_handler` не реализован, поэтому
    оборачиваем вызов в try/except и тихо пропускаем при `NotImplementedError`.
    """

    def _signal_handler(_: int, __: Optional[object]) -> None:  # noqa: D401, E501
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler, sig, None)
        except (NotImplementedError, ValueError):
            # Windows / некоторые event-loop'ы не поддерживают сигнал-хендлеры.
            # В этом случае полагаемся на KeyboardInterrupt (SIGINT) для корректного
            # завершения, а SIGTERM обычно не посылается в интерактивной среде.
            pass


async def _main() -> None:
    consumer = asyncio.create_task(_consume())
    loop = asyncio.get_running_loop()
    _setup_signal_handlers(loop, consumer)

    try:
        await consumer
    except asyncio.CancelledError:
        print("\nReceived shutdown signal, closing consumer…")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down…")
        consumer.cancel()
        await consumer


if __name__ == "__main__":
    asyncio.run(_main()) 