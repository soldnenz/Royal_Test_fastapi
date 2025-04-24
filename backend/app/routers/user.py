# app/routers/user.py

import logging
from typing import Optional, Literal
import secrets
import string
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Body
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

router = APIRouter()
logger = logging.getLogger(__name__)


from fastapi import HTTPException

@router.get("/me")
async def get_current_profile(actor = Depends(get_current_actor)):
    """
    actor["type"]  →  'user' | 'admin'
    actor["role"]  →  'user' | 'admin' | 'moder'
    """
    if actor["type"] == "user":
        profile = {
            "full_name": actor["full_name"],
            "email": actor["email"],
            "phone": actor["phone"],
            "iin": actor["iin"],
            "money": actor["money"],
        }

    elif actor["type"] == "admin":           # включает и модераторов
        profile = {
            "role": actor["role"],           # 'admin' ИЛИ 'moder'
            "full_name": actor["full_name"],
            "iin": actor["iin"],
        }

    else:
        raise HTTPException(
            status_code=403,
            detail={"message": "Unknown role", "hint": "Роль пользователя не распознана"}
        )

    return success(data=profile, message="Профиль получен")




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
    query: str = Query(..., description="ID, ИИН, email, телефон или ФИО"),
    current_user: dict = Depends(get_current_actor),
    db=Depends(get_database)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступ запрещён", "path": "/admin/search_users"}
        )

    query = query.strip()
    filters = []

    # Поиск по ObjectId, если подходит
    if ObjectId.is_valid(query):
        filters.append({"_id": ObjectId(query)})

    # Основные поля
    filters.extend([
        {"iin": query},
        {"email": query},
        {"phone": query},
        {"full_name": {"$regex": re.escape(query), "$options": "i"}}
    ])

    cursor = db.users.find({"$or": filters}).limit(50)
    results = []
    async for user in cursor:
        _id = user.pop("_id", None)
        if _id is not None:
            user["id"] = str(_id)
        # Преобразуем все значения типа datetime, если есть
        if "created_at" in user and isinstance(user["created_at"], datetime):
            user["created_at"] = user["created_at"].isoformat()
        results.append(user)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Пользователь не найден", "query": query}
        )

    return success(data=results, message=f"Найдено пользователей: {len(results)}")




# @router.patch("/me", response_model=UserOut)
# async def update_my_profile(
#     update_data: UserUpdate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Обновить профиль текущего пользователя (частично).
#     Можно поменять phone, email и т.д. (зависит от схемы UserUpdate).
#     """
#     update_fields = {}
#     if update_data.phone is not None:
#         update_fields["phone"] = update_data.phone
#     if update_data.email is not None:
#         update_fields["email"] = update_data.email
#
#     if not update_fields:
#         # Не было передано никаких полей для обновления
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="No fields to update"
#         )
#
#     # Обновляем в БД
#     result = await db.users.update_one(
#         {"_id": current_user["_id"]},
#         {"$set": update_fields}
#     )
#     if result.modified_count != 1:
#         logger.warning(f"User update failed or no changes: {current_user['_id']}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Update failed or no changes made"
#         )
#
#     # Получим обновлённый документ
#     updated_user = await db.users.find_one({"_id": current_user["_id"]})
#     return UserOut(
#         id=str(updated_user["_id"]),
#         iin=updated_user["iin"],
#         phone=updated_user["phone"],
#         email=updated_user["email"],
#         role=updated_user.get("role", "user"),
#         created_at=updated_user["created_at"]
#     )
#
#
# @router.get("/{user_id}", response_model=UserOut)
# async def get_user_by_id(
#     user_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Пример эндпоинта получения пользователя по ID.
#     Может быть ограничен только для admin.
#     """
#     # Допустим, проверим, что роль текущего юзера = admin
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only admin can get other user profiles"
#         )
#
#     # Проверяем корректность user_id (Mongo ObjectId)
#     if not ObjectId.is_valid(user_id):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid user_id"
#         )
#
#     user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
#     if not user_doc:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#
#     return UserOut(
#         id=str(user_doc["_id"]),
#         iin=user_doc["iin"],
#         phone=user_doc["phone"],
#         email=user_doc["email"],
#         role=user_doc.get("role", "user"),
#         created_at=user_doc["created_at"]
#     )
#
#
# @router.delete("/{user_id}")
# async def delete_user_by_id(
#     user_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Удалить пользователя по ID (например, только admin).
#     """
#     # Проверяем роль
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only admin can delete users"
#         )
#
#     if not ObjectId.is_valid(user_id):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid user_id"
#         )
#
#     result = await db.users.delete_one({"_id": ObjectId(user_id)})
#     if result.deleted_count != 1:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found or already deleted"
#         )
#
#     logger.info(f"User deleted by admin. user_id={user_id}")
#     return {"message": f"User {user_id} deleted successfully"}

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

