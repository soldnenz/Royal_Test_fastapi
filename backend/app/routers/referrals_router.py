from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.db.database import db
from app.admin.permissions import get_current_admin_user
from app.core.response import success
from app.core.security import get_current_actor
from app.schemas.referral_schemas import Referral, ReferralSearchParams, ReferralCreate, ReferralCreateUser, ReferralUpdateAdmin
from app.models.referral_model import Referral as ReferralModel
import random
from app.core.config import settings
from app.core.finance import process_referral



router = APIRouter()

# Логирование
logger = logging.getLogger(__name__)


@router.post("/", summary="Создать реферальный код (пользователь)")
async def create_referral_user(data: ReferralCreateUser, request: Request, current_user=Depends(get_current_actor)):
    # Только обычные пользователи могут создавать реферальный код через этот маршрут
    user_role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)
    if user_role != "user":
        logger.warning(
            f"[REFERRAL_CREATE][{request.client.host}] Попытка создания кода не пользователем (role={user_role})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"message": "Только пользователи могут создавать реферальные коды"})

    owner_id_str = str(current_user["id"]) if isinstance(current_user, dict) else str(
        getattr(current_user, "id", "") or getattr(current_user, "_id", ""))
    # Проверка наличия активной подписки (economy, vip или royal)
    subscription = await db.subscriptions.find_one({
        "user_id": ObjectId(owner_id_str),
        "is_active": True,
        "subscription_type": {"$in": ["economy", "vip", "royal"]}
    })
    if not subscription:
        logger.warning(f"[REFERRAL_CREATE][{request.client.host}] Попытка создания кода без подписки (user_id={owner_id_str})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Система реферальных ссылок недоступна. Для создания реферального кода вам нужно иметь активный Economy, VIP или Royal подписку."})
    existing = await db.referrals.find_one({"owner_user_id": owner_id_str, "active": True})
    if existing:
        logger.info(f"[REFERRAL_CREATE][{request.client.host}] У пользователя уже есть код (user_id={owner_id_str})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"message": "У вас уже есть активный реферальный код"})

    # Генерация уникального 8-значного кода
    code = str(random.randint(10000000, 99999999))
    while await db.referrals.find_one({"code": code}):
        code = str(random.randint(10000000, 99999999))

    referral_doc = {
        "code": code,
        "type": "user",  # принудительно для пользователей
        "owner_user_id": owner_id_str,
        "rate": {"type": "percent", "value": settings.DEFAULT_REFERRAL_RATE},
        "description": data.description,
        "active": True,
        "comment": None,
        "created_by": current_user["full_name"] if isinstance(current_user,
                                                              dict) and "full_name" in current_user else getattr(
            current_user, "full_name", "Пользователь"),
        "created_at": datetime.utcnow()
    }
    
    # Выполняем в Mongo-транзакции
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.referrals.insert_one(referral_doc, session=session)
            
    logger.info(
        f"[REFERRAL_CREATE][{request.client.host}] Создан реферальный код {code} для пользователя {owner_id_str}")
    response_data = {
        "code": code,
        "rate": referral_doc["rate"],
        "created_at": referral_doc["created_at"].isoformat()
    }
    return success(data=response_data)

@router.post("/admin", summary="Создать реферальный код (админ)")
async def create_referral_admin(data: ReferralCreate, request: Request, current_admin = Depends(get_current_admin_user)):
    # Проверяем, существует ли пользователь-владелец с данным ID
    try:
        owner_oid = ObjectId(data.owner_user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Неверный формат ID пользователя"})
    owner = await db.users.find_one({"_id": owner_oid})
    if not owner:
        logger.warning(f"[REFERRAL_CREATE_ADMIN][{request.client.host}] Пользователь не найден (owner_id={data.owner_user_id})")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Пользователь с данным ID не найден"})
    # Проверяем, нет ли уже активного кода этого типа у данного пользователя
    existing_ref = await db.referrals.find_one({"owner_user_id": data.owner_user_id, "type": data.type, "active": True})
    if existing_ref:
        logger.warning(f"[REFERRAL_CREATE_ADMIN][{request.client.host}] У пользователя {data.owner_user_id} уже есть активный код типа {data.type}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "У пользователя уже есть активный код данного типа"})
    # Если код не задан, генерируем (8-значный)
    code = data.code
    if not code:
        code = str(random.randint(10000000, 99999999))
        while await db.referrals.find_one({"code": code}):
            code = str(random.randint(10000000, 99999999))
    else:
        # Проверяем уникальность указанного кода
        existing_code = await db.referrals.find_one({"code": code})
        if existing_code:
            logger.warning(f"[REFERRAL_CREATE_ADMIN][{request.client.host}] Код уже используется: {code}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Указанный код уже используется"})
    # Используем ставку по умолчанию, если не задана явно
    rate = data.rate.model_dump() if data.rate else (settings.DEFAULT_REFERRAL_RATE if hasattr(settings, "DEFAULT_REFERRAL_RATE") else DEFAULT_REFERRAL_RATE)
    # Определяем, кто создал (имя или идентификатор администратора)
    created_by = None
    if isinstance(current_admin, dict):
        created_by = current_admin.get("full_name") or current_admin.get("email") or current_admin.get("iin")
    else:
        created_by = getattr(current_admin, "full_name", None) or getattr(current_admin, "email", None) or getattr(current_admin, "iin", None)
    if not created_by:
        created_by = "Администратор"
    # Формируем документ реферального кода
    referral_doc = {
        "code": code,
        "type": data.type,
        "owner_user_id": data.owner_user_id,
        "rate": rate,
        "description": data.description.strip() if data.description else "",
        "active": True,
        "comment": data.comment.strip() if data.comment else None,
        "created_by": created_by,
        "created_at": datetime.utcnow()
    }
    
    # Выполняем в Mongo-транзакции
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            result = await db.referrals.insert_one(referral_doc, session=session)
            
    logger.info(f"[REFERRAL_CREATE_ADMIN][{request.client.host}] Админ {created_by} создал код {code} для пользователя {data.owner_user_id}")
    # Готовим данные для ответа (все поля созданной записи)
    referral_doc["id"] = str(result.inserted_id)
    referral_doc["_id"] = str(result.inserted_id)
    if isinstance(referral_doc["created_at"], datetime):
        referral_doc["created_at"] = referral_doc["created_at"].isoformat()
    return success(data=referral_doc)

@router.get("/my", summary="Получить свой реферальный код (пользователь)")
async def get_my_referral(request: Request, current_user = Depends(get_current_actor)):
    # Только пользователь (не админ) имеет собственный реферальный код
    role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)
    if role != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "У администратора нет персонального реферального кода"})
    owner_id_str = str(current_user["id"]) if isinstance(current_user, dict) else str(getattr(current_user, "id", "") or getattr(current_user, "_id", ""))
    referral = await db.referrals.find_one({"owner_user_id": owner_id_str, "active": True})
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "У вас нет реферального кода"})
    # Формируем ответ с нужными полями
    response_data = {
        "code": referral["code"],
           "rate": referral["rate"],
        "created_at": referral["created_at"].isoformat() if isinstance(referral["created_at"], datetime) else str(referral["created_at"])
    }
    return success(data=response_data)

