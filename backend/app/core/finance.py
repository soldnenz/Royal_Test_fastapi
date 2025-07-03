from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from app.core.config import settings

# Новая структурированная система логирования
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection

logger = get_structured_logger("core.finance")

# Подключение к MongoDB с использованием переменных окружения
client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB_NAME]
transactions_collection = db['transactions']


async def log_transaction(data, session=None):
    """
    Логирует транзакцию в MongoDB.
    :param data: Словарь с данными о транзакции
    :param session: Опциональная сессия MongoDB для транзакций
    """
    try:
        if session:
            await transactions_collection.insert_one(data, session=session)
        else:
            await transactions_collection.insert_one(data)
        logger.info(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.TRANSACTION,
            message=f"Транзакция успешно сохранена в базе данных: пользователь {data.get('user_id')}, сумма {data.get('amount')} тг, тип {data.get('type')}, описание: {data.get('description')}"
        )
    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.TRANSACTION,
            message=f"ОШИБКА сохранения транзакции в базе данных: {str(e)}"
        )


async def process_referral(user_id, amount, description):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("referred_by") or user.get("referred_use"):
        return

    referral = await db.referrals.find_one({"code": user["referred_by"], "active": True})
    if not referral:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.REFERRAL,
            message=f"Реферальный код {user['referred_by']} не найден или неактивен - не можем начислить бонус пользователю {user_id}"
        )
        return

    referral_amount = round(amount * (referral["rate"]["value"] / 100), 2)
    now = datetime.utcnow()

    async with await db.client.start_session() as session:
        async with session.start_transaction():
            # Начисляем бонус
            await db.users.update_one(
                {"_id": ObjectId(referral["owner_user_id"])},
                {"$inc": {"money": referral_amount}},
                session=session
            )
            # Логируем транзакцию
            await db.transactions.insert_one({
                "user_id":          ObjectId(referral["owner_user_id"]),
                "amount":           referral_amount,
                "type":             "referral",
                "description":      description,
                "referred_user_id": ObjectId(user_id),
                "created_at":       now
            }, session=session)
            # Помечаем, что пользователь уже «отработал» рефералку
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"referred_use": True}},
                session=session
            )

    logger.info(
        section=LogSection.PAYMENT,
        subsection=LogSubsection.PAYMENT.REFERRAL,
        message=f"Реферальный бонус {referral_amount} тг успешно начислен владельцу кода {referral['owner_user_id']} за приведенного пользователя {user_id} - ставка {referral['rate']['value']}%"
    )


async def update_user_balance(user_id, amount, description):
    """
    Обновляет баланс пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для обновления
    :param description: Описание транзакции
    """
    try:
        amount = round(amount, 2)
        
        # Выполняем всё в Mongo-транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                result = await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$inc": {"money": amount}},
                    session=session
                )
                
                if result.modified_count > 0:
                    await log_transaction({
                        "user_id": ObjectId(user_id),
                        "amount": amount,
                        "type": "balance_update",
                        "description": description,
                        "created_at": datetime.utcnow()
                    }, session=session)
                    
                    logger.info(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.BALANCE,
                        message=f"Баланс пользователя {user_id} успешно изменен на {amount} тг - {description}"
                    )
                else:
                    logger.error(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.BALANCE,
                        message=f"НЕ УДАЛОСЬ обновить баланс пользователя {user_id} на сумму {amount} тг"
                    )
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"КРИТИЧЕСКАЯ ОШИБКА при обновлении баланса пользователя {user_id}: {str(e)}"
        )