class PurchaseSubscription(BaseModel):
    subscription_type: Literal["economy", "vip", "royal"]
    duration_days: int = Field(..., gt=0, le=365)
    use_balance: bool = True

@router.post("/purchase-subscription", summary="Покупка подписки для себя")
async def purchase_subscription(
    sub_data: PurchaseSubscription,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Пользователь покупает подписку для себя с баланса.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут покупать подписки", "path": "/purchase-subscription"}
        )
    
    user_id = current_user["id"]
    user_iin = current_user["iin"]
    
    # Получаем полные данные пользователя из БД (включая поля referred_by и referred_use)
    full_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Пользователь не найден"}
        )
    
    # Проверяем, есть ли уже активная подписка
    existing = await db.subscriptions.find_one({
        "user_id": ObjectId(user_id),
        "is_active": True
    })
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "У вас уже есть активная подписка"}
        )
    
    # Рассчитываем стоимость подписки
    price = calculate_subscription_price(sub_data.subscription_type, sub_data.duration_days)
    
    # Проверяем достаточность средств на балансе
    if current_user["money"] < price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Недостаточно средств на балансе. Требуется: {price} тг."}
        )
    
    try:
        now = datetime.utcnow()
        expires_at = now + timedelta(days=sub_data.duration_days)
        
        # Создаем подписку
        subscription = {
            "user_id": ObjectId(user_id),
            "iin": user_iin,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancel_reason": None,
            "amount": price,
            "activation_method": "payment",
            "issued_by": {
                "admin_iin": None,
                "full_name": "Самостоятельная покупка"
            },
            "subscription_type": sub_data.subscription_type,
            "duration_days": sub_data.duration_days,
            "expires_at": expires_at,
            "payment": {
                "payment_id": str(ObjectId()),
                "price": price,
                "payment_method": "balance"
            }
        }
        
        # Вставляем подписку в базу данных
        subscription_result = await db.subscriptions.insert_one(subscription)
        subscription_id = str(subscription_result.inserted_id)
        
        # Снимаем средства с баланса пользователя
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"money": -price}}
        )
        
        # Создаем транзакцию в истории платежей
        transaction = {
            "user_id": ObjectId(user_id),
            "amount": -price,
            "type": "subscription_purchase",
            "description": f"Покупка подписки {sub_data.subscription_type} на {sub_data.duration_days} дней",
            "created_at": now,
            "subscription_id": subscription_id
        }
        
        await db.transactions.insert_one(transaction)
        
        # Обработка реферальной системы через finance.process_referral
        description = f"Реферальный бонус за покупку подписки {sub_data.subscription_type}"
        process_referral(str(user_id), price, description)
        
        logger.info(f"[PURCHASE] Пользователь {user_id} купил подписку {sub_data.subscription_type} на {sub_data.duration_days} дней за {price} тг.")
        
        # Формируем ответ
        return success(
            data={
                "subscription_id": subscription_id,
                "subscription_type": sub_data.subscription_type,
                "duration_days": sub_data.duration_days,
                "expires_at": expires_at.isoformat(),
                "price": price,
                "balance_after": current_user["money"] - price
            },
            message="Подписка успешно приобретена"
        )
        
    except Exception as e:
        logger.error(f"[PURCHASE ERROR] Ошибка при покупке подписки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при покупке подписки: {str(e)}"}
        )

