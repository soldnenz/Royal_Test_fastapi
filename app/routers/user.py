# app/routers/user.py

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from fastapi.security import HTTPBearer
from app.db.database import db
from app.schemas.user_schemas import UserOut, UserUpdate
from app.core.security import get_current_actor

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/me")
async def get_current_profile(actor=Depends(get_current_actor)):
    if actor["type"] == "user":
        return {
            "role": "user",
            "email": actor["email"],
            "phone": actor["phone"],
            "iin": actor["iin"]
        }
    elif actor["type"] == "admin":
        return {
            "role": "admin",
            "full_name": actor["full_name"],
            "iin": actor["iin"]
        }
    else:
        return {"detail": "Unknown role"}


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
