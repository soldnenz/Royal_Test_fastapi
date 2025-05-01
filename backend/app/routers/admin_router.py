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
import logging

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

@router.get("/admin/active")
async def check_active_session(request: Request, db=Depends(get_database)):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(f"Security: Access attempt without token from IP {get_ip(request)}")
        raise HTTPException(status_code=401, detail="Не передан токен")

    payload = decode_token(token)

    admin_id = payload.get("sub")
    ip = get_ip(request)
    ua = get_user_agent(request)

    logger.info(f"Security: Admin session check - ID: {admin_id}, IP: {ip}")

    admin = await db.admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        logger.warning(f"Security: Unknown admin ID {admin_id} attempted access from IP {ip}")
        raise HTTPException(status_code=404, detail="Не найден")

    if not admin.get("active_session") or admin["active_session"].get("token") != token:
        logger.warning(f"Security: Invalid session for admin {admin_id} from IP {ip}")
        raise HTTPException(status_code=401, detail="Сессия недействительна")

    if admin["active_session"].get("ip") != ip or admin["active_session"].get("user_agent") != ua:
        logger.warning(f"Security: IP/UA change for admin {admin_id}. Old: {admin['active_session'].get('ip')}, New: {ip}")
        raise HTTPException(status_code=401, detail="Сессия сброшена из-за смены IP/UA")

    logger.info(f"Security: Successful admin session check for {admin['full_name']} ({admin_id})")
    return {"status": "ok", "admin": admin["full_name"], "role": admin["role"]}

@router.get("/admin/list")
async def list_admins(request: Request, db=Depends(get_database)):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(f"Security: Access attempt to admin list without token from IP {get_ip(request)}")
        raise HTTPException(status_code=401, detail="Не передан токен")

    payload = decode_token(token)
    if not is_super_admin(int(payload.get("sub"))):
        logger.warning(f"Security: Non-superadmin attempt to access admin list from IP {get_ip(request)}")
        raise HTTPException(status_code=403, detail="Только для суперадминов")

    cursor = db.admins.find({}, {"full_name": 1, "role": 1, "last_login": 1})
    result = []
    async for doc in cursor:
        result.append({"full_name": doc["full_name"], "role": doc["role"], "last_login": doc.get("last_login")})
    
    logger.info(f"Admin list accessed by superadmin from IP {get_ip(request)}")
    return result

# User ban system
@router.post("/ban", response_model=dict)
async def ban_user(
    ban_data: UserBanCreate,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(f"Security: Non-admin user {current_user['_id']} attempted to ban a user")
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может блокировать пользователей"}
        )
    
    try:
        # Check if user exists
        user = await db.users.find_one({"_id": ObjectId(ban_data.user_id)})
        if not user:
            logger.warning(f"Security: Admin {current_user['_id']} attempted to ban non-existent user {ban_data.user_id}")
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
        
        # Invalidate all user tokens
        await db.tokens.delete_many({"user_id": ObjectId(ban_data.user_id)})
        
        ban["_id"] = str(result.inserted_id)
        ban["user_id"] = str(ban["user_id"])
        ban["admin_id"] = str(ban["admin_id"])
        
        logger.info(f"[BAN] Пользователь {ban_data.user_id} заблокирован админом {current_user['_id']} ({current_user['full_name']}) - Тип: {ban_data.ban_type}, Причина: {ban_data.reason}")
        
        return success(data=jsonable_encoder(ban))
        
    except Exception as e:
        logger.error(f"[BAN ERROR] Ошибка при блокировке пользователя: {e}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при блокировке пользователя", "hint": str(e)}
        )

@router.post("/unban/{user_id}", response_model=dict)
async def unban_user(
    user_id: str,
    unban_data: dict = Body(...),
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] != "admin":
        logger.warning(f"Security: Non-admin user {current_user['_id']} attempted to unban a user")
        raise HTTPException(
            status_code=403,
            detail={"message": "Только администратор может разблокировать пользователей"}
        )
    
    try:
        # Check if user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(f"Security: Admin {current_user['_id']} attempted to unban non-existent user {user_id}")
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )
        
        if not user.get("is_banned", False):
            logger.info(f"Admin {current_user['_id']} attempted to unban user {user_id} who is not banned")
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
        
        logger.info(f"[UNBAN] Пользователь {user_id} разблокирован админом {current_user['_id']} ({current_user['full_name']}) - Причина: {unban_reason}")
        
        return success(data={"message": "Пользователь успешно разблокирован"})
        
    except Exception as e:
        logger.error(f"[UNBAN ERROR] Ошибка при разблокировке пользователя: {e}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при разблокировке пользователя", "hint": str(e)}
        )

@router.get("/bans/{user_id}", response_model=dict)
async def get_user_bans(
    user_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_admin_user)
):
    if current_user["role"] not in ["admin", "moderator"]:
        logger.warning(f"Security: Unauthorized user {current_user['_id']} attempted to view ban history")
        raise HTTPException(
            status_code=403,
            detail={"message": "Недостаточно прав"}
        )
    
    try:
        # Check if user exists first
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(f"Admin {current_user['_id']} attempted to view bans for non-existent user {user_id}")
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )
            
        bans = await db.user_bans.find({"user_id": ObjectId(user_id)}).sort("created_at", -1).to_list(length=100)
        
        for ban in bans:
            ban["_id"] = str(ban["_id"])
            ban["user_id"] = str(ban["user_id"])
            ban["admin_id"] = str(ban["admin_id"])
            
        logger.info(f"Admin {current_user['_id']} viewed ban history for user {user_id}")
        return success(data=jsonable_encoder(bans))
        
    except Exception as e:
        logger.error(f"[GET BANS ERROR] Ошибка при получении истории банов: {e}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ошибка при получении истории банов", "hint": str(e)}
        )