@router.get("/transactions", summary="Получить данные по реферальным транзакциям")
async def get_referral_transactions(
    request: Request,
    current_user=Depends(get_current_actor),
):
    """
    Получение информации о пользователях, зарегистрировавшихся по реферальному коду
    текущего пользователя, включая статистику по заработку и платежам.
    """
    # Только для обычных пользователей
    if current_user.get("role") != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Доступно только для пользователей"}
        )

    user_id_str = str(current_user["id"])

    # Ищем активный реферальный код
    referral = await db.referrals.find_one({
        "owner_user_id": user_id_str,
        "active": True
    })
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "У вас нет активного реферального кода"}
        )
    referral_code = referral["code"]

    # Пользователи, зарегистрировавшиеся по коду
    referred_users = await db.users.find(
        {"referred_by": referral_code}
    ).to_list(length=1000)

    # Список ObjectId этих пользователей
    referred_ids = [u["_id"] for u in referred_users]

    # Транзакции типа "referral" именно для этих пользователей
    transactions = await db.transactions.find({
        "type": "referral",
        "referred_user_id": {"$in": referred_ids}
    }).sort("created_at", -1).to_list(length=1000)

    # Общие метрики
    total_earned    = sum(tx.get("amount", 0) for tx in transactions)
    total_registered= len(referred_users)
    total_purchased = sum(1 for u in referred_users if u.get("referred_use", False))

    # Формируем детальный список
    result_transactions = []
    for user in referred_users:
        uid = str(user["_id"])
        # Все транзакции, где referred_user_id == uid
        user_tx = [
            tx for tx in transactions
            if str(tx.get("referred_user_id")) == uid
        ]

        amount  = None
        tx_date = None
        if user_tx:
            best   = max(user_tx, key=lambda t: t.get("amount", 0))
            amount = best.get("amount")
            tx_date = best.get("created_at")

        reg_date = user.get("created_at")
        result_transactions.append({
            "id":                 uid,
            "user_iin":           user.get("iin", ""),
            "user_name":          user.get("full_name", ""),
            "registration_date":  (
                reg_date.isoformat()
                if isinstance(reg_date, datetime)
                else str(reg_date)
            ),
            "has_purchased":      user.get("referred_use", False),
            "amount":             amount,
            "transaction_date":   (
                tx_date.isoformat()
                if isinstance(tx_date, datetime)
                else (str(tx_date) if tx_date is not None else None)
            )
        })

    # Сортируем: сначала с транзакцией, потом по дате
    result_transactions.sort(
        key=lambda x: (
            x["transaction_date"] is not None,
            x["transaction_date"] or x["registration_date"]
        ),
        reverse=True
    )

    return success(
        data={
            "transactions":     result_transactions,
            "totalEarned":      total_earned,
            "totalRegistered":  total_registered,
            "totalPurchased":   total_purchased
        },
        message="Данные по реферальным транзакциям получены"
    )

