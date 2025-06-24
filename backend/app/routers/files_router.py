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
from collections import defaultdict
import time

# Security functions will be imported after definition in lobby_router
import json



router = APIRouter()
logger = logging.getLogger("files_router")

# Список разрешенных типов медиа
ALLOWED_MEDIA_TYPES = settings.allowed_media_types

def get_user_id(current_user):
    """
    Извлекает ID пользователя из объекта, возвращаемого get_current_actor
    """
    return str(current_user["id"])

@router.get("/files/{file_id}", summary="Получить файл по ID")
async def get_file(
    file_id: str,
    as_base64: bool = Query(False, description="Вернуть файл в формате base64"),
    request: Request = None,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Возвращает медиа-файл по его ID.
    
    Безопасность:
    - Проверяет, что у пользователя есть активное лобби
    - Проверяет, что запрашиваемый файл принадлежит вопросу в этом лобби
    
    Поддерживаемые типы файлов:
    - Изображения: image/jpeg, image/png
    - Видео: video/mp4, video/quicktime
    
    - Если параметр as_base64=true, возвращает файл в формате base64
    - Иначе возвращает файл напрямую
    """
    try:
        # Получаем ID пользователя
        user_id = get_user_id(current_user)
        logger.info(f"User {user_id} requested file {file_id}")

        # Проверяем, что у пользователя есть активное лобби
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": "in_progress"
        })
        if not active_lobby:
            logger.warning(f"User {user_id} has no active lobbies but tried to access file {file_id}")
            raise HTTPException(status_code=403, detail="У вас нет активного теста. Доступ к файлам возможен только во время прохождения теста.")
        
        lobby_id = active_lobby["_id"]
        logger.info(f"Found active lobby {lobby_id} for user {user_id}")
        
        # Получаем вопросы из активного лобби
        question_ids = active_lobby.get("question_ids", [])
        
        # Получаем ID всех медиа-файлов, связанных с вопросами в этом лобби
        questions_cursor = db.questions.find({
            "_id": {"$in": [ObjectId(qid) for qid in question_ids]}
        })
        
        allowed_media_files = set()
        media_types = {}  # Словарь для хранения типов медиа
        async for question in questions_cursor:
            if question.get("media_file_id"):
                file_id_str = str(question["media_file_id"])
                allowed_media_files.add(file_id_str)
                media_types[file_id_str] = question.get("media_type", "image/jpeg")  # По умолчанию изображение
            
            # Также добавляем after-answer медиа файлы
            after_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
            if after_media_id:
                after_file_id_str = str(after_media_id)
                allowed_media_files.add(after_file_id_str)
                # Определяем тип файла по расширению имени файла
                filename = question.get("after_answer_media_filename", "")
                if filename:
                    is_video = filename.lower().endswith((".mp4", ".webm", ".mov", ".avi"))
                    media_types[after_file_id_str] = "video/mp4" if is_video else "image/jpeg"
                else:
                    media_types[after_file_id_str] = "image/jpeg"  # По умолчанию изображение
        
        # Проверяем, что запрашиваемый файл принадлежит вопросу в активном лобби
        if file_id not in allowed_media_files:
            logger.warning(f"User {user_id} tried to access unauthorized file {file_id}")
            raise HTTPException(
                status_code=403, 
                detail="Доступ к файлу запрещен. Файл не принадлежит ни одному из вопросов вашего текущего теста."
            )

        # Преобразуем строку в ObjectId
        file_obj_id = ObjectId(file_id)
    except errors.InvalidId:
        logger.error(f"Invalid file ID format: {file_id}")
        raise HTTPException(status_code=400, detail="Неверный формат ID файла. ID файла должен быть валидным ObjectId.")

    try:
        # Получаем данные файла из GridFS (байты)
        file_data = await get_media_file(file_id, db)

        # Получаем объект GridOut для получения метаданных
        fs = AsyncIOMotorGridFSBucket(db)
        file_obj_id = ObjectId(file_id)  # Обязательно преобразуем строку в ObjectId
        gridout = await fs.open_download_stream(file_obj_id)

        # Получаем content_type из metadata или используем fallback
        content_type = (
            gridout.metadata.get("content_type", "application/octet-stream")
            if gridout.metadata
            else media_types.get(file_id, "application/octet-stream")
        )

        # Проверяем поддерживаемые типы
        if content_type not in ALLOWED_MEDIA_TYPES:
            logger.warning(f"Unsupported media type requested: {content_type}")
            content_type = "application/octet-stream"

        is_video = content_type.startswith("video/")

        if as_base64:
            # Возвращаем как base64
            base64_data = base64.b64encode(file_data).decode("utf-8")
            logger.info(f"Serving file {file_id} as base64 (type: {content_type}) to user {user_id}")
            return success(data={
                "media_base64": base64_data,
                "content_type": content_type,
                "is_video": is_video
            })
        else:
            # Отдаём потоково
            logger.info(f"Serving file {file_id} as {content_type} stream to user {user_id}")
            return StreamingResponse(
                iter([file_data]),
                media_type=content_type
            )

    except Exception as e:
        logger.error(f"Error retrieving file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении файла: {str(e)}. Попробуйте позже или обратитесь к администратору."
        )

