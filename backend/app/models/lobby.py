# app/models/lobby.py
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
import uuid

class LobbyStatus(str, Enum):
    waiting = "waiting"         # ожидание запуска
    in_progress = "in_progress" # тест идет
    finished = "finished"       # тест завершен

class LobbyMode(str, Enum):
    solo = "solo"               # одиночный режим
    multi = "multi"             # многопользовательский режим

class Lobby(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    host_id: str               # ID пользователя-создателя (хоста) лобби
    status: LobbyStatus = LobbyStatus.waiting
    mode: LobbyMode = LobbyMode.solo
    question_ids: List[str]    # список ID вопросов для этого лобби
    correct_answers: Dict[str, int]  # словарь правильных ответов {question_id: correct_option_index}
    participants: List[str] = []     # список ID участников, присоединившихся к лобби
    participants_answers: Dict[str, Dict[str, bool]] = {}
    # структура: {user_id: {question_id: True/False, ...}, ...}
    # хранит для каждого участника, на каждый вопрос, отметку правильно ли ответил (True/False)
    
    current_index: int = 0     # индекс текущего вопроса (для отслеживания прогресса в тесте)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    sections: List[str] = []   # список разделов ПДД, выбранных для теста
    categories: List[str] = [] # список категорий транспорта
    subscription_type: str = "Demo" # тип подписки создателя (влияет на лобби)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
