from bson import ObjectId
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class OptionModel(BaseModel):
    label: str    # Например: "A", "B", "C", …
    text: str     # Текст варианта ответа

class QuestionModel(BaseModel):
    _id: Optional[ObjectId] = None
    question_text: str                       # Текст вопроса
    options: List[OptionModel]               # Список вариантов ответа
    correct_label: str                       # Метка правильного варианта (например, "B")
    categories: List[str]                    # Массив категорий, к которым относится вопрос
    created_by_name: str                     # ФИО пользователя, создавшего вопрос
    created_by_iin: str                      # ИИН пользователя, создавшего вопрос
    uid: str = Field(..., min_length=10, max_length=10)  # Уникальный идентификатор вопроса (10-значное число)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deleted: bool = False                    # Флаг мягкого удаления
    deleted_by: Optional[str] = None         # Кто удалил (например, ФИО или идентификатор)
    deleted_at: Optional[datetime] = None    # Когда удалено
    media_file_id: Optional[ObjectId] = None # Идентификатор медиафайла в GridFS (если есть)
    media_filename: Optional[str] = None     # Имя медиафайла (если есть)
