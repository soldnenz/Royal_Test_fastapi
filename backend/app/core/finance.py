import logging
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from app.core.config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Подключение к MongoDB с использованием переменных окружения
client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB_NAME]
transactions_collection = db['transactions']


def log_transaction(data):
    """
    Логирует транзакцию в MongoDB.
    :param data: Словарь с данными о транзакции
    """
    try:
        transactions_collection.insert_one(data)
        logger.info(f"Транзакция успешно залогирована: {data}")
    except Exception as e:
        logger.error(f"Ошибка при логировании транзакции: {e}")


def process_referral(user_id, amount, description):
    """
    Обрабатывает реферальную транзакцию и сохраняет её описание в базе данных.
    :param user_id: ID пользователя
    :param amount: Сумма транзакции
    :param description: Описание транзакции
    """
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден.")
            return

        if user.get("referred_by") and not user.get("referred_use"):
            referral = db.referrals.find_one({"code": user["referred_by"]})
            if referral:
                referral_amount = round(amount * (referral["rate"]["value"] / 100), 2)
                db.users.update_one(
                    {"_id": ObjectId(referral["owner_user_id"])},
                    {"$inc": {"money": referral_amount}}
                )
                log_transaction({
                    "user_id": user_id,
                    "amount": referral_amount,
                    "type": "referral",
                    "referred_by": user["referred_by"],
                    "referral_rate": referral["rate"],
                    "description": description,
                    "created_at": datetime.utcnow()
                })
            else:
                logger.error(f"Реферальный код {user['referred_by']} не найден.")
    except Exception as e:
        logger.error(f"Ошибка при обработке реферальной транзакции: {e}")


def update_user_balance(user_id, amount, description):
    """
    Обновляет баланс пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для обновления
    :param description: Описание транзакции
    """
    try:
        amount = round(amount, 2)
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"money": amount}}
        )
        if result.modified_count > 0:
            log_transaction({
                "user_id": user_id,
                "amount": amount,
                "type": "balance_update",
                "description": description,
                "created_at": datetime.utcnow()
            })
            logger.info(f"Баланс пользователя {user_id} обновлён на {amount}.")
        else:
            logger.error(f"Не удалось обновить баланс пользователя {user_id}.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении баланса пользователя: {e}")


def get_user_balance(user_id):
    """
    Возвращает текущий баланс пользователя.
    :param user_id: ID пользователя
    :return: Баланс пользователя
    """
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден.")
            return None
        balance = round(user.get("money", 0.0), 2)
        logger.info(f"Баланс пользователя {user_id}: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Ошибка при получении баланса пользователя: {e}")
        return None


def credit_user_balance(user_id, amount, description):
    """
    Начисляет средства на баланс пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для начисления
    :param description: Описание транзакции
    :return: Статус транзакции
    """
    try:
        amount = round(amount, 2)
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"money": amount}}
        )
        if result.modified_count > 0:
            log_transaction({
                "user_id": user_id,
                "amount": amount,
                "type": "credit",
                "description": description,
                "created_at": datetime.utcnow()
            })
            logger.info(f"Баланс пользователя {user_id} увеличен на {amount}.")
            return {"status": "ok", "details": "Транзакция успешна"}
        else:
            logger.error(f"Не удалось увеличить баланс пользователя {user_id}.")
            return {"status": "error", "details": "Не удалось обновить баланс"}
    except Exception as e:
        logger.error(f"Ошибка при увеличении баланса пользователя: {e}")
        return {"status": "error", "details": f"Ошибка сервера: {str(e)}"}


def debit_user_balance(user_id, amount, description):
    """
    Списывает средства с баланса пользователя и сохраняет описание транзакции.
    :param user_id: ID пользователя
    :param amount: Сумма для списания
    :param description: Описание транзакции
    :return: Статус транзакции
    """
    try:
        amount = round(amount, 2)
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден.")
            return {"status": "error", "details": "Пользователь не найден"}

        current_balance = user.get("money", 0.0)
        if current_balance < amount:
            logger.error(f"Недостаточно средств на балансе пользователя {user_id}.")
            return {"status": "error", "details": "Недостаточно средств на балансе"}

        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"money": -amount}}
        )
        if result.modified_count > 0:
            log_transaction({
                "user_id": user_id,
                "amount": -amount,
                "type": "debit",
                "description": description,
                "created_at": datetime.utcnow()
            })
            logger.info(f"Баланс пользователя {user_id} уменьшен на {amount}.")
            return {"status": "ok", "details": "Транзакция успешна"}
        else:
            logger.error(f"Не удалось уменьшить баланс пользователя {user_id}.")
            return {"status": "error", "details": "Не удалось обновить баланс"}
    except Exception as e:
        logger.error(f"Ошибка при уменьшении баланса пользователя: {e}")
        return {"status": "error", "details": f"Ошибка сервера: {str(e)}"} 