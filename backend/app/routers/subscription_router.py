from fastapi import APIRouter, Depends, HTTPException, status, Request
from bson import ObjectId
from datetime import datetime
from app.schemas.subscription_schemas import (
    SubscriptionCreate, SubscriptionOut, SubscriptionCancel, IssuedBy,
    SubscriptionUpdate
)
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.logging import get_logger, LogSection, LogSubsection
from app.core.finance import process_referral
from pymongo import ReturnDocument
from app.core.response import success
from app.rate_limit import rate_limit_ip

router = APIRouter()
logger = get_logger(__name__)

# 🎯 Создание подписки
@router.post("/", response_model=SubscriptionOut)
@rate_limit_ip("subscription_create", max_requests=5, window_seconds=600)
async def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка создания подписки от пользователя без прав администратора: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может создавать подписки"}
        )

    if not ObjectId.is_valid(payload.user_id):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Администратор {current_user['iin']} пытался создать подписку с некорректным user_id: {payload.user_id}"
        )
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
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Администратор {current_user['iin']} пытался создать подписку для несуществующего пользователя: user_id={payload.user_id}, IIN={payload.iin}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден по user_id и IIN"}
        )

    existing = await db.subscriptions.find_one({"user_id": user_object_id, "is_active": True})
    if existing:
        logger.warning(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
            message=f"Администратор {current_user['iin']} пытался создать подписку для пользователя {payload.user_id}, у которого уже есть активная подписка {existing['_id']}"
        )
        raise HTTPException(
            status_code=409,
            detail={"message": "У пользователя уже есть активная подписка"}
        )

    # Новое поле для суммы
    amount = payload.amount
    
    logger.info(
        section=LogSection.ADMIN,
        subsection=LogSubsection.ADMIN.VALIDATION,
        message=f"Администратор {current_user['full_name']} (IIN: {current_user['iin']}) начинает создание подписки для пользователя {payload.user_id} (IIN: {payload.iin}) - валидация пройдена успешно"
    )

    try:
        # Инициализация переменной referral
        referral = None
        referral_used = False
        description = None

        # Проверка на наличие активной реферальной ссылки
        if payload.use_referral:
            if user.get("referred_by") and not user.get("referred_use"):
                # Уведомление админа о наличии активной реферальной ссылки
                logger.info(
                    section=LogSection.PAYMENT,
                    subsection=LogSubsection.PAYMENT.REFERRAL,
                    message=f"Обнаружена активная реферальная ссылка у пользователя {payload.user_id}: код {user['referred_by']} готов к использованию"
                )

                # Подготовка деталей реферала
                referral = await db.referrals.find_one({"code": user["referred_by"]})
                if referral:
                    referral_amount = round(amount * (referral["rate"]["value"] / 100), 2)
                    description = (f"Админ {current_user['full_name']} активировал вручную подписку пользователю {payload.user_id} "
                                   f"с типом {payload.subscription_type} на {payload.duration_days} дней и ввёл сумму {amount}. "
                                   f"У пользователя была рефералка {user['referred_by']} с процентом {referral['rate']['value']}%, "
                                   f"и после вычислений на аккаунт реферала {referral['owner_user_id']} начислено {referral_amount} тенге.")
                    referral_used = True
                    
                    logger.info(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.REFERRAL,
                        message=f"Найден реферальный код {user['referred_by']} в базе данных: владелец {referral['owner_user_id']}, ставка {referral['rate']['value']}%, к начислению {referral_amount} тенге"
                    )
                else:
                    logger.warning(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.REFERRAL,
                        message=f"Реферальный код {user['referred_by']} не найден в базе данных для пользователя {payload.user_id}"
                    )

        # Если рефералка использована, обработать реферал
        if referral_used:
            await process_referral(
                ObjectId(payload.user_id),
                amount,
                description,
                db_instance=db
            )
            user["referred_use"] = True
            await db.users.find_one_and_update(
                {"_id": user_object_id},
                {"$set": {"referred_use": True}},
                return_document=ReturnDocument.AFTER
            )
            
            logger.info(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.REFERRAL,
                message=f"Реферальный бонус успешно обработан для пользователя {payload.user_id}: код {user['referred_by']}, владелец {referral['owner_user_id']}, начислено {referral_amount} тенге"
            )

        now = datetime.utcnow()

        # Создание словаря с нужными полями
        subscription = {
            "user_id": ObjectId(payload.user_id),
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
        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_MANAGEMENT,
            message=f"Администратор {current_user['full_name']} (IIN: {current_user['iin']}) создал подписку {result.inserted_id} для пользователя {payload.user_id} типа {payload.subscription_type} на {payload.duration_days} дней за {amount} тенге"
        )

        subscription["_id"] = str(result.inserted_id)
        subscription["user_id"] = str(subscription["user_id"])

        # Обновление ответа с информацией о рефералке
        response_data = jsonable_encoder(subscription)
        response_data["referral_used"] = referral_used

        return success(data=response_data)

    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
            message=f"Критическая ошибка при создании подписки для пользователя {payload.user_id} администратором {current_user['iin']}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка при создании подписки {e}"}
        )


