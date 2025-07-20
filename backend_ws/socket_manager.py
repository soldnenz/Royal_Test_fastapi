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
        print(f"[DEBUG] Getting online users for lobby {lobby_id}, participants count: {len(participants)}")
        for sid_tuple in participants:
            sid = sid_tuple[0]
            try:
                session = await self.get_session(sid)
                if session and session.get('user_id'):
                    user_id = session.get('user_id')
                    online_ids.append(user_id)
                    print(f"[DEBUG] Found online user: {user_id} (SID: {sid})")
            except Exception as e:
                print(f"[DEBUG] Error getting session for SID {sid}: {e}")
                continue
        print(f"[DEBUG] Final online users for lobby {lobby_id}: {online_ids}")
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
            # Уведомляем всех, КРОМЕ отключившегося пользователя, что пользователь вышел
            await self.emit('user_left', {'user_id': user_id}, room=lobby_id, skip_sid=sid)
            
            # Получаем список онлайн пользователей и вручную исключаем отключившегося
            online_users = await self._get_online_user_ids(lobby_id)
            if user_id in online_users:
                online_users.remove(user_id)
                print(f"[DEBUG] Manually removed {user_id} from online users")
            
            # Отправляем обновленный список онлайн пользователей
            await self.emit('online_status_update', {
                'online_users': online_users
            }, room=lobby_id)
        
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
            
            # Проверяем статус лобби
            lobby_status = lobby.get('status')
            if lobby_status == 'waiting':
                print(f"[{sid}] Host {host_id} successfully starting test for lobby {lobby_id}")
            elif lobby_status == 'in_progress':
                print(f"[{sid}] Host {host_id} requesting test start for already started lobby {lobby_id}")
            else:
                print(f"[{sid}] Start test failed: Lobby {lobby_id} status is '{lobby_status}', not 'waiting' or 'in_progress'")
                return await self.emit('error', {'message': 'Lobby is already closed or finished'}, to=sid)
            
            # Уведомляем всех участников о начале теста (или переходе к уже запущенному тесту)
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

            # Проверяем, что пользователь находится в комнате (онлайн)
            target_sid = await self._get_user_sid(lobby_id, target_user_id)
            if not target_sid:
                print(f"[{sid}] Kick failed: Target user {target_user_id} not found in lobby {lobby_id} (user may have already left)")
                # Не возвращаем ошибку, так как пользователь мог уже выйти
                # Просто уведомляем хоста, что кик не нужен
                return await self.emit('kick_success', {'message': 'User already left the lobby'}, to=sid)
            
            print(f"[{sid}] Host {host_id} successfully kicking {target_user_id} (SID: {target_sid}) from lobby {lobby_id}")
            
            # Отправляем кикнутому игроку персональное событие и принудительно отключаем его
            await self.emit('kicked', {'reason': 'You have been kicked by the host.'}, to=target_sid)
            await self.disconnect(target_sid)
            
            # Уведомляем всех остальных участников о кике для обновления списка
            await self.emit('participant_kicked', {
                'user_id': target_user_id,
                'kicked_by': host_id
            }, room=lobby_id, skip_sid=target_sid)

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

    # --- Participant Actions ---

    async def on_participant_answered(self, sid, data):
        """Событие когда участник отвечает на вопрос."""
        session = await self.get_session(sid)
        user_id = session.get('user_id')
        lobby_id = data.get('lobby_id')
        question_id = data.get('question_id')
        answer_index = data.get('answer_index')

        if not all([lobby_id, question_id, answer_index is not None]):
            print(f"[{sid}] Participant answered failed: Missing required data")
            return await self.emit('error', {'message': 'Missing data for answer'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Participant answered failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
            
            # Проверяем, что пользователь является участником лобби
            if user_id not in lobby.get('participants', []):
                print(f"[{sid}] Participant answered failed: User {user_id} is not participant of lobby {lobby_id}")
                return await self.emit('error', {'message': 'You are not a participant of this lobby'}, to=sid)

            print(f"[{sid}] Participant {user_id} answered question {question_id} with answer {answer_index} in lobby {lobby_id}")
            
            # Отправляем детальную информацию хосту о том, на какой вариант ответил участник
            host_sid = await self._get_user_sid(lobby_id, str(lobby.get('host_id')))
            if host_sid and host_sid != sid:
                await self.emit('participant_answer_details', {
                    'user_id': user_id,
                    'question_id': question_id,
                    'answer_index': answer_index,
                    'lobby_id': lobby_id
                }, to=host_sid)
            
            # Отправляем всем участникам (кроме отвечающего) общую информацию о том, что кто-то ответил
            await self.emit('participant_answered', {
                'user_id': user_id,
                'question_id': question_id,
                'lobby_id': lobby_id
            }, room=lobby_id, skip_sid=sid)

        except Exception as e:
            print(f"Error during participant_answered: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_participant_answer_details(self, sid, data):
        """Событие для отправки детальной информации об ответе участника."""
        session = await self.get_session(sid)
        user_id = session.get('user_id')
        lobby_id = data.get('lobby_id')
        question_id = data.get('question_id')
        answer_index = data.get('answer_index')
        is_host = data.get('is_host', False)

        if not all([lobby_id, question_id, answer_index is not None]):
            print(f"[{sid}] Participant answer details failed: Missing required data")
            return await self.emit('error', {'message': 'Missing data for answer'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Participant answer details failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
            
            # Проверяем, что пользователь является участником лобби
            if user_id not in lobby.get('participants', []):
                print(f"[{sid}] Participant answer details failed: User {user_id} is not participant of lobby {lobby_id}")
                return await self.emit('error', {'message': 'You are not a participant of this lobby'}, to=sid)

            print(f"[{sid}] Participant {user_id} sending answer details for question {question_id} with answer {answer_index} in lobby {lobby_id}")
            
            if is_host:
                # Если это хост, отправляем детали всем участникам
                await self.emit('participant_answer_details', {
                    'user_id': user_id,
                    'question_id': question_id,
                    'answer_index': answer_index,
                    'lobby_id': lobby_id,
                    'is_host': True
                }, room=lobby_id)
            else:
                # Если это обычный участник, отправляем детали только хосту
                host_sid = await self._get_user_sid(lobby_id, str(lobby.get('host_id')))
                if host_sid and host_sid != sid:
                    await self.emit('participant_answer_details', {
                        'user_id': user_id,
                        'question_id': question_id,
                        'answer_index': answer_index,
                        'lobby_id': lobby_id,
                        'is_host': False
                    }, to=host_sid)

        except Exception as e:
            print(f"Error during participant_answer_details: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_show_correct_answer(self, sid, data):
        """Событие для показа правильного ответа (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')
        question_id = data.get('question_id')

        if not all([lobby_id, question_id]):
            print(f"[{sid}] Show correct answer failed: Missing required data")
            return await self.emit('error', {'message': 'Missing data for show answer'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Show correct answer failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Show correct answer permission denied: User {host_id} is not host of lobby {lobby_id}")
                return await self.emit('error', {'message': 'Permission denied: Only host can show answers'}, to=sid)

            print(f"[{sid}] Host {host_id} showing correct answer for question {question_id} in lobby {lobby_id}")
            
            # Уведомляем всех участников о показе правильного ответа
            await self.emit('correct_answer_shown', {
                'question_id': question_id,
                'lobby_id': lobby_id,
                'shown_by': host_id
            }, room=lobby_id)

        except Exception as e:
            print(f"Error during show_correct_answer: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_next_question(self, sid, data):
        """Событие для перехода к следующему вопросу (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')
        question_index = data.get('question_index')

        if not all([lobby_id, question_index is not None]):
            print(f"[{sid}] Next question failed: Missing required data")
            return await self.emit('error', {'message': 'Missing data for next question'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Next question failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Next question permission denied: User {host_id} is not host of lobby {lobby_id}")
                return await self.emit('error', {'message': 'Permission denied: Only host can move to next question'}, to=sid)

            print(f"[{sid}] Host {host_id} moving to next question {question_index} in lobby {lobby_id}")
            
            # Уведомляем всех участников о переходе к следующему вопросу
            await self.emit('next_question', {
                'question_index': question_index,
                'lobby_id': lobby_id,
                'moved_by': host_id
            }, room=lobby_id)

        except Exception as e:
            print(f"Error during next_question: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_test_finished(self, sid, data):
        """Событие для завершения теста (только для хоста)."""
        session = await self.get_session(sid)
        host_id = session.get('user_id')
        lobby_id = data.get('lobby_id')

        if not lobby_id:
            print(f"[{sid}] Test finished failed: Missing lobby_id")
            return await self.emit('error', {'message': 'Missing lobby_id'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Test finished failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
                
            if str(lobby.get('host_id')) != host_id:
                print(f"[{sid}] Test finished permission denied: User {host_id} is not host of lobby {lobby_id}")
                return await self.emit('error', {'message': 'Permission denied: Only host can finish the test'}, to=sid)

            print(f"[{sid}] Host {host_id} finishing test for lobby {lobby_id}")
            
            # Уведомляем всех участников о завершении теста
            await self.emit('test_finished', {
                'lobby_id': lobby_id,
                'finished_by': host_id,
                'timestamp': json.dumps(datetime.datetime.now().isoformat())
            }, room=lobby_id)

        except Exception as e:
            print(f"Error during test_finished: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

    async def on_leave_lobby(self, sid, data):
        """Событие для выхода из лобби (для всех участников кроме хоста)."""
        session = await self.get_session(sid)
        user_id = session.get('user_id')
        lobby_id = data.get('lobby_id')

        if not lobby_id:
            print(f"[{sid}] Leave lobby failed: Missing lobby_id")
            return await self.emit('error', {'message': 'Missing lobby_id'}, to=sid)

        try:
            lobby = await get_lobby_by_id(lobby_id)
            if not lobby:
                print(f"[{sid}] Leave lobby failed: Lobby {lobby_id} not found")
                return await self.emit('error', {'message': 'Lobby not found'}, to=sid)
            
            # Проверяем, что пользователь является участником лобби
            if user_id not in lobby.get('participants', []):
                print(f"[{sid}] Leave lobby failed: User {user_id} is not participant of lobby {lobby_id}")
                return await self.emit('error', {'message': 'You are not a participant of this lobby'}, to=sid)
            
            # Проверяем, что пользователь не является хостом
            if str(lobby.get('host_id')) == user_id:
                print(f"[{sid}] Leave lobby failed: Host {user_id} cannot leave lobby {lobby_id}")
                return await self.emit('error', {'message': 'Host cannot leave lobby. Use close lobby instead.'}, to=sid)

            print(f"[{sid}] User {user_id} leaving lobby {lobby_id}")
            
            # Уведомляем всех участников (кроме выходящего) о выходе пользователя
            await self.emit('user_left', {
                'user_id': user_id,
                'lobby_id': lobby_id,
                'left_at': json.dumps(datetime.datetime.now().isoformat())
            }, room=lobby_id, skip_sid=sid)
            
            # Обновляем статус онлайн для всех участников
            await self._broadcast_online_status(lobby_id)
            
            # Отключаем пользователя от комнаты
            await self.leave_room(sid, lobby_id)

        except Exception as e:
            print(f"Error during leave_lobby: {e}")
            await self.emit('error', {'message': 'An internal error occurred'}, to=sid)

# Регистрируем Namespace с путем /ws, как ожидает клиент
sio.register_namespace(MultiplayerNamespace('/ws'))

# Оборачиваем ASGI-приложением для FastAPI
sio_app = socketio.ASGIApp(sio) 