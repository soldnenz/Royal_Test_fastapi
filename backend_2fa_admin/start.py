#!/usr/bin/env python3
"""
Скрипт для запуска микросервиса 2FA
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавляем текущую директорию в PYTHONPATH
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from main import app
from config import settings
from log_system import get_2fa_logger, LogSection, LogSubsection

logger = get_2fa_logger()

def main():
    """Главная функция запуска"""
    try:
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message=f"Запуск 2FA микросервиса на {settings.host}:{settings.port}"
        )
        
        import uvicorn
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=False,
            log_level=settings.log_level.lower()
        )
        
    except KeyboardInterrupt:
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.SHUTDOWN,
            message="Получен сигнал остановки - завершаем работу 2FA микросервиса"
        )
    except Exception as e:
        logger.critical(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.ERROR,
            message=f"Критическая ошибка при запуске 2FA микросервиса: {str(e)}"
        )
        sys.exit(1)

if __name__ == "__main__":
    main() 