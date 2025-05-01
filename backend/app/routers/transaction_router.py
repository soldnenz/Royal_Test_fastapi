from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from app.core.finance import get_user_balance, credit_user_balance, debit_user_balance
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

    balance = await get_user_balance(user_id)
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

# 💰 Пополнение баланса пользователя
@router.post("/credit", response_model=dict)
async def add_money(
    request_data: dict,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )
    
    # Извлекаем данные из запроса
    user_id = request_data.get("user_id")
    amount = request_data.get("amount")
    comment = request_data.get("comment", "Ручное пополнение администратором")
    
    # Проверяем валидность данных
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректная сумма"}
        )
    
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Сумма должна быть положительной"}
        )
    
    # Проверка на аномально большую сумму
    if amount > 20000:
        logger.warning(f"ANOMALY: Large credit transaction of {amount} for user {user_id} by admin {current_user['_id']}")
        # Продолжаем выполнение, но логируем событие
    
    # Выполняем операцию начисления средств
    description = f"{comment} (by {current_user['full_name']})"
    result = await credit_user_balance(user_id, amount, description, admin_id=str(current_user["_id"]))
    
    if result["status"] == "ok":
        logger.info(f"Balance credited for user {user_id}: +{amount} tenge")
        return success(data={"message": "Баланс успешно пополнен", "amount": amount})
    else:
        logger.error(f"Failed to credit balance: {result['details']}")
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка при пополнении баланса: {result['details']}"}
        )

# 💸 Списание денег с баланса пользователя
@router.post("/debit", response_model=dict)
async def subtract_money(
    request_data: dict,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )
    
    # Извлекаем данные из запроса
    user_id = request_data.get("user_id")
    amount = request_data.get("amount")
    comment = request_data.get("comment", "Ручное списание администратором")
    
    # Проверяем валидность данных
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректная сумма"}
        )
    
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Сумма должна быть положительной"}
        )
    
    # Проверка на аномально большую сумму
    if amount > 20000:
        logger.warning(f"ANOMALY: Large debit transaction of {amount} for user {user_id} by admin {current_user['_id']}")
        # Продолжаем выполнение, но логируем событие
    
    # Получаем текущий баланс пользователя для проверки
    current_balance = await get_user_balance(user_id)
    if current_balance is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден"}
        )
    
    # Проверка на достаточность средств
    if current_balance < amount:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Недостаточно средств на балансе. Текущий баланс: {current_balance}"}
        )
    
    # Выполняем операцию списания средств
    description = f"{comment} (by {current_user['full_name']})"
    result = await debit_user_balance(user_id, amount, description, admin_id=str(current_user["_id"]))
    
    if result["status"] == "ok":
        logger.info(f"Balance debited for user {user_id}: -{amount} tenge")
        return success(data={"message": "Средства успешно списаны", "amount": amount})
    else:
        logger.error(f"Failed to debit balance: {result['details']}")
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка при списании средств: {result['details']}"}
        ) 