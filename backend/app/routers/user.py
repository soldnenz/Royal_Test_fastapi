# app/routers/user.py

import logging
from typing import Optional, Literal
import secrets
import string
import json
import math

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Body, BackgroundTasks
from bson import ObjectId
from fastapi.security import HTTPBearer
from app.db.database import db
from app.schemas.user_schemas import UserOut, UserUpdate
from app.core.security import get_current_actor
from app.db.database import get_database
from datetime import datetime, timedelta
from app.core.response import success
import re
from fastapi.encoders import jsonable_encoder
from app.schemas.subscription_schemas import SubscriptionCreate, GiftSubscriptionCreate, IssuedBy, PaymentInfo
from app.schemas.promo_code_schemas import PromoCodeActivate, PromoCodeCreate, PromoCodeOut, PromoCodeAdminUpdate
from pydantic import BaseModel, Field
from app.core.finance import process_referral
from enum import Enum

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me")
async def get_current_profile(actor = Depends(get_current_actor)):
    """
    actor["type"]  →  'user' | 'admin' | 'guest'
    actor["role"]  →  'user' | 'admin' | 'moder' | 'guest'
    """
    if actor["type"] == "user":
        profile = {
            "id": str(actor["id"]),
            "full_name": actor["full_name"],
            "email": actor["email"],
            "phone": actor["phone"],
            "iin": actor["iin"],
            "money": actor["money"],
            "created_at": actor["created_at"].isoformat() if actor.get("created_at") else None,
            "is_guest": False
        }

    elif actor["type"] == "guest":
        profile = {
            "id": actor["id"],
            "full_name": actor.get("full_name", "Guest User"),
            "email": actor.get("email"),
            "lobby_id": actor.get("lobby_id"),
            "created_at": actor["created_at"].isoformat() if actor.get("created_at") else None,
            "is_guest": True
        }

    elif actor["type"] == "admin":           # включает и модераторов
        profile = {
            "id": str(actor["id"]),
            "role": actor["role"],           # 'admin' ИЛИ 'moder'
            "full_name": actor["full_name"],
            "iin": actor["iin"],
            "is_guest": False
        }

    else:
        raise HTTPException(
            status_code=403,
            detail={"message": "Unknown role", "hint": "Роль пользователя не распознана"}
        )

    return success(data=profile, message="Профиль получен")


