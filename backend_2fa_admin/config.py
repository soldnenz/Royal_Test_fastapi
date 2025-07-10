import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    mongo_uri: str = "mongodb://admin:rmh_1337_polnokrasoti@185.146.3.206:27017/admin?authSource=admin&replicaSet=rs0"
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
    
    # RabbitMQ
    # URL брокера можно переопределить через переменную окружения RABBITMQ_URL
    rabbitmq_url: str = "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs"

    # Exchange и routing key должны совпадать с потребителями (rabbitmq_consumer)
    # Используем корректные значения для совместимости
    rabbitmq_exchange: str = "logs"
    rabbitmq_routing_key: str = "2fa.logs"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings() 