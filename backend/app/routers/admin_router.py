from fastapi import APIRouter, Request, Depends, HTTPException, Body
from app.db.database import get_database
from app.admin.utils import decode_token, get_ip, get_user_agent
from app.admin.permissions import is_super_admin, get_current_admin_user
from fastapi.security import HTTPBearer
from bson import ObjectId
from datetime import datetime, timedelta
from app.schemas.user_schemas import UserBanCreate, UserBanOut
from app.core.response import success
from fastapi.encoders import jsonable_encoder
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer()

@router.get("/admin/active")
@rate_limit_ip("admin_session_check", max_requests=30, window_seconds=60)
async def check_active_session(request: Request, db=Depends(get_database)):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_MISSING,
            message=f"Попытка доступа к админ-панели без токена с IP {get_ip(request)}"
        )
        raise HTTPException(status_code=401, detail="Не передан токен")

    payload = decode_token(token)

    admin_id = payload.get("sub")
    ip = get_ip(request)
    ua = get_user_agent(request)

    logger.info(
        section=LogSection.ADMIN,
        subsection=LogSubsection.ADMIN.SESSION_CHECK,
        message=f"Проверка активной сессии администратора {admin_id} с IP {ip}"
    )

    admin = await db.admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка доступа с неизвестным ID администратора {admin_id} с IP {ip}"
        )
        raise HTTPException(status_code=404, detail="Не найден")

    if not admin.get("active_session") or admin["active_session"].get("token") != token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.SESSION_INVALID,
            message=f"Недействительная сессия администратора {admin.get('full_name', 'неизвестен')} ({admin_id}) с IP {ip}"
        )
        raise HTTPException(status_code=401, detail="Сессия недействительна")

    if admin["active_session"].get("ip") != ip or admin["active_session"].get("user_agent") != ua:
        old_ip = admin["active_session"].get("ip", "неизвестен")
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
            message=f"Смена IP/браузера для администратора {admin.get('full_name', 'неизвестен')} ({admin_id}) - старый IP {old_ip}, новый IP {ip} - сессия сброшена"
        )
        raise HTTPException(status_code=401, detail="Сессия сброшена из-за смены IP/UA")

    logger.info(
        section=LogSection.ADMIN,
        subsection=LogSubsection.ADMIN.SESSION_VALIDATED,
        message=f"Успешная проверка сессии администратора {admin.get('full_name', 'неизвестен')} ({admin_id}) с ролью {admin.get('role', 'неизвестна')} с IP {ip}"
    )
    return {"status": "ok", "admin": admin["full_name"], "role": admin["role"]}

@router.get("/admin/list")
@rate_limit_ip("admin_list", max_requests=10, window_seconds=300)
async def list_admins(request: Request, db=Depends(get_database)):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_MISSING,
            message=f"Попытка доступа к списку администраторов без токена с IP {get_ip(request)}"
        )
        raise HTTPException(status_code=401, detail="Не передан токен")

    payload = decode_token(token)
    if not is_super_admin(int(payload.get("sub"))):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка доступа к списку администраторов не-суперадмином {payload.get('sub')} с IP {get_ip(request)}"
        )
        raise HTTPException(status_code=403, detail="Только для суперадминов")

    cursor = db.admins.find({}, {"full_name": 1, "role": 1, "last_login": 1})
    result = []
    async for doc in cursor:
        result.append({"full_name": doc["full_name"], "role": doc["role"], "last_login": doc.get("last_login")})
    
    logger.info(
        section=LogSection.ADMIN,
        subsection=LogSubsection.ADMIN.LIST_ACCESS,
        message=f"Суперадминистратор получил список из {len(result)} администраторов с IP {get_ip(request)}"
    )
    return result

