from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.db.database import get_database
from app.admin.permissions import get_current_admin_user
from fastapi.responses import JSONResponse
from app.core.finance import get_user_balance, credit_user_balance, debit_user_balance
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from datetime import datetime

router = APIRouter()
logger = get_logger(__name__)

# 🔍 Получение баланса пользователя
@router.get("/balance/{user_id}", response_model=dict)
async def get_balance(
    user_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка доступа к балансу пользователя {user_id} пользователем {current_user.get('_id')} с ролью {current_user.get('role')}"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )

    if not ObjectId.is_valid(user_id):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Некорректный формат user_id при запросе баланса: {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )

    balance = await get_user_balance(user_id)
    if balance is None:
        logger.warning(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"Пользователь {user_id} не найден при запросе баланса администратором {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден"}
        )

    logger.info(
        section=LogSection.PAYMENT,
        subsection=LogSubsection.PAYMENT.BALANCE,
        message=f"Получен баланс пользователя {user_id}: {balance} тенге, запрос от администратора {current_user.get('full_name', current_user.get('_id'))}"
    )
    return success(data={"balance": balance})

# 📊 Просмотр всех транзакций
@router.get("/transactions", response_model=list)
async def get_all_transactions(
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка доступа к списку транзакций пользователем {current_user.get('_id')} с ролью {current_user.get('role')}"
        )
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

    logger.info(
        section=LogSection.ADMIN,
        subsection=LogSubsection.ADMIN.LIST_ACCESS,
        message=f"Получен список всех транзакций администратором {current_user.get('full_name', current_user.get('_id'))}: найдено {len(transactions)} транзакций"
    )
    return success(data=transactions)

# 💰 Пополнение баланса пользователя
@router.post("/credit", response_model=dict)
async def add_money(
    request_data: dict,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in {"admin", "moderator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка пополнения баланса пользователем {current_user.get('_id')} с ролью {current_user.get('role')}"
        )
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
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Некорректный user_id при пополнении баланса: {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Некорректная сумма при пополнении баланса: {amount} для пользователя {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректная сумма"}
        )
    
    if amount <= 0:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Отрицательная или нулевая сумма при пополнении: {amount} для пользователя {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Сумма должна быть положительной"}
        )
    
    # Проверка на аномально большую сумму
    if amount > 20000:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
            message=f"АНОМАЛИЯ: Крупная транзакция пополнения на {amount} тенге для пользователя {user_id} от администратора {current_user.get('full_name', current_user.get('_id'))}"
        )
        # Продолжаем выполнение, но логируем событие
    
    logger.info(
        section=LogSection.PAYMENT,
        subsection=LogSubsection.PAYMENT.CREDIT,
        message=f"Начато пополнение баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('full_name', current_user.get('_id'))}, комментарий: {comment}"
    )
    
    # Выполняем операцию начисления средств
    description = f"{comment} (by {current_user['full_name']})"
    result = await credit_user_balance(user_id, amount, description, admin_id=str(current_user["_id"]))
    
    if result["status"] == "ok":
        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.CREDIT,
            message=f"Успешно пополнен баланс пользователя {user_id} на +{amount} тенге администратором {current_user.get('full_name', current_user.get('_id'))}"
        )
        return success(data={"message": "Баланс успешно пополнен", "amount": amount})
    else:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.CREDIT,
            message=f"Ошибка при пополнении баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('_id')}: {result.get('details', 'Неизвестная ошибка')}"
        )
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
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка списания средств пользователем {current_user.get('_id')} с ролью {current_user.get('role')}"
        )
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
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Некорректный user_id при списании средств: {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный user_id"}
        )
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Некорректная сумма при списании средств: {amount} для пользователя {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректная сумма"}
        )
    
    if amount <= 0:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Отрицательная или нулевая сумма при списании: {amount} для пользователя {user_id} от администратора {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Сумма должна быть положительной"}
        )
    
    # Проверка на аномально большую сумму
    if amount > 20000:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
            message=f"АНОМАЛИЯ: Крупная транзакция списания на {amount} тенге для пользователя {user_id} от администратора {current_user.get('full_name', current_user.get('_id'))}"
        )
        # Продолжаем выполнение, но логируем событие
    
    # Получаем текущий баланс пользователя для проверки
    current_balance = await get_user_balance(user_id)
    if current_balance is None:
        logger.warning(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"Пользователь {user_id} не найден при попытке списания {amount} тенге администратором {current_user.get('_id')}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден"}
        )
    
    # Проверка на достаточность средств
    if current_balance < amount:
        logger.warning(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"Недостаточно средств для списания: попытка списать {amount} тенге при балансе {current_balance} у пользователя {user_id} администратором {current_user.get('full_name', current_user.get('_id'))}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": f"Недостаточно средств на балансе. Текущий баланс: {current_balance}"}
        )
    
    logger.info(
        section=LogSection.PAYMENT,
        subsection=LogSubsection.PAYMENT.DEBIT,
        message=f"Начато списание средств с баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('full_name', current_user.get('_id'))}, текущий баланс: {current_balance}, комментарий: {comment}"
    )
    
    # Выполняем операцию списания средств
    description = f"{comment} (by {current_user['full_name']})"
    result = await debit_user_balance(user_id, amount, description, admin_id=str(current_user["_id"]))
    
    if result["status"] == "ok":
        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"Успешно списано с баланса пользователя {user_id}: -{amount} тенге администратором {current_user.get('full_name', current_user.get('_id'))}, новый баланс: {current_balance - amount}"
        )
        return success(data={"message": "Средства успешно списаны", "amount": amount})
    else:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"Ошибка при списании средств с баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('_id')}: {result.get('details', 'Неизвестная ошибка')}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка при списании средств: {result['details']}"}
        ) 