from fastapi import APIRouter, Request, Depends, HTTPException
from app.db.database import db
from app.admin.utils import decode_token, get_ip, get_user_agent
from app.admin.permissions import is_super_admin
from fastapi.security import HTTPBearer
from bson import ObjectId

router = APIRouter()
security = HTTPBearer()

@router.get("/admin/active")
async def check_active_session(request: Request, credentials=Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    admin_id = payload.get("sub")
    ip = get_ip(request)
    ua = get_user_agent(request)

    admin = await db.admins.find_one({"_id": ObjectId(admin_id)})
    if not admin:
        raise HTTPException(status_code=404, detail="Не найден")

    if not admin.get("active_session") or admin["active_session"].get("token") != token:
        raise HTTPException(status_code=401, detail="Сессия недействительна")

    if admin["active_session"].get("ip") != ip or admin["active_session"].get("user_agent") != ua:
        raise HTTPException(status_code=401, detail="Сессия сброшена из-за смены IP/UA")

    return {"status": "ok", "admin": admin["full_name"], "role": admin["role"]}

@router.get("/admin/list")
async def list_admins(credentials=Depends(security)):
    payload = decode_token(credentials.credentials)
    if not is_super_admin(int(payload.get("sub"))):
        raise HTTPException(status_code=403, detail="Только для суперадминов")

    cursor = db.admins.find({}, {"full_name": 1, "role": 1, "last_login": 1})
    result = []
    async for doc in cursor:
        result.append({"full_name": doc["full_name"], "role": doc["role"], "last_login": doc.get("last_login")})
    return result

