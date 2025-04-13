import uuid
import random
import string
from app.db.database import db

async def generate_unique_lobby_id():
    """
    Generates a user-friendly unique ID for lobbies.
    Format: 6 characters, alphanumeric, uppercase (e.g. "AB12CD")
    Ensures uniqueness by checking against existing lobbies in the database.
    """
    while True:
        # Generate a random 6-character alphanumeric code (uppercase letters and numbers)
        chars = string.ascii_uppercase + string.digits
        lobby_id = ''.join(random.choice(chars) for _ in range(6))
        
        # Check if this ID already exists in the database
        existing = await db.lobbies.find_one({"_id": lobby_id})
        if not existing:
            return lobby_id
            
def generate_lobby_id_sync():
    """
    Synchronous version for cases where async isn't available.
    Less safe (doesn't check for duplicates) but works as a fallback.
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))