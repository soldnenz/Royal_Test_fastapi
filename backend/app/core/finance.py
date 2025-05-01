import logging
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from app.core.config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info(f"Транзакция успешно залогирована: {data}")
    except Exception as e:
        logger.error(f"Ошибка при логировании транзакции: {e}")


async def process_referral(user_id, amount, description):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("referred_by") or user.get("referred_use"):
        return

    referral = await db.referrals.find_one({"code": user["referred_by"], "active": True})
    if not referral:
        logger.error(f"[referral] Код {user['referred_by']} не найден или не активен")
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

    logger.info(f"[referral] Бонус {referral_amount} тг. начислен владельцу {referral['owner_user_id']}")


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
                    
                    logger.info(f"Баланс пользователя {user_id} обновлён на {amount}.")
                else:
                    logger.error(f"Не удалось обновить баланс пользователя {user_id}.")
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(f"Ошибка при обновлении баланса пользователя: {e}")


async def get_user_balance(user_id):
    """
    Возвращает текущий баланс пользователя.
    :param user_id: ID пользователя
    :return: Баланс пользователя
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден.")
            return None
        balance = round(user.get("money", 0.0), 2)
        logger.info(f"Баланс пользователя {user_id}: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Ошибка при получении баланса пользователя: {e}")
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
                    
                    logger.info(f"Баланс пользователя {user_id} увеличен на {amount}.")
                    return {"status": "ok", "details": "Транзакция успешна"}
                else:
                    logger.error(f"Не удалось увеличить баланс пользователя {user_id}.")
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(f"Ошибка при увеличении баланса пользователя: {e}")
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
            logger.error(f"Пользователь с ID {user_id} не найден.")
            return {"status": "error", "details": "Пользователь не найден"}

        current_balance = user.get("money", 0.0)
        if current_balance < amount:
            logger.error(f"Недостаточно средств на балансе пользователя {user_id}.")
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
                    
                    logger.info(f"Баланс пользователя {user_id} уменьшен на {amount}.")
                    return {"status": "ok", "details": "Транзакция успешна"}
                else:
                    logger.error(f"Не удалось уменьшить баланс пользователя {user_id}.")
                    raise Exception("Не удалось обновить баланс пользователя.")
                    
    except Exception as e:
        logger.error(f"Ошибка при уменьшении баланса пользователя: {e}")
        return {"status": "error", "details": f"Ошибка сервера: {str(e)}"} 