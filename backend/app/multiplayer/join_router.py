import json
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.response import success
from app.core.security import get_current_actor
from app.db.database import db
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip
from app.multiplayer.lobby_utils import get_user_id
from app.multiplayer.ws_utils import create_ws_token
from app.multiplayer.lobby_validator import (
    check_active_session,
    validate_guest_join,
    validate_user_subscription
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("/lobbies/{lobby_id}/join", summary="Присоединиться к лобби")
@rate_limit_ip("lobby_join", max_requests=20, window_seconds=300)
async def join_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Присоединение к существующему лобби с расширенной проверкой.
    """
    user_id = get_user_id(current_user)
    is_guest = current_user.get("is_guest", False)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Попытка присоединения к лобби: пользователь {user_id} к лобби {lobby_id}"
    )

    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")

        # --- НОВЫЕ ПРОВЕРКИ ---
        # 1. Проверка на наличие активного теста у пользователя
        await check_active_session(db, user_id)

        # 2. Проверки для гостя
        if is_guest:
            validate_guest_join(lobby)
        # 3. Проверки для зарегистрированного пользователя
        else:
            await validate_user_subscription(db, user_id, lobby)
        # --- КОНЕЦ НОВЫХ ПРОВЕРОК ---

        if user_id in lobby.get("blacklisted_users", []):
            raise HTTPException(status_code=403, detail="Вы были исключены из этого лобби")

        if lobby["status"] == "finished":
            raise HTTPException(status_code=400, detail="Лобби уже завершено")

        if lobby["status"] == "in_progress":
            if user_id in lobby.get("participants", []):
                return success(data={
                    "message": "Перенаправление на активный тест",
                    "redirect": f"/multiplayer/test/{lobby_id}",
                    "lobby_status": "in_progress"
                })
            else:
                raise HTTPException(status_code=400, detail="Тест уже начался, присоединение невозможно")

        if user_id in lobby.get("participants", []):
            # Генерируем новый WS токен, чтобы пользователь мог переподключиться
            ws_token = await create_ws_token(current_user, lobby_id)

            return success(data={
                "message": "Вы уже участник этого лобби",
                "lobby_id": lobby_id,
                "already_member": True,
                "ws_token": ws_token
            })

        current_participants = len(lobby.get("participants", []))
        max_participants = lobby.get("max_participants", 8)

        if current_participants >= max_participants:
            raise HTTPException(status_code=400, detail=f"Лобби заполнено ({current_participants}/{max_participants})")

        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$addToSet": {"participants": user_id}}
        )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Успешное присоединение: пользователь {user_id} присоединился к лобби {lobby_id}"
        )

        # Генерируем и возвращаем WS токен
        ws_token = await create_ws_token(current_user, lobby_id)
        
        # Получаем имя пользователя для ответа
        user_name = current_user.get("full_name")
        if current_user.get("is_guest", False):
            user_name = f"Гость {user_id[-8:]}"

        return success(data={
            "message": "Успешно присоединились к лобби",
            "lobby_id": lobby_id,
            "user_name": user_name,
            "participants_count": current_participants + 1,
            "max_participants": max_participants,
            "ws_token": ws_token
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка присоединения к лобби: пользователь {user_id}, лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при присоединении к лобби") 