@router.get("/{user_id}")
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получить профиль пользователя или гостя по ID
    """
    if current_user["role"] not in {"user", "guest"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещён"}
        )
    
    # Проверяем, является ли это гостем (ID начинается с "guest_")
    if user_id.startswith("guest_"):
        # Ищем в коллекции гостей
        guest = await db.guests.find_one({"_id": user_id})
        
        if not guest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Гость не найден"}
            )
        
        # Возвращаем информацию о госте
        profile = {
            "id": guest["_id"],
            "full_name": guest.get("full_name", "Guest User"),
            "created_at": guest.get("created_at").isoformat() if guest.get("created_at") else None,
            "is_guest": True
        }
        
        return success(data=profile, message="Профиль гостя получен")
    
    else:
        # Проверяем валидность ObjectId для обычных пользователей
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Неверный формат ID пользователя"}
            )
        
        # Ищем в коллекции пользователей
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Пользователь не найден"}
            )
        
        # Возвращаем только публичную информацию
        profile = {
            "id": str(user["_id"]),
            "full_name": user.get("full_name", "Unknown User"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
            "is_guest": False
        }
        
        return success(data=profile, message="Профиль пользователя получен")




@router.get("/my/subscription", response_model=dict)
async def get_my_subscription_info(
    current_user: dict = Depends(get_current_actor),
    db=Depends(get_database)
):
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только для пользователей", "path": "/my/subscription"}
        )

    user_id = current_user["id"]
    now = datetime.utcnow()

    subscription = await db.subscriptions.find_one({
        "user_id": ObjectId(user_id),
        "is_active": True
    })

    if not subscription:
        return success(
            data={"has_subscription": False},
            message="У вас нет активной подписки"
        )

    if subscription["expires_at"] < now:
        await db.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {"$set": {
                "is_active": False,
                "cancel_reason": "Истек срок действия",
                "cancelled_at": now,
                "cancelled_by": "system",
                "updated_at": now
            }}
        )
        return success(
            data={"has_subscription": False},
            message="Подписка истекла"
        )

    days_left = (subscription["expires_at"] - now).days
    return success(
        data={
            "has_subscription": True,
            "subscription_type": subscription["subscription_type"],
            "expires_at": subscription["expires_at"].isoformat(),
            "days_left": max(days_left, 0),
            "duration_days": subscription["duration_days"] 
        },
        message="Подписка активна"
    )


@router.get("/admin/search_users", response_model=list[UserOut])
async def search_users_by_query(
    query: str = Query(..., description="ID, ИИН, email, телефон, ФИО или код реферала"),
    current_user: dict = Depends(get_current_actor),
    db=Depends(get_database)
):
    """
    Поиск пользователей по различным параметрам с расширенной информацией
    о подписках, реферальной системе и активности.
    """
    start_time = datetime.utcnow()
    
    if current_user["role"] not in {"admin", "moderator"}:
        logger.warning(f"Unauthorized access attempt to search_users by user {current_user['id']} with role {current_user['role']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещён", "path": "/admin/search_users"}
        )

    # Санитизация запроса для предотвращения NoSQL-инъекций
    sanitized_query = query.strip()
    if not sanitized_query:
        logger.warning(f"Empty query in search_users by user {current_user['id']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Поисковый запрос не может быть пустым"}
        )
    
    # Безопасно проверяем, является ли запрос ObjectId
    is_valid_object_id = False
    try:
        if ObjectId.is_valid(sanitized_query):
            is_valid_object_id = True
    except Exception:
        is_valid_object_id = False
    
    # Строим безопасный поисковый фильтр
    filters = []
    
    # Добавляем безопасные поисковые условия
    if is_valid_object_id:
        filters.append({"_id": ObjectId(sanitized_query)})
    
    # Эскейпим регулярные выражения для предотвращения ReDoS атак
    regex_pattern = re.escape(sanitized_query)
    
    # Безопасно добавляем остальные фильтры
    filters.extend([
        {"iin": sanitized_query},
        {"email": sanitized_query},
        {"phone": sanitized_query},
        {"full_name": {"$regex": regex_pattern, "$options": "i"}},
        {"referred_by": sanitized_query},
        {"referral_code": sanitized_query}  # Добавляем поиск по реферальному коду
    ])
    
    logger.info(f"User search initiated by {current_user['id']} with query: {sanitized_query}")
    
    try:
        # Ограничиваем выборку и устанавливаем таймаут для защиты от DoS
        cursor = db.users.find({"$or": filters}).limit(50).max_time_ms(5000)
        results = []
        
        now = datetime.utcnow()
        user_cache = {}
        
        # Оптимизированный сбор данных пользователей
        async for user in cursor:
            user_id = user.pop("_id", None)
            user_id_str = str(user_id) if user_id else None
            
            # Базовая информация о пользователе
            user_data = {
                "id": user_id_str,
                "iin": user.get("iin", None),
                "full_name": user.get("full_name", None),
                "email": user.get("email", None),
                "phone": user.get("phone", None),
                "money": user.get("money", 0),
                "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
                "referred_by": user.get("referred_by", None),
                "referred_use": user.get("referred_use", False),
                "subscription": None,
                "subscription_history": [],
                "referral_system": None,
                "last_activity": None
            }
            
            # Сохраняем пользовательский объект для последующей обработки
            # Важно сохранить referral_code и другие важные поля
            user_cache[user_id_str] = {
                "referral_code": user.get("referral_code", None),
                **user
            }
            
            results.append(user_data)
        
        # Параллельное получение данных для всех пользователей для увеличения производительности
        if results:
            user_ids = [ObjectId(user["id"]) for user in results if user["id"]]
            
            # 1. Получаем все активные подписки этих пользователей пакетным запросом
            active_subs_cursor = db.subscriptions.find({
                "user_id": {"$in": user_ids},
                "is_active": True
            })
            
            active_subscriptions = {}
            async for sub in active_subs_cursor:
                user_id_str = str(sub["user_id"])
                if user_id_str in user_cache:
                    active_subscriptions[user_id_str] = {
                        "subscription_type": sub.get("subscription_type", None),
                        "is_active": sub.get("is_active", False),
                        "expires_at": sub.get("expires_at").isoformat() if sub.get("expires_at") else None,
                        "activation_method": sub.get("activation_method", None),
                        "created_at": sub.get("created_at").isoformat() if sub.get("created_at") else None
                    }
            
            # 2. Получаем историю подписок
            sub_history_pipeline = [
                {"$match": {"user_id": {"$in": user_ids}}},
                {"$sort": {"created_at": -1}},
                {"$group": {
                    "_id": "$user_id",
                    "subscriptions": {"$push": "$$ROOT"}
                }}
            ]
            
            subscription_history = {}
            async for result in db.subscriptions.aggregate(sub_history_pipeline):
                user_id_str = str(result["_id"])
                subscription_history[user_id_str] = []
                
                for sub in result["subscriptions"]:
                    sub_status = "Активна" if sub.get("is_active", False) else "Истекла"
                    
                    # Проверка на истекшую подписку
                    if sub_status == "Активна" and sub.get("expires_at") and sub.get("expires_at") < now:
                        sub_status = "Истекла"
                    
                    subscription_history[user_id_str].append({
                        "date": sub.get("created_at").isoformat() if sub.get("created_at") else None,
                        "type": sub.get("subscription_type", "Unknown"),
                        "duration": f"{sub.get('duration_days', 0)} дней",
                        "status": sub_status
                    })
            
            # 3. Получаем последнюю активность пользователей из коллекции tokens
            last_activity_pipeline = [
                {"$match": {"user_id": {"$in": user_ids}}},
                {"$sort": {"last_activity": -1}},
                {"$group": {
                    "_id": "$user_id",
                    "last_activity": {"$first": "$last_activity"},
                    "ip": {"$first": "$ip"},
                    "user_agent": {"$first": "$user_agent"}
                }}
            ]
            
            user_activity = {}
            async for activity in db.tokens.aggregate(last_activity_pipeline):
                user_id_str = str(activity["_id"])
                user_activity[user_id_str] = {
                    "last_login": activity.get("last_activity").isoformat() if activity.get("last_activity") else None,
                    "ip_address": activity.get("ip", None),
                    "user_agent": activity.get("user_agent", None)
                }
            
            # 4. Получаем информацию о промокодах пользователей
            promo_codes = {}
            
            # Создаем список ID пользователей в обоих форматах (ObjectId и строки)
            user_id_objs = user_ids
            user_id_strs = [str(user_id) for user_id in user_ids]
            
            # Ищем промокоды, созданные пользователями, учитывая оба формата хранения ID
            promo_query = {
                "$or": [
                    {"created_by_user_id": {"$in": user_id_objs}},  # Если ID хранится как ObjectId
                    {"created_by_user_id": {"$in": user_id_strs}}   # Если ID хранится как строка
                ]
            }
            
            promo_cursor = db.promo_codes.find(promo_query)
            
            async for promo in promo_cursor:
                # Определяем ID пользователя, учитывая, что оно может быть как ObjectId, так и строкой
                user_id_raw = promo.get("created_by_user_id")
                if isinstance(user_id_raw, ObjectId):
                    user_id_str = str(user_id_raw)
                else:
                    user_id_str = user_id_raw
                
                # Если ID не найдено или не валидно, пропускаем запись
                if not user_id_str or user_id_str not in user_cache:
                    continue
                
                if user_id_str not in promo_codes:
                    promo_codes[user_id_str] = []
                
                # Собираем информацию о пользователях, которые активировали промокод
                promo_used_by = promo.get("used_by", [])
                used_by_users = []
                
                for used_user_id in promo_used_by:
                    if ObjectId.is_valid(used_user_id):
                        user_info = await db.users.find_one({"_id": ObjectId(used_user_id)})
                        if user_info:
                            # Находим подписку, активированную этим промокодом
                            sub = await db.subscriptions.find_one({
                                "user_id": ObjectId(used_user_id),
                                "promo_code": promo.get("code"),
                                "activation_method": "promocode"
                            })
                            
                            used_by_users.append({
                                "user_id": str(user_info["_id"]),
                                "full_name": user_info.get("full_name", ""),
                                "iin": user_info.get("iin", ""),
                                "activated_at": sub.get("created_at").isoformat() if sub and sub.get("created_at") else None
                            })
                
                promo_codes[user_id_str].append({
                    "code": promo.get("code"),
                    "subscription_type": promo.get("subscription_type"),
                    "duration_days": promo.get("duration_days"),
                    "is_active": promo.get("is_active"),
                    "usage_limit": promo.get("usage_limit"),
                    "usage_count": promo.get("usage_count", 0),
                    "expires_at": promo.get("expires_at").isoformat() if promo.get("expires_at") else None,
                    "type": "created",  # Пометка, что это созданный пользователем промокод
                    "used_by": used_by_users
                })
            
            # Также ищем промокоды, которые пользователь активировал
            for user_id in user_ids:
                user_id_str = str(user_id)
                
                # Находим подписки пользователя, активированные через промокод
                user_subs = await db.subscriptions.find({
                    "user_id": user_id,
                    "activation_method": "promocode"
                }).to_list(length=10)
                
                for sub in user_subs:
                    promo_code = sub.get("promo_code")
                    if not promo_code:
                        continue
                        
                    # Находим детали промокода
                    promo = await db.promo_codes.find_one({"code": promo_code})
                    if not promo:
                        continue
                        
                    if user_id_str not in promo_codes:
                        promo_codes[user_id_str] = []
                        
                    # Добавляем информацию о использованном промокоде
                    promo_codes[user_id_str].append({
                        "code": promo_code,
                        "subscription_type": promo.get("subscription_type"),
                        "duration_days": promo.get("duration_days"),
                        "is_active": False,  # Уже использован
                        "activated_at": sub.get("created_at").isoformat() if sub.get("created_at") else None,
                        "expires_at": sub.get("expires_at").isoformat() if sub.get("expires_at") else None,
                        "type": "used"  # Пометка, что это использованный промокод
                    })
            
            # 5. Добавляем данные в результат
            for user_data in results:
                user_id_str = user_data["id"]
                user_obj = user_cache.get(user_id_str, {})
                
                # Добавляем активную подписку, если есть
                if user_id_str in active_subscriptions:
                    user_data["subscription"] = active_subscriptions[user_id_str]
                
                # Добавляем историю подписок
                if user_id_str in subscription_history:
                    user_data["subscription_history"] = subscription_history[user_id_str]
                
                # Добавляем информацию о последней активности
                if user_id_str in user_activity:
                    user_data["last_activity"] = user_activity[user_id_str]
                
                # Добавляем информацию о промокодах
                if user_id_str in promo_codes:
                    if "promo_codes" not in user_data:
                        user_data["promo_codes"] = promo_codes[user_id_str]
                
                # Добавляем информацию о реферальной системе
                referral_code = user_obj.get("referral_code")
                if referral_code:
                    try:
                        # Счетчик приведенных пользователей с лимитом времени
                        referred_users_cursor = db.users.find(
                            {"referred_by": referral_code}
                        ).limit(20).max_time_ms(2000)
                        
                        referred_users = []
                        referred_count = 0
                        
                        # Собираем информацию о пользователях, которые использовали реферальный код
                        async for ref_user in referred_users_cursor:
                            referred_count += 1
                            referred_users.append({
                                "user_id": str(ref_user["_id"]),
                                "full_name": ref_user.get("full_name", ""),
                                "iin": ref_user.get("iin", ""),
                                "created_at": ref_user.get("created_at").isoformat() if ref_user.get("created_at") else None,
                                "has_subscription": await db.subscriptions.count_documents(
                                    {"user_id": ref_user["_id"], "is_active": True}
                                ) > 0,
                                "referred_use": ref_user.get("referred_use", False)
                            })
                        
                        # Подсчет бонусов с лимитом времени
                        total_bonus = 0
                        bonus_cursor = db.transactions.find(
                            {"user_id": ObjectId(user_id_str), "type": "referral"}
                        ).max_time_ms(2000)
                        
                        async for tx in bonus_cursor:
                            total_bonus += tx.get("amount", 0)
                        
                        user_data["referral_system"] = {
                            "code": referral_code,
                            "referred_users_count": referred_count,
                            "earned_bonus": total_bonus,
                            "referred_users": referred_users
                        }
                    except Exception as e:
                        logger.error(f"Error processing referral data for user {user_id_str}: {str(e)}")
                        user_data["referral_system"] = {
                            "code": referral_code,
                            "referred_users_count": 0,
                            "earned_bonus": 0,
                            "error": "Не удалось получить полные данные"
                        }
                
                # Также проверяем наличие реферальных кодов в коллекции referrals
                try:
                    referrals_cursor = db.referrals.find({"owner_user_id": user_id_str}).max_time_ms(2000)
                    referrals = []
                    
                    async for ref in referrals_cursor:
                        ref_code = ref.get("code")
                        
                        # Находим пользователей, которые активировали этот реферальный код
                        activated_users = []
                        if ref_code:
                            ref_users_cursor = db.users.find({"referred_by": ref_code}).limit(20).max_time_ms(2000)
                            
                            async for ref_user in ref_users_cursor:
                                has_subscription = await db.subscriptions.count_documents({
                                    "user_id": ref_user["_id"], 
                                    "is_active": True
                                }) > 0
                                
                                activated_users.append({
                                    "user_id": str(ref_user["_id"]),
                                    "full_name": ref_user.get("full_name", ""),
                                    "iin": ref_user.get("iin", ""),
                                    "created_at": ref_user.get("created_at").isoformat() if ref_user.get("created_at") else None,
                                    "has_subscription": has_subscription,
                                    "referred_use": ref_user.get("referred_use", False)
                                })
                        
                        referrals.append({
                            "code": ref_code,
                            "type": ref.get("type"),
                            "rate": ref.get("rate"),
                            "description": ref.get("description"),
                            "active": ref.get("active", True),
                            "created_at": ref.get("created_at").isoformat() if ref.get("created_at") else None,
                            "activated_users": activated_users,
                            "activated_count": len(activated_users)
                        })
                    
                    if referrals:
                        if not user_data.get("referral_system"):
                            user_data["referral_system"] = {"referrals": referrals}
                        else:
                            user_data["referral_system"]["referrals"] = referrals
                except Exception as e:
                    logger.error(f"Error fetching referrals for user {user_id_str}: {str(e)}")
        
        if not results:
            logger.info(f"No users found for query: {sanitized_query}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Пользователь не найден", "query": sanitized_query}
            )
        
        return success(
            data=results, 
            message=f"Найдено пользователей: {len(results)}",
        )
        
    except HTTPException:
        # Пробрасываем HTTP-исключения без изменений
        raise
    except Exception as e:
        # Обрабатываем неожиданные ошибки
        logger.error(f"Error in search_users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Произошла ошибка при поиске пользователей", "error": str(e)}
        )



@router.get("/users/history", summary="История тестов пользователя")
async def get_user_history(
    limit: int = 50, 
    offset: int = 0, 
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает историю прохождения тестов пользователя
    """
    user_id = str(current_user["id"])
    
    # Подсчитываем общее количество
    total = await db.history.count_documents({"user_id": user_id})
    
    # Получаем записи с пагинацией и сортировкой по дате (новые в начале)
    history = await db.history.find(
        {"user_id": user_id}
    ).sort("date", -1).skip(offset).limit(limit).to_list(length=limit)
    
    # Преобразуем ObjectId в строки
    for record in history:
        record["id"] = str(record["_id"])
        del record["_id"]
    
    return success(data={
        "history": history,
        "total": total,
        "limit": limit,
        "offset": offset
    })

