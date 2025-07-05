import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from bson import ObjectId
import requests

from database import get_database
from log_system import get_2fa_logger, LogSection, LogSubsection
from config import settings

logger = get_2fa_logger()

router = Router()

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# TTL запросов (в секундах)
TWO_FA_TTL = 300


def get_location_by_ip(ip: str) -> str:
    """Получение геолокации по IP"""
    # Проверяем, что IP не является "unknown" или пустым
    if not ip or ip.lower() in ["unknown", "none", "null", ""]:
        logger.debug(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"IP адрес не определен или равен '{ip}' - пропускаем геолокацию"
        )
        return "IP не определен"
    
    try:
        logger.debug(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Ищем откуда подключается пользователь - отправляем запрос геолокации для IP {ip}"
        )
        
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = response.json()
        
        if data['status'] == 'success':
            location = f"{data['country']}, {data['city']}"
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Геолокация найдена: IP {ip} находится в стране {data['country']}, город {data['city']}, провайдер {data.get('isp', 'неизвестен')}"
            )
            return location
        else:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=f"Не удалось определить местоположение IP {ip} - сервис геолокации вернул ошибку {data.get('status')}"
            )
            return "Неизвестное местоположение"
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Произошла ошибка при поиске геолокации для IP {ip}: {str(e)}"
        )
        return "Ошибка получения местоположения"


async def send_2fa_request(admin_data: dict, new_ip: str, new_ua: str) -> dict:
    """Отправка 2FA запроса в Telegram"""
    try:
        admin_name = admin_data.get('admin_name', 'Неизвестный админ')
        admin_email = admin_data.get('admin_email', 'email не указан')
        telegram_id = admin_data.get('telegram_id')
        admin_id = admin_data.get('admin_id')
        
        # Формируем сообщение для лога в зависимости от наличия IP
        if new_ip and new_ip.lower() not in ["unknown", "none", "null", ""]:
            log_message = f"Администратор {admin_name} ({admin_email}) пытается войти в систему с IP {new_ip} - запускаем двухфакторную проверку через Telegram"
        else:
            log_message = f"Администратор {admin_name} ({admin_email}) пытается войти в систему с неопределенным IP - запускаем двухфакторную проверку через Telegram"
        
        logger.info(
            section=LogSection.TWO_FA,
            subsection=LogSubsection.TWO_FA.REQUEST_SENT,
            message=log_message
        )
        
        now = datetime.utcnow()
        expire_at = now + timedelta(seconds=TWO_FA_TTL)
        
        logger.debug(
            section=LogSection.TWO_FA,
            subsection=LogSubsection.TWO_FA.REQUEST_SENT,
            message=f"Создаем временную запись 2FA для {admin_name} - срок действия {TWO_FA_TTL//60} минут (до {expire_at.strftime('%H:%M:%S')})"
        )
        
        # Создаем запись в базе данных
        db = await get_database()
        request_doc = {
            "admin_id": ObjectId(admin_id),
            "ip": new_ip,
            "user_agent": new_ua,
            "created_at": now,
            "expires_at": expire_at,
            "status": "pending"
        }
        
        result = await db.twofa_requests.insert_one(request_doc)
        request_id = str(result.inserted_id)

        # Получаем геолокацию
        location = get_location_by_ip(new_ip)

        # Создаем клавиатуру
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Разрешить",
                    callback_data=f"2fa_allow_{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Запретить",
                    callback_data=f"2fa_deny_{request_id}"
                )
            ]
        ])
        
        # Формируем текст сообщения в зависимости от наличия IP
        if new_ip and new_ip.lower() not in ["unknown", "none", "null", ""]:
            ip_text = f"📍 IP: {new_ip} ({location})"
        else:
            ip_text = f"📍 IP: не определен ({location})"
        
        text = (
            f"🔐 Попытка входа в админ-панель\n"
            f"👤 {admin_name}\n"
            f"{ip_text}\n"
            f"🖥 Устройство: {new_ua}\n"
            f"Разрешить вход? У вас есть 5 минут, чтобы ответить на запрос, в противном случае доступ будет запрещён."
        )
        
        message = await bot.send_message(chat_id=telegram_id, text=text, reply_markup=kb)
        
        # Формируем сообщение для лога в зависимости от наличия IP
        if new_ip and new_ip.lower() not in ["unknown", "none", "null", ""]:
            log_message = f"Уведомление о входе отправлено администратору {admin_name} в Telegram (ID: {telegram_id}) - ожидаем решение о предоставлении доступа с IP {new_ip} ({location})"
        else:
            log_message = f"Уведомление о входе отправлено администратору {admin_name} в Telegram (ID: {telegram_id}) - ожидаем решение о предоставлении доступа с неопределенным IP ({location})"
        
        logger.info(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.MESSAGE_SENT,
            message=log_message
        )
        
        return {
            "success": True,
            "request_id": request_id,
            "expires_at": expire_at,
            "message": "2FA запрос отправлен"
        }
        
    except Exception as e:
        admin_name = admin_data.get('admin_name', 'Неизвестный админ')
        admin_email = admin_data.get('admin_email', 'email не указан')
        telegram_id = admin_data.get('telegram_id', 'Telegram ID не указан')
        
        # Формируем сообщение об ошибке в зависимости от наличия IP
        if new_ip and new_ip.lower() not in ["unknown", "none", "null", ""]:
            error_message = f"КРИТИЧЕСКАЯ ОШИБКА! Не удалось отправить 2FA запрос администратору {admin_name} ({admin_email}) с IP {new_ip} в Telegram (ID: {telegram_id}). Ошибка: {str(e)}"
        else:
            error_message = f"КРИТИЧЕСКАЯ ОШИБКА! Не удалось отправить 2FA запрос администратору {admin_name} ({admin_email}) с неопределенным IP в Telegram (ID: {telegram_id}). Ошибка: {str(e)}"
        
        logger.error(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.MESSAGE_FAILED,
            message=error_message
        )
        
        return {
            "success": False,
            "message": f"Ошибка отправки 2FA запроса: {str(e)}"
        }


