import uvicorn
from fastapi import FastAPI
import socketio

# Импортируем экземпляр sio_app из socket_manager, а не sio
from socket_manager import sio_app, sio
# Импортируем экземпляр db_client, а не класс DBClient
from db_client import db_client
from redis_client import redis_client

# Создаем приложение FastAPI
app = FastAPI()

# Монтируем FastAPI как под-приложение к Socket.IO
# sio_app теперь является основным приложением
app.mount("/", sio_app)

@app.on_event("startup")
async def startup():
    """Действия при старте сервера."""
    # Соединение с БД и Redis теперь управляется их модулями при импорте.
    # Добавим проверку соединения для уверенности.
    try:
        await db_client.db.command('ping')
        print("INFO:     MongoDB connection verified.")
    except Exception as e:
        print(f"ERROR:    MongoDB connection verification failed: {e}")
    
    try:
        redis_conn = await redis_client.get_connection()
        await redis_conn.ping()
        print("INFO:     Redis connection verified.")
    except Exception as e:
        print(f"ERROR:    Redis connection verification failed: {e}")

    print("INFO:     Application startup complete.")


@app.on_event("shutdown")
async def shutdown():
    """Действия при остановке сервера."""
    await db_client.close()
    await redis_client.disconnect()
    print("INFO:     Application shutdown complete.")


if __name__ == '__main__':
    # Запускаем uvicorn с основным приложением FastAPI,
    # которое теперь содержит в себе sio_app
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True) 