@router.get("/", summary="Получить список реферальных кодов (админ/модератор)")
async def list_referrals(
    code: Optional[str] = None,
    type: Optional[str] = None,
    active: Optional[bool] = None,
    owner_user_id: Optional[str] = None,
    current_admin = Depends(get_current_admin_user)
):
    # Формируем фильтр на основе переданных параметров
    query = {}
    if code:
        # Проверяем наличие недопустимых символов в коде фильтра
        forbidden_chars = ['$', '{', '}', '<', '>', '|', '&', '*', '?', '^']
        if any(ch in code for ch in forbidden_chars):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Недопустимые символы в параметре code"})
        query["code"] = code
    if type:
        query["type"] = type
    if active is not None:
        query["active"] = active
    if owner_user_id:
        query["owner_user_id"] = owner_user_id
    # Выполняем поиск в базе данных по сформированному фильтру
    cursor = db.referrals.find(query)
    referrals_list = await cursor.to_list(length=None)
    # Преобразуем ObjectId и datetime для каждого результата перед возвратом
    for ref in referrals_list:
        ref["id"] = str(ref["_id"])
        ref["_id"] = str(ref["_id"])
        if isinstance(ref.get("created_at"), datetime):
            ref["created_at"] = ref["created_at"].isoformat()
    return success(data=referrals_list)