# User ban system
@router.post("/ban", response_model=dict)
@rate_limit_ip("user_ban", max_requests=15, window_seconds=300)
async def ban_user(
    ban_data: UserBanCreate,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Пользователь {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) с ролью {current_user['role']} пытается заблокировать пользователя без прав администратора"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может блокировать пользователей"}
        )
    
    try:
        # Check if user exists
        user = await db.users.find_one({"_id": ObjectId(ban_data.user_id)})
        if not user:
            logger.warning(
                section=LogSection.ADMIN,
                subsection=LogSubsection.ADMIN.USER_BAN,
                message=f"Администратор {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) пытается заблокировать несуществующего пользователя {ban_data.user_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )
        
        # Deactivate any existing active bans
        await db.user_bans.update_many(
            {"user_id": ObjectId(ban_data.user_id), "is_active": True},
            {"$set": {"is_active": False}}
        )
        
        now = datetime.utcnow()
        ban_until = None
        
        if ban_data.ban_type == "temporary":
            ban_until = now + timedelta(days=ban_data.ban_days)
        
        # Create ban record
        ban = {
            "user_id": ObjectId(ban_data.user_id),
            "admin_id": ObjectId(current_user["_id"]),
            "admin_name": current_user["full_name"],
            "ban_type": ban_data.ban_type,
            "ban_until": ban_until,
            "reason": ban_data.reason,
            "created_at": now,
            "is_active": True
        }
        
        result = await db.user_bans.insert_one(ban)
        
        # Update user record to mark as banned
        await db.users.update_one(
            {"_id": ObjectId(ban_data.user_id)},
            {
                "$set": {
                    "is_banned": True,
                    "ban_info": {
                        "ban_id": str(result.inserted_id),
                        "ban_type": ban_data.ban_type,
                        "ban_until": ban_until,
                        "reason": ban_data.reason
                    }
                }
            }
        )
        
        # Mark all user tokens as inactive instead of deleting them
        await db.tokens.update_many(
            {"user_id": ObjectId(ban_data.user_id)},
            {"$set": {"revoked": True}}
        )
        
        ban["_id"] = str(result.inserted_id)
        ban["user_id"] = str(ban["user_id"])
        ban["admin_id"] = str(ban["admin_id"])
        
        ban_type_str = "навсегда" if ban_data.ban_type == "permanent" else f"на {ban_data.ban_days} дней"
        ban_until_str = ban_until.strftime("%H:%M:%S %d.%m.%Y") if ban_until else "навсегда"
        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_BAN,
            message=f"Пользователь {user.get('full_name', 'неизвестен')} ({ban_data.user_id}) заблокирован администратором {current_user['full_name']} ({current_user['_id']}) {ban_type_str} до {ban_until_str} - причина: {ban_data.reason}"
        )
        
        return success(data=jsonable_encoder(ban))
        
    except Exception as e:
        logger.error(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_BAN,
            message=f"Ошибка при блокировке пользователя {ban_data.user_id} администратором {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}): {e}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при блокировке пользователя", "hint": str(e)}
        )

@router.post("/unban/{user_id}", response_model=dict)
@rate_limit_ip("user_unban", max_requests=15, window_seconds=300)
async def unban_user(
    request: Request,
    user_id: str,
    unban_data: dict = Body(...),
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Пользователь {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) с ролью {current_user['role']} пытается разблокировать пользователя без прав администратора"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может разблокировать пользователей"}
        )
    
    try:
        # Check if user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(
                section=LogSection.ADMIN,
                subsection=LogSubsection.ADMIN.USER_UNBAN,
                message=f"Администратор {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) пытается разблокировать несуществующего пользователя {user_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )
        
        if not user.get("is_banned", False):
            logger.info(
                section=LogSection.ADMIN,
                subsection=LogSubsection.ADMIN.USER_UNBAN,
                message=f"Администратор {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) пытается разблокировать пользователя {user.get('full_name', 'неизвестен')} ({user_id}) который не заблокирован"
            )
            return success(data={"message": "Пользователь не заблокирован"})
        
        # Get the reason for unbanning from request body
        unban_reason = unban_data.get("reason", "Разблокировка администратором")
        
        # Deactivate all active bans
        await db.user_bans.update_many(
            {"user_id": ObjectId(user_id), "is_active": True},
            {
                "$set": {
                    "is_active": False,
                    "unbanned_by": {
                        "admin_id": str(current_user["_id"]),
                        "admin_name": current_user["full_name"],
                        "timestamp": datetime.utcnow(),
                        "reason": unban_reason
                    }
                }
            }
        )
        
        # Update user record
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {"is_banned": False},
                "$unset": {"ban_info": ""}
            }
        )
        
        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_UNBAN,
            message=f"Пользователь {user.get('full_name', 'неизвестен')} ({user_id}) разблокирован администратором {current_user['full_name']} ({current_user['_id']}) - причина разблокировки: {unban_reason}"
        )
        
        return success(data={"message": "Пользователь успешно разблокирован"})
        
    except Exception as e:
        logger.error(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.USER_UNBAN,
            message=f"Ошибка при разблокировке пользователя {user_id} администратором {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}): {e}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при разблокировке пользователя", "hint": str(e)}
        )

@router.get("/bans/{user_id}", response_model=dict)
@rate_limit_ip("admin_bans_view", max_requests=30, window_seconds=60)
async def get_user_bans(
    user_id: str,
    request: Request,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in ["admin", "moderator"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Пользователь {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) с ролью {current_user['role']} пытается просмотреть историю банов без достаточных прав"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )
    
    try:
        # Check if user exists first
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(
                section=LogSection.ADMIN,
                subsection=LogSubsection.ADMIN.BAN_HISTORY,
                message=f"Администратор {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) пытается просмотреть историю банов несуществующего пользователя {user_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )
            
        bans = await db.user_bans.find({"user_id": ObjectId(user_id)}).sort("created_at", -1).to_list(length=100)
        
        for ban in bans:
            ban["_id"] = str(ban["_id"])
            ban["user_id"] = str(ban["user_id"])
            ban["admin_id"] = str(ban["admin_id"])
            
        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.BAN_HISTORY,
            message=f"Администратор {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}) с ролью {current_user['role']} просмотрел историю банов пользователя {user.get('full_name', 'неизвестен')} ({user_id}) - найдено {len(bans)} записей"
        )
        return success(data=jsonable_encoder(bans))
        
    except Exception as e:
        logger.error(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.BAN_HISTORY,
            message=f"Ошибка при получении истории банов пользователя {user_id} администратором {current_user.get('full_name', 'неизвестен')} ({current_user['_id']}): {e}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при получении истории банов", "hint": str(e)}
        )

