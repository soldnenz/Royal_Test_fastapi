from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from fastapi import UploadFile
from bson import ObjectId, errors
import base64
import logging
import time

logger = logging.getLogger("media")

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
        logger.info(f"Finding file info for {file_id} took {find_time:.4f} seconds")
        
        if not file_info:
            logger.warning(f"File with ID {file_id} not found in GridFS")
            return None
            
        # Получаем чанки файла
        chunks_start_time = time.time()
        chunks = await db.fs.chunks.find({"files_id": obj_id}).sort("n", 1).to_list(length=None)
        chunks_time = time.time() - chunks_start_time
        logger.info(f"Retrieving chunks for file {file_id} took {chunks_time:.4f} seconds")
        
        if not chunks:
            logger.warning(f"No chunks found for file {file_id} in GridFS")
            return None
            
        # Собираем файл из чанков
        assembly_start_time = time.time()
        file_data = bytearray()
        for chunk in chunks:
            file_data.extend(chunk["data"])
        
        assembly_time = time.time() - assembly_start_time
        logger.info(f"Assembling file data for {file_id} took {assembly_time:.4f} seconds")
        
        total_time = time.time() - start_time
        logger.info(f"Total time to retrieve file {file_id}: {total_time:.4f} seconds, size: {len(file_data)} bytes")
            
        return bytes(file_data)
    except Exception as e:
        logger.error(f"Error retrieving file from GridFS: {e}")
        total_time = time.time() - start_time
        logger.error(f"Failed to retrieve file {file_id} after {total_time:.4f} seconds")
        raise RuntimeError(f"Не удалось прочитать файл: {e}")

async def delete_media_file(file_id: str, db: AsyncIOMotorDatabase) -> bool:
    """
    Удаляет файл из GridFS.
    """
    fs = AsyncIOMotorGridFSBucket(db)
    try:
        await fs.delete(ObjectId(file_id))
    except Exception as e:
        logger.error(f"[media] Ошибка удаления из GridFS: {file_id} — {e}")
        raise RuntimeError(f"Ошибка удаления файла: {e}")
    return True
