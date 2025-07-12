from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from fastapi.responses import StreamingResponse
from app.core.media_manager import media_manager
from app.db.database import get_database
from bson import ObjectId, errors
import base64
from app.core.security import get_current_actor
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from app.core.config import settings
from app.rate_limit import rate_limit_ip
from app.multiplayer.lobby_utils import get_user_id, get_lobby_from_db

router = APIRouter(tags=["Multiplayer Media"])
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

@router.get("/lobbies/{lobby_id}/media/{question_id}", summary="Получить медиа-файл вопроса (мультиплеер)")
@rate_limit_ip("multiplayer_media_download", max_requests=100, window_seconds=60)
async def get_question_media_multiplayer(
    request: Request,
    lobby_id: str,
    question_id: str,
    current_user: dict = Depends(get_current_actor),
    db = Depends(get_database)
):
    """
    Получает медиа-файл для конкретного вопроса в мультиплеерном режиме.
    
    Безопасность:
    - Проверяет, что пользователь является участником лобби
    - Проверяет, что вопрос входит в состав лобби
    - Проверяет, что вопрос является текущим или уже отвеченным
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Запрос медиа-файла: пользователь {user_id} запрашивает медиа для вопроса {question_id} в лобби {lobby_id}"
    )
    
    try:
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Лобби не найдено: попытка доступа к несуществующему лобби {lobby_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем участие пользователя
        if user_id not in lobby.get("participants", []):
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Доступ к лобби запрещён: пользователь {user_id} не является участником лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем, что вопрос входит в состав лобби
        question_ids = lobby.get("question_ids", [])
        if question_id not in question_ids:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Вопрос не входит в лобби: вопрос {question_id} не входит в состав лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вопрос не входит в состав этого лобби")
        
        # Находим вопрос в базе данных
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
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем наличие медиа-файла
        media_file_id = question.get("media_file_id")
        if not media_file_id:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Медиа-файл отсутствует: у вопроса {question_id} нет привязанного медиа-файла"
            )
            raise HTTPException(status_code=404, detail="Медиа-файл для данного вопроса отсутствует")
        
        # Проверяем доступ к вопросу
        current_index = lobby.get("current_index", 0)
        current_question_id = question_ids[current_index] if current_index < len(question_ids) else None
        user_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
        
        # Доступ разрешен, если пользователь хост, или если вопрос текущий или уже отвеченный
        is_host = user_id == lobby.get("host_id")
        is_current = question_id == current_question_id
        is_answered = question_id in user_answers
        
        if not (is_host or is_current or is_answered):
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Доступ к медиа запрещён: пользователь {user_id} не имеет прав доступа к файлу вопроса {question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Доступ к медиа-файлу запрещен")
        
        # Получаем медиа-файл из системы
        try:
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Загрузка медиа: начинаем получение файла ID {media_file_id} для вопроса {question_id}"
            )
            
            # Проверяем существование файла в системе медиа
            file_info = await media_manager.get_media_file(str(media_file_id), db)
            if not file_info:
                logger.error(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.GRIDFS,
                    message=f"Медиа-файл не найден в системе: файл ID {media_file_id} отсутствует в коллекции media_files"
                )
                raise HTTPException(status_code=404, detail="Медиа-файл не найден")
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.GRIDFS,
                message=f"Медиа-файл найден в системе: имя '{file_info.get('original_filename', 'неизвестно')}', размер {file_info.get('file_size', 0)} байт"
            )
            
            # Получение информации о файле (content type)
            content_type = file_info.get("content_type", "application/octet-stream")
            filename = file_info.get("original_filename", "media_file")
                
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
            if not question.get("has_media"):
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
                if lobby.get("questions_data") and lobby["questions_data"].get(question_id):
                    await db.lobbies.update_one(
                        {"_id": lobby["_id"]},
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
            
            # Используем X-Accel-Redirect для прямой отдачи файла через nginx
            return StreamingResponse(
                iter([]),  # Пустой итератор, так как nginx сам отдаст файл
                media_type=content_type,
                headers={
                    "X-Accel-Redirect": f"/media/{file_info['relative_path']}",
                    "Content-Type": content_type,
                    "Content-Disposition": content_disposition,
                    "Content-Length": str(file_info.get("file_size", 0)),
                    "Accept-Ranges": "bytes",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Access-Control-Allow-Headers": "Range, Content-Type, Accept, Origin, X-Requested-With",
                    "Cache-Control": "public, max-age=3600"
                }
            )
            
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