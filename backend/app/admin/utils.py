import re
import jwt
from datetime import datetime, timedelta
import os
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict, hours: int = 24):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

def is_strong_password(password: str) -> bool:
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[\W_]", password)
    )

def sanitize_input(value: str) -> str:
    if any(c in value for c in ["$", "{", "}", "[", "]"]):
        raise ValueError("Неправильный ввод")
    return value

def get_ip(request):
    return request.client.host

def get_user_agent(request):
    return request.headers.get("user-agent", "")