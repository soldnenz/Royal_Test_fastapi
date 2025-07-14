import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_WARNING_TOPIC
from models import QuestionReport, ReportStatus
from database import DatabaseManager

logger = logging.getLogger(__name__)

class TelegramBotManager:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID
        self.topic_id = TELEGRAM_WARNING_TOPIC
        
    async def send_report_message(self, report: QuestionReport) -> bool:
        """Отправка сообщения с отчетом в Telegram"""
        try:
            # Форматирование сообщения
            message = self._format_report_message(report)
            
            # Отправка сообщения с указанием топика
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML',
                message_thread_id=self.topic_id
            )
            
            logger.info(f"Successfully sent report {report._id} to Telegram")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending report {report._id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending report {report._id}: {e}")
            return False
    
    def _format_report_message(self, report: QuestionReport) -> str:
        """Форматирование сообщения для Telegram"""
        # Определение эмодзи для типа отчета
        report_type_emoji = {
            "technical_error": "🔧",
            "content_error": "📝",
            "inappropriate_content": "⚠️",
            "other": "❓"
        }
        
        emoji = report_type_emoji.get(report.report_type, "📋")
        
        # Форматирование даты
        date_str = report.created_at.strftime("%d.%m.%Y %H:%M:%S UTC")
        
        message = f"""
{emoji} <b>Новый отчет о вопросе</b>

📊 <b>Тип отчета:</b> {report.report_type.replace('_', ' ').title()}
🆔 <b>ID отчета:</b> <code>{report._id}</code>
🎮 <b>ID лобби:</b> <code>{report.lobby_id}</code>
❓ <b>ID вопроса:</b> <code>{report.question_id}</code>
👤 <b>ID пользователя:</b> <code>{report.user_id}</code>

📝 <b>Описание:</b>
{report.description}

🌐 <b>IP адрес:</b> <code>{report.ip_address}</code>
📅 <b>Дата создания:</b> {date_str}

⏳ <b>Статус:</b> {report.status}
        """.strip()
        
        return message
    
    async def process_reports(self):
        """Обработка всех отчетов со статусом 'sending'"""
        try:
            with DatabaseManager() as db:
                reports = db.get_pending_reports()
                
                if not reports:
                    logger.debug("No pending reports found")
                    return
                
                logger.info(f"Found {len(reports)} pending reports")
                
                for report in reports:
                    # Отправка сообщения в Telegram
                    success = await self.send_report_message(report)
                    
                    if success:
                        # Обновление статуса на 'pending'
                        db.update_report_status(report._id, ReportStatus.PENDING)
                        logger.info(f"Report {report._id} processed successfully")
                    else:
                        logger.error(f"Failed to process report {report._id}")
                        
        except Exception as e:
            logger.error(f"Error processing reports: {e}")
    
    async def run_polling(self, interval: int = 60):
        """Запуск постоянного мониторинга отчетов"""
        logger.info("Starting Telegram bot polling...")
        
        while True:
            try:
                await self.process_reports()
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(interval)
    
    async def close(self):
        """Закрытие соединения с ботом"""
        await self.bot.session.close() 