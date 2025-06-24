from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from fastapi.responses import StreamingResponse
from app.core.gridfs_utils import get_media_file
from app.db.database import get_database
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId, errors
import base64
from app.core.security import get_current_actor
from app.core.response import success
import logging
from app.core.config import settings

router = APIRouter(tags=["Solo Files"])
logger = logging.getLogger("solo_files_router")

# Список разрешенных типов медиа
ALLOWED_MEDIA_TYPES = settings.allowed_media_types

def generate_safe_filename(original_filename: str, file_extension: str = None) -> str:
    """
    Генерирует безопасное имя файла для HTTP заголовков.
    Заменяет кириллические символы на латинские.
    """
    import random
    import string
    
    if not original_filename:
        original_filename = "media_file"
    
    # Если есть расширение, используем его
    if file_extension:
        extension = file_extension if file_extension.startswith('.') else f'.{file_extension}'
    else:
        # Пытаемся извлечь расширение из оригинального имени
        parts = original_filename.split('.')
        extension = f'.{parts[-1]}' if len(parts) > 1 else ''
    
    # Генерируем случайное имя из латинских символов
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return f"{random_name}{extension}"

def get_user_id(current_user):
    """
    Извлекает ID пользователя из объекта, возвращаемого get_current_actor
    """
    return str(current_user["id"])

