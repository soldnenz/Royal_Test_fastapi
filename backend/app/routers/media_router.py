from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List
from bson import ObjectId
from app.admin.permissions import get_current_admin_user
from app.db.database import get_database
from app.core.media_manager import media_manager
from app.core.response import success
from app.schemas.media_schemas import (
    MediaFileUpdate,
    MediaFileDeleteRequest,
    MediaFileSearchRequest,
    MediaFileUploadResponse
)
from app.logging import get_logger, LogSection, LogSubsection
from app.core.config import settings
import time

router = APIRouter()
logger = get_logger(__name__)

@router.post("/upload", response_model=dict)
async def upload_media_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON строка с тегами
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Загрузка медиафайла с использованием новой системы MediaManager.
    Поддерживает только администраторов и создателей тестов.
    """
    start_time = time.time()
    
    # Проверка прав доступа
    if not current_user or current_user.get("role") not in ["admin", "tests_creator"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка загрузки медиафайла от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён. Требуется роль администратора или создателя тестов.")

    # Проверка наличия обязательных полей у пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Пользователь с неполными данными пытался загрузить медиафайл: {current_user}"
        )
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.UPLOAD,
        message=f"Пользователь {current_user['full_name']} (IIN: {current_user['iin']}) начинает загрузку файла {file.filename}"
    )

    # Подготовка метаданных
    metadata = {}
    if description:
        metadata["description"] = description
    if category:
        metadata["category"] = category
    if tags:
        try:
            import json
            metadata["tags"] = json.loads(tags)
        except Exception as e:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Ошибка парсинга тегов от пользователя {current_user['iin']}: {str(e)}"
            )
            metadata["tags"] = []

    # Информация о создателе
    created_by = {
        "full_name": current_user["full_name"],
        "iin": current_user["iin"],
        "role": current_user["role"]
    }

    try:
        # Сохранение файла через MediaManager
        result = await media_manager.save_media_file(
            file=file,
            db=db,
            created_by=created_by,
            metadata=metadata
        )
        
        # Добавляем URL для доступа к файлу
        result["file_url"] = media_manager.get_file_url(result)
        
        upload_time = time.time() - start_time
        
        # Проверяем, был ли это дубликат
        if result.get("is_duplicate"):
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.UPLOAD,
                message=f"Использован существующий файл {file.filename} за {upload_time:.4f} секунд пользователем {current_user['iin']} (дубликат)"
            )
        else:
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.UPLOAD,
                message=f"Файл {file.filename} успешно загружен за {upload_time:.4f} секунд пользователем {current_user['iin']}"
            )
        
        return success(data=result)
        
    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.ERROR,
            message=f"Ошибка загрузки файла {file.filename} пользователем {current_user['iin']}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки файла: {e}")

@router.get("/file/{file_id}", response_model=dict)
async def get_media_file_info(
    file_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Получение информации о медиафайле по ID.
    """
    if current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения информации о медиафайле от пользователя без прав: {current_user.get('iin', 'неизвестен')}"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) запрашивает информацию о файле {file_id}"
    )

    file_info = await media_manager.get_media_file(file_id, db)
    if not file_info:
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    # Добавляем URL для доступа к файлу
    file_info["file_url"] = media_manager.get_file_url(file_info)
    file_info["id"] = str(file_info["_id"])
    del file_info["_id"]

    return success(data=file_info)

