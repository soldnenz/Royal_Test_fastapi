from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from fastapi import UploadFile
from bson import ObjectId, errors
import base64
import time
from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)

async def save_media_to_gridfs(file: UploadFile, db: AsyncIOMotorDatabase) -> ObjectId:
    """
    Сохраняет файл в GridFS и возвращает ID сохранённого файла.
    """
    fs = AsyncIOMotorGridFSBucket(db)
    file_id = await fs.upload_from_stream(
        file.filename,
        file.file,
        metadata={"content_type": file.content_type}
    )
    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.UPLOAD,
        message=f"Медиафайл успешно сохранен в GridFS: {file.filename} (тип {file.content_type}) получил ID {file_id}"
    )
    return file_id

async def get_media_file(file_id: str, db):
    """
    Получает медиафайл из GridFS по его ID.
    
    Args:
        file_id: идентификатор файла в GridFS
        db: соединение с базой данных
        
    Returns:
        bytes: двоичные данные файла
        
    Raises:
        RuntimeError: если файл не найден или не удалось прочитать
    """
    start_time = time.time()
    try:
        # Преобразуем строковый ID в ObjectId
        obj_id = ObjectId(file_id)
        
        # Находим информацию о файле
        find_start_time = time.time()
        file_info = await db.fs.files.find_one({"_id": obj_id})
        find_time = time.time() - find_start_time

        
        if not file_info:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.DOWNLOAD,
                message=f"Файл с ID {file_id} не найден в GridFS - возможно файл был удален или ID указан неверно"
            )
            return None
            
        # Получаем чанки файла
        chunks_start_time = time.time()
        chunks = await db.fs.chunks.find({"files_id": obj_id}).sort("n", 1).to_list(length=None)
        chunks_time = time.time() - chunks_start_time

        
        if not chunks:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.DOWNLOAD,
                message=f"Чанки для файла {file_id} не найдены в GridFS - файл поврежден или неполный"
            )
            return None
            
        # Собираем файл из чанков
        assembly_start_time = time.time()
        file_data = bytearray()
        for chunk in chunks:
            file_data.extend(chunk["data"])
        
        assembly_time = time.time() - assembly_start_time

        
        total_time = time.time() - start_time

            
        return bytes(file_data)
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.DOWNLOAD,
            message=f"Ошибка при извлечении файла {file_id} из GridFS: {e} - операция заняла {total_time:.4f} секунд"
        )
        raise RuntimeError(f"Не удалось прочитать файл: {e}")

async def delete_media_file(file_id: str, db: AsyncIOMotorDatabase) -> bool:
    """
    Удаляет файл из GridFS.
    """
    fs = AsyncIOMotorGridFSBucket(db)
    try:
        await fs.delete(ObjectId(file_id))
        logger.info(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.DELETE,
            message=f"Медиафайл {file_id} успешно удален из GridFS"
        )
    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.DELETE,
            message=f"Ошибка удаления файла {file_id} из GridFS: {e}"
        )
        raise RuntimeError(f"Ошибка удаления файла: {e}")
    return True