def calculate_subscription_price(subscription_type: str, duration_days: int) -> int:
    """
    Рассчитывает стоимость подписки на основе типа и продолжительности в днях.
    """
    base_prices = {
        "economy": 5000,
        "vip": 10000, 
        "royal": 15000
    }
    
    base_price = base_prices.get(subscription_type.lower(), 5000)
    
    # Convert days to months for calculation
    months = duration_days / 30
    
    # Применяем скидку в зависимости от продолжительности
    discount = 0
    if 80 <= duration_days <= 95:  # ~3 months
        discount = 0.05  # 5% скидка на 3 месяца
    elif 175 <= duration_days <= 185:  # ~6 months
        discount = 0.10  # 10% скидка на 6 месяцев
    
    # Рассчитываем общую цену с учетом скидки
    # Monthly price * number of months * (1 - discount)
    total_price = base_price * months * (1 - discount)
    
    return int(total_price)

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
        
        # Вставляем подписку в базу данных
        result = await db.subscriptions.insert_one(subscription)
        subscription_id = str(result.inserted_id)
        
        # Снимаем средства с баланса дарителя
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"money": -price}}
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
        
        await db.transactions.insert_one(transaction)
        
        # Обработка реферальной системы через finance.process_referral
        description = f"Реферальный бонус за покупку подарочной подписки {gift_data.subscription_type}"
        process_referral(str(user_id), price, description)
        
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
    promo_data: PromoCodeCreate,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Пользователь покупает подписку и получает промокод, который можно активировать позже.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут покупать промокоды", "path": "/generate-promo-code"}
        )
    
    # Рассчитываем стоимость подписки
    price = calculate_subscription_price(promo_data.subscription_type, promo_data.duration_days)
    
    # Проверяем достаточность средств
    if current_user["money"] < price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Недостаточно средств на балансе. Требуется: {price} тг."}
        )
    
    try:
        now = datetime.utcnow()
        
        # Срок действия промокода - 3 месяца от даты создания, если не указано иное
        expires_at = promo_data.expires_at if promo_data.expires_at else now + timedelta(days=90)  
        
        # Генерируем уникальный промокод, если он не был указан в запросе
        promo_code = promo_data.code if promo_data.code else generate_promo_code()
        
        # Проверяем, что такого промокода еще нет в системе
        existing_promo = await db.promo_codes.find_one({"code": promo_code})
        if existing_promo:
            # В реальном приложении здесь должна быть генерация нового кода
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Ошибка при генерации уникального промокода"}
            )
        
        # Создаем промокод в БД
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
            "purchase_amount": price
        }
        
        promo_result = await db.promo_codes.insert_one(promo)
        promo_id = str(promo_result.inserted_id)
        
        # Снимаем средства с баланса пользователя
        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            {"$inc": {"money": -price}}
        )
        
        # Создаем транзакцию
        transaction = {
            "user_id": ObjectId(current_user["id"]),
            "amount": -price,
            "type": "promo_code_purchase",
            "description": f"Покупка промокода на подписку {promo_data.subscription_type} на {promo_data.duration_days} дней",
            "created_at": now,
            "promo_code": promo_code
        }
        
        await db.transactions.insert_one(transaction)
        
        logger.info(f"[PROMO] Пользователь {current_user['id']} купил промокод {promo_code} за {price} тг.")
        
        return success(
            data={
                "promo_code": promo_code,
                "subscription_type": promo_data.subscription_type,
                "duration_days": promo_data.duration_days,
                "expires_at": expires_at.isoformat(),
                "price": price,
                "balance_after": current_user["money"] - price
            },
            message="Промокод успешно создан и оплачен"
        )
        
    except Exception as e:
        logger.error(f"[PROMO ERROR] Ошибка при создании промокода: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при создании промокода: {str(e)}"}
        )

