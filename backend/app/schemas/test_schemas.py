from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from app.core.config import settings

class OptionCreate(BaseModel):
    text: str

class OptionOut(BaseModel):
    label: str
    text: str

class QuestionCreate(BaseModel):
    question_text: str
    options: List[OptionCreate]
    correct_index: int  # Индекс правильного варианта в списке options
    categories: List[str]  # Массив категорий
    pdd_section_uids: List[str]
    media_filename: Optional[str] = None  # Если с фронта передается имя медиафайла

    @validator('options')
    def validate_options(cls, value):
        if len(value) < 2:
            raise ValueError('Должно быть минимум два варианта ответа')
        if len(value) > 8:
            raise ValueError('Максимум 8 вариантов ответа')
        return value

    @validator('correct_index')
    def validate_correct_index(cls, index, values):
        options = values.get('options')
        if options is not None and not (0 <= index < len(options)):
            raise ValueError('Некорректный индекс правильного ответа')
        return index

    @validator('pdd_section_uids')
    def validate_section_uids(cls, uids):
        valid_uids = {section["uid"] for section in settings.PDD_SECTIONS}
        for uid in uids:
            if uid not in valid_uids:
                raise ValueError(f"Раздела с uid '{uid}' не существует в pdd_sections")
        return uids

class QuestionOut(BaseModel):
    id: str
    question_text: str
    options: List[OptionOut]
    correct_label: str  # Например, "B"
    categories: List[str]
    pdd_section_uids: List[str]
    created_by_name: str    # ФИО пользователя, создавшего вопрос
    created_by_iin: str     # ИИН пользователя, создавшего вопрос
    uid: str = Field(..., min_length=10, max_length=10)  # Уникальный идентификатор вопроса (10-значная строка)
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted: bool = False
    deleted_by: Optional[str] = None  # Кто удалил вопрос
    deleted_at: Optional[datetime] = None
    media_file_id: Optional[str] = None  # Идентификатор медиафайла (в виде строки)
    media_filename: Optional[str] = None

class QuestionEdit(BaseModel):
    question_id: str
    new_question_text: Optional[str] = None
    new_options: Optional[List[OptionCreate]] = None
    new_correct_index: Optional[int] = None
    new_categories: Optional[List[str]] = None
    replace_media: Optional[bool] = False
    new_pdd_section_uids: Optional[List[str]] = None


    @validator('new_options')
    def validate_new_options(cls, value):
        if value is not None:
            if len(value) < 2:
                raise ValueError('Должно быть минимум два варианта ответа')
            if len(value) > 8:
                raise ValueError('Максимум 8 вариантов ответа')
        return value

    @validator('new_correct_index')
    def validate_new_correct_index(cls, index, values):
        options = values.get('new_options')
        if options is not None and index is not None and not (0 <= index < len(options)):
            raise ValueError('Некорректный индекс правильного ответа')
        return index

    @validator('new_pdd_section_uids')
    def validate_new_section_uids(cls, uids):
        if uids is not None:
            valid_uids = {section["uid"] for section in settings.PDD_SECTIONS}
            for uid in uids:
                if uid not in valid_uids:
                    raise ValueError(f"Раздела с uid '{uid}' не существует в pdd_sections")
        return uids

class QuestionDelete(BaseModel):
    question_id: str
    deleted_by: str  # ФИО или идентификатор пользователя, удалившего вопрос
