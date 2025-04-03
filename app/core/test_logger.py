from datetime import datetime
from app.db.database import get_database


async def log_action(
    action: str,
    user_id: str,
    user_name: str,
    metadata: dict = None,
):
    """
    Логирует действие администратора или пользователя.

    :param action: тип действия (например, create_test, delete_question)
    :param user_id: ObjectId пользователя (строкой)
    :param user_name: ФИО пользователя
    :param metadata: доп. инфа — ID теста, вопроса и т.п.
    """
    db = await get_database()
    log_entry = {
        "timestamp": datetime.utcnow(),
        "action": action,
        "user_id": user_id,
        "user_name": user_name,
        "metadata": metadata or {}
    }
    await db.action_logs.insert_one(log_entry)