@router.put("/cancel", response_model=dict)
@rate_limit_ip("subscription_cancel", max_requests=10, window_seconds=600)
async def cancel_subscription(
    data: SubscriptionCancel,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка отмены подписки от пользователя без прав администратора: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может отменить подписку"}
        )

    try:
        subscription = await db.subscriptions.find_one({"_id": ObjectId(data.subscription_id)})
        if not subscription:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Администратор {current_user['iin']} пытался отменить несуществующую подписку: {data.subscription_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Подписка не найдена"}
            )

        if subscription["is_active"] is False:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Администратор {current_user['iin']} пытался отменить уже неактивную подписку {data.subscription_id} для пользователя {subscription['user_id']}"
            )
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

        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_MANAGEMENT,
            message=f"Администратор {current_user['full_name']} (IIN: {current_user['iin']}) отменил подписку {data.subscription_id} по причине: {data.cancel_reason}"
        )
        return success(data={"message": "Подписка отменена"})

    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
            message=f"Ошибка при отмене подписки {data.subscription_id} администратором {current_user['iin']}: {str(e)}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при отмене подписки", "hint": str(e)}
        )


# 🔍 Получение подписки по user_id (включая неактивную)
@router.get("/user/{user_id}", response_model=SubscriptionOut)
@rate_limit_ip("subscription_view", max_requests=30, window_seconds=60)
async def get_subscription_by_user_id(
    user_id: str,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения подписки от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
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
            logger.info(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Подписка не найдена для пользователя {user_id} - запрос от {current_user['role']} {current_user['iin']}"
            )
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
            
            logger.info(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Система автоматически отменила подписку {subscription['_id']} для пользователя {user_id} из-за истечения срока действия (истекла: {subscription['expires_at']})"
            )

        subscription["_id"] = str(subscription["_id"])
        subscription["user_id"] = str(subscription["user_id"])
        return success(data=jsonable_encoder(subscription))

    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
            message=f"Ошибка при получении подписки для пользователя {user_id} администратором {current_user['iin']}: {str(e)}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при получении подписки", "hint": str(e)}
        )


@router.put("/update", response_model=dict)
@rate_limit_ip("subscription_update", max_requests=10, window_seconds=600)
async def update_subscription(
    data: SubscriptionUpdate,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка обновления подписки от пользователя без прав администратора: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может редактировать подписки"}
        )

    try:
        # Проверяем, что подписка существует
        subscription = await db.subscriptions.find_one({"_id": ObjectId(data.subscription_id)})
        if not subscription:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Администратор {current_user['iin']} пытался обновить несуществующую подписку: {data.subscription_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Подписка не найдена"}
            )

        # Проверяем, что подписка активна
        if subscription["is_active"] is False:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Администратор {current_user['iin']} пытался обновить неактивную подписку {data.subscription_id} для пользователя {subscription['user_id']}"
            )
            raise HTTPException(
                status_code=409,
                detail={"message": "Нельзя изменить неактивную подписку"}
            )

        # Формируем данные для обновления
        update_data = {
            "subscription_type": data.subscription_type.lower(),
            "expires_at": data.expires_at,
            "updated_at": datetime.utcnow(),
            "update_log": {
                "admin_iin": current_user["iin"],
                "admin_name": current_user["full_name"],
                "timestamp": datetime.utcnow(),
                "note": data.note,
                "previous_type": subscription["subscription_type"],
                "previous_expires_at": subscription["expires_at"],
                "previous_duration_days": subscription.get("duration_days")
            }
        }
        
        # Обновляем duration_days если он предоставлен
        if data.duration_days is not None:
            update_data["duration_days"] = data.duration_days
        
        # Записываем предыдущие значения в историю
        history_entry = {
            "admin_iin": current_user["iin"],
            "admin_name": current_user["full_name"],
            "timestamp": datetime.utcnow(),
            "note": data.note,
            "previous_type": subscription["subscription_type"],
            "previous_expires_at": subscription["expires_at"],
            "previous_duration_days": subscription.get("duration_days"),
            "new_type": data.subscription_type.lower(),
            "new_expires_at": data.expires_at,
            "new_duration_days": data.duration_days
        }
        
        # Проверяем, существует ли уже поле update_history
        if "update_history" in subscription:
            # Если поле существует, используем $push для добавления записи
            result = await db.subscriptions.update_one(
                {"_id": ObjectId(data.subscription_id)},
                {
                    "$set": update_data,
                    "$push": {"update_history": history_entry}
                }
            )
        else:
            # Если поля еще нет, создаем его с первой записью
            update_data["update_history"] = [history_entry]
            result = await db.subscriptions.update_one(
                {"_id": ObjectId(data.subscription_id)},
                {"$set": update_data}
            )
        
        if result.modified_count == 0:
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
                message=f"Не удалось обновить подписку {data.subscription_id} в базе данных - операция не внесла изменений (администратор: {current_user['iin']})"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Не удалось обновить подписку"}
            )
            
        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_MANAGEMENT,
            message=f"Администратор {current_user['full_name']} (IIN: {current_user['iin']}) обновил подписку {data.subscription_id}: тип {subscription['subscription_type']} → {data.subscription_type}, срок действия {subscription['expires_at']} → {data.expires_at}, заметка: {data.note}"
        )
        
        # Получаем обновленную запись
        updated_subscription = await db.subscriptions.find_one({"_id": ObjectId(data.subscription_id)})
        updated_subscription["_id"] = str(updated_subscription["_id"])
        updated_subscription["user_id"] = str(updated_subscription["user_id"])
        
        return success(data=jsonable_encoder(updated_subscription))

    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.SUBSCRIPTION,
            message=f"Ошибка при обновлении подписки {data.subscription_id} администратором {current_user['iin']}: {str(e)}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при обновлении подписки", "hint": str(e)}
        )