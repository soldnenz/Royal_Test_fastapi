from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.security import get_current_actor
from app.db.database import get_database
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from app.core.finance import get_user_balance, credit_user_balance, debit_user_balance
from bson import ObjectId
from datetime import datetime
from app.rate_limit import rate_limit_ip
import traceback
import sys

router = APIRouter()
logger = get_logger(__name__)

# 🔍 Получение баланса пользователя
@router.get("/balance/{user_id}", response_model=dict)
@rate_limit_ip("balance_view", max_requests=120, window_seconds=30)
async def get_balance(
    user_id: str,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_actor)
):
    try:
        # Проверка аутентификации и авторизации
        if current_user is None:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTHENTICATION,
                message=f"Попытка доступа к балансу без аутентификации с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Требуется аутентификация"}
            )

        if current_user["role"] not in {"admin", "moderator"}:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа к балансу пользователя {user_id} пользователем {current_user.get('id')} с ролью {current_user.get('role')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=403,
                detail={"message": "Недостаточно прав"}
            )

        # Валидация user_id
        if user_id is None or not isinstance(user_id, str):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Пустой или некорректный user_id при запросе баланса: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )

        if not ObjectId.is_valid(user_id):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректный формат user_id при запросе баланса: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )

        # Проверка подключения к базе данных
        if db is None:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.DATABASE,
                message=f"Ошибка подключения к базе данных при запросе баланса пользователя {user_id} администратором {current_user.get('id')}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка подключения к базе данных"}
            )

        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"Запрос баланса пользователя {user_id} администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
        )

        balance = await get_user_balance(user_id, db_instance=db)
        if balance is None:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.BALANCE,
                message=f"Пользователь {user_id} не найден при запросе баланса администратором {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )

        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"Получен баланс пользователя {user_id}: {balance} тенге, запрос от администратора {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
        )
        return success(data={"balance": balance})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"КРИТИЧЕСКАЯ ОШИБКА при получении баланса пользователя {user_id}: {str(e)}, администратор: {current_user.get('id') if current_user is not None else 'Unknown'}, IP: {request.client.host}"
        )
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"Traceback: {traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Внутренняя ошибка сервера"}
        )

# 📊 Просмотр всех транзакций
@router.get("/transactions", response_model=list)
@rate_limit_ip("transactions_list", max_requests=30, window_seconds=60)
async def get_all_transactions(
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_actor)
):
    try:
        # Проверка аутентификации и авторизации
        if current_user is None:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTHENTICATION,
                message=f"Попытка доступа к списку транзакций без аутентификации с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Требуется аутентификация"}
            )

        if current_user["role"] not in {"admin", "moderator"}:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа к списку транзакций пользователем {current_user.get('id')} с ролью {current_user.get('role')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=403,
                detail={"message": "Недостаточно прав"}
            )

        # Проверка подключения к базе данных
        if db is None:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.DATABASE,
                message=f"Ошибка подключения к базе данных при запросе списка транзакций администратором {current_user.get('id')}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка подключения к базе данных"}
            )

        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.LIST_ACCESS,
            message=f"Запрос списка всех транзакций администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
        )

        transactions = []
        try:
            async for transaction in db.transactions.find():
                try:
                    transaction["_id"] = str(transaction["_id"])
                    transaction["user_id"] = str(transaction["user_id"])
                    
                    # Преобразование всех объектов datetime в строки
                    for key, value in transaction.items():
                        if isinstance(value, datetime):
                            transaction[key] = value.isoformat()

                    transactions.append(transaction)
                except Exception as e:
                    logger.warning(
                        section=LogSection.SYSTEM,
                        subsection=LogSubsection.SYSTEM.DATA_PROCESSING,
                        message=f"Ошибка обработки транзакции {transaction.get('_id', 'Unknown')}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.DATABASE,
                message=f"Ошибка при получении транзакций из базы данных: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка при получении данных"}
            )

        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.LIST_ACCESS,
            message=f"Получен список всех транзакций администратором {current_user.get('full_name', current_user.get('id'))}: найдено {len(transactions)} транзакций"
        )
        return success(data=transactions)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"КРИТИЧЕСКАЯ ОШИБКА при получении списка транзакций: {str(e)}, администратор: {current_user.get('id') if current_user is not None else 'Unknown'}, IP: {request.client.host}"
        )
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"Traceback: {traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Внутренняя ошибка сервера"}
        )