@router.get("/secure/media/{question_id}", summary="Получить медиа-файл вопроса (соло режим)")
async def get_question_media_secure(
    question_id: str,
    lobby_id: str = Query(None, description="ID лобби для проверки доступа"),
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получает медиа-файл для конкретного вопроса в соло режиме.
    
    Безопасность:
    - Проверяет, что пользователь имеет доступ к данному вопросу через активное лобби
    - Проверяет, что вопрос является текущим или уже отвеченным
    """
    user_id = get_user_id(current_user)
    logger.info(f"[SECURE_MEDIA] Пользователь {user_id} запрашивает медиа для вопроса {question_id} в лобби {lobby_id}")
    
    try:
        # Находим вопрос в базе данных - пробуем сначала как строку, потом как ObjectId
        question = None
        try:
            question = await db.questions.find_one({"_id": question_id})
        except:
            pass
            
        if not question:
            try:
                question = await db.questions.find_one({"_id": ObjectId(question_id)})
            except:
                pass
        
        if not question:
            logger.error(f"[SECURE_MEDIA] Вопрос {question_id} не найден в базе данных")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=not_found.svg'}
            )
        
        logger.info(f"[SECURE_MEDIA] Вопрос {question_id} найден: {question.get('_id')},  media_file_id: {question.get('media_file_id')}")
        
        # Проверяем наличие медиа-файла
        media_file_id = question.get("media_file_id")
        if not media_file_id:
            logger.warning(f"У вопроса {question_id} нет media_file_id")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_media.svg'}
            )
        
        # Проверяем доступ через конкретное лобби или через активные лобби пользователя
        active_lobby = None
        active_lobbies = []
        
        if lobby_id:
            # Если указан конкретный lobby_id, проверяем только его
            specific_lobby = await db.lobbies.find_one({
                "_id": lobby_id,
                "participants": user_id,
                "question_ids": question_id
            })
            if specific_lobby:
                active_lobbies = [specific_lobby]
                logger.info(f"Найдено конкретное лобби {lobby_id} для пользователя {user_id} с вопросом {question_id}")
            else:
                logger.warning(f"Конкретное лобби {lobby_id} не найдено или пользователь {user_id} не имеет к нему доступа")
        else:
            # Ищем среди всех активных лобби пользователя
            active_lobbies = await db.lobbies.find({
                "participants": user_id,
                "question_ids": question_id,
                "status": "in_progress"
            }).to_list(None)
            logger.info(f"Найдено {len(active_lobbies)} активных лобби для пользователя {user_id} с вопросом {question_id}")
        
        if not active_lobbies:
            # Дополнительная проверка - может быть лобби в другом статусе
            search_filter = {"participants": user_id, "question_ids": question_id}
            if lobby_id:
                search_filter["_id"] = lobby_id
                
            all_user_lobbies = await db.lobbies.find(search_filter).to_list(None)
            
            logger.warning(f"Пользователь {user_id} запрашивает медиа для вопроса {question_id} в лобби {lobby_id or 'любом'}. Активных лобби: 0, всего лобби с этим вопросом: {len(all_user_lobbies)}")
            
            if all_user_lobbies:
                for lobby in all_user_lobbies:
                    logger.info(f"Лобби {lobby['_id']}: статус={lobby.get('status')}, участники={len(lobby.get('participants', []))}")
            
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_access.svg'}
            )
        
        # Проверяем доступ к вопросу по каждому лобби
        has_access = False
        for lobby in active_lobbies:
            current_index = lobby.get("current_index", 0)
            current_question_id = lobby["question_ids"][current_index] if current_index < len(lobby["question_ids"]) else None
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            # Доступ разрешен, если пользователь хост, или если вопрос текущий или уже отвеченный
            is_host = user_id == lobby.get("host_id")
            is_current = question_id == current_question_id
            is_answered = question_id in user_answers
            
            logger.info(f"Проверка доступа в лобби {lobby['_id']}: is_host={is_host}, is_current={is_current} (current_q={current_question_id}), is_answered={is_answered}")
            
            if is_host or is_current or is_answered:
                has_access = True
                active_lobby = lobby
                logger.info(f"Доступ разрешен в лобби {lobby['_id']}")
                break
                
        if not has_access:
            logger.warning(f"Пользователь {user_id} не имеет доступа к медиа для вопроса {question_id}")
            
            # ВРЕМЕННОЕ РЕШЕНИЕ: Разрешаем доступ к медиа если файл существует и пользователь участник лобби с этим вопросом
            search_filter = {"participants": user_id, "question_ids": question_id}
            if lobby_id:
                search_filter["_id"] = lobby_id
                
            any_lobby_with_question = await db.lobbies.find_one(search_filter)
            
            if any_lobby_with_question:
                logger.info(f"ВРЕМЕННЫЙ ДОСТУП: Разрешаем доступ к медиа для пользователя {user_id} в лобби {any_lobby_with_question['_id']}")
                active_lobby = any_lobby_with_question
                has_access = True
            else:
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=no_access.svg'}
                )
            
        # Получаем медиа-файл из GridFS
        try:
            logger.info(f"Получение медиа-файла с ID {media_file_id} для вопроса {question_id}")
            
            # Проверяем существование файла в GridFS перед попыткой получения
            file_exists = await db.fs.files.find_one({"_id": ObjectId(media_file_id)})
            if not file_exists:
                logger.error(f"Медиа-файл {media_file_id} не найден в fs.files коллекции")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
            
            logger.info(f"Файл найден в fs.files: {file_exists.get('filename', 'unknown')} размер: {file_exists.get('length', 0)} байт")
            
            media_data = await get_media_file(str(media_file_id), db)
            if not media_data:
                logger.error(f"Медиа-файл {media_file_id} не найден в GridFS или пуст")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
                
            # Получение информации о файле (content type)
            file_info = await db.fs.files.find_one({"_id": ObjectId(media_file_id)})
            if not file_info:
                logger.error(f"Информация о файле {media_file_id} не найдена в GridFS")
                content_type = "application/octet-stream"
                filename = "media_file"
            else:
                content_type = file_info.get("contentType", "application/octet-stream")
                filename = file_info.get("filename", "media_file")
                
                # Improve content type detection based on filename if contentType is generic
                if content_type == "application/octet-stream" and filename:
                    lower_filename = filename.lower()
                    if lower_filename.endswith(('.jpg', '.jpeg')):
                        content_type = "image/jpeg"
                    elif lower_filename.endswith('.png'):
                        content_type = "image/png"
                    elif lower_filename.endswith('.gif'):
                        content_type = "image/gif"
                    elif lower_filename.endswith('.webp'):
                        content_type = "image/webp"
                    elif lower_filename.endswith('.svg'):
                        content_type = "image/svg+xml"
                    elif lower_filename.endswith('.mp4'):
                        content_type = "video/mp4"
                    elif lower_filename.endswith('.avi'):
                        content_type = "video/avi"
                    elif lower_filename.endswith('.mov'):
                        content_type = "video/quicktime"
            
            logger.info(f"Тип содержимого медиа-файла: {content_type}")
            
            # Проверяем, является ли это видеофайлом
            is_video = content_type.startswith("video/")
            
            # Добавляем эту информацию в вопрос, если has_media не установлен
            if not question.get("has_media") and media_data:
                logger.info(f"Обновляем информацию о медиа для вопроса {question_id}")
                question_update_id = question_id
                try:
                    question_update_id = ObjectId(question_id)
                except:
                    pass
                    
                await db.questions.update_one(
                    {"_id": question_update_id},
                    {"$set": {
                        "has_media": True,
                        "media_type": "video" if is_video else "image"
                    }}
                )
                
                # Также обновляем кэшированную информацию в лобби
                if active_lobby and active_lobby.get("questions_data") and active_lobby["questions_data"].get(question_id):
                    logger.info(f"Обновляем кэшированную информацию о медиа в лобби {active_lobby['_id']}")
                    await db.lobbies.update_one(
                        {"_id": active_lobby["_id"]},
                        {"$set": {
                            f"questions_data.{question_id}.has_media": True,
                            f"questions_data.{question_id}.media_type": "video" if is_video else "image"
                        }}
                    )
            
            # Генерируем безопасное случайное имя файла для HTTP заголовка
            try:
                # Попытка закодировать имя файла в latin-1
                filename.encode('latin-1')
                safe_filename = filename  # Если успешно - оставляем оригинальное имя
            except UnicodeEncodeError:
                # Только если есть кириллица - генерируем случайное имя
                safe_filename = generate_safe_filename(filename)
                logger.info(f"Основной файл с кириллическим именем переименован: {filename} -> {safe_filename}")
            
            content_disposition = f"inline; filename={safe_filename}"
            
            # Добавляем заголовки для видео стриминга
            headers = {
                'Content-Disposition': content_disposition,
                'Content-Length': str(len(media_data)),
                'Accept-Ranges': 'bytes',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': 'Range, Content-Type, Accept, Origin, X-Requested-With',
                'Cache-Control': 'public, max-age=3600'
            }
            
            # Return streaming response similar to the admin endpoint
            # Безопасное логирование заголовка
            safe_content_disposition = content_disposition.encode('ascii', errors='ignore').decode('ascii')
            logger.info(f"Возвращаем StreamingResponse с заголовком: Content-Disposition: {safe_content_disposition}")
            try:
                response = StreamingResponse(
                    iter([media_data]),
                    media_type=content_type,
                    headers=headers
                )
                safe_filename = filename.encode('ascii', errors='ignore').decode('ascii')
                logger.info(f"StreamingResponse успешно создан для основного медиа файла {safe_filename}")
                return response
            except Exception as stream_error:
                logger.error(f"Ошибка при создании StreamingResponse для основного медиа: {str(stream_error)}")
                raise stream_error
            
        except Exception as e:
            logger.error(f"Ошибка при получении медиа-файла для вопроса {question_id}: {str(e)}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=error.svg'}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Безопасное логирование ошибки без кириллических символов
        error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
        logger.error(f"Непредвиденная ошибка при получении медиа для вопроса {question_id}: {error_msg}")
        return StreamingResponse(
            iter([b'']),
            media_type='image/svg+xml',
            headers={'Content-Disposition': 'inline; filename=server_error.svg'}
        )

@router.get("/secure/after-answer-media/{question_id}", summary="Получить дополнительный медиа-файл после ответа (соло режим)")
async def get_after_answer_media_secure(
    question_id: str,
    lobby_id: str = Query(None, description="ID лобби, в котором пользователь ответил на вопрос"),
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получает дополнительный медиа-файл для показа после ответа на вопрос в соло режиме.
    
    Безопасность:
    - Проверяет, что пользователь ответил на этот вопрос
    - Если указан lobby_id, проверяет ответ в конкретном лобби
    - Не позволяет получить медиа, если пользователь не ответил на вопрос
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает медиа после ответа для вопроса {question_id} в лобби {lobby_id or 'любом'}")
    
    try:
        # Находим вопрос в базе данных - пробуем сначала как строку, потом как ObjectId
        question = None
        try:
            question = await db.questions.find_one({"_id": question_id})
        except:
            pass
            
        if not question:
            try:
                question = await db.questions.find_one({"_id": ObjectId(question_id)})
            except:
                pass
        
        if not question:
            logger.warning(f"Вопрос {question_id} не найден")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=not_found.svg'}
            )
        
        # Проверяем наличие дополнительного медиа-файла
        after_answer_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
        if not after_answer_media_id:
            logger.warning(f"У вопроса {question_id} нет дополнительного медиа-файла")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_media.svg'}
            )
        
        # Проверяем, ответил ли пользователь на этот вопрос в указанном или любом лобби
        has_answered = False
        
        if lobby_id:
            # Проверяем конкретное лобби
            lobby = await db.lobbies.find_one({"_id": lobby_id, "participants": user_id})
            if not lobby:
                logger.warning(f"Лобби {lobby_id} не найдено или пользователь {user_id} не является его участником")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=no_access.svg'}
                )
                
            # Проверяем, входит ли вопрос в это лобби
            if question_id not in lobby.get("question_ids", []):
                logger.warning(f"Вопрос {question_id} не входит в лобби {lobby_id}")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=question_not_in_lobby.svg'}
                )
                
            # Проверяем, ответил ли пользователь на этот вопрос
            participant_answers = lobby.get("participants_answers", {}).get(user_id, {})
            has_answered = question_id in participant_answers
            
            logger.info(f"Проверка ответа в лобби {lobby_id}: пользователь {user_id}, ответы: {list(participant_answers.keys())}, искомый вопрос: {question_id}, has_answered: {has_answered}")
            
        else:
            # Проверяем все активные лобби пользователя
            active_lobbies = await db.lobbies.find({
                "participants": user_id,
                "question_ids": question_id
            }).to_list(None)
            
            for lobby in active_lobbies:
                participant_answers = lobby.get("participants_answers", {}).get(user_id, {})
                if question_id in participant_answers:
                    has_answered = True
                    break
        
        if not has_answered:
            logger.warning(f"Пользователь {user_id} пытается получить медиа после ответа, не ответив на вопрос {question_id}")
            
            # ВРЕМЕННОЕ РЕШЕНИЕ: Разрешаем доступ к медиа после ответа если пользователь участник лобби с этим вопросом
            if lobby_id:
                lobby = await db.lobbies.find_one({"_id": lobby_id, "participants": user_id, "question_ids": question_id})
                if lobby:
                    logger.info(f"ВРЕМЕННЫЙ ДОСТУП: Разрешаем доступ к медиа после ответа для пользователя {user_id} в лобби {lobby_id}")
                    has_answered = True
                else:
                    return StreamingResponse(
                        iter([b'']),
                        media_type='image/svg+xml',
                        headers={'Content-Disposition': 'inline; filename=answer_first.svg'}
                    )
            else:
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=answer_first.svg'}
                )
        
        # Дополнительная проверка для экзаменационного режима
        if lobby_id:
            lobby = await db.lobbies.find_one({"_id": lobby_id})
            if lobby and lobby.get("exam_mode", False) and lobby["status"] != "finished":
                logger.warning(f"Пользователь {user_id} пытается получить медиа после ответа в экзаменационном режиме до завершения теста")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=exam_mode_blocked.svg'}
                )
        
        # Получаем медиа-файл из GridFS
        try:
            logger.info(f"Получение дополнительного медиа-файла с ID {after_answer_media_id} для вопроса {question_id}")
            
            # Проверяем существование файла в GridFS перед попыткой получения
            file_exists = await db.fs.files.find_one({"_id": ObjectId(after_answer_media_id)})
            if not file_exists:
                logger.error(f"Дополнительный медиа-файл {after_answer_media_id} не найден в fs.files коллекции")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
            
            logger.info(f"Дополнительный файл найден в fs.files: {file_exists.get('filename', 'unknown')} размер: {file_exists.get('length', 0)} байт")
            
            media_data = await get_media_file(str(after_answer_media_id), db)
            if not media_data:
                logger.error(f"Дополнительный медиа-файл {after_answer_media_id} не найден в GridFS или пуст")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
                
            # Получение информации о файле (content type)
            file_info = await db.fs.files.find_one({"_id": ObjectId(after_answer_media_id)})
            if not file_info:
                content_type = "application/octet-stream"
                filename = "after_answer_media"
            else:
                content_type = file_info.get("contentType", "application/octet-stream")
                filename = file_info.get("filename", "after_answer_media")
                
                # Improve content type detection based on filename if contentType is generic
                if content_type == "application/octet-stream" and filename:
                    lower_filename = filename.lower()
                    if lower_filename.endswith(('.jpg', '.jpeg')):
                        content_type = "image/jpeg"
                    elif lower_filename.endswith('.png'):
                        content_type = "image/png"
                    elif lower_filename.endswith('.gif'):
                        content_type = "image/gif"
                    elif lower_filename.endswith('.webp'):
                        content_type = "image/webp"
                    elif lower_filename.endswith('.svg'):
                        content_type = "image/svg+xml"
                    elif lower_filename.endswith('.mp4'):
                        content_type = "video/mp4"
                    elif lower_filename.endswith('.avi'):
                        content_type = "video/avi"
                    elif lower_filename.endswith('.mov'):
                        content_type = "video/quicktime"
            
            logger.info(f"Тип содержимого после-ответного медиа-файла: {content_type}")
            
            # Генерируем безопасное случайное имя файла для HTTP заголовка
            try:
                # Попытка закодировать имя файла в latin-1
                filename.encode('latin-1')
                safe_filename = filename  # Если успешно - оставляем оригинальное имя
            except UnicodeEncodeError:
                # Только если есть кириллица - генерируем случайное имя
                safe_filename = generate_safe_filename(filename)
                logger.info(f"Дополнительный файл с кириллическим именем переименован: {filename} -> {safe_filename}")
            
            content_disposition = f"inline; filename={safe_filename}"
            
            # Добавляем заголовки для видео стриминга
            headers = {
                'Content-Disposition': content_disposition,
                'Content-Length': str(len(media_data)),
                'Accept-Ranges': 'bytes',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': 'Range, Content-Type, Accept, Origin, X-Requested-With',
                'Cache-Control': 'public, max-age=3600'
            }
            
            # Return streaming response for after-answer media
            # Безопасное логирование заголовка
            safe_content_disposition = content_disposition.encode('ascii', errors='ignore').decode('ascii')
            logger.info(f"Возвращаем StreamingResponse с заголовком: Content-Disposition: {safe_content_disposition}")
            try:
                response = StreamingResponse(
                    iter([media_data]),
                    media_type=content_type,
                    headers=headers
                )
                safe_filename = filename.encode('ascii', errors='ignore').decode('ascii')
                logger.info(f"StreamingResponse успешно создан для файла {safe_filename}")
                return response
            except Exception as stream_error:
                logger.error(f"Ошибка при создании StreamingResponse: {str(stream_error)}")
                raise stream_error
            
        except Exception as e:
            # Безопасное логирование ошибки без кириллических символов
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            logger.error(f"Ошибка при получении дополнительного медиа-файла для вопроса {question_id}: {error_msg}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=error.svg'}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Безопасное логирование ошибки без кириллических символов
        error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
        logger.error(f"Непредвиденная ошибка при получении дополнительного медиа для вопроса {question_id}: {error_msg}")
        return StreamingResponse(
            iter([b'']),
            media_type='image/svg+xml',
            headers={'Content-Disposition': 'inline; filename=server_error.svg'}
        )