# New user subscription endpoints below:
class SubscriptionType(str, Enum):
    economy = "economy"
    vip     = "vip"
    royal   = "royal"
    
class PurchaseSubscription(BaseModel):
    subscription_type: SubscriptionType
    duration_days:     int = Field(..., gt=0, le=90)  # максимум 3 месяца = 90 дней
    use_balance:       bool = True

@router.post("/purchase-subscription", summary="Покупка подписки для себя")
async def purchase_subscription(
    sub_data: PurchaseSubscription,
    background_tasks: BackgroundTasks,          # ← нет дефолта, идёт сразу после sub_data
    current_user: dict       = Depends(get_current_actor),
    db:           any        = Depends(get_database),
):
    # Только обычные пользователи
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут покупать подписки"}
        )

    user_id  = current_user["id"]
    user_iin = current_user["iin"]

    # Подтягиваем полный профиль
    full_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Пользователь не найден"}
        )

    # Проверяем, нет ли уже активной подписки
    existing = await db.subscriptions.find_one({
        "user_id":   ObjectId(user_id),
        "is_active": True
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "У вас уже есть активная подписка"}
        )

    # Рассчитываем цену и проверяем баланс
    price = calculate_subscription_price(
        sub_data.subscription_type,
        sub_data.duration_days
    )
    if sub_data.use_balance and full_user.get("money", 0) < price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Недостаточно средств. Требуется: {price} тг."}
        )

    # Готовим документы
    now        = datetime.utcnow()
    expires_at = now + timedelta(days=sub_data.duration_days)

    subscription_doc = {
        "user_id":           ObjectId(user_id),
        "iin":               user_iin,
        "created_at":        now,
        "updated_at":        now,
        "is_active":         True,
        "cancelled_at":      None,
        "cancelled_by":      None,
        "cancel_reason":     None,
        "amount":            price,
        "activation_method": "payment",
        "issued_by": {
            "admin_iin": None,
            "full_name": "Самостоятельная покупка"
        },
        "subscription_type": sub_data.subscription_type.value,
        "duration_days":     sub_data.duration_days,
        "expires_at":        expires_at,
        "payment": {
            "payment_id":    str(ObjectId()),
            "price":         price,
            "payment_method": "balance"
        }
    }

    transaction_doc = {
        "user_id":    ObjectId(user_id),
        "amount":     -price,
        "type":       "subscription_purchase",
        "description": f"Покупка {sub_data.subscription_type.value} на {sub_data.duration_days} дн.",
        "created_at": now,
        # "subscription_id" добавим после вставки
    }

    # Выполняем всё в Mongo-транзакции
    try:
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                res = await db.subscriptions.insert_one(subscription_doc, session=session)
                subscription_id = str(res.inserted_id)

                if sub_data.use_balance:
                    await db.users.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$inc": {"money": -price}},
                        session=session
                    )
                    transaction_doc["subscription_id"] = subscription_id
                    await db.transactions.insert_one(transaction_doc, session=session)

        # Реферальный бонус
        background_tasks.add_task(
            process_referral,
            str(user_id),
            price,
            f"Реферальный бонус за {sub_data.subscription_type.value}"
        )

        return success(
            data={
                "subscription_id":   subscription_id,
                "subscription_type": sub_data.subscription_type.value,
                "duration_days":     sub_data.duration_days,
                "expires_at":        expires_at.isoformat(),
                "price":             price,
                "balance_after":     full_user.get("money", 0) - price
            },
            message="Подписка успешно приобретена"
        )

    except HTTPException:
        # Пробрасываем наши 400/403/409 ошибки
        raise
    except Exception as e:
        logger.error(f"[PURCHASE ERROR] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Не удалось оформить подписку: {e}"}
        )

    

