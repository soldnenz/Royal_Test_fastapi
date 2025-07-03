import os
from datetime import datetime, timedelta
from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from app.db.database import db
from bson import ObjectId
import requests

# Новая структурированная система логирования
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection

logger = get_structured_logger("admin.telegram_2fa")

router = Router()

bot = Bot(
    token=os.getenv("TELEGRAM_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# TTL запросов (в секундах)
TWO_FA_TTL = 300

def get_location_by_ip(ip):
    try:
        logger.debug(
            section=LogSection.ADMIN,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Ищем откуда подключается пользователь - отправляем запрос геолокации для IP {ip}"
        )
        
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        
        if data['status'] == 'success':
            location = f"{data['country']}, {data['city']}"
            logger.info(
                section=LogSection.ADMIN,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Геолокация найдена: IP {ip} находится в стране {data['country']}, город {data['city']}, провайдер {data.get('isp', 'неизвестен')}"
            )
            return location
        else:
            logger.warning(
                section=LogSection.ADMIN,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Не удалось определить местоположение IP {ip} - сервис геолокации вернул ошибку {data.get('status')}"
            )
            return "Неизвестное местоположение"
    except Exception as e:
        logger.error(
            section=LogSection.ADMIN,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Произошла ошибка при поиске геолокации для IP {ip}: {str(e)}"
        )
        return "Ошибка получения местоположения"

async def send_2fa_request(admin: dict, new_ip: str, new_ua: str):
    try:
        admin_name = admin.get('full_name', 'Неизвестный админ')
        admin_email = admin.get('email', 'email не указан')
        telegram_id = admin.get('telegram_id')
        
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"Администратор {admin_name} ({admin_email}) пытается войти в систему с IP {new_ip} - запускаем двухфакторную проверку через Telegram"
        )
        
        now = datetime.utcnow()
        expire_at = now + timedelta(seconds=TWO_FA_TTL)
        
        logger.debug(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"Создаем временную запись 2FA для {admin_name} - срок действия {TWO_FA_TTL//60} минут (до {expire_at.strftime('%H:%M:%S')})"
        )
        
        request_id = await db.twofa_requests.insert_one({
            "admin_id": admin["_id"],
            "ip": new_ip,
            "user_agent": new_ua,
            "created_at": now,
            "expires_at": expire_at,
            "status": "pending"
        })

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
            f"👤 {admin_name}\n"
            f"📍 IP: {new_ip} ({location})\n"
            f"🖥 Устройство: {new_ua}\n"
            f"Разрешить вход? У вас есть 5 минут, чтобы ответить на запрос, в противном случае доступ будет запрещён."
        )
        
        message = await bot.send_message(chat_id=telegram_id, text=text, reply_markup=kb)
        
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"Уведомление о входе отправлено администратору {admin_name} в Telegram (ID: {telegram_id}) - ожидаем решение о предоставлении доступа с IP {new_ip} ({location})"
        )
        
    except Exception as e:
        admin_name = admin.get('full_name', 'Неизвестный админ')
        admin_email = admin.get('email', 'email не указан')
        telegram_id = admin.get('telegram_id', 'Telegram ID не указан')
        
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"КРИТИЧЕСКАЯ ОШИБКА! Не удалось отправить 2FA запрос администратору {admin_name} ({admin_email}) с IP {new_ip} в Telegram (ID: {telegram_id}). Ошибка: {str(e)}"
        )
        raise

@router.callback_query(F.data.startswith("2fa_"))
async def process_2fa_callback(callback: CallbackQuery):
    try:
        telegram_user = callback.from_user
        user_name = telegram_user.first_name or "Пользователь"
        username = telegram_user.username or "без username"
        
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"Пользователь {user_name} (@{username}) нажал кнопку в Telegram - получаем его решение по 2FA запросу"
        )
        
        action, admin_id = callback.data.split("_", 2)[1:]
        admin_obj_id = ObjectId(admin_id)

        # Получим актуальный 2FA-запрос
        request = await db.twofa_requests.find_one({
            "admin_id": admin_obj_id,
            "status": "pending",
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not request:
            current_time = datetime.utcnow()
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FA,
                message=f"Пользователь {user_name} попытался ответить на 2FA запрос, но активный запрос не найден - либо время истекло, либо запрос уже обработан (текущее время: {current_time.strftime('%H:%M:%S')})"
            )
            await callback.answer("⌛ Время истекло или запрос уже обработан", show_alert=True)
            return

        if action == "allow":
            request_ip = request["ip"]
            request_ua = request["user_agent"]
            created_time = request["created_at"].strftime('%H:%M:%S')
            
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FA,
                message=f"Администратор {user_name} РАЗРЕШИЛ вход в систему с IP {request_ip} - предоставляем полный доступ к админ-панели"
            )
            
            # Обновляем is_verified и active_session
            result = await db.admins.update_one(
                {"_id": admin_obj_id},
                {
                    "$set": {
                        "is_verified": True,
                        "active_session": {
                            "ip": request_ip,
                            "user_agent": request_ua,
                            "token": None  # будет установлен при следующем login
                        }
                    }
                }
            )
            
            update_result = await db.twofa_requests.update_one(
                {"_id": request["_id"]}, 
                {"$set": {"status": "allowed"}}
            )
            
            await callback.answer("✅ Вход разрешён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Вход разрешён",
                reply_markup=None
            )
            
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Безопасность: Администратор {user_name} успешно прошел 2FA проверку и получил доступ к системе с IP {request_ip} в {datetime.utcnow().strftime('%H:%M:%S')}"
            )

        else:  # deny
            request_ip = request["ip"]
            request_ua = request["user_agent"]
            created_time = request["created_at"].strftime('%H:%M:%S')
            deny_time = datetime.utcnow().strftime('%H:%M:%S')
            
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FA,
                message=f"Администратор {user_name} ОТКЛОНИЛ попытку входа с IP {request_ip} - блокируем доступ к системе"
            )
            
            update_result = await db.twofa_requests.update_one(
                {"_id": request["_id"]}, 
                {"$set": {"status": "denied"}}
            )
            
            await callback.answer("❌ Вход запрещён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Вход запрещён",
                reply_markup=None
            )
            
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Безопасность: Попытка входа с IP {request_ip} ЗАБЛОКИРОВАНА! Администратор {user_name} сам отклонил доступ в {deny_time} - подозрительная активность или несанкционированная попытка входа"
            )
    
    except Exception as e:
        error_user_id = getattr(callback.from_user, 'id', 'неизвестен') if callback and callback.from_user else 'неизвестен'
        error_username = getattr(callback.from_user, 'username', 'без username') if callback and callback.from_user else 'неизвестен'
        error_callback = getattr(callback, 'data', 'неизвестно') if callback else 'неизвестно'
        
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TWO_FA,
            message=f"КРИТИЧЕСКАЯ ОШИБКА! Не удалось обработать ответ пользователя {error_username} (ID: {error_user_id}) на 2FA запрос. Ошибка: {str(e)}"
        )
        await callback.answer("Произошла ошибка. Подробности в логах.", show_alert=True)