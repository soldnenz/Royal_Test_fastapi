import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from app.db.database import db
from bson import ObjectId
import requests

# Configure logger
logger = logging.getLogger(__name__)

router = Router()

bot = Bot(
    token=os.getenv("TELEGRAM_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# TTL запросов (в секундах)
TWO_FA_TTL = 300

def get_location_by_ip(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        if data['status'] == 'success':
            return f"{data['country']}, {data['city']}"
        else:
            return "Неизвестное местоположение"
    except Exception as e:
        logger.error(f"Error getting location for IP {ip}: {str(e)}")
        return "Ошибка получения местоположения"

async def send_2fa_request(admin: dict, new_ip: str, new_ua: str):
    try:
        logger.info(f"Sending 2FA request for admin {admin['_id']} ({admin.get('full_name')}) from IP {new_ip}")
        now = datetime.utcnow()
        expire_at = now + timedelta(seconds=TWO_FA_TTL)
        request_id = await db.twofa_requests.insert_one({
            "admin_id": admin["_id"],
            "ip": new_ip,
            "user_agent": new_ua,
            "created_at": now,
            "expires_at": expire_at,
            "status": "pending"
        })
        logger.info(f"Created 2FA request with ID: {request_id.inserted_id}")

        location = get_location_by_ip(new_ip)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Разрешить",
                    callback_data=f"2fa_allow_{admin['_id']}"
                ),
                InlineKeyboardButton(
                    text="❌ Запретить",
                    callback_data=f"2fa_deny_{admin['_id']}"
                )
            ]
        ])
        text = (
            f"🔐 Попытка входа в админ-панель\n"
            f"👤 {admin['full_name']}\n"
            f"📍 IP: {new_ip} ({location})\n"
            f"🖥 Устройство: {new_ua}\n"
            f"Разрешить вход? У вас есть 5 минут, чтобы ответить на запрос, в противном случае доступ будет запрещён."
        )
        message = await bot.send_message(chat_id=admin['telegram_id'], text=text, reply_markup=kb)
        logger.info(f"2FA request sent to Telegram ID {admin['telegram_id']}, message ID: {message.message_id}")
    except Exception as e:
        logger.error(f"Error sending 2FA request: {str(e)}")
        raise

@router.callback_query(F.data.startswith("2fa_"))
async def process_2fa_callback(callback: CallbackQuery):
    try:
        logger.info(f"Received 2FA callback: {callback.data} from user {callback.from_user.id}")
        action, admin_id = callback.data.split("_", 2)[1:]
        admin_obj_id = ObjectId(admin_id)
        logger.info(f"Processing 2FA {action} action for admin ID: {admin_id}")

        # Получим актуальный 2FA-запрос
        request = await db.twofa_requests.find_one({
            "admin_id": admin_obj_id,
            "status": "pending",
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not request:
            logger.warning(f"No valid pending 2FA request found for admin {admin_id}")
            await callback.answer("⌛ Время истекло или запрос уже обработан", show_alert=True)
            return

        if action == "allow":
            logger.info(f"Allowing 2FA request {request['_id']} for admin {admin_id}")
            # Обновляем is_verified и active_session
            result = await db.admins.update_one(
                {"_id": admin_obj_id},
                {
                    "$set": {
                        "is_verified": True,
                        "active_session": {
                            "ip": request["ip"],
                            "user_agent": request["user_agent"],
                            "token": None  # будет установлен при следующем login
                        }
                    }
                }
            )
            logger.info(f"Admin document updated: matched={result.matched_count}, modified={result.modified_count}")
            
            update_result = await db.twofa_requests.update_one({"_id": request["_id"]}, {"$set": {"status": "allowed"}})
            logger.info(f"2FA request status updated to 'allowed': {update_result.modified_count}")
            
            await callback.answer("✅ Вход разрешён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Вход разрешён",
                reply_markup=None
            )
            logger.info(f"2FA request {request['_id']} successfully allowed")

        else:
            logger.info(f"Denying 2FA request {request['_id']} for admin {admin_id}")
            update_result = await db.twofa_requests.update_one({"_id": request["_id"]}, {"$set": {"status": "denied"}})
            logger.info(f"2FA request status updated to 'denied': {update_result.modified_count}")
            
            await callback.answer("❌ Вход запрещён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Вход запрещён",
                reply_markup=None
            )
            logger.info(f"2FA request {request['_id']} successfully denied")
    
    except Exception as e:
        logger.error(f"Error processing 2FA callback: {str(e)}", exc_info=True)
        await callback.answer("Произошла ошибка. Подробности в логах.", show_alert=True)