def calculate_subscription_price(
    subscription_type: SubscriptionType,
    duration_days: int
) -> int:
    """
    Рассчитывает стоимость подписки по daily-prorated модели и скидкам:
      - 5% скидка за 60 дней (2 месяца)
      - 10% скидка за 90 дней (3 месяца)
    """
    # Базовая цена за месяц (НОВЫЕ ЦЕНЫ)
    base_prices = {
        SubscriptionType.economy: 1500,  # новая цена
        SubscriptionType.vip:     3000,  # новая цена
        SubscriptionType.royal:   5000,  # новая цена
    }

    # Получаем базовую цену и считаем цену за 1 день
    monthly_price = base_prices[subscription_type]
    daily_price   = monthly_price / 30.0

    # Вычисляем скидку
    if duration_days == 90:  # 3 месяца
        discount = 0.10
    elif duration_days == 60:  # 2 месяца
        discount = 0.05
    else:
        discount = 0.0

    # Считаем сумму по дням с учётом скидки
    total = daily_price * duration_days * (1 - discount)

    # Округляем вверх до целого тенге
    return math.ceil(total)

@router.post("/purchase-gift-subscription", summary="Покупка подписки в подарок по ИИН")
async def purchase_gift_subscription(
    gift_data: GiftSubscriptionCreate,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Пользователь покупает подписку в подарок другому пользователю по ИИН.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут покупать подписки в подарок", "path": "/purchase-gift-subscription"}
        )
    
    user_id = current_user["id"]
    
    # Получаем полные данные пользователя из БД (включая поля referred_by и referred_use)
    full_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Пользователь не найден"}
        )
    
    # Проверяем, существует ли получатель
    recipient = await db.users.find_one({"iin": gift_data.gift_iin})
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Пользователь с указанным ИИН не найден"}
        )
    
    recipient_id = recipient["_id"]
    
    # Проверяем, не дарит ли пользователь сам себе
    if current_user["iin"] == gift_data.gift_iin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Нельзя подарить подписку самому себе"}
        )
    
    # Проверяем, нет ли уже активной подписки у получателя
    existing = await db.subscriptions.find_one({
        "user_id": recipient_id,
        "is_active": True
    })
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "У получателя уже есть активная подписка"}
        )
    
    # Рассчитываем стоимость подписки
    price = calculate_subscription_price(gift_data.subscription_type, gift_data.duration_days)
    
    # Проверяем, хватает ли средств
    if current_user["money"] < price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Недостаточно средств на балансе. Требуется: {price} тг."}
        )
    
    try:
        now = datetime.utcnow()
        expires_at = now + timedelta(days=gift_data.duration_days)
        
        # Создаем подписку для получателя
        subscription = {
            "user_id": recipient_id,
            "iin": gift_data.gift_iin,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancel_reason": None,
            "amount": price,
            "activation_method": "gift",
            "issued_by": {
                "admin_iin": None,
                "full_name": f"Подарок от {current_user['full_name']}"
            },
            "subscription_type": gift_data.subscription_type,
            "duration_days": gift_data.duration_days,
            "expires_at": expires_at,
            "payment": {
                "payment_id": str(ObjectId()),
                "price": price,
                "payment_method": "balance"
            },
            "gift": True,
            "gifted_by": {
                "user_id": ObjectId(current_user["id"]),
                "iin": current_user["iin"],
                "full_name": current_user["full_name"]
            }
        }
        
        # Выполняем всё в Mongo-транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                # Вставляем подписку в базу данных
                result = await db.subscriptions.insert_one(subscription, session=session)
                subscription_id = str(result.inserted_id)
                
                # Снимаем средства с баланса дарителя
                await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$inc": {"money": -price}},
                    session=session
                )
                
                # Создаем транзакцию
                transaction = {
                    "user_id": ObjectId(user_id),
                    "amount": -price,
                    "type": "gift_subscription",
                    "description": f"Подарок подписки {gift_data.subscription_type} на {gift_data.duration_days} дней пользователю {gift_data.gift_iin}",
                    "created_at": now,
                    "subscription_id": subscription_id,
                    "recipient_iin": gift_data.gift_iin
                }
                
                await db.transactions.insert_one(transaction, session=session)
        
        # Обработка реферальной системы через finance.process_referral
        description = f"Реферальный бонус за покупку подарочной подписки {gift_data.subscription_type}"
        await process_referral(str(user_id), price, description)
        
        logger.info(
            f"[GIFT] Пользователь {user_id} подарил подписку {gift_data.subscription_type} " +
            f"на {gift_data.duration_days} дней пользователю {gift_data.gift_iin} за {price} тг."
        )
        
        # По возможности отправляем уведомление получателю
        if "email" in recipient and recipient["email"]:
            # Здесь код для отправки email (будет реализован отдельно)
            pass
        
        return success(
            data={
                "subscription_id": subscription_id,
                "recipient_iin": gift_data.gift_iin,
                "subscription_type": gift_data.subscription_type,
                "duration_days": gift_data.duration_days,
                "expires_at": expires_at.isoformat(),
                "price": price,
                "balance_after": current_user["money"] - price
            },
            message="Подписка успешно подарена"
        )
        
    except Exception as e:
        logger.error(f"[GIFT ERROR] Ошибка при дарении подписки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при дарении подписки: {str(e)}"}
        )