# 💰 Пополнение баланса пользователя
@router.post("/credit", response_model=dict)
@rate_limit_ip("balance_credit", max_requests=15, window_seconds=300)
async def add_money(
    request_data: dict,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_actor)
):
    try:
        # Проверка аутентификации и авторизации
        if current_user is None:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTHENTICATION,
                message=f"Попытка пополнения баланса без аутентификации с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Требуется аутентификация"}
            )

        if current_user["role"] not in {"admin", "moderator"}:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка пополнения баланса пользователем {current_user.get('id')} с ролью {current_user.get('role')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=403,
                detail={"message": "Недостаточно прав"}
            )
        
        # Проверка входных данных
        if request_data is None or not isinstance(request_data, dict):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректные данные запроса при пополнении баланса от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректные данные запроса"}
            )
        
        # Извлекаем данные из запроса
        user_id = request_data.get("user_id")
        amount = request_data.get("amount")
        comment = request_data.get("comment", "Ручное пополнение администратором")
        
        # Валидация user_id
        if user_id is None or not isinstance(user_id, str):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Пустой или некорректный user_id при пополнении баланса: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )

        if not ObjectId.is_valid(user_id):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректный формат user_id при пополнении баланса: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )
        
        # Валидация суммы
        if amount is None:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Отсутствует сумма при пополнении баланса для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Сумма обязательна"}
            )

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректная сумма при пополнении баланса: {amount} для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректная сумма"}
            )
        
        if amount <= 0:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Отрицательная или нулевая сумма при пополнении: {amount} для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Сумма должна быть положительной"}
            )

        # Валидация комментария
        if comment and not isinstance(comment, str):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректный комментарий при пополнении баланса: {comment} для пользователя {user_id} от администратора {current_user.get('id')}"
            )
            comment = "Ручное пополнение администратором"
        
        # Проверка на аномально большую сумму
        if amount > 20000:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"АНОМАЛИЯ: Крупная транзакция пополнения на {amount} тенге для пользователя {user_id} от администратора {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
            )
            # Продолжаем выполнение, но логируем событие
        
        # Проверка подключения к базе данных
        if db is None:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.DATABASE,
                message=f"Ошибка подключения к базе данных при пополнении баланса пользователя {user_id} администратором {current_user.get('id')}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка подключения к базе данных"}
            )
        
        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.CREDIT,
            message=f"Начато пополнение баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}, комментарий: {comment}"
        )
        
        # Выполняем операцию начисления средств
        try:
            description = f"{comment} (by {current_user.get('full_name', 'Unknown')})"
            admin_id = str(current_user.get('id')) if current_user.get('id') else None
            result = await credit_user_balance(user_id, amount, description, admin_id=admin_id, db_instance=db)
        except Exception as e:
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.CREDIT,
                message=f"Ошибка при вызове credit_user_balance для пользователя {user_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка при выполнении операции"}
            )
        
        if result is not None and result.get("status") == "ok":
            logger.info(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.CREDIT,
                message=f"Успешно пополнен баланс пользователя {user_id} на +{amount} тенге администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
            )
            return success(data={"message": "Баланс успешно пополнен", "amount": amount})
        else:
            error_details = result.get('details', 'Неизвестная ошибка') if result is not None else 'Нет ответа от сервиса'
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.CREDIT,
                message=f"Ошибка при пополнении баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('id')} с IP {request.client.host}: {error_details}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": f"Ошибка при пополнении баланса: {error_details}"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"КРИТИЧЕСКАЯ ОШИБКА при пополнении баланса: {str(e)}, администратор: {current_user.get('id') if current_user is not None else 'Unknown'}, IP: {request.client.host}"
        )
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"Traceback: {traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Внутренняя ошибка сервера"}
        )

