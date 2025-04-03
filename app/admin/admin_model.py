from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime
from bson import ObjectId

class Admin(BaseModel):
    id: Optional[ObjectId]
    iin: Optional[str]
    email: Optional[EmailStr]
    full_name: str
    hashed_password: str
    telegram_id: int
    role: str
    is_verified: bool = False
    last_login: Optional[Dict]
    active_session: Optional[Dict]

    class Config:
        json_encoders = {ObjectId: str}