def generate_promo_code(length=10):
    """
    Генерирует случайный промокод указанной длины.
    """
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        return code  # В реальном приложении здесь нужна проверка на уникальность

@router.post("/generate-promo-code", summary="Покупка подписки в виде промокода")
async def purchase_promo_code(
    promo_data:   PromoCodeCreate,
    request:      Request,
    current_user: dict      = Depends(get_current_actor),
    db:           any       = Depends(get_database)
):
    ip = request.client.host

    # Только для обычных пользователей
    if current_user.get("role") != "user":
        logger.warning(
            f"[PROMO][{ip}] Пользователь {current_user.get('id')} с ролью "
            f"{current_user.get('role')} попытался создать промокод"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут покупать промокоды"}
        )

    user_id = current_user["id"]
    balance = current_user.get("money", 0)

    # Рассчитываем цену
    price = calculate_subscription_price(
        promo_data.subscription_type,
        promo_data.duration_days
    )

    # Проверяем баланс
    if balance < price:
        logger.info(
            f"[PROMO][{ip}] Недостаточно средств у пользователя {user_id}: "
            f"баланс={balance}, требуется={price}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Недостаточно средств на балансе. Требуется: {price} тг."}
        )

    now = datetime.utcnow()
    expires_at = promo_data.expires_at or (now + timedelta(days=90))

    try:
        # Генерируем или принимаем код
        code = promo_data.code or generate_promo_code()
        # Гарантируем уникальность
        while await db.promo_codes.find_one({"code": code}):
            code = generate_promo_code()

        # Документ промокода
        promo_doc = {
            "code":               code,
            "subscription_type":  promo_data.subscription_type,
            "duration_days":      promo_data.duration_days,
            "usage_limit":        promo_data.usage_limit,
            "usage_count":        0,
            "used_by":            [],
            "is_active":          True,
            "purchase_amount":    price,
            "created_by_user_id": ObjectId(user_id),
            "created_at":         now,
            "updated_at":         now,
            "expires_at":         expires_at
        }
        
        # Выполняем всё в Mongo-транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db.promo_codes.insert_one(promo_doc, session=session)

                # Списание средств
                await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$inc": {"money": -price}},
                    session=session
                )

                # Лог транзакции
                txn = {
                    "user_id":     ObjectId(user_id),
                    "amount":      -price,
                    "type":        "promo_code_purchase",
                    "description": f"Покупка промокода {code}",
                    "created_at":  now,
                    "promo_code":  code
                }
                await db.transactions.insert_one(txn, session=session)

        logger.info(
            f"[PROMO][{ip}] Промокод {code} создан для пользователя {user_id}, "
            f"цена={price}, баланс_после={balance - price}"
        )

        return success(
            data={
                "promo_code":        code,
                "subscription_type": promo_data.subscription_type,
                "duration_days":     promo_data.duration_days,
                "expires_at":        expires_at.isoformat(),
                "price":             price,
                "balance_after":     balance - price
            },
            message="Промокод успешно создан и оплачен"
        )

    except HTTPException:
        # пробрасываем 403/400
        raise
    except Exception as e:
        logger.error(f"[PROMO ERROR][{ip}] Ошибка создания промокода для {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Внутренняя ошибка при создании промокода"}
        )

# Схема для активации
class PromoCodeActivate(BaseModel):
    promo_code: str = Field(..., min_length=1)


