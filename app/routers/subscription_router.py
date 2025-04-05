from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from app.schemas.subscription_schemas import (
    SubscriptionCreate, SubscriptionOut, SubscriptionCancel
)
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import logging



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
        raise HTTPException(status_code=403, detail="Только администратор может создавать подписки")

    if not ObjectId.is_valid(payload.user_id):
        raise HTTPException(status_code=400, detail="Некорректный user_id")

    user_object_id = ObjectId(payload.user_id)

    user = await db.users.find_one({
        "_id": user_object_id,
        "iin": payload.iin
    })

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден по user_id и IIN")

    existing = await db.subscriptions.find_one({"user_id": user_object_id, "is_active": True})
    if existing:
        raise HTTPException(status_code=409, detail="У пользователя уже есть активная подписка")

    now = datetime.utcnow()

    subscription = payload.dict()
    subscription.update({
        "user_id": user_object_id,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "cancelled_at": None,
        "cancelled_by": None,
        "cancel_reason": None,
        "issued_by": {
            "admin_iin": current_user["iin"],
            "full_name": current_user["full_name"]
        }
    })

    try:
        result = await db.subscriptions.insert_one(subscription)
        logger.info(f"[CREATE] Подписка создана: {result.inserted_id} для user_id={payload.user_id} админом {current_user['iin']}")
        subscription["_id"] = str(result.inserted_id)
        subscription["user_id"] = str(subscription["user_id"])
        return JSONResponse(content=jsonable_encoder(subscription))
    except Exception as e:
        logger.error(f"[CREATE ERROR] Ошибка при создании подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании подписки")

@router.put("/cancel", response_model=dict)
async def cancel_subscription(
    data: SubscriptionCancel,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Только администратор может отменить подписку")

    try:
        subscription = await db.subscriptions.find_one({"_id": ObjectId(data.subscription_id)})
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")

        if subscription["is_active"] is False:
            raise HTTPException(status_code=409, detail="Подписка уже отменена или не активна")

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
        return {"message": "Подписка отменена"}
    except Exception as e:
        logger.error(f"[CANCEL ERROR] Ошибка при отмене подписки: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка: {e}")


# 🔍 Получение подписки по user_id (включая неактивную)
@router.get("/user/{user_id}", response_model=SubscriptionOut)
async def get_subscription_by_user_id(
    user_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    try:
        user_oid = ObjectId(user_id)

        # 📅 Проверяем активные и неактивные подписки, но учитываем срок действия
        subscription = await db.subscriptions.find_one(
            {"user_id": user_oid},
            sort=[("created_at", -1)]
        )
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")

        # Проверка, истекла ли подписка
        if subscription["expires_at"] < datetime.utcnow() and subscription["is_active"]:
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
            subscription["cancel_reason"] = "Истек срок действия"
            subscription["cancelled_by"] = "system"
            subscription["cancelled_at"] = datetime.utcnow()

        subscription["_id"] = str(subscription["_id"])
        subscription["user_id"] = str(subscription["user_id"])
        return JSONResponse(content=jsonable_encoder(subscription))
    except Exception as e:
        logger.error(f"[GET BY USER_ID ERROR] {e}")
        raise HTTPException(status_code=400, detail=str(e))