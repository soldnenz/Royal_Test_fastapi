import os
import shutil
import hashlib
import mimetypes
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from fastapi import UploadFile, HTTPException
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.logging import get_logger, LogSection, LogSubsection
from app.core.config import settings

logger = get_logger(__name__)

class MediaManager:
    """
    Модульная система для управления медиафайлами.
    Поддерживает локальное хранение файлов и X-Accel-Redirect для эффективной раздачи.
    """
    
    def __init__(self, base_path: str = None):
        """
        Инициализация менеджера медиафайлов.
        
        Args:
            base_path: Базовый путь для хранения файлов (по умолчанию из settings.MEDIA_BASE_PATH)
        """
        if base_path is None:
            # Определяем путь относительно корня проекта
            project_root = Path(__file__).parent.parent.parent.parent
            self.base_path = project_root / settings.MEDIA_BASE_PATH
        else:
            self.base_path = Path(base_path)
        
        # Создаем директории если не существуют
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Поддиректории для разных типов медиа
        self.video_path = self.base_path / "videos"
        self.image_path = self.base_path / "images"
        self.audio_path = self.base_path / "audio"
        self.document_path = self.base_path / "documents"
        
        # Создаем поддиректории
        for path in [self.video_path, self.image_path, self.audio_path, self.document_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.UPLOAD,
            message=f"MediaManager инициализирован с базовым путем: {self.base_path}"
        )
    
    def _get_media_type_path(self, content_type: str) -> Path:
        """
        Определяет путь для типа медиафайла.
        
        Args:
            content_type: MIME-тип файла
            
        Returns:
            Path: Путь для хранения файлов данного типа
        """
        if content_type.startswith('video/'):
            return self.video_path
        elif content_type.startswith('image/'):
            return self.image_path
        elif content_type.startswith('audio/'):
            return self.audio_path
        else:
            return self.document_path
    
    def _generate_safe_filename(self, original_filename: str, content_type: str) -> str:
        """
        Генерирует безопасное имя файла.
        
        Args:
            original_filename: Оригинальное имя файла
            content_type: MIME-тип файла
            
        Returns:
            str: Безопасное имя файла
        """
        # Получаем расширение из оригинального имени
        extension = Path(original_filename).suffix.lower()
        
        # Если расширение не определено, определяем по MIME-типу
        if not extension:
            extension = mimetypes.guess_extension(content_type) or '.bin'
        
        # Генерируем уникальное имя файла
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{extension}"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Вычисляет SHA-256 хеш файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            str: SHA-256 хеш файла
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def save_media_file(
        self, 
        file: UploadFile, 
        db: AsyncIOMotorDatabase,
        created_by: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Сохраняет медиафайл локально и создает запись в MongoDB.
        
        Args:
            file: Загружаемый файл
            db: Соединение с MongoDB
            created_by: Информация о создателе файла
            metadata: Дополнительные метаданные
            
        Returns:
            Dict[str, Any]: Информация о сохраненном файле
        """
        start_time = datetime.utcnow()
        
        # Валидация файла
        if file.size and file.size > settings.MEDIA_MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"Превышен допустимый размер файла (макс. {settings.MEDIA_MAX_FILE_SIZE_MB} МБ)"
            )
        
        if file.content_type not in settings.MEDIA_ALLOWED_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Недопустимый тип файла: {file.content_type}"
            )
        
        # Определяем путь для сохранения
        media_path = self._get_media_type_path(file.content_type)
        safe_filename = self._generate_safe_filename(file.filename, file.content_type)
        file_path = media_path / safe_filename
        
        # Сохраняем файл локально
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка сохранения файла {file.filename}: {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")
        
        # Вычисляем хеш файла
        file_hash = self._calculate_file_hash(file_path)
        
        # Проверяем, существует ли уже файл с таким хешем
        existing_file = await db.media_files.find_one({"file_hash": file_hash})
        if existing_file:
            # Удаляем только что сохраненный файл, так как он дубликат
            if file_path.exists():
                file_path.unlink()
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.UPLOAD,
                message=f"Файл {file.filename} является дубликатом существующего файла {existing_file.get('original_filename', 'неизвестен')} (ID: {existing_file['_id']})"
            )
            
            # Возвращаем информацию о существующем файле
            return {
                "id": str(existing_file["_id"]),
                "filename": existing_file["safe_filename"],
                "original_filename": existing_file["original_filename"],
                "content_type": existing_file["content_type"],
                "file_size": existing_file["file_size"],
                "relative_path": existing_file["relative_path"],
                "created_at": existing_file["created_at"].isoformat(),
                "created_by": existing_file["created_by"],
                "is_duplicate": True
            }
        
        # Определяем относительный путь для X-Accel-Redirect
        relative_path = file_path.relative_to(self.base_path)
        
        # Подготавливаем метаданные для MongoDB
        file_metadata = {
            "original_filename": file.filename,
            "safe_filename": safe_filename,
            "content_type": file.content_type,
            "file_size": file_path.stat().st_size,
            "file_hash": file_hash,
            "relative_path": str(relative_path).replace("\\", "/"),
            "created_by": created_by,
            "created_at": start_time,
            "updated_at": start_time,
            "is_hidden": False,
            "is_deleted": False,
            "download_count": 0,
            "last_accessed": None,
            "tags": metadata.get("tags", []) if metadata else [],
            "description": metadata.get("description", "") if metadata else "",
            "category": metadata.get("category", "") if metadata else "",
        }
        
        # Сохраняем метаданные в MongoDB
        try:
            result = await db.media_files.insert_one(file_metadata)
            file_metadata["_id"] = result.inserted_id
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.UPLOAD,
                message=f"Файл {file.filename} успешно сохранен: {safe_filename} (ID: {result.inserted_id})"
            )
            
            return {
                "id": str(result.inserted_id),
                "filename": safe_filename,
                "original_filename": file.filename,
                "content_type": file.content_type,
                "file_size": file_metadata["file_size"],
                "relative_path": str(relative_path).replace("\\", "/"),
                "created_at": start_time.isoformat(),
                "created_by": created_by
            }
            
        except Exception as e:
            # Удаляем файл если не удалось сохранить метаданные
            if file_path.exists():
                file_path.unlink()
            
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка сохранения метаданных файла {file.filename}: {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения метаданных: {e}")
    
    async def get_media_file(self, file_id: str, db: AsyncIOMotorDatabase) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о медиафайле по ID.
        
        Args:
            file_id: ID файла в MongoDB
            db: Соединение с MongoDB
            
        Returns:
            Optional[Dict[str, Any]]: Информация о файле или None
        """
        try:
            file_info = await db.media_files.find_one({"_id": ObjectId(file_id)})
            if not file_info:
                return None
            
            # Проверяем существование файла
            file_path = self.base_path / file_info["relative_path"]
            if not file_path.exists():
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ERROR,
                    message=f"Файл {file_id} не найден на диске: {file_path}"
                )
                return None
            
            # Обновляем статистику доступа
            await db.media_files.update_one(
                {"_id": ObjectId(file_id)},
                {
                    "$inc": {"download_count": 1},
                    "$set": {"last_accessed": datetime.utcnow()}
                }
            )
            
            return file_info
            
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка получения файла {file_id}: {str(e)}"
            )
            return None
    
    async def delete_media_file(self, file_id: str, db: AsyncIOMotorDatabase) -> bool:
        """
        Удаляет медиафайл и его метаданные.
        
        Args:
            file_id: ID файла в MongoDB
            db: Соединение с MongoDB
            
        Returns:
            bool: True если файл успешно удален
        """
        try:
            # Получаем информацию о файле
            file_info = await db.media_files.find_one({"_id": ObjectId(file_id)})
            if not file_info:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.DELETE,
                    message=f"Файл {file_id} не найден в базе данных"
                )
                return False
            
            # Удаляем файл с диска
            file_path = self.base_path / file_info["relative_path"]
            if file_path.exists():
                file_path.unlink()
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.DELETE,
                    message=f"Файл {file_id} удален с диска: {file_path}"
                )
            
            # Удаляем метаданные из MongoDB
            await db.media_files.delete_one({"_id": ObjectId(file_id)})
            
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.DELETE,
                message=f"Метаданные файла {file_id} удалены из базы данных"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка удаления файла {file_id}: {str(e)}"
            )
            return False
    
    async def update_media_metadata(
        self, 
        file_id: str, 
        db: AsyncIOMotorDatabase, 
        updates: Dict[str, Any]
    ) -> bool:
        """
        Обновляет метаданные медиафайла.
        
        Args:
            file_id: ID файла в MongoDB
            db: Соединение с MongoDB
            updates: Словарь с обновлениями
            
        Returns:
            bool: True если обновление успешно
        """
        try:
            # Удаляем служебные поля из обновлений
            updates.pop("_id", None)
            updates.pop("file_hash", None)
            updates.pop("relative_path", None)
            updates.pop("safe_filename", None)

            # Добавляем время обновления
            updates["updated_at"] = datetime.utcnow()

            result = await db.media_files.update_one(
                {"_id": ObjectId(file_id)},
                {"$set": updates}
            )

            if result.raw_result.get('nModified', 0) > 0:
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPDATE,
                    message=f"Метаданные файла {file_id} обновлены"
                )
                return True
            else:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPDATE,
                    message=f"Файл {file_id} не найден для обновления"
                )
                return False
                
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка обновления метаданных файла {file_id}: {str(e)}"
            )
            return False
    
    async def get_media_files_by_creator(
        self, 
        creator_iin: str, 
        db: AsyncIOMotorDatabase,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получает список медиафайлов созданных пользователем.
        
        Args:
            creator_iin: IIN создателя файлов
            db: Соединение с MongoDB
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей
            
        Returns:
            List[Dict[str, Any]]: Список файлов
        """
        try:
            cursor = db.media_files.find(
                {"created_by.iin": creator_iin, "is_deleted": False}
            ).skip(skip).limit(limit).sort("created_at", -1)
            
            files = []
            async for file in cursor:
                file["id"] = str(file["_id"])
                del file["_id"]
                files.append(file)
            
            return files
            
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка получения файлов создателя {creator_iin}: {str(e)}"
            )
            return []
    
    def get_x_accel_redirect_path(self, relative_path: str) -> str:
        """
        Формирует путь для X-Accel-Redirect.
        
        Args:
            relative_path: Относительный путь к файлу
            
        Returns:
            str: Путь для X-Accel-Redirect
        """
        return f"{settings.MEDIA_X_ACCEL_PREFIX}/{relative_path}"
    
    def get_file_url(self, file_info: Dict[str, Any]) -> str:
        """
        Формирует URL для доступа к файлу через X-Accel-Redirect.
        
        Args:
            file_info: Информация о файле из MongoDB
            
        Returns:
            str: URL для доступа к файлу
        """
        return self.get_x_accel_redirect_path(file_info["relative_path"])
    
    async def find_file_by_hash(self, file_hash: str, db: AsyncIOMotorDatabase) -> Optional[Dict[str, Any]]:
        """
        Находит файл по хешу.
        
        Args:
            file_hash: SHA-256 хеш файла
            db: Соединение с MongoDB
            
        Returns:
            Optional[Dict[str, Any]]: Информация о файле или None
        """
        try:
            file_info = await db.media_files.find_one({"file_hash": file_hash})
            if file_info:
                file_info["id"] = str(file_info["_id"])
                del file_info["_id"]
            return file_info
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка поиска файла по хешу {file_hash}: {str(e)}"
            )
            return None

    async def get_media_file_content(self, file_id: str, db: AsyncIOMotorDatabase) -> Optional[bytes]:
        """
        Получает содержимое медиафайла по ID.
        
        Args:
            file_id: ID файла в MongoDB
            db: Соединение с MongoDB
            
        Returns:
            Optional[bytes]: Содержимое файла или None
        """
        try:
            file_info = await db.media_files.find_one({"_id": ObjectId(file_id)})
            if not file_info:
                return None
            
            # Проверяем существование файла
            file_path = self.base_path / file_info["relative_path"]
            if not file_path.exists():
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.ERROR,
                    message=f"Файл {file_id} не найден на диске: {file_path}"
                )
                return None
            
            # Читаем содержимое файла
            with open(file_path, "rb") as f:
                content = f.read()
            
            # Обновляем статистику доступа
            await db.media_files.update_one(
                {"_id": ObjectId(file_id)},
                {
                    "$inc": {"download_count": 1},
                    "$set": {"last_accessed": datetime.utcnow()}
                }
            )
            
            return content
            
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка получения содержимого файла {file_id}: {str(e)}"
            )
            return None

# Создаем глобальный экземпляр менеджера
media_manager = MediaManager() 