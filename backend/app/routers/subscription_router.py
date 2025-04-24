from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from app.schemas.subscription_schemas import (
    SubscriptionCreate, SubscriptionOut, SubscriptionCancel, IssuedBy
)
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import logging
from app.core.finance import process_referral
from pymongo import ReturnDocument
from app.core.response import success

router = APIRouter()
logger = logging.getLogger(__name__)

# 🎯 Создание подписки
@router.post("/", response_model=SubscriptionOut)
async def create_subscription(
    payload: SubscriptionCreate,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может создавать подписки"}
        )

    if not ObjectId.is_valid(payload.user_id):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )

    user_object_id = ObjectId(payload.user_id)

    user = await db.users.find_one({
        "_id": user_object_id,
        "iin": payload.iin
    })

    if not user:
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден по user_id и IIN"}
        )

    existing = await db.subscriptions.find_one({"user_id": user_object_id, "is_active": True})
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"message": "У пользователя уже есть активная подписка"}
        )

    # Новое поле для суммы
    amount = payload.amount

    try:
        # Инициализация переменной referral
        referral = None
        referral_used = False
        description = None

        # Проверка на наличие активной реферальной ссылки
        if payload.use_referral:
            if user.get("referred_by") and not user.get("referred_use"):
                # Уведомление админа о наличии активной реферальной ссылки
                logger.info(f"У пользователя есть активная реферальная ссылка: {user['referred_by']}")

                # Подготовка деталей реферала
                referral = await db.referrals.find_one({"code": user["referred_by"]})
                if referral:
                    referral_amount = round(amount * (referral["rate"]["value"] / 100), 2)
                    description = (f"Админ {current_user['full_name']} активировал вручную подписку пользователю {payload.user_id} "
                                   f"с типом {payload.subscription_type} на {payload.duration_days} дней и ввёл сумму {amount}. "
                                   f"У пользователя была рефералка {user['referred_by']} с процентом {referral['rate']['value']}%, "
                                   f"и после вычислений на аккаунт реферала {referral['owner_user_id']} начислено {referral_amount} тенге.")
                    referral_used = True

        # Если рефералка использована, обработать реферал
        if referral_used:
            await process_referral(
                str(user_object_id),
                amount,
                description
            )
            user["referred_use"] = True
            await db.users.find_one_and_update(
                {"_id": user_object_id},
                {"$set": {"referred_use": True}},
                return_document=ReturnDocument.AFTER
            )

        now = datetime.utcnow()

        # Создание словаря с нужными полями
        subscription = {
            "user_id": user_object_id,
            "iin": payload.iin,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancel_reason": None,
            "amount": amount,
            "activation_method": "manual",
            "issued_by": IssuedBy(
                admin_iin=current_user["iin"],
                full_name=current_user["full_name"]
            ).dict(),
            "subscription_type": payload.subscription_type,
            "duration_days": payload.duration_days,
            "expires_at": payload.expires_at,
            "referred_by": user.get("referred_by") if user.get("referred_use") else None
        }

        result = await db.subscriptions.insert_one(subscription)
        logger.info(f"[CREATE] Подписка создана: {result.inserted_id} для user_id={payload.user_id} админом {current_user['iin']}")

        subscription["_id"] = str(result.inserted_id)
        subscription["user_id"] = str(subscription["user_id"])

        # Обновление ответа с информацией о рефералке
        response_data = jsonable_encoder(subscription)
        response_data["referral_used"] = referral_used

        return success(data=response_data)

    except Exception as e:
        logger.error(f"[CREATE ERROR] Ошибка при создании подписки: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка при создании подписки {e}"}
        )


@router.put("/cancel", response_model=dict)
async def cancel_subscription(
    data: SubscriptionCancel,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может отменить подписку"}
        )

    try:
        subscription = await db.subscriptions.find_one({"_id": ObjectId(data.subscription_id)})
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail={"message": "Подписка не найдена"}
            )

        if subscription["is_active"] is False:
            raise HTTPException(
                status_code=409,
                detail={"message": "Подписка уже отменена или не активна"}
            )

        await db.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "is_active": False,
                    "cancelled_at": datetime.utcnow(),
                    "cancelled_by": current_user["iin"],
                    "cancel_reason": data.cancel_reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"[CANCEL] Подписка отменена: {data.subscription_id} админом {current_user['iin']}")
        return success(data={"message": "Подписка отменена"})

    except Exception as e:
        logger.error(f"[CANCEL ERROR] Ошибка при отмене подписки: {e}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при отмене подписки", "hint": str(e)}
        )


# 🔍 Получение подписки по user_id (включая неактивную)
@router.get("/user/{user_id}", response_model=SubscriptionOut)
async def get_subscription_by_user_id(
    user_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )

    try:
        user_oid = ObjectId(user_id)

        subscription = await db.subscriptions.find_one(
            {"user_id": user_oid},
            sort=[("created_at", -1)]
        )
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail={"message": "Подписка не найдена"}
            )

        # Проверяем срок действия и статус
        if subscription.get("expires_at") and subscription["expires_at"] < datetime.utcnow() and subscription["is_active"]:
            await db.subscriptions.update_one(
                {"_id": subscription["_id"]},
                {
                    "$set": {
                        "is_active": False,
                        "cancelled_at": datetime.utcnow(),
                        "cancelled_by": "system",
                        "cancel_reason": "Истек срок действия",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            subscription["is_active"] = False
            subscription["cancelled_by"] = "system"
            subscription["cancel_reason"] = "Истек срок действия"
            subscription["cancelled_at"] = datetime.utcnow()

        subscription["_id"] = str(subscription["_id"])
        subscription["user_id"] = str(subscription["user_id"])
        return success(data=jsonable_encoder(subscription))

    except Exception as e:
        logger.error(f"[GET BY USER_ID ERROR] {e}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при получении подписки", "hint": str(e)}
        )