@router.get("/files", response_model=dict)
async def get_media_files(
    creator_iin: Optional[str] = Query(None, description="IIN создателя файлов"),
    content_type: Optional[str] = Query(None, description="MIME-тип файла"),
    category: Optional[str] = Query(None, description="Категория файла"),
    is_hidden: Optional[bool] = Query(None, description="Фильтр по скрытым файлам"),
    skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество записей"),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Получение списка медиафайлов с фильтрацией.
    """
    if current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения списка медиафайлов от пользователя без прав: {current_user.get('iin', 'неизвестен')}"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) запрашивает список медиафайлов"
    )

    try:
        # Формируем фильтр для MongoDB
        filter_query = {"is_deleted": False}
        
        if creator_iin:
            filter_query["created_by.iin"] = creator_iin
        if content_type:
            filter_query["content_type"] = content_type
        if category:
            filter_query["category"] = category
        if is_hidden is not None:
            filter_query["is_hidden"] = is_hidden

        # Получаем общее количество файлов
        total = await db.media_files.count_documents(filter_query)
        
        # Получаем файлы с пагинацией
        cursor = db.media_files.find(filter_query).skip(skip).limit(limit).sort("created_at", -1)
        
        files = []
        async for file in cursor:
            file["id"] = str(file["_id"])
            del file["_id"]
            file["file_url"] = media_manager.get_file_url(file)
            files.append(file)

        return success(data={
            "files": files,
            "total": total,
            "skip": skip,
            "limit": limit
        })
        
    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.ERROR,
            message=f"Ошибка получения списка медиафайлов: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка файлов: {e}")

@router.put("/file/{file_id}", response_model=dict)
async def update_media_file(
    file_id: str,
    update_data: MediaFileUpdate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Обновление метаданных медиафайла.
    """
    if current_user["role"] not in {"admin", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка обновления медиафайла от пользователя без прав: {current_user.get('iin', 'неизвестен')}"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.UPDATE,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) обновляет файл {file_id}"
    )

    # Подготавливаем обновления
    updates = {}
    if update_data.is_hidden is not None:
        updates["is_hidden"] = update_data.is_hidden
    if update_data.tags is not None:
        updates["tags"] = update_data.tags
    if update_data.description is not None:
        updates["description"] = update_data.description
    if update_data.category is not None:
        updates["category"] = update_data.category

    if not updates:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    success_update = await media_manager.update_media_metadata(file_id, db, updates)
    if not success_update:
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.UPDATE,
        message=f"Метаданные файла {file_id} успешно обновлены пользователем {current_user['iin']}"
    )

    return success(data={"message": "Метаданные файла обновлены"})

@router.delete("/file/{file_id}", response_model=dict)
async def delete_media_file(
    file_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Удаление медиафайла.
    """
    if current_user["role"] not in {"admin", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка удаления медиафайла от пользователя без прав: {current_user.get('iin', 'неизвестен')}"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.DELETE,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) удаляет файл {file_id}"
    )

    success_delete = await media_manager.delete_media_file(file_id, db)
    if not success_delete:
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.DELETE,
        message=f"Файл {file_id} успешно удален пользователем {current_user['iin']}"
    )

    return success(data={"message": "Медиафайл успешно удален"})

@router.get("/stream/{file_id}")
async def stream_media_file(
    file_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Потоковая передача медиафайла через X-Accel-Redirect.
    """
    if current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка потоковой передачи медиафайла от пользователя без прав: {current_user.get('iin', 'неизвестен')}"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.STREAM,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) запрашивает потоковую передачу файла {file_id}"
    )

    file_info = await media_manager.get_media_file(file_id, db)
    if not file_info:
        raise HTTPException(status_code=404, detail="Медиафайл не найден")

    if file_info.get("is_hidden", False):
        raise HTTPException(status_code=403, detail="Доступ к файлу запрещен")

    # Формируем заголовки для X-Accel-Redirect
    headers = {
        "X-Accel-Redirect": f"/media/{file_info['relative_path']}",
        "Content-Type": file_info["content_type"],
        "Content-Disposition": f"inline; filename={file_info['safe_filename']}",
        "Content-Length": str(file_info["file_size"])
    }

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.STREAM,
        message=f"Потоковая передача файла {file_id} через X-Accel-Redirect: {file_info['relative_path']}"
    )

    # Возвращаем пустой ответ с заголовками для X-Accel-Redirect
    return StreamingResponse(
        iter([]),
        headers=headers,
        media_type=file_info["content_type"]
    ) 