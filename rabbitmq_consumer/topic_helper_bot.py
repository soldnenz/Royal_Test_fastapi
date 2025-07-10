"""topic_helper_bot.py

Бот-помощник для Telegram-форумов:
1. Команда /start выводит инструкцию.
2. Если отправить команду /id в ответ на сообщение внутри топика — бот сообщит
   chat_id, message_id и message_thread_id.
3. Бот отслеживает все сообщения и сервисные события forum_topic_created /
   forum_topic_edited, собирает в памяти карту <thread_id -> название>.
   Команда /topics выводит список известных топиков с их thread_id.

Ограничения: Bot API не предоставляет способа получить полный список топиков
RETROактивно, поэтому бот видит только те топики, в которых уже появились
сообщения после его добавления или что были созданы/переименованы при его
присутствии.
"""

from __future__ import annotations

import asyncio
import os
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ForumTopicCreated, ForumTopicEdited
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN: str = os.getenv(
    "TELEGRAM_BOT_TOKEN"  # токен по умолчанию
)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Храним обнаруженные топики (в рамках жизни процесса)
# {chat_id: {thread_id: topic_name}}
known_topics: Dict[int, Dict[int, str]] = {}

dp = Dispatcher()


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _remember_topic(chat_id: int, thread_id: int, name: str) -> None:
    topics = known_topics.setdefault(chat_id, {})
    topics[thread_id] = name


def _format_topics(chat_id: int) -> str:
    topics = known_topics.get(chat_id)
    if not topics:
        return "<i>Пока не обнаружено ни одного топика. Отправьте сообщение в нужном топике или создайте его.</i>"

    lines = ["<b>Известные топики:</b>"]
    for tid, name in topics.items():
        lines.append(f"• <code>{tid}</code> — {name}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Хэндлеры
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:  # noqa: D401
    text = (
        "Привет! Я помогу узнать <b>chat_id</b> и <b>message_thread_id</b> (ID топика).\n\n"
        "• Ответьте командой <code>/id</code> на любое сообщение внутри нужного топика,\n"
        "  и я пришлю информацию.\n"
        "• Команда <code>/topics</code> покажет список всех топиков, о которых я знаю."
    )
    await message.answer(text)


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    if not message.reply_to_message:
        await message.answer("❗️ Используйте команду <code>/id</code> в ответ на сообщение в топике.")
        return

    reply = message.reply_to_message
    chat_id = reply.chat.id
    message_id = reply.message_id
    thread_id = reply.message_thread_id or "General"

    # Пытаемся получить название топика (если возможно)
    topic_name = "General"
    if isinstance(thread_id, int):
        try:
            topic = await bot.get_forum_topic(chat_id, thread_id)
            topic_name = topic.name
            _remember_topic(chat_id, thread_id, topic_name)
        except Exception:
            pass

    text = (
        f"<b>Информация:</b>\n"
        f"chat_id: <code>{chat_id}</code>\n"
        f"message_id: <code>{message_id}</code>\n"
        f"message_thread_id: <code>{thread_id}</code> ({topic_name})"
    )
    await message.answer(text)


@dp.message(Command("topics"))
async def cmd_topics(message: Message) -> None:
    chat_id = message.chat.id
    await message.answer(_format_topics(chat_id))


# Сервисные сообщения о создании или редактировании топиков
@dp.message(F.forum_topic_created)
async def on_topic_created(message: Message) -> None:
    data: ForumTopicCreated = message.forum_topic_created
    _remember_topic(message.chat.id, message.message_thread_id, data.name)


@dp.message(F.forum_topic_edited)
async def on_topic_edited(message: Message) -> None:
    data: ForumTopicEdited = message.forum_topic_edited
    _remember_topic(message.chat.id, message.message_thread_id, data.name)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 