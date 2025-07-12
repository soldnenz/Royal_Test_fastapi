from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

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
    required_categories = lobby.get("categories")
    if not required_categories:
        return  # Если в лобби нет требований по категориям, доступ разрешен

    subscription = await db.subscriptions.find_one({
        "user_id": ObjectId(user_id),
        "is_active": True,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="У вас нет активной подписки для доступа к лобби с ограничением по категориям."
        )

    sub_type = subscription.get("subscription_type")
    
    # VIP, Royal, School имеют доступ ко всему
    if sub_type in ["Vip", "Royal", "School"]:
        return

    # Проверяем другие типы подписок
    allowed_categories = SUBSCRIPTION_CATEGORIES.get(sub_type)
    if not allowed_categories or not set(required_categories).issubset(set(allowed_categories)):
        raise HTTPException(
            status_code=403,
            detail=f"Ваша подписка ({sub_type}) не предоставляет доступ к необходимым для этого лобби категориям."
        ) 