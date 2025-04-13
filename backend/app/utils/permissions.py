# app/utils/permissions.py
from fastapi import HTTPException

def require_host(lobby, user_id: str):
    if lobby["host_id"] != user_id:
        raise HTTPException(status_code=403, detail="Operation allowed only for lobby host")

def require_participant(lobby, user_id: str):
    if user_id not in lobby["participants"]:
        raise HTTPException(status_code=403, detail="User is not a participant of this lobby")