async def get_user_balance(user_id):
    """
    Возвращает текущий баланс пользователя.
    :param user_id: ID пользователя
    :return: Баланс пользователя
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(
                section=LogSection.USER,
                subsection=LogSubsection.USER.PROFILE,
                message=f"Пользователь с ID {user_id} не найден при запросе баланса"
            )
            return None
        balance = round(user.get("money", 0.0), 2)
        logger.debug(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"Запрос баланса пользователя {user_id}: {balance} тг"
        )
        return balance
    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.BALANCE,
            message=f"ОШИБКА получения баланса пользователя {user_id}: {str(e)}"
        )
        return None


async def credit_user_balance(user_id, amount, description, admin_id=None):
    """
    Начисляет средства на баланс пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для начисления
    :param description: Описание транзакции
    :param admin_id: ID администратора, выполняющего транзакцию
    :return: Статус транзакции
    """
    try:
        amount = round(amount, 2)
        
        # Выполняем всё в Mongo-транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                result = await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$inc": {"money": amount}},
                    session=session
                )
                
                if result.modified_count > 0:
                    txn = {
                        "user_id": ObjectId(user_id),
                        "amount": amount,
                        "type": "credit",
                        "description": description,
                        "created_at": datetime.utcnow()
                    }
                    if admin_id:
                        txn["admin_id"] = admin_id
                    await log_transaction(txn, session=session)
                    
                    logger.info(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.CREDIT,
                        message=f"Пополнение баланса: пользователю {user_id} начислено {amount} тг{f' администратором {admin_id}' if admin_id else ''} - {description}"
                    )
                    return {"status": "ok", "details": "Транзакция успешна"}
                else:
                    logger.error(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.CREDIT,
                        message=f"НЕ УДАЛОСЬ пополнить баланс пользователя {user_id} на {amount} тг"
                    )
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.CREDIT,
            message=f"КРИТИЧЕСКАЯ ОШИБКА пополнения баланса пользователя {user_id} на {amount} тг: {str(e)}"
        )
        return {"status": "error", "details": f"Ошибка сервера: {str(e)}"}


async def debit_user_balance(user_id, amount, description, admin_id=None):
    """
    Списывает средства с баланса пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для списания
    :param description: Описание транзакции
    :param admin_id: ID администратора, выполняющего транзакцию
    :return: Статус транзакции
    """
    try:
        amount = round(amount, 2)
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(
                section=LogSection.USER,
                subsection=LogSubsection.USER.PROFILE,
                message=f"Пользователь с ID {user_id} не найден при попытке списания {amount} тг"
            )
            return {"status": "error", "details": "Пользователь не найден"}

        current_balance = user.get("money", 0.0)
        if current_balance < amount:
            logger.warning(
                section=LogSection.PAYMENT,
                subsection=LogSubsection.PAYMENT.DEBIT,
                message=f"Недостаточно средств у пользователя {user_id}: пытается списать {amount} тг при балансе {current_balance} тг"
            )
            return {"status": "error", "details": "Недостаточно средств на балансе"}

        # Выполняем всё в Mongo-транзакции
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                result = await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$inc": {"money": -amount}},
                    session=session
                )
                
                if result.modified_count > 0:
                    txn = {
                        "user_id": ObjectId(user_id),
                        "amount": -amount,
                        "type": "debit",
                        "description": description,
                        "created_at": datetime.utcnow()
                    }
                    if admin_id:
                        txn["admin_id"] = admin_id
                    await log_transaction(txn, session=session)
                    
                    logger.info(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.DEBIT,
                        message=f"Списание с баланса: у пользователя {user_id} списано {amount} тг{f' администратором {admin_id}' if admin_id else ''} - {description}"
                    )
                    return {"status": "ok", "details": "Транзакция успешна"}
                else:
                    logger.error(
                        section=LogSection.PAYMENT,
                        subsection=LogSubsection.PAYMENT.DEBIT,
                        message=f"НЕ УДАЛОСЬ списать с баланса пользователя {user_id} сумму {amount} тг"
                    )
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(
            section=LogSection.PAYMENT,
            subsection=LogSubsection.PAYMENT.DEBIT,
            message=f"КРИТИЧЕСКАЯ ОШИБКА списания с баланса пользователя {user_id} суммы {amount} тг: {str(e)}"
        )
        return {"status": "error", "details": f"Ошибка сервера: {str(e)}"} 