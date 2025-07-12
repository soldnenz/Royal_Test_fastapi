import socketio
import json
import hashlib
from redis.asyncio import Redis
from config import settings
from redis_client import redis_client
from db_client import get_lobby_by_id, get_user_by_id
import datetime

# Создаем экземпляр Socket.IO сервера
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    # Увеличиваем пинг-таймаут для стабильности
    ping_timeout=15, 
    ping_interval=10
)

def hash_token(token: str) -> str:
    """Хэширует токен для безопасного сравнения."""
    return hashlib.sha256(token.encode()).hexdigest()

class MultiplayerNamespace(socketio.AsyncNamespace):
    """
    Namespace для всей мультиплеерной логики.
    Обеспечивает изоляцию и более чистую структуру.
    """
    
    async def _get_user_sid(self, lobby_id: str, user_id: str) -> str | None:
        """Находит SID пользователя по его ID в конкретной комнате."""
        participants = sio.manager.get_participants(self.namespace, lobby_id)
        for sid_tuple in participants:
            sid = sid_tuple[0]
            try:
                session = await self.get_session(sid)
                if session and session.get('user_id') == user_id:
                    return sid
            except Exception:
                # Сессия может быть недоступна, если пользователь уже отключается
                continue
        return None

    async def _get_online_user_ids(self, lobby_id: str):
        """Собирает ID всех онлайн-пользователей в комнате."""
        online_ids = []
        participants = list(sio.manager.get_participants(self.namespace, lobby_id))
        for sid_tuple in participants:
            sid = sid_tuple[0]
            try:
                session = await self.get_session(sid)
                if session and session.get('user_id'):
                    online_ids.append(session.get('user_id'))
            except Exception:
                continue
        return online_ids

    async def _broadcast_online_status(self, lobby_id: str):
        """Рассылает всем в лобби обновленный список онлайн-пользователей."""
        online_users = await self._get_online_user_ids(lobby_id)
        await self.emit('online_status_update', {
            'online_users': online_users
        }, room=lobby_id)


    async def on_connect(self, sid, environ, auth):
        """Аутентификация пользователя при подключении."""
        print(f"[{sid}] Auth attempt for namespace {self.namespace}")
        token = auth.get("token")
        if not token:
            raise socketio.exceptions.ConnectionRefusedError("Auth failed: token missing")
        
        hashed_token = hash_token(token)
        redis_conn = await redis_client.get_connection()
        user_info_raw = await redis_conn.get(f"ws_token:{hashed_token}")

        if not user_info_raw:
            raise socketio.exceptions.ConnectionRefusedError("Auth failed: invalid token")

        user_info = json.loads(user_info_raw)
        await self.save_session(sid, user_info)
        print(f"[{sid}] User {user_info.get('user_id')} authenticated successfully.")

    async def on_join_lobby(self, sid, data):
        """Присоединение аутентифицированного пользователя к комнате лобби."""
        session = await self.get_session(sid)
        lobby_id = data.get('lobby_id')

        if not lobby_id:
            await self.emit('error', {'message': 'Lobby ID is required'}, to=sid)
            return

        user_id = session.get('user_id')
        print(f"[{sid}] User {user_id} attempting to join lobby {lobby_id}")

        await self.enter_room(sid, lobby_id)
        session['lobby_id'] = lobby_id
        await self.save_session(sid, session)
        
        print(f"[{sid}] User {user_id} joined lobby {lobby_id}. Notifying room.")
        # 1. Уведомляем всех, КРОМЕ СЕБЯ, что зашел новый юзер
        await self.emit('user_joined', {'user_id': user_id}, room=lobby_id, skip_sid=sid)
        # 2. Рассылаем ВСЕМ (включая себя) обновленный статус онлайн
        await self._broadcast_online_status(lobby_id)


    async def on_disconnect(self, sid):
        """Обработка отключения пользователя."""
        session = await self.get_session(sid)
        if not session:
            return

        lobby_id = session.get('lobby_id')
        user_id = session.get('user_id')
        print(f"[{sid}] User {user_id} disconnected from lobby {lobby_id}")
        
        if lobby_id:
            # Уведомляем всех, что пользователь вышел и обновляем список онлайн
            await self.emit('user_left', {'user_id': user_id}, room=lobby_id)
            await self._broadcast_online_status(lobby_id)
        
    # --- Host Actions ---

    async def on_start_test(self, sid, data):
        """Событие для начала теста (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')

        if not lobby_id:
            print(f"[{sid}] Start test failed: Missing lobby_id")
            return await self.emit('error', {'message': 'Missing lobby_id'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Start test failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Start test permission denied: User {host_id} is not host of lobby {lobby_id} (host: {lobby.get('host_id')})")
                return await self.emit('error', {'message': 'Permission denied: Only host can start the test'}, to=sid)
            
            # Дополнительная проверка: убеждаемся, что лобби еще не началось
            if lobby.get('status') != 'waiting':
                print(f"[{sid}] Start test failed: Lobby {lobby_id} status is '{lobby.get('status')}', not 'waiting'")
                return await self.emit('error', {'message': 'Lobby is already started or closed'}, to=sid)
            
            print(f"[{sid}] Host {host_id} successfully starting test for lobby {lobby_id}")
            
            # Уведомляем всех участников о начале теста
            await self.emit('lobby_started', {
                'lobby_id': lobby_id,
                'started_by': host_id,
                'timestamp': json.dumps(datetime.datetime.now().isoformat())
            }, room=lobby_id)

        except Exception as e:
            print(f"Error during start_test: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_kick_user(self, sid, data):
        """Событие для кика игрока (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')
        target_user_id = data.get('target_user_id')

        if not all([lobby_id, target_user_id]):
            print(f"[{sid}] Kick failed: Missing required data")
            return await self.emit('error', {'message': 'Missing data for kick'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Kick failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Kick permission denied: User {host_id} is not host of lobby {lobby_id} (host: {lobby.get('host_id')})")
                return await self.emit('error', {'message': 'Permission denied: Only host can kick users'}, to=sid)

            target_sid = await self._get_user_sid(lobby_id, target_user_id)
            if not target_sid:
                print(f"[{sid}] Kick failed: Target user {target_user_id} not found in lobby {lobby_id}")
                return await self.emit('error', {'message': 'User not found in lobby'}, to=sid)
            
            print(f"[{sid}] Host {host_id} successfully kicking {target_user_id} (SID: {target_sid}) from lobby {lobby_id}")
            
            # Отправляем кикнутому игроку персональное событие и принудительно отключаем его
            await self.emit('kicked', {'reason': 'You have been kicked by the host.'}, to=target_sid)
            await self.disconnect(target_sid)

        except Exception as e:
            print(f"Error during kick_user: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_close_lobby(self, sid, data):
        """Событие для закрытия лобби (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')

        if not lobby_id:
            print(f"[{sid}] Close lobby failed: Missing lobby_id")
            return await self.emit('error', {'message': 'Missing lobby_id'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Close lobby failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Close lobby permission denied: User {host_id} is not host of lobby {lobby_id} (host: {lobby.get('host_id')})")
                return await self.emit('error', {'message': 'Permission denied: Only host can close the lobby'}, to=sid)

            print(f"[{sid}] Host {host_id} successfully closing lobby {lobby_id}")

            # Уведомляем всех в комнате о закрытии и закрываем комнату
            await self.emit('lobby_closed', {'reason': 'The host has closed the lobby.'}, room=lobby_id)
            await self.close_room(lobby_id)

        except Exception as e:
            print(f"Error during close_lobby: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

# Регистрируем Namespace с путем /ws, как ожидает клиент
sio.register_namespace(MultiplayerNamespace('/ws'))

# Оборачиваем ASGI-приложением для FastAPI
sio_app = socketio.ASGIApp(sio) 