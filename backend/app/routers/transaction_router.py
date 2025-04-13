from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from app.core.finance import get_user_balance
from app.core.response import success
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

# 🔍 Получение баланса пользователя
@router.get("/balance/{user_id}", response_model=dict)
async def get_balance(
    user_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )

    balance = get_user_balance(user_id)
    if balance is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден"}
        )

    return success(data={"balance": balance})

# 📊 Просмотр всех транзакций
@router.get("/transactions", response_model=list)
async def get_all_transactions(
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )

    transactions = []
    async for transaction in db.transactions.find():
        transaction["_id"] = str(transaction["_id"])
        transaction["user_id"] = str(transaction["user_id"])
        
        # Преобразование всех объектов datetime в строки
        for key, value in transaction.items():
            if isinstance(value, datetime):
                transaction[key] = value.isoformat()

        transactions.append(transaction)

    return success(data=transactions) 