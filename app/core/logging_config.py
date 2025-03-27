# app/core/logging_config.py

import logging
import os
from pythonjsonlogger import jsonlogger

from logging.handlers import RotatingFileHandler


def setup_logging():
    """
    Расширенная настройка логирования:
    - Уровень логов из переменных окружения (LOG_LEVEL)
    - JSON-формат логов в консоль (для удобной передачи в централизованную систему)
    - Ротация логов в файле (по размеру) - опционально
    """
    # Прочитаем уровень логирования из env или возьмём INFO по умолчанию
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Получим корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Удалим все существующие хендлеры (чтобы не дублировать вывод)
    while root_logger.hasHandlers():
        root_logger.removeHandler(root_logger.handlers[0])

    # ------------------------------
    # 1) Консольный хендлер (JSON)
    # ------------------------------
    console_handler = logging.StreamHandler()
    # Настраиваем JSON-форматер
    console_formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)%(levelname)%(name)%(message)",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # ---------------------------------------------------
    # 2) Опционально: ротация логов в файле
    #    Если переменная окружения LOG_FILE задана – пишем в файл
    #    с ротацией по размеру
    # ---------------------------------------------------
    log_file = os.getenv("LOG_FILE", "")
    if log_file:
        # Скажем, 5 мегабайт на файл и до 3 бэкапов
        max_bytes = int(os.getenv("LOG_MAX_BYTES", "5242880"))  # 5 MB
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "3"))

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        # Можно тоже сделать JSON-формат или классический
        file_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)%(levelname)%(name)%(message)",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # ------------------------------
    # Настраиваем логгер uvicorn
    # ------------------------------
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = root_logger.handlers
    uvicorn_logger.setLevel(log_level)

    # Если используете gunicorn, аналогично можно переназначить хендлеры:
    # gunicorn_logger = logging.getLogger("gunicorn.error")
    # gunicorn_logger.handlers = root_logger.handlers
    # gunicorn_logger.setLevel(log_level)

    # Тестовое сообщение, чтобы проверить инициализацию (можно убрать)
    root_logger.info("Logging has been set up. Level=%s, JSON console=%s, Log file='%s'",
                     log_level, True, log_file or "disabled")
