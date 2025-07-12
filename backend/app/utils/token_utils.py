import jwt
from datetime import datetime, timedelta
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

def create_ws_token(user_id: str, lobby_id: str, role: str, nickname: str) -> str:
    """
    Creates a unified WebSocket token that the backend_ws service can verify.
    The token is stored in Redis by the main backend and read by the ws backend.
    """
    # The token itself doesn't need a long expiry if it's a one-time use for session creation,
    # but we give it a generous window to account for delays. The Redis session expiry is the real controller.
    expire = datetime.utcnow() + timedelta(hours=4) 
    
    to_encode = {
        "user_id": str(user_id),
        "lobby_id": str(lobby_id),
        "role": role,
        "nickname": nickname,
        "exp": expire,
        "type": "websocket_auth" # Differentiate from standard access tokens
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 