# 💸 Списание денег с баланса пользователя
@router.post("/debit", response_model=dict)
@rate_limit_ip("balance_debit", max_requests=15, window_seconds=300)
async def subtract_money(
    request_data: dict,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_actor)
):
    try:
        # Проверка аутентификации и авторизации
        if current_user is None:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTHENTICATION,
                message=f"Попытка списания средств без аутентификации с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Требуется аутентификация"}
            )

        if current_user["role"] not in {"admin", "moderator"}:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка списания средств пользователем {current_user.get('id')} с ролью {current_user.get('role')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=403,
                detail={"message": "Недостаточно прав"}
            )
        
        # Проверка входных данных
        if request_data is None or not isinstance(request_data, dict):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректные данные запроса при списании средств от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректные данные запроса"}
            )
        
        # Извлекаем данные из запроса
        user_id = request_data.get("user_id")
        amount = request_data.get("amount")
        comment = request_data.get("comment", "Ручное списание администратором")
        
        # Валидация user_id
        if user_id is None or not isinstance(user_id, str):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Пустой или некорректный user_id при списании средств: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )

        if not ObjectId.is_valid(user_id):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректный формат user_id при списании средств: {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректный user_id"}
            )
        
        # Валидация суммы
        if amount is None:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Отсутствует сумма при списании средств для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Сумма обязательна"}
            )

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректная сумма при списании средств: {amount} для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Некорректная сумма"}
            )
        
        if amount <= 0:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Отрицательная или нулевая сумма при списании: {amount} для пользователя {user_id} от администратора {current_user.get('id')} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Сумма должна быть положительной"}
            )

        # Валидация комментария
        if comment and not isinstance(comment, str):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Некорректный комментарий при списании средств: {comment} для пользователя {user_id} от администратора {current_user.get('id')}"
            )
            comment = "Ручное списание администратором"
        
        # Проверка на аномально большую сумму
        if amount > 20000:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"АНОМАЛИЯ: Крупная транзакция списания на {amount} тенге для пользователя {user_id} от администратора {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
            )
            # Продолжаем выполнение, но логируем событие
        
        # Проверка подключения к базе данных
        if db is None:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.DATABASE,
                message=f"Ошибка подключения к базе данных при списании средств пользователя {user_id} администратором {current_user.get('id')}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка подключения к базе данных"}
            )
        
        # Получаем текущий баланс пользователя для проверки
        try:
            current_balance = await get_user_balance(user_id, db_instance=db)
        except Exception as e:
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Ошибка при получении баланса пользователя {user_id} для списания: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка при получении баланса пользователя"}
            )

        if current_balance is None:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Пользователь {user_id} не найден при попытке списания {amount} тенге администратором {current_user.get('id')} с IP {request.client.host}"
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
                message=f"Недостаточно средств для списания: попытка списать {amount} тенге при балансе {current_balance} у пользователя {user_id} администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": f"Недостаточно средств на балансе. Текущий баланс: {current_balance}"}
            )
        
        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"Начато списание средств с баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}, текущий баланс: {current_balance}, комментарий: {comment}"
        )
        
        # Выполняем операцию списания средств
        try:
            description = f"{comment} (by {current_user.get('full_name', 'Unknown')})"
            admin_id = str(current_user.get('id')) if current_user.get('id') else None
            result = await debit_user_balance(user_id, amount, description, admin_id=admin_id, db_instance=db)
        except Exception as e:
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Ошибка при вызове debit_user_balance для пользователя {user_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Ошибка при выполнении операции"}
            )
        
        if result is not None and result.get("status") == "ok":
            logger.info(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Успешно списано с баланса пользователя {user_id}: -{amount} тенге администратором {current_user.get('full_name', current_user.get('id'))} с IP {request.client.host}, новый баланс: {current_balance - amount}"
            )
            return success(data={"message": "Средства успешно списаны", "amount": amount})
        else:
            error_details = result.get('details', 'Неизвестная ошибка') if result is not None else 'Нет ответа от сервиса'
            logger.error(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Ошибка при списании средств с баланса пользователя {user_id} на {amount} тенге администратором {current_user.get('id')} с IP {request.client.host}: {error_details}"
            )
            raise HTTPException(
                status_code=500,
                detail={"message": f"Ошибка при списании средств: {error_details}"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"КРИТИЧЕСКАЯ ОШИБКА при списании средств: {str(e)}, администратор: {current_user.get('id') if current_user is not None else 'Unknown'}, IP: {request.client.host}"
        )
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.GENERAL,
            message=f"Traceback: {traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Внутренняя ошибка сервера"}
        ) 