@router.callback_query(F.data.startswith("2fa_"))
async def process_2fa_callback(callback: CallbackQuery):
    """Обработка callback от Telegram бота"""
    try:
        telegram_user = callback.from_user
        user_name = telegram_user.first_name or "Пользователь"
        username = telegram_user.username or "без username"
        
        logger.info(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.CALLBACK_RECEIVED,
            message=f"Пользователь {user_name} (@{username}) нажал кнопку в Telegram - получаем его решение по 2FA запросу"
        )
        
        action, request_id = callback.data.split("_", 2)[1:]
        request_obj_id = ObjectId(request_id)

        # Получаем актуальный 2FA-запрос
        db = await get_database()
        request = await db.twofa_requests.find_one({
            "_id": request_obj_id,
            "status": "pending",
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not request:
            current_time = datetime.utcnow()
            logger.warning(
                section=LogSection.TWO_FA,
                subsection=LogSubsection.TWO_FA.REQUEST_EXPIRED,
                message=f"Пользователь {user_name} попытался ответить на 2FA запрос, но активный запрос не найден - либо время истекло, либо запрос уже обработан (текущее время: {current_time.strftime('%H:%M:%S')})"
            )
            await callback.answer("⌛ Время истекло или запрос уже обработан", show_alert=True)
            return

        if action == "allow":
            request_ip = request["ip"]
            request_ua = request["user_agent"]
            admin_id = request["admin_id"]
            
            # Формируем сообщение для лога в зависимости от наличия IP
            if request_ip and request_ip.lower() not in ["unknown", "none", "null", ""]:
                log_message = f"Администратор {user_name} РАЗРЕШИЛ вход в систему с IP {request_ip} - предоставляем полный доступ к админ-панели"
            else:
                log_message = f"Администратор {user_name} РАЗРЕШИЛ вход в систему с неопределенным IP - предоставляем полный доступ к админ-панели"
            
            logger.info(
                section=LogSection.TWO_FA,
                subsection=LogSubsection.TWO_FA.REQUEST_ALLOWED,
                message=log_message
            )
            
            # Обновляем is_verified и active_session в основной базе
            result = await db.admins.update_one(
                {"_id": admin_id},
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
            
            # Обновляем статус запроса
            update_result = await db.twofa_requests.update_one(
                {"_id": request["_id"]}, 
                {"$set": {"status": "allowed"}}
            )
            
            await callback.answer("✅ Вход разрешён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Вход разрешён",
                reply_markup=None
            )
            
            # Формируем сообщение для лога безопасности в зависимости от наличия IP
            if request_ip and request_ip.lower() not in ["unknown", "none", "null", ""]:
                security_message = f"Безопасность: Администратор {user_name} успешно прошел 2FA проверку и получил доступ к системе с IP {request_ip} в {datetime.utcnow().strftime('%H:%M:%S')}"
            else:
                security_message = f"Безопасность: Администратор {user_name} успешно прошел 2FA проверку и получил доступ к системе с неопределенным IP в {datetime.utcnow().strftime('%H:%M:%S')}"
            
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=security_message
            )

        else:  # deny
            request_ip = request["ip"]
            request_ua = request["user_agent"]
            deny_time = datetime.utcnow().strftime('%H:%M:%S')
            
            # Формируем сообщение для лога в зависимости от наличия IP
            if request_ip and request_ip.lower() not in ["unknown", "none", "null", ""]:
                log_message = f"Администратор {user_name} ОТКЛОНИЛ попытку входа с IP {request_ip} - блокируем доступ к системе"
            else:
                log_message = f"Администратор {user_name} ОТКЛОНИЛ попытку входа с неопределенным IP - блокируем доступ к системе"
            
            logger.warning(
                section=LogSection.TWO_FA,
                subsection=LogSubsection.TWO_FA.REQUEST_DENIED,
                message=log_message
            )
            
            # Обновляем статус запроса
            update_result = await db.twofa_requests.update_one(
                {"_id": request["_id"]}, 
                {"$set": {"status": "denied"}}
            )
            
            await callback.answer("❌ Вход запрещён", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Вход запрещён",
                reply_markup=None
            )
            
            # Формируем сообщение для лога безопасности в зависимости от наличия IP
            if request_ip and request_ip.lower() not in ["unknown", "none", "null", ""]:
                security_message = f"Безопасность: Попытка входа с IP {request_ip} ЗАБЛОКИРОВАНА! Администратор {user_name} сам отклонил доступ в {deny_time} - подозрительная активность или несанкционированная попытка входа"
            else:
                security_message = f"Безопасность: Попытка входа с неопределенным IP ЗАБЛОКИРОВАНА! Администратор {user_name} сам отклонил доступ в {deny_time} - подозрительная активность или несанкционированная попытка входа"
            
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUDIT,
                message=security_message
            )
    
    except Exception as e:
        error_user_id = getattr(callback.from_user, 'id', 'неизвестен') if callback and callback.from_user else 'неизвестен'
        error_username = getattr(callback.from_user, 'username', 'без username') if callback and callback.from_user else 'неизвестен'
        error_callback = getattr(callback, 'data', 'неизвестно') if callback else 'неизвестно'
        
        logger.error(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.CALLBACK_FAILED,
            message=f"КРИТИЧЕСКАЯ ОШИБКА! Не удалось обработать ответ пользователя {error_username} (ID: {error_user_id}) на 2FA запрос. Ошибка: {str(e)}"
        )
        await callback.answer("Произошла ошибка. Подробности в логах.", show_alert=True)


async def cleanup_expired_requests():
    """Очистка истекших запросов"""
    try:
        db = await get_database()
        now = datetime.utcnow()
        result = await db.twofa_requests.update_many(
            {
                "status": "pending",
                "expires_at": {"$lt": now}
            },
            {"$set": {"status": "expired"}}
        )
        
        if result.modified_count > 0:
            logger.info(
                section=LogSection.TWO_FA,
                subsection=LogSubsection.TWO_FA.REQUEST_EXPIRED,
                message=f"Очищено {result.modified_count} истекших 2FA запросов"
            )
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.MAINTENANCE,
            message=f"Ошибка при очистке истекших 2FA запросов: {str(e)}"
        ) 