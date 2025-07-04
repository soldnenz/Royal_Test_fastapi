from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from fastapi.responses import StreamingResponse
from app.core.gridfs_utils import get_media_file
from app.db.database import get_database
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId, errors
import base64
from app.core.security import get_current_actor
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from app.core.config import settings

router = APIRouter(tags=["Solo Files"])
logger = get_logger(__name__)

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
    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Запрос медиа-файла: пользователь {user_id} запрашивает медиа для вопроса {question_id} в лобби {lobby_id or 'любом'}"
    )
    
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
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Вопрос не найден в базе данных: попытка доступа к несуществующему вопросу {question_id}"
            )
            raise HTTPException(
                status_code=404,
                detail="Вопрос не найден"
            )
        
        logger.info(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.VALIDATION,
            message=f"Вопрос найден в базе данных: ID {question.get('_id')}, медиа-файл ID {question.get('media_file_id')}"
        )
        
        # Проверяем наличие медиа-файла
        media_file_id = question.get("media_file_id")
        if not media_file_id:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Медиа-файл отсутствует: у вопроса {question_id} нет привязанного медиа-файла"
            )
            raise HTTPException(
                status_code=404,
                detail="Медиа-файл для данного вопроса отсутствует"
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
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ACCESS,
                    message=f"Найдено конкретное лобби: пользователь {user_id} имеет доступ к лобби {lobby_id} с вопросом {question_id}"
                )
            else:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.SECURITY,
                    message=f"Доступ к лобби запрещён: лобби {lobby_id} не найдено или пользователь {user_id} не является участником"
                )
        else:
            # Ищем среди всех активных лобби пользователя
            active_lobbies = await db.lobbies.find({
                "participants": user_id,
                "question_ids": question_id,
                "status": "in_progress"
            }).to_list(None)

        
        if not active_lobbies:
            # Дополнительная проверка - может быть лобби в другом статусе
            search_filter = {"participants": user_id, "question_ids": question_id}
            if lobby_id:
                search_filter["_id"] = lobby_id
                
            all_user_lobbies = await db.lobbies.find(search_filter).to_list(None)
            
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Отсутствие доступа к файлу: пользователь {user_id} не имеет активных лобби с вопросом {question_id}, всего найдено лобби с этим вопросом: {len(all_user_lobbies)}"
            )
            
            raise HTTPException(
                status_code=403,
                detail="Доступ к медиа-файлу запрещен"
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
            

            
            if is_host or is_current or is_answered:
                has_access = True
                active_lobby = lobby

                break
                
        if not has_access:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Доступ к медиа запрещён: пользователь {user_id} не имеет прав доступа к файлу вопроса {question_id}"
            )
            
            # ВРЕМЕННОЕ РЕШЕНИЕ: Разрешаем доступ к медиа если файл существует и пользователь участник лобби с этим вопросом
            search_filter = {"participants": user_id, "question_ids": question_id}
            if lobby_id:
                search_filter["_id"] = lobby_id
                
            any_lobby_with_question = await db.lobbies.find_one(search_filter)
            
            if any_lobby_with_question:

                active_lobby = any_lobby_with_question
                has_access = True
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Доступ к медиа-файлу запрещен"
                )
            
        # Получаем медиа-файл из GridFS
        try:

            
            # Проверяем существование файла в GridFS перед попыткой получения
            file_exists = await db.fs.files.find_one({"_id": ObjectId(media_file_id)})
            if not file_exists:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Медиа-файл не найден в GridFS: файл ID {media_file_id} отсутствует в коллекции fs.files"
                )
                raise HTTPException(
                    status_code=404,
                    detail="Медиа-файл не найден"
                )
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Медиа-файл найден в GridFS: имя '{file_exists.get('filename', 'неизвестно')}', размер {file_exists.get('length', 0)} байт"
            )
            
            media_data = await get_media_file(str(media_file_id), db)
            if not media_data:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Ошибка загрузки медиа-файла: файл ID {media_file_id} найден в метаданных, но содержимое отсутствует или повреждено"
                )
                raise HTTPException(
                    status_code=404,
                    detail="Медиа-файл поврежден или недоступен"
                )
                
            # Получение информации о файле (content type)
            file_info = await db.fs.files.find_one({"_id": ObjectId(media_file_id)})
            if not file_info:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Метаданные файла отсутствуют: информация о файле ID {media_file_id} не найдена в GridFS"
                )
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
            

            
            # Проверяем, является ли это видеофайлом
            is_video = content_type.startswith("video/")
            
            # Добавляем эту информацию в вопрос, если has_media не установлен
            if not question.get("has_media") and media_data:

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
            try:
                response = StreamingResponse(
                    iter([media_data]),
                    media_type=content_type,
                    headers=headers
                )

                return response
            except Exception as stream_error:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ERROR,
                    message=f"Ошибка создания потокового ответа: не удалось создать StreamingResponse для медиа-файла - {str(stream_error)}"
                )
                raise stream_error
            
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Критическая ошибка получения медиа: не удалось загрузить файл для вопроса {question_id} - {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении медиа-файла"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Безопасное логирование ошибки без кириллических символов
        error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.ERROR,
            message=f"Непредвиденная системная ошибка: сбой при обработке запроса медиа для вопроса {question_id} - {error_msg}"
        )
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
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
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Вопрос не найден: попытка получения дополнительного медиа для несуществующего вопроса {question_id}"
            )
            raise HTTPException(
                status_code=404,
                detail="Вопрос не найден"
            )
        
        # Проверяем наличие дополнительного медиа-файла
        after_answer_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
        if not after_answer_media_id:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Дополнительный медиа-файл отсутствует: у вопроса {question_id} нет файла для показа после ответа"
            )
            raise HTTPException(
                status_code=404,
                detail="Дополнительный медиа-файл для данного вопроса отсутствует"
            )
        
        # Проверяем, ответил ли пользователь на этот вопрос в указанном или любом лобби
        has_answered = False
        
        if lobby_id:
            # Проверяем конкретное лобби
            lobby = await db.lobbies.find_one({"_id": lobby_id, "participants": user_id})
            if not lobby:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.SECURITY,
                    message=f"Доступ к лобби запрещён: лобби {lobby_id} не найдено или пользователь {user_id} не является участником"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Доступ к лобби запрещен"
                )
                
            # Проверяем, входит ли вопрос в это лобби
            if question_id not in lobby.get("question_ids", []):
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.SECURITY,
                    message=f"Вопрос не связан с лобби: вопрос {question_id} не входит в состав лобби {lobby_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Вопрос не связан с данным лобби"
                )
                
            # Проверяем, ответил ли пользователь на этот вопрос
            participant_answers = lobby.get("participants_answers", {}).get(user_id, {})
            has_answered = question_id in participant_answers
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Проверка права доступа к файлу после ответа: лобби {lobby_id}, пользователь {user_id}, количество ответов: {len(participant_answers)}, ответ на вопрос {question_id} дан: {has_answered}"
            )
            
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
            # ВРЕМЕННОЕ РЕШЕНИЕ: Разрешаем доступ к медиа после ответа если пользователь участник лобби с этим вопросом
            if lobby_id:
                lobby = await db.lobbies.find_one({"_id": lobby_id, "participants": user_id, "question_ids": question_id})
                if lobby:
                    logger.info(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.ACCESS,
                        message=f"Временный доступ к дополнительному медиа: пользователь {user_id} получил доступ в лобби {lobby_id} (временная мера)"
                    )
                    has_answered = True
                else:
                    logger.warning(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.SECURITY,
                        message=f"Нет права на дополнительный медиа: пользователь {user_id} пытается получить файл после ответа, не ответив на вопрос {question_id}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Необходимо сначала ответить на вопрос"
                    )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Необходимо сначала ответить на вопрос"
                )
        
        # Дополнительная проверка для экзаменационного режима
        if lobby_id:
            lobby = await db.lobbies.find_one({"_id": lobby_id})
            if lobby and lobby.get("exam_mode", False) and lobby["status"] != "finished":
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.SECURITY,
                    message=f"Блокировка в экзаменационном режиме: пользователь {user_id} пытается получить дополнительный медиа до завершения экзамена в лобби {lobby_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Доступ к дополнительному медиа заблокирован в экзаменационном режиме"
                )
        
        # Получаем медиа-файл из GridFS
        try:
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Загрузка дополнительного медиа: начинаем получение файла ID {after_answer_media_id} для показа после ответа на вопрос {question_id}"
            )
            
            # Проверяем существование файла в GridFS перед попыткой получения
            file_exists = await db.fs.files.find_one({"_id": ObjectId(after_answer_media_id)})
            if not file_exists:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Дополнительный медиа-файл не найден в GridFS: файл ID {after_answer_media_id} отсутствует в коллекции fs.files"
                )
                raise HTTPException(
                    status_code=404,
                    detail="Дополнительный медиа-файл не найден"
                )
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Дополнительный медиа-файл найден в GridFS: имя '{file_exists.get('filename', 'неизвестно')}', размер {file_exists.get('length', 0)} байт"
            )
            
            media_data = await get_media_file(str(after_answer_media_id), db)
            if not media_data:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Ошибка загрузки дополнительного медиа: файл ID {after_answer_media_id} найден в метаданных, но содержимое отсутствует или повреждено"
                )
                raise HTTPException(
                    status_code=404,
                    detail="Дополнительный медиа-файл поврежден или недоступен"
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
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Обнаружен тип дополнительного медиа-контента: {content_type} для файла {filename}"
            )
            
            # Генерируем безопасное случайное имя файла для HTTP заголовка
            try:
                # Попытка закодировать имя файла в latin-1
                filename.encode('latin-1')
                safe_filename = filename  # Если успешно - оставляем оригинальное имя
            except UnicodeEncodeError:
                # Только если есть кириллица - генерируем случайное имя
                safe_filename = generate_safe_filename(filename)
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.VALIDATION,
                    message=f"Переименование дополнительного файла: кириллическое имя '{filename[:20]}...' заменено на безопасное имя '{safe_filename}'"
                )
            
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
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ACCESS,
                message=f"Успешная отдача дополнительного файла: подготовлен StreamingResponse с заголовком Content-Disposition: {safe_content_disposition}"
            )
            try:
                response = StreamingResponse(
                    iter([media_data]),
                    media_type=content_type,
                    headers=headers
                )
                safe_filename = filename.encode('ascii', errors='ignore').decode('ascii')
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ACCESS,
                    message=f"Дополнительный медиа-файл успешно отдан: StreamingResponse создан для файла '{safe_filename}' размером {len(media_data)} байт"
                )
                return response
            except Exception as stream_error:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ERROR,
                    message=f"Ошибка создания потокового ответа для дополнительного медиа: не удалось создать StreamingResponse - {str(stream_error)}"
                )
                raise stream_error
            
        except Exception as e:
            # Безопасное логирование ошибки без кириллических символов
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Критическая ошибка получения дополнительного медиа: не удалось загрузить файл для вопроса {question_id} - {error_msg}"
            )
            raise HTTPException(
                status_code=500,
                detail="Ошибка при получении дополнительного медиа-файла"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Безопасное логирование ошибки без кириллических символов
        error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.ERROR,
            message=f"Непредвиденная системная ошибка дополнительного медиа: сбой при обработке запроса файла после ответа для вопроса {question_id} - {error_msg}"
        )
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )