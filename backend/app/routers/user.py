# app/routers/user.py

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from bson import ObjectId
from fastapi.security import HTTPBearer
from app.db.database import db
from app.schemas.user_schemas import UserOut, UserUpdate
from app.core.security import get_current_actor
from app.db.database import get_database
from datetime import datetime, timedelta
from app.core.response import success
import re

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
            "role": actor["role"],           # ← всегда 'user'
            "full_name": actor["full_name"],
            "email": actor["email"],
            "phone": actor["phone"],
            "iin": actor["iin"],
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
            "days_left": max(days_left, 0)
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