@router.post("/activate-promo-code", summary="Активация промокода")
async def activate_promo_code(
    promo_data:    PromoCodeActivate,
    request:       Request,
    current_user:  dict   = Depends(get_current_actor),
    db = Depends(get_database)
):
    ip = request.client.host
    user_id = current_user.get("id")
    user_role = current_user.get("role")

    logger.info(f"[PROMO ACT][{ip}] Пользователь {user_id} (role={user_role}) пытается активировать промокод '{promo_data.promo_code}'")

    # Только для обычных пользователей
    if user_role != "user":
        logger.warning(f"[PROMO ACT][{ip}] Отказ: роль {user_role} не может активировать промокоды")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут активировать промокоды"}
        )

    # Санитизация и нормализация кода
    code = promo_data.promo_code.strip().upper()
    if not code:
        logger.warning(f"[PROMO ACT][{ip}] Пустой промокод после очистки")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Промокод не может быть пустым"}
        )

    now = datetime.utcnow()

    # Проверяем существование промокода
    promo = await db.promo_codes.find_one({"code": code})
    if not promo:
        logger.info(f"[PROMO ACT][{ip}] Промокод '{code}' не найден")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Промокод не найден"}
        )

    # Проверяем, активен ли он
    if not promo.get("is_active", False):
        logger.info(f"[PROMO ACT][{ip}] Промокод '{code}' не активен")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Промокод недействителен или уже использован"}
        )

    # Проверяем срок действия
    expires_at = promo.get("expires_at")
    if expires_at and expires_at < now:
        # Выполняем обновление в транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db.promo_codes.update_one(
                    {"_id": promo["_id"]},
                    {"$set": {"is_active": False, "updated_at": now}},
                    session=session
                )
        logger.info(f"[PROMO ACT][{ip}] Срок промокода '{code}' истёк, деактивирован")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Срок действия промокода истек"}
        )

    # Специальные типы только для админов
    sub_type = promo.get("subscription_type", "").lower()
    if sub_type in ["demo", "school"]:
        logger.warning(f"[PROMO ACT][{ip}] Промокод '{code}' типа '{sub_type}' недоступен для user")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": f"Тип подписки '{sub_type}' не доступен для обычных пользователей"}
        )

    # Проверяем лимит использования
    usage_limit = promo.get("usage_limit", 1)
    usage_count = promo.get("usage_count", 0)
    if usage_count >= usage_limit:
        # деактивируем в транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db.promo_codes.update_one(
                    {"_id": promo["_id"]},
                    {"$set": {"is_active": False, "updated_at": now}},
                    session=session
                )
        logger.info(f"[PROMO ACT][{ip}] Промокод '{code}' превысил лимит использования ({usage_count}/{usage_limit})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Промокод уже использован максимальное количество раз"}
        )

    # Проверяем, не активировал ли пользователь уже
    used_by = promo.get("used_by", [])
    if str(user_id) in used_by:
        logger.info(f"[PROMO ACT][{ip}] Пользователь {user_id} уже использовал промокод '{code}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Вы уже активировали этот промокод ранее"}
        )

    # Нет ли у пользователя уже подписки?
    existing = await db.subscriptions.find_one({
        "user_id":   ObjectId(user_id),
        "is_active": True
    })
    if existing:
        logger.info(f"[PROMO ACT][{ip}] Пользователь {user_id} уже имеет активную подписку, невозможно активировать промокод")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "У вас уже есть активная подписка"}
        )

    try:
        # Параметры подписки
        duration_days = promo["duration_days"]
        new_expires = now + timedelta(days=duration_days)

        # Вставка подписки и обновление промокода в транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                # Вставка подписки
                sub_doc = {
                    "user_id":          ObjectId(user_id),
                    "iin":              current_user.get("iin"),
                    "created_at":       now,
                    "updated_at":       now,
                    "is_active":        True,
                    "cancelled_at":     None,
                    "amount":           promo.get("purchase_amount", 0),
                    "activation_method": "promocode",
                    "issued_by": {
                        "admin_iin": None,
                        "full_name": "Активация по промокоду"
                    },
                    "subscription_type": promo.get("subscription_type"),
                    "duration_days":     duration_days,
                    "expires_at":        new_expires,
                    "promo_code":        code
                }
                res = await db.subscriptions.insert_one(sub_doc, session=session)
                subscription_id = str(res.inserted_id)

                # Обновляем сам промокод
                used_by.append(str(user_id))
                is_active_now = (usage_count + 1) < usage_limit

                await db.promo_codes.update_one(
                    {"_id": promo["_id"]},
                    {
                        "$set": {
                            "updated_at": now,
                            "used_by":    used_by,
                            "is_active":  is_active_now
                        },
                        "$inc": {"usage_count": 1}
                    },
                    session=session
                )

        logger.info(f"[PROMO ACT][{ip}] Пользователь {user_id} активировал промокод '{code}', подписка {subscription_id}")

        return success(
            data={
                "subscription_id":    subscription_id,
                "subscription_type":  promo.get("subscription_type"),
                "duration_days":      duration_days,
                "expires_at":         new_expires.isoformat()
            },
            message="Промокод успешно активирован"
        )

    except HTTPException:
        # пропускаем контролируемые ошибки
        raise
    except Exception as e:
        logger.error(f"[PROMO ACT ERROR][{ip}] Ошибка при активации промокода '{code}' для {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Ошибка при активации промокода"}
        )