@router.delete("/{referral_id}", summary="Деактивировать реферальный код")
async def deactivate_referral(referral_id: str, request: Request, current_actor = Depends(get_current_actor)):
    # Преобразуем идентификатор в ObjectId и находим реферальный код
    try:
        oid = ObjectId(referral_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Некорректный ID реферального кода"})
    referral = await db.referrals.find_one({"_id": oid})
    if not referral:
        logger.warning(f"[REFERRAL_DEACTIVATE][{request.client.host}] Код не найден (id={referral_id})")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Реферальный код не найден"})
    # Проверка прав: пользователь может деактивировать только свой собственный код
    actor_role = current_actor.get("role") if isinstance(current_actor, dict) else getattr(current_actor, "role", None)
    owner_id_str = referral.get("owner_user_id")
    if actor_role == "user":
        curr_user_id_str = str(current_actor["_id"]) if isinstance(current_actor, dict) else str(getattr(current_actor, "id", "") or getattr(current_actor, "_id", ""))
        if owner_id_str != curr_user_id_str:
            logger.warning(f"[REFERRAL_DEACTIVATE][{request.client.host}] Чужой код (user_id={curr_user_id_str}, owner_id={owner_id_str})")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Нельзя деактивировать чужой реферальный код"})
    # Если код уже не активен, нельзя деактивировать его повторно
    if not referral.get("active", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Реферальный код уже деактивирован"})
    
    # Выполняем деактивацию в Mongo-транзакции
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.referrals.update_one(
                {"_id": oid}, 
                {"$set": {"active": False}},
                session=session
            )
            
    logger.info(f"[REFERRAL_DEACTIVATE][{request.client.host}] Код деактивирован (code={referral['code']}, owner={owner_id_str})")
    return success(message="Реферальный код деактивирован")

@router.patch("/{referral_id}", summary="Обновить реферальный код (админ)")
async def update_referral(referral_id: str, data: ReferralUpdateAdmin, request: Request, current_admin = Depends(get_current_admin_user)):
    # Ищем существующую запись реферального кода по ID
    try:
        oid = ObjectId(referral_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Некорректный ID реферального кода"})
    referral = await db.referrals.find_one({"_id": oid})
    if not referral:
        logger.warning(f"[REFERRAL_UPDATE][{request.client.host}] Код не найден (id={referral_id})")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Реферальный код не найден"})
    # Проверяем конфликт: у нового владельца не должно быть другого активного кода этого же типа
    new_owner_for_check = data.owner_user_id or referral.get("owner_user_id")
    new_type_for_check = data.type or referral.get("type")
    if data.owner_user_id is not None or data.type is not None:
        conflict_ref = await db.referrals.find_one({"owner_user_id": new_owner_for_check, "type": new_type_for_check, "active": True, "_id": {"$ne": oid}})
        if conflict_ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "У указанного пользователя уже есть активный код данного типа"})
    updates = {}
    # Формируем словарь изменений на основании входных данных
    if data.code is not None:
        # Проверяем уникальность нового кода
        existing_code = await db.referrals.find_one({"code": data.code, "_id": {"$ne": oid}})
        if existing_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Указанный код уже используется"})
        updates["code"] = data.code
    if data.type is not None:
        updates["type"] = data.type
    if data.owner_user_id is not None:
        # Проверяем, что новый владелец существует
        try:
            new_owner_oid = ObjectId(data.owner_user_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Неверный формат ID пользователя"})
        new_owner = await db.users.find_one({"_id": new_owner_oid})
        if not new_owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Пользователь с данным ID не найден"})
        updates["owner_user_id"] = data.owner_user_id
    if data.rate is not None:
        updates["rate"] = data.rate.model_dump()
    if data.description is not None:
        updates["description"] = data.description.strip() if data.description is not None else ""
    if data.active is not None:
        updates["active"] = data.active
    if data.comment is not None:
        updates["comment"] = data.comment.strip() if data.comment is not None else None
    if not updates:
        # Нет данных для обновления
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Нет данных для обновления"})
    
    # Применяем обновления в базе данных в транзакции
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.referrals.update_one(
                {"_id": oid}, 
                {"$set": updates},
                session=session
            )
            
    # Получаем обновлённый документ из базы
    updated = await db.referrals.find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Реферальный код не найден"})
    # Подготавливаем данные обновлённой записи для вывода
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    if isinstance(updated.get("created_at"), datetime):
        updated["created_at"] = updated["created_at"].isoformat()
    logger.info(f"[REFERRAL_UPDATE][{request.client.host}] Код обновлён (id={referral_id})")
    return success(data=updated)
