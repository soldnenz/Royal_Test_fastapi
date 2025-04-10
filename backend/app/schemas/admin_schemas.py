from pydantic import BaseModel, EmailStr, constr, root_validator
from typing import Optional

class AdminLogin(BaseModel):
    email: Optional[EmailStr] = None
    iin: Optional[constr(min_length=12, max_length=12)] = None
    password: constr(min_length=8)

    @root_validator(pre=True)
    def check_either_email_or_iin(cls, values):
        if not values.get("email") and not values.get("iin"):
            raise ValueError("Нужно указать либо email, либо ИИН")
        return values

class AdminOut(BaseModel):
    email: Optional[EmailStr]
    iin: Optional[str]
    full_name: str
    role: str
    last_login: Optional[dict]
    is_verified: bool

class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
