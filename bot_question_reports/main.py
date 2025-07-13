import asyncio
import logging
import os
from datetime import datetime
from typing import List
from dotenv import load_dotenv
from pymongo import MongoClient
from pydantic import BaseModel, Field
from aiogram import Bot

# Загрузка переменных окружения
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
COLLECTION_NAME = "question_reports"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
TELEGRAM_WARNING_TOPIC = int(os.getenv("TELEGRAM_WARNING_TOPIC"))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", 60))

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot.log', encoding='utf-8')]
)
logger = logging.getLogger(__name__)

# Выводим конфигурацию при запуске
logger.info(f"=== КОНФИГУРАЦИЯ БОТА ===")
logger.info(f"MONGO_URI: {MONGO_URI}")
logger.info(f"MONGO_DB_NAME: {MONGO_DB_NAME}")
logger.info(f"TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN[:10]}...")
logger.info(f"TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")
logger.info(f"TELEGRAM_WARNING_TOPIC: {TELEGRAM_WARNING_TOPIC}")
logger.info(f"POLLING_INTERVAL: {POLLING_INTERVAL}")
logger.info(f"==========================")

# Модель отчета
class QuestionReport(BaseModel):
    id: str = Field(alias="_id")
    lobby_id: str
    question_id: str
    user_id: str
    report_type: str
    description: str
    status: str
    created_at: datetime
    ip_address: str
    
    class Config:
        populate_by_name = True

REPORT_TYPE_EMOJI = {
    "technical_error": "🔧",
    "content_error": "📝",
    "inappropriate_content": "⚠️",
    "other": "❓"
}

# Получение отчетов со статусом 'sending'
def get_sending_reports(collection) -> List[QuestionReport]:
    docs = collection.find({"status": "sending"})
    reports = []
    for doc in docs:
        # _id может быть ObjectId, приводим к str
        doc["_id"] = str(doc["_id"])
        try:
            reports.append(QuestionReport(**doc))
        except Exception as e:
            logger.error(f"Ошибка парсинга отчета: {e}")
    return reports

# Обновление статуса отчета
def update_report_status(collection, report_id: str, new_status: str):
    result = collection.update_one({"_id": report_id}, {"$set": {"status": new_status}})
    return result.modified_count > 0

# Форматирование сообщения
def format_report_message(report: QuestionReport) -> str:
    emoji = REPORT_TYPE_EMOJI.get(report.report_type, "📋")
    date_str = report.created_at.strftime("%d.%m.%Y %H:%M:%S UTC")
    return (
        f"{emoji} <b>Новый отчет о вопросе</b>\n\n"
        f"📊 <b>Тип отчета:</b> {report.report_type.replace('_', ' ').title()}\n"
        f"🆔 <b>ID отчета:</b> <code>{report.id}</code>\n"
        f"🎮 <b>ID лобби:</b> <code>{report.lobby_id}</code>\n"
        f"❓ <b>ID вопроса:</b> <code>{report.question_id}</code>\n"
        f"👤 <b>ID пользователя:</b> <code>{report.user_id}</code>\n\n"
        f"📝 <b>Описание:</b>\n{report.description}\n\n"
        f"🌐 <b>IP адрес:</b> <code>{report.ip_address}</code>\n"
        f"📅 <b>Дата создания:</b> {date_str}\n\n"
        f"⏳ <b>Статус:</b> {report.status}"
    )

async def process_reports(bot: Bot, collection):
    reports = get_sending_reports(collection)
    if not reports:
        logger.info("Нет новых отчетов со статусом 'sending'")
        return
    logger.info(f"Найдено {len(reports)} новых отчетов")
    for report in reports:
        try:
            msg = format_report_message(report)
            logger.info(f"Пытаюсь отправить отчет {report.id} в чат {TELEGRAM_CHAT_ID}")
            logger.info(f"Топик: {TELEGRAM_WARNING_TOPIC}")
            
            # Отправляем сообщение с указанием топика
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="HTML",
                message_thread_id=TELEGRAM_WARNING_TOPIC
            )
            update_report_status(collection, report.id, "pending")
            logger.info(f"Отчет {report.id} успешно отправлен и обновлен")
        except Exception as e:
            logger.error(f"Ошибка отправки отчета {report.id}: {e}")
            logger.error(f"Детали ошибки: {type(e).__name__}")
            logger.error(f"Попытка отправки в чат: {TELEGRAM_CHAT_ID}")
            logger.error(f"Попытка отправки в топик: {TELEGRAM_WARNING_TOPIC}")

async def main():
    logger.info("Starting Question Reports Telegram Bot...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    collection = db[COLLECTION_NAME]
    try:
        while True:
            await process_reports(bot, collection)
            await asyncio.sleep(POLLING_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()
        client.close()

if __name__ == "__main__":
    asyncio.run(main()) 