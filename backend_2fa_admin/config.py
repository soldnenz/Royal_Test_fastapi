import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "royal_test"
    
    # Telegram Bot
    telegram_bot_token: str
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    
    # Security
    access_token_expire_minutes: int = 30
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/2fa_service.log"
    
    # RabbitMQ (optional)
    rabbitmq_url: Optional[str] = None
    rabbitmq_exchange: str = "logs"
    rabbitmq_routing_key: str = "2fa.logs"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings() 