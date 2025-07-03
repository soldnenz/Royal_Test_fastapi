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
from collections import defaultdict
import time
import re

# Security functions will be imported after definition in lobby_router
import json



router = APIRouter()
logger = get_logger(__name__)

# Список разрешенных типов медиа
ALLOWED_MEDIA_TYPES = settings.allowed_media_types

def validate_file_id(file_id: str) -> ObjectId:
    """
    Строгая валидация file_id для предотвращения path traversal и injection атак
    """
    if not file_id:
        raise HTTPException(
            status_code=400, 
            detail="File ID не может быть пустым"
        )
    
    # Проверяем, что это только валидный ObjectId (24 hex символа)
    if not re.match(r'^[0-9a-fA-F]{24}$', file_id):
        logger.warning(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.VALIDATION,
            message=f"Попытка доступа к файлу с некорректным форматом ID: {file_id[:20]}... - ожидался 24-символьный hex ObjectId"
        )
        raise HTTPException(
            status_code=400, 
            detail="Неверный формат ID файла. ID должен быть 24-символьным hex значением"
        )
    
    # Проверяем на path traversal попытки
    dangerous_patterns = [
        '..',      # path traversal
        '/',       # directory separator
        '\\',      # windows path separator
        '%2e%2e',  # URL encoded ..
        '%2f',     # URL encoded /
        '%5c',     # URL encoded \
        'null',    # null injection
        '$',       # MongoDB injection
        '{',       # JSON injection
        '}',       # JSON injection
    ]
    
    file_id_lower = file_id.lower()
    for pattern in dangerous_patterns:
        if pattern in file_id_lower:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Попытка атаки через ID файла: обнаружен опасный паттерн '{pattern}' в запросе {file_id} - заблокировано"
            )
            raise HTTPException(
                status_code=400,
                detail="ID файла содержит запрещённые символы"
            )
    
    # Преобразуем в ObjectId с дополнительной проверкой
    try:
        object_id = ObjectId(file_id)
        # Проверяем, что ObjectId валидный и не был подделан
        if str(object_id) != file_id:
            raise HTTPException(
                status_code=400,
                detail="Некорректный ObjectId"
            )
        return object_id
    except errors.InvalidId:
        logger.warning(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.VALIDATION,
            message=f"Попытка использования невалидного ObjectId: {file_id} - отклонено"
        )
        raise HTTPException(
            status_code=400, 
            detail="Неверный формат ObjectId"
        )

async def check_file_access_permissions(user_id: str, file_id: str, db) -> bool:
    """
    Проверяет права доступа пользователя к файлу
    """
    try:
        # Получаем активное лобби пользователя
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": "in_progress"
        })
        
        if not active_lobby:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Пользователь {user_id} запросил файл {file_id} без активного лобби - доступ запрещён"
            )
            return False
        
        # Получаем все разрешенные файлы для этого лобби
        question_ids = active_lobby.get("question_ids", [])
        if not question_ids:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Лобби {active_lobby['_id']} пользователя {user_id} не содержит вопросов - запрос файла {file_id} отклонён"
            )
            return False
        
        # Ищем файлы в вопросах лобби
        questions_cursor = db.questions.find({
            "_id": {"$in": [ObjectId(qid) for qid in question_ids]}
        })
        
        allowed_files = set()
        async for question in questions_cursor:
            # Основной медиа файл
            if question.get("media_file_id"):
                allowed_files.add(str(question["media_file_id"]))
            
            # After-answer медиа файл
            after_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
            if after_media_id:
                allowed_files.add(str(after_media_id))
        
        is_allowed = file_id in allowed_files
        if not is_allowed:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Попытка несанкционированного доступа: пользователь {user_id} запросил файл {file_id} который не принадлежит его активному тесту"
            )
        
        return is_allowed
        
    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.SECURITY,
            message=f"Ошибка проверки прав доступа к файлу: пользователь {user_id}, файл {file_id}, ошибка {str(e)}"
        )
        return False

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
    Возвращает медиа-файл по его ID с улучшенной безопасностью.
    
    Безопасность:
    - Строгая валидация file_id (только валидные ObjectId)
    - Проверка прав доступа к файлу
    - Защита от path traversal атак
    
    Поддерживаемые типы файлов:
    - Изображения: image/jpeg, image/png
    - Видео: video/mp4, video/quicktime
    
    - Если параметр as_base64=true, возвращает файл в формате base64
    - Иначе возвращает файл напрямую
    """
    # СТРОГАЯ ВАЛИДАЦИЯ file_id
    file_obj_id = validate_file_id(file_id)
    
    # Получаем ID пользователя
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Запрос файла: пользователь {user_id} запросил доступ к файлу {file_id}"
    )

    # ПРОВЕРКА ПРАВ ДОСТУПА
    has_access = await check_file_access_permissions(user_id, file_id, db)
    if not has_access:
        raise HTTPException(
            status_code=403, 
            detail="Доступ к файлу запрещен. Файл не принадлежит ни одному из вопросов вашего текущего теста."
        )

    try:
        # Получаем данные файла из GridFS (байты) используя уже валидированный ObjectId
        file_data = await get_media_file(file_id, db)

        # Получаем объект GridOut для получения метаданных
        fs = AsyncIOMotorGridFSBucket(db)
        gridout = await fs.open_download_stream(file_obj_id)

        # Получаем content_type из metadata с fallback на безопасное значение
        content_type = "application/octet-stream"  # Безопасное значение по умолчанию
        
        if gridout.metadata and gridout.metadata.get("content_type"):
            requested_type = gridout.metadata["content_type"]
            # Проверяем, что тип разрешен
            if requested_type in ALLOWED_MEDIA_TYPES:
                content_type = requested_type
            else:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Файл {file_id} содержит неподдерживаемый тип медиа {requested_type} - используется безопасное значение по умолчанию"
                )

        is_video = content_type.startswith("video/")

        if as_base64:
            # Возвращаем как base64
            base64_data = base64.b64encode(file_data).decode("utf-8")
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ACCESS,
                message=f"Файл успешно отдан в base64: пользователю {user_id} выдан файл {file_id} типа {content_type} размером {len(file_data)} байт"
            )
            return success(data={
                "media_base64": base64_data,
                "content_type": content_type,
                "is_video": is_video
            })
        else:
            # Отдаём потоково
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ACCESS,
                message=f"Файл успешно отдан потоком: пользователю {user_id} выдан файл {file_id} типа {content_type} размером {len(file_data)} байт"
            )
            return StreamingResponse(
                iter([file_data]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"inline; filename=file_{file_id}",
                    "X-Content-Type-Options": "nosniff",  # Предотвращает MIME sniffing
                    "Cache-Control": "private, max-age=3600"  # Кэш на 1 час
                }
            )

    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.GRIDFS,
            message=f"Ошибка получения файла из GridFS: пользователь {user_id}, файл {file_id}, ошибка {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении файла. Попробуйте позже или обратитесь к администратору."
        )

