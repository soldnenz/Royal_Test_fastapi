from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MediaFileCreate(BaseModel):
    """Схема для создания медиафайла"""
    original_filename: str = Field(..., description="Оригинальное имя файла")
    safe_filename: str = Field(..., description="Безопасное имя файла")
    content_type: str = Field(..., description="MIME-тип файла")
    file_size: int = Field(..., description="Размер файла в байтах")
    file_hash: str = Field(..., description="SHA-256 хеш файла")
    relative_path: str = Field(..., description="Относительный путь к файлу")
    absolute_path: str = Field(..., description="Абсолютный путь к файлу")
    created_by: Dict[str, Any] = Field(..., description="Информация о создателе")
    tags: Optional[List[str]] = Field(default=[], description="Теги файла")
    description: Optional[str] = Field(default="", description="Описание файла")
    category: Optional[str] = Field(default="", description="Категория файла")

class MediaFileUpdate(BaseModel):
    """Схема для обновления метаданных медиафайла"""
    is_hidden: Optional[bool] = Field(None, description="Скрыт ли файл")
    tags: Optional[List[str]] = Field(None, description="Теги файла")
    description: Optional[str] = Field(None, description="Описание файла")
    category: Optional[str] = Field(None, description="Категория файла")

class MediaFileResponse(BaseModel):
    """Схема для ответа с информацией о медиафайле"""
    id: str = Field(..., description="ID файла в MongoDB")
    original_filename: str = Field(..., description="Оригинальное имя файла")
    safe_filename: str = Field(..., description="Безопасное имя файла")
    content_type: str = Field(..., description="MIME-тип файла")
    file_size: int = Field(..., description="Размер файла в байтах")
    relative_path: str = Field(..., description="Относительный путь к файлу")
    file_url: str = Field(..., description="URL для доступа к файлу")
    created_by: Dict[str, Any] = Field(..., description="Информация о создателе")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата последнего обновления")
    is_hidden: bool = Field(..., description="Скрыт ли файл")
    is_deleted: bool = Field(..., description="Удален ли файл")
    download_count: int = Field(..., description="Количество загрузок")
    last_accessed: Optional[datetime] = Field(None, description="Последний доступ")
    tags: List[str] = Field(default=[], description="Теги файла")
    description: str = Field(default="", description="Описание файла")
    category: str = Field(default="", description="Категория файла")

class MediaFileListResponse(BaseModel):
    """Схема для списка медиафайлов"""
    files: List[MediaFileResponse] = Field(..., description="Список файлов")
    total: int = Field(..., description="Общее количество файлов")
    skip: int = Field(..., description="Количество пропущенных записей")
    limit: int = Field(..., description="Максимальное количество записей")

class MediaFileDeleteRequest(BaseModel):
    """Схема для запроса на удаление медиафайла"""
    file_id: str = Field(..., description="ID файла для удаления")

class MediaFileSearchRequest(BaseModel):
    """Схема для поиска медиафайлов"""
    creator_iin: Optional[str] = Field(None, description="IIN создателя")
    content_type: Optional[str] = Field(None, description="MIME-тип файла")
    category: Optional[str] = Field(None, description="Категория файла")
    tags: Optional[List[str]] = Field(None, description="Теги для поиска")
    is_hidden: Optional[bool] = Field(None, description="Фильтр по скрытым файлам")
    skip: int = Field(default=0, description="Количество пропущенных записей")
    limit: int = Field(default=50, description="Максимальное количество записей")

class MediaFileUploadResponse(BaseModel):
    """Схема для ответа при загрузке медиафайла"""
    id: str = Field(..., description="ID файла в MongoDB")
    filename: str = Field(..., description="Безопасное имя файла")
    original_filename: str = Field(..., description="Оригинальное имя файла")
    content_type: str = Field(..., description="MIME-тип файла")
    file_size: int = Field(..., description="Размер файла в байтах")
    relative_path: str = Field(..., description="Относительный путь к файлу")
    file_url: str = Field(..., description="URL для доступа к файлу")
    created_at: str = Field(..., description="Дата создания (ISO формат)")
    created_by: Dict[str, Any] = Field(..., description="Информация о создателе") 