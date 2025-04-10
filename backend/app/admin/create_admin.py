import asyncio
from app.db.database import db
from app.admin.utils import hash_password, is_strong_password

async def create_admin():
    iin = input("IIN (или пропусти): ") or None
    email = input("Email (или пропусти): ") or None
    full_name = input("ФИО: ")
    telegram_id = int(input("Telegram ID: "))
    role = input("Роль (admin/superadmin): ")
    password = input("Пароль: ")

    if not is_strong_password(password):
        print("Пароль слишком слабый. Требуется: минимум 8 символов, заглавная, цифра, спецсимвол.")
        return

    hashed = hash_password(password)

    await db.admins.insert_one({
        "iin": iin,
        "email": email,
        "full_name": full_name,
        "telegram_id": telegram_id,
        "role": role,
        "hashed_password": hashed,
        "is_verified": True,
        "last_login": None,
        "active_session": None
    })

    print("✅ Администратор создан")

if __name__ == "__main__":
    asyncio.run(create_admin())