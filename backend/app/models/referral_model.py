from datetime import datetime

class Referral:
    """
    Класс, описывающий структуру документа реферального кода для хранения в MongoDB.
    Этот класс используется для структурирования данных, хотя при работе с Motor документы хранятся в виде словарей.
    """
    collection_name = "referrals"

    def __init__(self, code: str, type: str, owner_user_id: str, rate: dict,
                 description: str, active: bool, comment: str, created_by: str,
                 created_at: datetime = None):
        self.code = code
        self.type = type            # "user" или "school"
        self.owner_user_id = owner_user_id
        self.rate = rate            # например: {"type": "percent", "value": 10}
        self.description = description
        self.active = active
        self.comment = comment
        self.created_by = created_by  # Полное имя создателя (пользователь или админ)
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self):
        return {
            "code": self.code,
            "type": self.type,
            "owner_user_id": self.owner_user_id,
            "rate": self.rate,
            "description": self.description,
            "active": self.active,
            "comment": self.comment,
            "created_by": self.created_by,
            "created_at": self.created_at
        }
