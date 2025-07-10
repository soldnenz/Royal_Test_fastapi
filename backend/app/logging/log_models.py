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
    USER = "user"
    ADMIN = "admin"
    WEBSOCKET = "websocket"
    FILES = "files"
    LOBBY = "lobby"
    TEST = "test"
    PAYMENT = "payment"
    SECURITY = "security"
    DATABASE = "database"
    SYSTEM = "system"
    API = "api"
    REDIS = "redis"


class LogSubsection:
    """Подразделы для каждого раздела"""
    
    # AUTH подразделы
    class AUTH:
        LOGIN = "login"
        LOGIN_ATTEMPT = "login_attempt"
        LOGIN_SUCCESS = "login_success"
        LOGIN_FAILED = "login_failed"
        LOGIN_BLOCKED = "login_blocked"
        LOGOUT = "logout"
        LOGOUT_SUCCESS = "logout_success"
        LOGOUT_FAILED = "logout_failed"
        REGISTRATION = "registration"
        REGISTER_ATTEMPT = "register_attempt"
        REGISTER_SUCCESS = "register_success"
        REGISTER_FAILED = "register_failed"
        GUEST_REGISTER_ATTEMPT = "guest_register_attempt"
        GUEST_REGISTER_SUCCESS = "guest_register_success"
        GUEST_REGISTER_FAILED = "guest_register_failed"
        TOKEN_VALIDATION = "token_validation"
        PASSWORD_RESET = "password_reset"
        TWO_FA = "2fa"
        TWO_FACTOR_REQUIRED = "two_factor_required"
        TOKEN_CREATE = "token_create"
        TOKEN_LIMIT = "token_limit"
        TOKEN_STORE = "token_store"
        TOKEN_MISSING = "token_missing"
        TOKEN_INVALID = "token_invalid"
        TOKEN_EXPIRED = "token_expired"
        TOKEN_NOT_FOUND = "token_not_found"
        TOKEN_REVOKED = "token_revoked"
        ACCESS_DENIED = "access_denied"
        USER_NOT_FOUND = "user_not_found"
        USER_VALIDATED = "user_validated"
        GUEST_VALIDATED = "guest_validated"
        ADMIN_NOT_FOUND = "admin_not_found"
        SESSION_INVALID = "session_invalid"
        ADMIN_VALIDATED = "admin_validated"
        ADMIN_LOGIN_SUCCESS = "admin_login_success"
        ADMIN_VALIDATION_SUCCESS = "admin_validation_success"
        ADMIN_VALIDATION_FAILED = "admin_validation_failed"
        AUTO_UNBAN = "auto_unban"
        REFERRAL_USED = "referral_used"
        ROLE_UNKNOWN = "role_unknown"
    
    # USER подразделы
    class USER:
        PROFILE_UPDATE = "profile_update"
        PROFILE = "profile"
        SUBSCRIPTION = "subscription"
        BALANCE = "balance"
        BAN = "ban"
        HISTORY = "history"
        ACTION = "action"
        REFERRAL = "referral"
    
    # ADMIN подразделы  
    class ADMIN:
        USER_MANAGEMENT = "user_management"
        SYSTEM_CONFIG = "system_config"
        MONITORING = "monitoring"
        PERMISSIONS = "permissions"
        VALIDATION = "validation"
        REFERRAL = "referral"
        SESSION_CHECK = "session_check"
        SESSION_VALIDATED = "session_validated"
        LIST_ACCESS = "list_access"
        USER_BAN = "user_ban"
        USER_UNBAN = "user_unban"
        BAN_HISTORY = "ban_history"
    
    # WEBSOCKET подразделы
    class WEBSOCKET:
        CONNECTION = "connection"
        DISCONNECTION = "disconnection"
        MESSAGE = "message"
        PING_PONG = "ping_pong"
        LOBBY_EVENTS = "lobby_events"
        MESSAGE_SEND = "message_send"
        TOKEN_CREATE = "token_create"
        TOKEN_VALIDATION = "token_validation"
        TOKEN_REVOKE = "token_revoke"
        ERROR = "error"
    
    # FILES подразделы
    class FILES:
        UPLOAD = "upload"
        DOWNLOAD = "download"
        DELETE = "delete"
        UPDATE = "update"
        ACCESS_CHECK = "access_check"
        VALIDATION = "validation"
        ACCESS = "access"
        SECURITY = "security"
        GRIDFS = "gridfs"
        ERROR = "error"
    
    # LOBBY подразделы
    class LOBBY:
        CREATE = "create"
        JOIN = "join"
        LEAVE = "leave"
        START_TEST = "start_test"
        FINISH_TEST = "finish_test"
        ACCESS = "access"
        CREATION = "creation"
        LIFECYCLE = "lifecycle"
        SECURITY = "security"
        VALIDATION = "validation"
        QUESTIONS = "questions"
        ANSWERS = "answers"
        STATUS = "status"
        DATABASE = "database"
        ERROR = "error"
        EXAM = "exam"
        EXAM_TIMER = "exam_timer"
        STATS = "stats"
        SUBSCRIPTION = "subscription"
        RESULTS = "results"
    
    # TEST подразделы
    class TEST:
        QUESTION_LOAD = "question_load"
        ANSWER_SUBMIT = "answer_submit"
        RESULTS = "results"
        VALIDATION = "validation"
        QUESTION_CREATE = "question_create"
        QUESTION_UPDATE = "question_update"
        QUESTION_DELETE = "question_delete"
        MEDIA_PROCESSING = "media_processing"
    
    # PAYMENT подразделы
    class PAYMENT:
        TRANSACTION = "transaction"
        REFERRAL = "referral"
        BALANCE = "balance"
        CREDIT = "credit"
        DEBIT = "debit"
        SUBSCRIPTION = "subscription"
    
    # SECURITY подразделы
    class SECURITY:
        RATE_LIMIT = "rate_limit"
        RATE_LIMIT_WARNING = "rate_limit_warning"
        RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
        RATE_LIMIT_BLOCKED = "rate_limit_blocked"
        RATE_LIMIT_HIGH_ACTIVITY = "rate_limit_high_activity"
        RATE_LIMIT_RESET = "rate_limit_reset"
        RATE_LIMIT_INFO = "rate_limit_info"
        RATE_LIMIT_STATS = "rate_limit_stats"
        RATE_LIMIT_FAIL_OPEN = "rate_limit_fail_open"
        INJECTION_ATTEMPT = "injection_attempt"
        UNAUTHORIZED_ACCESS = "unauthorized_access"
        SUSPICIOUS_ACTIVITY = "suspicious_activity"
        TOKEN_SECURITY = "token_security"
        AUDIT = "audit"
        AUTO_TASK = "auto_task"
        CLEANUP = "cleanup"
        BACKGROUND_TASK = "background_task"
        ACCESS_CONTROL = "access_control"
        ACCESS_DENIED = "access_denied"
        INJECTION = "injection"
        VALIDATION = "validation"
        TURNSTILE = "turnstile"
        REPORT_CREATE = "report_create"
        REPORT_VIEW = "report_view"
        REPORT_UPDATE = "report_update"
        REPORT_ERROR = "report_error"
    
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
        DEBUG = "debug"
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
    
    # REDIS подразделы
    class REDIS:
        CONNECTION = "connection"
        DISCONNECTION = "disconnection"
        ERROR = "error"
        RATE_LIMIT = "rate_limit"
        RATE_LIMIT_WARNING = "rate_limit_warning"
        RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
        RATE_LIMIT_BLOCKED = "rate_limit_blocked"
        RATE_LIMIT_HIGH_ACTIVITY = "rate_limit_high_activity"
        RATE_LIMIT_RESET = "rate_limit_reset"
        RATE_LIMIT_INFO = "rate_limit_info"
        RATE_LIMIT_STATS = "rate_limit_stats"
        RATE_LIMIT_FAIL_OPEN = "rate_limit_fail_open"
        MEMORY = "memory"
        PERFORMANCE = "performance"
        SCRIPT_LOAD = "script_load"


class StructuredLogEntry:
    """Модель структурированного лог-сообщения"""
    
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
        kz_timezone = pytz.timezone('Asia/Almaty')
        
        self.timestamp = datetime.now(kz_timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
        self.log_id = str(uuid.uuid4())[:8]  # Короткий уникальный ID
        self.level = level.value
        self.section = section.value
        self.subsection = subsection
        self.message = message
        self.extra_data = extra_data or {}
        self.user_id = user_id
        self.ip_address = ip_address
        self.user_agent = user_agent
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для логирования"""
        log_dict = {
            "timestamp": self.timestamp,
            "log_id": self.log_id,
            "level": self.level,
            "section": self.section,
            "subsection": self.subsection,
            "message": self.message
        }
        
        # Добавляем опциональные поля если они есть
        if self.user_id:
            log_dict["user_id"] = self.user_id
        if self.ip_address:
            log_dict["ip_address"] = self.ip_address
        if self.user_agent:
            log_dict["user_agent"] = self.user_agent
        if self.extra_data:
            log_dict["extra_data"] = self.extra_data
            
        return log_dict
    
    def to_json_string(self) -> str:
        """Преобразование в JSON строку"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False) 