@router.get("/admin/promo-codes", summary="Получение списка промокодов (для админов)")
async def get_promo_codes(
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получение списка промокодов с возможностью фильтрации и пагинации.
    Доступно только для администраторов.
    """
    if current_user["role"] not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещен", "path": "/admin/promo-codes"}
        )
    
    # Формируем фильтр
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    
    # Получаем общее количество
    total = await db.promo_codes.count_documents(filter_query)
    
    # Получаем промокоды с пагинацией
    cursor = db.promo_codes.find(filter_query).sort("created_at", -1).skip(offset).limit(limit)
    promo_codes = []
    
    async for promo in cursor:
        # Преобразуем ObjectId в строки для JSON
        promo["_id"] = str(promo["_id"])
        if "created_by_user_id" in promo and promo["created_by_user_id"]:
            promo["created_by_user_id"] = str(promo["created_by_user_id"])
        
        # Преобразуем datetime в ISO формат
        for date_field in ["created_at", "updated_at", "expires_at"]:
            if date_field in promo and promo[date_field]:
                promo[date_field] = promo[date_field].isoformat()
        
        promo_codes.append(promo)
    
    return success(
        data={
            "promo_codes": promo_codes,
            "total": total,
            "limit": limit,
            "offset": offset
        },
        message=f"Получено {len(promo_codes)} промокодов"
    )

@router.get("/admin/promo-codes/{promo_id}", summary="Получение информации о промокоде (для админов)")
async def get_promo_code_details(
    promo_id: str,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получение детальной информации о промокоде по ID.
    Доступно только для администраторов.
    """
    if current_user["role"] not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещен", "path": f"/admin/promo-codes/{promo_id}"}
        )
    
    # Проверяем валидность ObjectId
    if not ObjectId.is_valid(promo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Некорректный ID промокода"}
        )
    
    # Получаем промокод из БД
    promo = await db.promo_codes.find_one({"_id": ObjectId(promo_id)})
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Промокод не найден"}
        )
    
    # Преобразуем ObjectId в строки для JSON
    promo["_id"] = str(promo["_id"])
    if "created_by_user_id" in promo and promo["created_by_user_id"]:
        promo["created_by_user_id"] = str(promo["created_by_user_id"])
    
    # Преобразуем datetime в ISO формат
    for date_field in ["created_at", "updated_at", "expires_at"]:
        if date_field in promo and promo[date_field]:
            promo[date_field] = promo[date_field].isoformat()
    
    # Получаем информацию о создателе, если есть
    if "created_by_user_id" in promo and promo["created_by_user_id"]:
        creator = await db.users.find_one({"_id": ObjectId(promo["created_by_user_id"])})
        if creator:
            promo["creator_info"] = {
                "full_name": creator.get("full_name", ""),
                "email": creator.get("email", ""),
                "iin": creator.get("iin", "")
            }
    
    # Получаем информацию о пользователях, использовавших промокод
    if "used_by" in promo and promo["used_by"]:
        used_by_info = []
        for user_id in promo["used_by"]:
            if ObjectId.is_valid(user_id):
                user = await db.users.find_one({"_id": ObjectId(user_id)})
                if user:
                    used_by_info.append({
                        "user_id": user_id,
                        "full_name": user.get("full_name", ""),
                        "email": user.get("email", ""),
                        "iin": user.get("iin", "")
                    })
        promo["used_by_info"] = used_by_info
    
    return success(
        data=promo,
        message="Информация о промокоде получена"
    )

@router.patch("/admin/promo-codes/{promo_id}", summary="Редактирование промокода (для админов)")
async def update_promo_code(
    promo_id: str,
    update_data: PromoCodeAdminUpdate,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Обновление параметров промокода.
    Доступно только для администраторов.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещен", "path": f"/admin/promo-codes/{promo_id}"}
        )
    
    # Проверяем валидность ObjectId
    if not ObjectId.is_valid(promo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Некорректный ID промокода"}
        )
    
    # Проверяем, существует ли промокод
    promo = await db.promo_codes.find_one({"_id": ObjectId(promo_id)})
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Промокод не найден"}
        )
    
    # Разрешенные поля для обновления
    allowed_fields = [
        "is_active", "expires_at", "usage_limit", 
        "subscription_type", "duration_days"
    ]
    
    # Фильтруем данные обновления
    update_fields = {}
    for field, value in update_data.dict().items():
        if field in allowed_fields:
            update_fields[field] = value
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Нет полей для обновления"}
        )
    
    # Добавляем дату обновления
    update_fields["updated_at"] = datetime.utcnow()
    
    try:
        # Обновляем промокод
        result = await db.promo_codes.update_one(
            {"_id": ObjectId(promo_id)},
            {"$set": update_fields}
        )
        
        if result.modified_count == 0:
            return success(
                data={"updated": False},
                message="Промокод не был изменен"
            )
        
        # Получаем обновленный промокод
        updated_promo = await db.promo_codes.find_one({"_id": ObjectId(promo_id)})
        
        # Преобразуем ObjectId в строки и datetime в ISO формат
        updated_promo["_id"] = str(updated_promo["_id"])
        if "created_by_user_id" in updated_promo and updated_promo["created_by_user_id"]:
            updated_promo["created_by_user_id"] = str(updated_promo["created_by_user_id"])
        
        for date_field in ["created_at", "updated_at", "expires_at"]:
            if date_field in updated_promo and updated_promo[date_field]:
                updated_promo[date_field] = updated_promo[date_field].isoformat()
        
        logger.info(f"[ADMIN] Промокод {promo_id} обновлен администратором {current_user['id']}")
        
        return success(
            data=updated_promo,
            message="Промокод успешно обновлен"
        )
        
    except Exception as e:
        logger.error(f"[ADMIN ERROR] Ошибка при обновлении промокода: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при обновлении промокода: {str(e)}"}
        )

