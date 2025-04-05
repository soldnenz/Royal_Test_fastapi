import os
from datetime import datetime, timedelta
from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from app.db.database import db
from bson import ObjectId

router = Router()

bot = Bot(
    token=os.getenv("TELEGRAM_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# TTL запросов (в секундах)
TWO_FA_TTL = 300

async def send_2fa_request(admin: dict, new_ip: str, new_ua: str):
    now = datetime.utcnow()
    expire_at = now + timedelta(seconds=TWO_FA_TTL)
    await db.twofa_requests.insert_one({
        "admin_id": admin["_id"],
        "ip": new_ip,
        "user_agent": new_ua,
        "created_at": now,
        "expires_at": expire_at,
        "status": "pending"
    })

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
        f"📍 IP: {new_ip}\n"
        f"🖥 Устройство: {new_ua}\n"
        f"Разрешить вход? (5 минут)"
    )
    await bot.send_message(chat_id=admin['telegram_id'], text=text, reply_markup=kb)

@router.callback_query(F.data.startswith("2fa_"))
async def process_2fa_callback(callback: CallbackQuery):
    action, admin_id = callback.data.split("_", 2)[1:]
    admin_obj_id = ObjectId(admin_id)

    # Получим актуальный 2FA-запрос
    request = await db.twofa_requests.find_one({
        "admin_id": admin_obj_id,
        "status": "pending",
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not request:
        await callback.answer("⌛ Время истекло или запрос уже обработан", show_alert=True)
        return

    if action == "allow":
        # Обновляем is_verified и active_session
        await db.admins.update_one(
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
        await db.twofa_requests.update_one({"_id": request["_id"]}, {"$set": {"status": "allowed"}})
        await callback.answer("✅ Вход разрешён", show_alert=True)

    else:
        await db.twofa_requests.update_one({"_id": request["_id"]}, {"$set": {"status": "denied"}})
        await callback.answer("❌ Вход запрещён", show_alert=True)