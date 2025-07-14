from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime
from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)

# Определение разрешенных категорий для разных типов подписок
SUBSCRIPTION_CATEGORIES = {
    "Economy": ["A1", "A", "B1", "B", "BE"],
    # Для VIP, Royal, School - доступ ко всем категориям, поэтому их здесь нет
}

async def check_active_session(db, user_id: str):
    """Проверяет, нет ли у пользователя уже активного теста."""
    active_lobby = await db.lobbies.find_one({
        "participants": user_id,
        "status": "in_progress"
    })
    if active_lobby:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"У вас уже есть активный тест в лобби {active_lobby['_id']}. Завершите его, чтобы присоединиться к новому.",
                "active_lobby_id": active_lobby['_id']
            }
        )

def validate_guest_join(lobby: dict):
    """Проверяет, могут ли гости присоединиться к этому лобби."""
    # Гости могут присоединяться только к лобби, созданным пользователем с подпиской "School"
    host_subscription_type = lobby.get("host_subscription_type") or lobby.get("subscription_type")
    if not host_subscription_type or host_subscription_type.lower() != "school":
        raise HTTPException(
            status_code=403,
            detail="Гости не могут присоединиться к этому типу лобби."
        )

async def validate_user_subscription(db, user_id: str, lobby: dict):
    """Проверяет, соответствует ли подписка пользователя требованиям лобби."""
    # Получаем тип подписки создателя лобби
    host_subscription_type = lobby.get("host_subscription_type") or lobby.get("subscription_type")
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Валидация подписки: пользователь {user_id}, лобби {lobby.get('_id')}, тип подписки хоста: {host_subscription_type}"
    )
    
    # Если лобби создал School пользователь - всем зарегистрированным пользователям разрешен доступ
    if host_subscription_type and host_subscription_type.lower() == "school":
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ разрешен: лобби создал School пользователь, зарегистрированному пользователю {user_id} разрешен доступ"
        )
        return  # Разрешаем доступ всем зарегистрированным пользователям
    
    # Если лобби создал Royal пользователь - нужна подписка, покрывающая категории
    if host_subscription_type and host_subscription_type.lower() == "royal":
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Проверка Royal лобби: пользователь {user_id}, лобби {lobby.get('_id')}"
        )
        
        required_categories = lobby.get("categories")
        if not required_categories:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ разрешен: Royal лобби без категорий, пользователь {user_id}"
            )
            return  # Если в лобби нет требований по категориям, доступ разрешен

        # Получаем подписку пользователя
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not subscription:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ запрещен: пользователь {user_id} не имеет активной подписки для Royal лобби"
            )
            raise HTTPException(
                status_code=403,
                detail="Для доступа к лобби Royal требуется активная подписка."
            )

        sub_type = subscription.get("subscription_type")
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Проверка подписки пользователя: {user_id}, тип подписки: {sub_type}, требуемые категории: {required_categories}"
        )
        
        # VIP, Royal, School имеют доступ ко всему
        if sub_type in ["Vip", "Royal", "School"]:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ разрешен: пользователь {user_id} имеет премиум подписку {sub_type}"
            )
            return

        # Проверяем другие типы подписок
        allowed_categories = SUBSCRIPTION_CATEGORIES.get(sub_type)
        if not allowed_categories or not set(required_categories).issubset(set(allowed_categories)):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ запрещен: подписка {sub_type} не покрывает категории {required_categories}, разрешены {allowed_categories}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Ваша подписка ({sub_type}) не предоставляет доступ к необходимым для этого лобби категориям."
            )
    
    # Для других типов создателей лобби - стандартная проверка
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Стандартная проверка: пользователь {user_id}, лобби {lobby.get('_id')}, тип хоста: {host_subscription_type}"
    )
    
    required_categories = lobby.get("categories")
    if not required_categories:
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ разрешен: лобби без категорий, пользователь {user_id}"
        )
        return  # Если в лобби нет требований по категориям, доступ разрешен

    # Получаем подписку пользователя
    subscription = await db.subscriptions.find_one({
        "user_id": ObjectId(user_id),
        "is_active": True,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not subscription:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещен: пользователь {user_id} не имеет активной подписки"
        )
        raise HTTPException(
            status_code=403,
            detail="У вас нет активной подписки для доступа к лобби с ограничением по категориям."
        )

    sub_type = subscription.get("subscription_type")
    
    # VIP, Royal, School имеют доступ ко всему
    if sub_type in ["Vip", "Royal", "School"]:
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ разрешен: пользователь {user_id} имеет премиум подписку {sub_type}"
        )
        return

    # Проверяем другие типы подписок
    allowed_categories = SUBSCRIPTION_CATEGORIES.get(sub_type)
    if not allowed_categories or not set(required_categories).issubset(set(allowed_categories)):
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещен: подписка {sub_type} не покрывает категории {required_categories}, разрешены {allowed_categories}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Ваша подписка ({sub_type}) не предоставляет доступ к необходимым для этого лобби категориям."
        ) 