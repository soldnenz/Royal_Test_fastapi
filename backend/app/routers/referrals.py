from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.database import get_database
from app.admin.permissions import get_current_admin_user
from app.core.response import success
from app.models import get_current_actor  # Если нужно для получения информации о текущем пользователе

router = APIRouter()

# Логирование
logger = logging.getLogger(__name__)

# Модель данных для создания/редактирования рефералки
class Referral(BaseModel):
    code: str
    type: str  # "school" или "user"
    owner_user_id: Optional[str] = None  # Не обязателен для типа "school"
    owner_school_id: Optional[str] = None  # Не обязателен для типа "user"
    rate: dict  # {'type': 'percent', 'value': 10}
    description: str
    active: bool = True
    comment: Optional[str] = None
    created_by: str

    class Config:
        orm_mode = True


# Модель для поиска рефералок
class ReferralSearchParams(BaseModel):
    code: Optional[str] = None
    type: Optional[str] = None
    owner_user_id: Optional[str] = None
    active: Optional[bool] = None

    class Config:
        orm_mode = True


# Добавление новой рефералки
@router.post("/referrals", response_model=dict)
async def create_referral(referral: Referral, current_user: dict = Depends(get_current_admin_user), db=Depends(get_database)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")

    referral_data = referral.dict()
    referral_data["created_at"] = datetime.utcnow()
    referral_data["created_by"] = current_user["full_name"]  # Записываем имя админа, который создал рефералку

    try:
        # Добавление рефералки в базу данных
        result = await db.referrals.insert_one(referral_data)
        logger.info(f"[CREATE_REFERRAL] Рефералка создана: {referral_data['code']} (user_id={current_user['id']})")
        return success(data={"referral_id": str(result.inserted_id)}, message="Рефералка успешно создана")
    except Exception as e:
        logger.error(f"[CREATE_REFERRAL] Ошибка при создании рефералки: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при создании рефералки")


# Редактирование рефералки
@router.put("/referrals/{referral_id}", response_model=dict)
async def update_referral(referral_id: str, referral: Referral, current_user: dict = Depends(get_current_admin_user), db=Depends(get_database)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")

    referral_data = referral.dict()
    referral_data["updated_at"] = datetime.utcnow()

    try:
        # Обновление данных рефералки
        result = await db.referrals.update_one({"_id": ObjectId(referral_id)}, {"$set": referral_data})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Рефералка не найдена")
        logger.info(f"[UPDATE_REFERRAL] Рефералка обновлена: {referral_data['code']} (user_id={current_user['id']})")
        return success(data={"referral_id": referral_id}, message="Рефералка успешно обновлена")
    except Exception as e:
        logger.error(f"[UPDATE_REFERRAL] Ошибка при обновлении рефералки: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при обновлении рефералки")


# Мягкое удаление рефералки (смена флага активной)
@router.delete("/referrals/{referral_id}", response_model=dict)
async def soft_delete_referral(referral_id: str, current_user: dict = Depends(get_current_admin_user), db=Depends(get_database)):
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")

    try:
        # Мягкое удаление рефералки (активация флага active)
        result = await db.referrals.update_one({"_id": ObjectId(referral_id)}, {"$set": {"active": False}})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Рефералка не найдена")
        logger.info(f"[SOFT_DELETE_REFERRAL] Рефералка деактивирована: {referral_id} (user_id={current_user['id']})")
        return success(data={"referral_id": referral_id}, message="Рефералка успешно деактивирована")
    except Exception as e:
        logger.error(f"[SOFT_DELETE_REFERRAL] Ошибка при деактивации рефералки: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при деактивации рефералки")


# Поиск рефералок
@router.get("/referrals", response_model=List[Referral])
async def search_referrals(params: ReferralSearchParams = Depends(), current_user: dict = Depends(get_current_admin_user), db=Depends(get_database)):
    if current_user["role"] not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Доступ только для администраторов и модераторов.")

    try:
        query = {key: value for key, value in params.dict().items() if value is not None}
        referrals = await db.referrals.find(query).to_list(length=100)
        logger.info(f"[SEARCH_REFERRALS] Найдено {len(referrals)} рефералок (user_id={current_user['id']})")
        return referrals
    except Exception as e:
        logger.error(f"[SEARCH_REFERRALS] Ошибка при поиске рефералок: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при поиске рефералок")
