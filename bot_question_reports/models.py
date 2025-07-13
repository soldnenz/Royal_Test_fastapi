from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class QuestionReport(BaseModel):
    _id: str
    lobby_id: str
    question_id: str
    user_id: str
    report_type: str
    description: str
    status: str
    created_at: datetime
    ip_address: str

class ReportStatus:
    SENDING = "sending"
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected" 