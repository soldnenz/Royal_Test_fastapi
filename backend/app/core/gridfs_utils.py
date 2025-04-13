from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from fastapi import UploadFile
from bson import ObjectId
import base64
import logging

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

async def get_media_file(file_id: str, db: AsyncIOMotorDatabase) -> bytes:
    fs = AsyncIOMotorGridFSBucket(db)

    try:
        object_id = ObjectId(file_id)
    except (TypeError, errors.InvalidId) as e:
        logger.error(f"[media] Невалидный ObjectId: {file_id} — {e}")
        raise ValueError("Невалидный ID файла")

    try:
        stream = await fs.open_download_stream(object_id)
        data = await stream.read()
        return data
    except Exception as e:
        logger.error(f"[media] Ошибка загрузки из GridFS: {file_id} — {e}")
        raise RuntimeError(f"Файл не найден или повреждён: {e}")

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