@router.delete("/admin/promo-codes/{promo_id}", summary="Удаление промокода (для админов)")
async def delete_promo_code(
    promo_id: str,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Удаление промокода из системы.
    Доступно только для администраторов.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещен", "path": f"/admin/promo-codes/{promo_id}"}
        )
    
    # Проверяем валидность ObjectId
    if not ObjectId.is_valid(promo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Некорректный ID промокода"}
        )
    
    try:
        # Удаляем промокод
        result = await db.promo_codes.delete_one({"_id": ObjectId(promo_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Промокод не найден или уже удален"}
            )
        
        logger.info(f"[ADMIN] Промокод {promo_id} удален администратором {current_user['id']}")
        
        return success(
            data={"deleted": True, "promo_id": promo_id},
            message="Промокод успешно удален"
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        logger.error(f"[ADMIN ERROR] Ошибка при удалении промокода: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при удалении промокода: {str(e)}"}
        )

@router.post("/admin/generate-promo-code", summary="Создание промокода администратором")
async def admin_create_promo_code(
    promo_data: PromoCodeCreate,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Создание нового промокода администратором.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещен", "path": "/admin/generate-promo-code"}
        )
    
    try:
        now = datetime.utcnow()
        expires_at = promo_data.expires_at if promo_data.expires_at else now + timedelta(days=90)
        
        # Генерируем уникальный промокод
        promo_code = generate_promo_code()
        
        # Проверяем уникальность
        while await db.promo_codes.find_one({"code": promo_code}):
            promo_code = generate_promo_code()
        
        # Создаем промокод
        promo = {
            "code": promo_code,
            "subscription_type": promo_data.subscription_type,
            "duration_days": promo_data.duration_days,
            "is_active": True,
            "created_by_user_id": ObjectId(current_user["id"]),
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
            "usage_count": 0,
            "used_by": [],
            "usage_limit": promo_data.usage_limit,
            "purchase_amount": 0,  # Бесплатно, т.к. создан админом
            "created_by_admin": {
                "admin_id": ObjectId(current_user["id"]),
                "admin_iin": current_user["iin"],
                "admin_name": current_user["full_name"]
            }
        }
        
        result = await db.promo_codes.insert_one(promo)
        promo_id = str(result.inserted_id)
        
        logger.info(f"[ADMIN] Создан промокод {promo_code} администратором {current_user['id']}")
        
        return success(
            data={
                "promo_id": promo_id,
                "promo_code": promo_code,
                "subscription_type": promo_data.subscription_type,
                "duration_days": promo_data.duration_days,
                "expires_at": expires_at.isoformat(),
                "usage_limit": promo_data.usage_limit
            },
            message="Промокод успешно создан"
        )
        
    except Exception as e:
        logger.error(f"[ADMIN ERROR] Ошибка при создании промокода: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при создании промокода: {str(e)}"}
        )

@router.get("/my/promo-codes", summary="Получение списка промокодов пользователя")
async def get_user_promo_codes(
    request: Request,
    current_user: dict       = Depends(get_current_actor),
    db                      = Depends(get_database),
):
    """
    Получение списка всех промокодов, созданных или использованных текущим пользователем.
    """
    ip      = request.client.host
    user_id = current_user.get("id")
    role    = current_user.get("role")

    logger.info(f"[PROMO LIST][{ip}] Пользователь {user_id} (role={role}) запросил список своих промокодов")

    if role != "user":
        logger.warning(f"[PROMO LIST][{ip}] Отказ в доступе: роль {role} не может просматривать свои промокоды")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут просматривать свои промокоды"}
        )

    try:
        # Промокоды, созданные пользователем
        created = []
        cursor = db.promo_codes.find({"created_by_user_id": ObjectId(user_id)}).sort("created_at", -1)
        async for promo in cursor:
            promo_id = str(promo["_id"])
            created.append({
                "id":               promo_id,
                "code":             promo["code"],
                "subscription_type":promo["subscription_type"],
                "duration_days":    promo["duration_days"],
                "is_active":        promo.get("is_active", False),
                "expires_at":       promo.get("expires_at").isoformat() if promo.get("expires_at") else None,
                "created_at":       promo.get("created_at").isoformat() if promo.get("created_at") else None,
                "usage_count":      promo.get("usage_count", 0),
                "usage_limit":      promo.get("usage_limit", 1),
                "status":           "active" if promo.get("is_active", False) else "inactive",
                "used_by_info":     []  # см. ниже
            })

            # собираем информацию о юзерах, если есть
            used = promo.get("used_by", [])
            info = []
            for u in used:
                usr = await db.users.find_one({"_id": ObjectId(u)})
                if usr:
                    info.append({
                        "full_name": usr.get("full_name", ""),
                        "iin":       usr.get("iin", "")
                    })
            created[-1]["used_by_info"] = info

        # Промокоды, которыми пользователь воспользовался
        used_list = []
        subs = await db.subscriptions.find({
            "user_id":           ObjectId(user_id),
            "activation_method": "promocode"
        }).to_list(length=100)
        for sub in subs:
            code = sub.get("promo_code")
            promo = await db.promo_codes.find_one({"code": code})
            if not promo:
                continue
            promo_id    = str(promo["_id"])
            creator_id  = promo.get("created_by_user_id")
            creator_info = None
            if creator_id:
                cr = await db.users.find_one({"_id": ObjectId(creator_id)})
                if cr:
                    creator_info = {
                        "user_id":   str(cr["_id"]),
                        "full_name": cr.get("full_name", "")
                    }
            used_list.append({
                "id":                promo_id,
                "code":              code,
                "subscription_type": promo["subscription_type"],
                "duration_days":     promo["duration_days"],
                "created_at":        promo.get("created_at").isoformat() if promo.get("created_at") else None,
                "status":            "used",
                "creator_info":      creator_info,
                "activated_at":      sub.get("created_at").isoformat() if sub.get("created_at") else None,
                "subscription_id":   str(sub["_id"])
            })

        logger.info(f"[PROMO LIST][{ip}] Пользователь {user_id} получил {len(created)} созданных и {len(used_list)} использованных промокодов")

        return success(
            data={
                "created_promo_codes": created,
                "used_promo_codes":    used_list
            },
            message=f"Найдено {len(created)} созданных и {len(used_list)} использованных промокодов"
        )

    except HTTPException:
        # пробрасываем контролируемые ошибки
        raise
    except Exception as e:
        logger.error(f"[PROMO LIST ERROR][{ip}] Ошибка при получении промокодов для {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Внутренняя ошибка сервера при получении промокодов"}
        )

@router.get("/my/transactions", summary="Получение истории транзакций пользователя")
async def get_my_transactions(
    limit: int = 50,
    offset: int = 0,
    request: Request = None,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Возвращает историю транзакций пользователя с пагинацией.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только для пользователей", "path": "/my/transactions"}
        )
    
    user_id = current_user["id"]
    
    # Подсчитываем общее количество транзакций пользователя
    total = await db.transactions.count_documents({"user_id": ObjectId(user_id)})
    
    # Получаем транзакции с пагинацией
    cursor = db.transactions.find(
        {"user_id": ObjectId(user_id)}
    ).sort("created_at", -1).skip(offset).limit(limit)
    
    transactions = []
    async for txn in cursor:
        # Удаляем чувствительные данные и преобразуем ObjectId
        filtered_txn = {
            "amount": txn.get("amount", 0),
            "type": txn.get("type", ""),
            "description": txn.get("description", ""),
            "created_at": txn.get("created_at").isoformat() if txn.get("created_at") else None,
        }
        
        # Добавляем дополнительные поля при необходимости
        if txn.get("type") == "referral" and "referred_user_id" in txn:
            # Находим информацию о пользователе, которого пригласили
            referred_user = await db.users.find_one({"_id": ObjectId(txn["referred_user_id"])})
            if referred_user:
                filtered_txn["referred_user"] = {
                    "full_name": referred_user.get("full_name", "")
                }
        
        transactions.append(filtered_txn)
    
    logger.info(f"Получено {len(transactions)} транзакций для пользователя {user_id}")
    
    return success(
        data={
            "transactions": transactions,
            "total": total,
            "limit": limit,
            "offset": offset
        },
        message="История транзакций успешно получена"
    )