# app/models/user_answer.py
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from typing import Optional

class UserAnswer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_id: str       # ID пользователя, который ответил
    lobby_id: str      # ID лобби, в котором происходил тест
    question_id: str   # ID вопроса
    answer: int        # ответ пользователя (например, индекс выбранного варианта)
    is_correct: bool   # флаг, правильный ли ответ
    timestamp: datetime = Field(default_factory=datetime.utcnow)  # время ответа

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
