from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import pytz


class LogLevel(Enum):
    """Уровни серьезности логов"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSection(Enum):
    """Основные разделы системы"""
    AUTH = "auth"
    TWO_FA = "2fa"
    TELEGRAM = "telegram"
    SECURITY = "security"
    DATABASE = "database"
    SYSTEM = "system"
    API = "api"


class LogSubsection:
    """Подразделы для каждого раздела"""
    
    # AUTH подразделы
    class AUTH:
        LOGIN_ATTEMPT = "login_attempt"
        LOGIN_SUCCESS = "login_success"
        LOGIN_FAILED = "login_failed"
        TOKEN_VALIDATION = "token_validation"
        ACCESS_DENIED = "access_denied"
        USER_NOT_FOUND = "user_not_found"
        ADMIN_NOT_FOUND = "admin_not_found"
    
    # TWO_FA подразделы
    class TWO_FA:
        REQUEST_SENT = "request_sent"
        REQUEST_FAILED = "request_failed"
        REQUEST_EXPIRED = "request_expired"
        REQUEST_ALLOWED = "request_allowed"
        REQUEST_DENIED = "request_denied"
        CALLBACK_RECEIVED = "callback_received"
        CALLBACK_PROCESSED = "callback_processed"
        CALLBACK_FAILED = "callback_failed"
        SESSION_UPDATE = "session_update"
        SESSION_CLEAR = "session_clear"
    
    # TELEGRAM подразделы
    class TELEGRAM:
        MESSAGE_SENT = "message_sent"
        MESSAGE_FAILED = "message_failed"
        CALLBACK_RECEIVED = "callback_received"
        CALLBACK_PROCESSED = "callback_processed"
        BOT_ERROR = "bot_error"
        CONNECTION = "connection"
        DISCONNECTION = "disconnection"
    
    # SECURITY подразделы
    class SECURITY:
        RATE_LIMIT = "rate_limit"
        INJECTION_ATTEMPT = "injection_attempt"
        UNAUTHORIZED_ACCESS = "unauthorized_access"
        SUSPICIOUS_ACTIVITY = "suspicious_activity"
        AUDIT = "audit"
        VALIDATION = "validation"
    
    # DATABASE подразделы
    class DATABASE:
        UPDATE = "update"
        ERROR = "error"
        QUERY = "query"
        TRANSACTION = "transaction"
    
    # SYSTEM подразделы
    class SYSTEM:
        INITIALIZATION = "initialization"
        MAINTENANCE = "maintenance"
        ERROR = "error"
        STARTUP = "startup"
        SHUTDOWN = "shutdown"
        CLEANUP = "cleanup"
    
    # API подразделы
    class API:
        REQUEST = "request"
        RESPONSE = "response"
        ERROR = "error"
        VALIDATION = "validation"
        PERFORMANCE = "performance"


class StructuredLogEntry:
    """Структурированная запись лога"""
    
    def __init__(
        self,
        level: LogLevel,
        section: LogSection,
        subsection: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        # Timezone GMT+5 (Kazakhstan time)
        self.timestamp = datetime.now(pytz.timezone('Asia/Almaty'))
        self.level = level
        self.section = section
        self.subsection = subsection
        self.message = message
        self.extra_data = extra_data or {}
        self.user_id = user_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.log_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует лог в словарь"""
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "section": self.section.value,
            "subsection": self.subsection,
            "message": self.message,
            "extra_data": self.extra_data,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }
    
    def to_json_string(self) -> str:
        """Преобразует лог в JSON строку"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str) 