@router.post("/activate-promo-code", summary="Активация промокода")
async def activate_promo_code(
    promo_data: PromoCodeActivate,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Пользователь активирует промокод для получения подписки.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут активировать промокоды", "path": "/activate-promo-code"}
        )
    
    user_id = current_user["id"]
    user_iin = current_user["iin"]
    
    # Проверяем, существует ли промокод
    promo = await db.promo_codes.find_one({"code": promo_data.promo_code.strip().upper()})
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Промокод не найден"}
        )
    
    # Проверяем, активен ли промокод
    if not promo["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Промокод недействителен или уже использован"}
        )
    
    # Проверяем, не истек ли срок действия промокода
    now = datetime.utcnow()
    if promo["expires_at"] < now:
        # Деактивируем промокод
        await db.promo_codes.update_one(
            {"_id": promo["_id"]},
            {"$set": {"is_active": False, "updated_at": now}}
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Срок действия промокода истек"}
        )
    
    # Проверяем тип подписки - demo и school только для админов
    subscription_type = promo["subscription_type"].lower()
    if subscription_type in ["demo", "school"] and current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail={"message": f"Тип подписки '{subscription_type}' не доступен для обычных пользователей"}
        )
    
    # Проверяем, не превышен ли лимит использований
    if promo["usage_count"] >= promo.get("usage_limit", 1):
        # Деактивируем промокод
        await db.promo_codes.update_one(
            {"_id": promo["_id"]},
            {"$set": {"is_active": False, "updated_at": now}}
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Промокод уже использован максимальное количество раз"}
        )
    
    # Проверяем, не использовал ли этот пользователь уже этот промокод
    used_by = promo.get("used_by", [])
    if str(user_id) in used_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Вы уже активировали этот промокод ранее"}
        )
    
    # Проверяем, нет ли у пользователя уже активной подписки
    existing = await db.subscriptions.find_one({
        "user_id": ObjectId(user_id),
        "is_active": True
    })
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "У вас уже есть активная подписка"}
        )
    
    try:
        # Определяем параметры подписки из промокода
        subscription_type = promo["subscription_type"]
        duration_days = promo["duration_days"]
        expires_at = now + timedelta(days=duration_days)
        
        # Создаем подписку
        subscription = {
            "user_id": ObjectId(user_id),
            "iin": user_iin,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancel_reason": None,
            "amount": promo.get("purchase_amount", 0),
            "activation_method": "promocode",
            "issued_by": {
                "admin_iin": None,
                "full_name": "Активация по промокоду"
            },
            "subscription_type": subscription_type,
            "duration_days": duration_days,
            "expires_at": expires_at,
            "promo_code": promo_data.promo_code
        }
        
        # Вставляем подписку в базу данных
        result = await db.subscriptions.insert_one(subscription)
        subscription_id = str(result.inserted_id)
        
        # Обновляем данные промокода
        used_by.append(str(user_id))
        
        # Деактивируем промокод, если достигнут лимит использования
        is_still_active = (promo["usage_count"] + 1) < promo.get("usage_limit", 1)
        
        await db.promo_codes.update_one(
            {"_id": promo["_id"]},
            {"$set": {
                "updated_at": now,
                "used_by": used_by,
                "is_active": is_still_active
            },
            "$inc": {"usage_count": 1}}
        )
        
        logger.info(f"[PROMO ACTIVATION] Пользователь {user_id} активировал промокод {promo_data.promo_code}")
        
        return success(
            data={
                "subscription_id": subscription_id,
                "subscription_type": subscription_type,
                "duration_days": duration_days,
                "expires_at": expires_at.isoformat()
            },
            message="Промокод успешно активирован"
        )
        
    except Exception as e:
        logger.error(f"[PROMO ACTIVATION ERROR] Ошибка при активации промокода: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"Ошибка при активации промокода: {str(e)}"}
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
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получение списка всех промокодов, созданных или использованных текущим пользователем.
    """
    if current_user["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Только пользователи могут просматривать свои промокоды", "path": "/my/promo-codes"}
        )
    
    user_id = current_user["id"]
    
    # Находим все промокоды, созданные пользователем
    created_promo_codes_cursor = db.promo_codes.find({
        "created_by_user_id": ObjectId(user_id)
    }).sort("created_at", -1)
    
    created_promo_codes = []
    async for promo in created_promo_codes_cursor:
        # Форматируем даты
        promo["_id"] = str(promo["_id"])
        if "created_at" in promo:
            promo["created_at"] = promo["created_at"].isoformat()
        if "updated_at" in promo:
            promo["updated_at"] = promo["updated_at"].isoformat()
        if "expires_at" in promo:
            promo["expires_at"] = promo["expires_at"].isoformat()
        
        # Добавляем информацию о пользователях, использовавших промокод
        if "used_by" in promo and promo["used_by"]:
            used_by_info = []
            for used_user_id in promo["used_by"]:
                user = await db.users.find_one({"_id": ObjectId(used_user_id)})
                if user:
                    used_by_info.append({
                        "full_name": user.get("full_name", ""),
                        "iin": user.get("iin", "")
                    })
            promo["used_by_info"] = used_by_info
        
        created_promo_codes.append({
            "code": promo["code"],
            "subscription_type": promo["subscription_type"],
            "duration_days": promo["duration_days"],
            "is_active": promo["is_active"],
            "expires_at": promo["expires_at"],
            "created_at": promo["created_at"],
            "usage_count": promo.get("usage_count", 0),
            "usage_limit": promo.get("usage_limit", 1),
            "status": "active" if promo["is_active"] else "inactive",
            "used_by_info": promo.get("used_by_info", [])
        })
    
    # Находим все промокоды, использованные пользователем
    used_promo_codes = []
    # Сначала находим подписки, созданные через промокоды
    promo_subscriptions = await db.subscriptions.find({
        "user_id": ObjectId(user_id),
        "activation_method": "promocode"
    }).to_list(length=100)
    
    # Собираем коды из этих подписок
    for sub in promo_subscriptions:
        if "promo_code" in sub and sub["promo_code"]:
            promo = await db.promo_codes.find_one({"code": sub["promo_code"]})
            if promo:
                # Форматируем даты
                promo["_id"] = str(promo["_id"])
                if "created_at" in promo:
                    promo["created_at"] = promo["created_at"].isoformat()
                if "expires_at" in promo:
                    promo["expires_at"] = promo["expires_at"].isoformat()
                
                # Добавляем информацию о создателе
                creator_info = None
                if "created_by_user_id" in promo and promo["created_by_user_id"]:
                    creator = await db.users.find_one({"_id": ObjectId(promo["created_by_user_id"])})
                    if creator:
                        creator_info = {
                            "user_id": str(creator["_id"]),
                            "full_name": creator.get("full_name", "")
                        }
                
                used_promo_codes.append({
                    "id": promo["_id"],
                    "code": promo["code"],
                    "subscription_type": promo["subscription_type"],
                    "duration_days": promo["duration_days"],
                    "created_at": promo["created_at"],
                    "status": "used",
                    "creator_info": creator_info,
                    "activated_at": sub.get("created_at", "").isoformat() if isinstance(sub.get("created_at"), datetime) else None,
                    "subscription_id": str(sub["_id"])
                })
    
    return success(
        data={
            "created_promo_codes": created_promo_codes,
            "used_promo_codes": used_promo_codes
        },
        message=f"Найдено {len(created_promo_codes)} созданных и {len(used_promo_codes)} использованных промокодов"
    )
