from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ReportType(str, Enum):
    """Типы жалоб на вопросы"""
    INCORRECT_ANSWER = "incorrect_answer"
    UNCLEAR_QUESTION = "unclear_question"
    TECHNICAL_ERROR = "technical_error"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    DUPLICATE_QUESTION = "duplicate_question"
    OTHER = "other"


class ReportStatus(str, Enum):
    """Статусы жалоб"""
    SENDING = "sending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class QuestionReportCreate(BaseModel):
    """Схема для создания жалобы на вопрос"""
    lobby_id: str = Field(..., min_length=1, max_length=100)
    question_id: str = Field(..., min_length=1, max_length=100)
    report_type: ReportType = Field(...)
    description: str = Field(..., min_length=10, max_length=1000)
    
    @validator('description')
    def validate_description(cls, v):
        if not v or not v.strip():
            raise ValueError('Описание не может быть пустым')
        return v.strip()

    @validator('question_id')
    def validate_question_id(cls, v):
        if not v or not v.strip():
            raise ValueError('ID вопроса не может быть пустым')
        return v.strip()

    @validator('lobby_id')
    def validate_lobby_id(cls, v):
        if not v or not v.strip():
            raise ValueError('ID лобби не может быть пустым')
        return v.strip()


class QuestionReportOut(BaseModel):
    """Схема для вывода информации о жалобе"""
    id: str
    lobby_id: str
    question_id: str
    user_id: str
    report_type: ReportType
    description: str
    status: ReportStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    admin_comment: Optional[str] = None


class QuestionReportUpdate(BaseModel):
    """Схема для обновления жалобы (админ)"""
    status: ReportStatus
    admin_comment: Optional[str] = Field(None, max_length=500)
    
    @validator('admin_comment')
    def validate_admin_comment(cls, v):
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class ReportStatsOut(BaseModel):
    """Схема для статистики жалоб"""
    total_reports: int
    pending_reports: int
    resolved_reports: int
    reports_by_type: dict
    recent_reports: List[QuestionReportOut] 


class QuestionReportAdminOut(QuestionReportOut):
    """Схема для вывода жалобы в админ-панели (без скрытых полей)"""
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True