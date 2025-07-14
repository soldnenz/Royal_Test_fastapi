import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# Конфигурация
BOT_TOKEN = "8184548760:AAFFbY5Xncx2y1GppUwkYSsLr2gZJfGtU6M"

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def handle_message(message: Message):
    """Обработчик всех сообщений"""
    chat_info = f"""
📋 <b>Информация о сообщении:</b>

💬 <b>Тип чата:</b> {message.chat.type}
🆔 <b>ID чата:</b> <code>{message.chat.id}</code>
📝 <b>ID сообщения:</b> <code>{message.message_id}</code>
👤 <b>ID пользователя:</b> <code>{message.from_user.id}</code>
📅 <b>Дата:</b> {message.date}

"""
    
    # Если есть топик
    if message.message_thread_id:
        chat_info += f"🏷️ <b>ID топика:</b> <code>{message.message_thread_id}</code>\n"
    
    # Если есть форвард
    if message.forward_from_chat:
        chat_info += f"🔄 <b>Переслано из чата:</b> <code>{message.forward_from_chat.id}</code>\n"
    
    # Если есть reply
    if message.reply_to_message:
        chat_info += f"↩️ <b>Ответ на сообщение:</b> <code>{message.reply_to_message.message_id}</code>\n"
    
    # Дополнительная информация о чате
    if message.chat.title:
        chat_info += f"📛 <b>Название чата:</b> {message.chat.title}\n"
    
    if message.chat.username:
        chat_info += f"🔗 <b>Username:</b> @{message.chat.username}\n"
    
    # Информация о пользователе
    if message.from_user.username:
        chat_info += f"👤 <b>Username:</b> @{message.from_user.username}\n"
    
    if message.from_user.first_name:
        chat_info += f"👤 <b>Имя:</b> {message.from_user.first_name}\n"
    
    if message.from_user.last_name:
        chat_info += f"👤 <b>Фамилия:</b> {message.from_user.last_name}\n"
    
    await message.reply(chat_info, parse_mode="HTML")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    welcome_text = """
🤖 <b>Бот для получения информации о чате и топиках</b>

Просто отправьте любое сообщение в чат или топик, и я покажу вам:
• ID чата
• ID топика (если есть)
• ID сообщения
• ID пользователя
• Другую полезную информацию

Добавьте меня в канал и напишите в любой топик!
"""
    await message.reply(welcome_text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📖 <b>Справка:</b>

• <b>/start</b> - Начать работу с ботом
• <b>/help</b> - Показать эту справку
• <b>Любое сообщение</b> - Получить информацию о чате/топике

<b>Как использовать:</b>
1. Добавьте бота в канал
2. Напишите сообщение в любой топик
3. Бот покажет ID чата и топика
"""
    await message.reply(help_text, parse_mode="HTML")

async def main():
    """Основная функция"""
    logger.info("Starting Chat Info Bot...")
    
    try:
        # Запуск бота
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 