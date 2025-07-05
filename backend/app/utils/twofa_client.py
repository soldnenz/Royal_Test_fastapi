import httpx
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import os
from dotenv import load_dotenv

from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)

# Загружаем переменные окружения
load_dotenv()

# URL микросервиса 2FA
TWOFA_SERVICE_URL = os.getenv("TWOFA_SERVICE_URL", "http://localhost:8001")


class TwoFAClient:
    """Клиент для работы с микросервисом 2FA"""
    
    def __init__(self, base_url: str = TWOFA_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
        self.timeout = httpx.Timeout(10.0)  # 10 секунд таймаут
    
    async def send_2fa_request(
        self,
        admin_data: Dict[str, Any],
        ip_address: str,
        user_agent: str
    ) -> Dict[str, Any]:
        """
        Отправляет 2FA запрос через микросервис
        
        Args:
            admin_data: Данные администратора
            ip_address: IP адрес
            user_agent: User Agent
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Отправляем 2FA запрос для администратора {admin_data.get('full_name', 'неизвестен')} через микросервис"
            )
            
            # Подготавливаем данные для отправки
            request_data = {
                "admin_id": str(admin_data["_id"]),
                "admin_name": admin_data.get("full_name", "Неизвестный админ"),
                "admin_email": admin_data.get("email"),
                "telegram_id": str(admin_data.get("telegram_id")) if admin_data.get("telegram_id") else None,
                "ip_address": ip_address if ip_address else "unknown",
                "user_agent": user_agent if user_agent else "unknown"
            }
            
            # Проверяем обязательные поля
            if not request_data["telegram_id"]:
                logger.error(
                    section=LogSection.AUTH,
                    subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                    message=f"У администратора {admin_data.get('full_name', 'неизвестен')} не указан Telegram ID"
                )
                return {
                    "success": False,
                    "message": "У администратора не указан Telegram ID"
                }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/send-2fa",
                    json=request_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                        message=f"2FA запрос успешно отправлен для администратора {admin_data.get('full_name', 'неизвестен')} через микросервис"
                    )
                    return result
                elif response.status_code == 429:
                    logger.warning(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.RATE_LIMIT,
                        message=f"Превышен лимит запросов к микросервису 2FA с IP {ip_address}"
                    )
                    return {
                        "success": False,
                        "message": "Превышен лимит запросов к сервису 2FA"
                    }
                elif response.status_code == 409:
                    logger.warning(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                        message=f"Уже есть активный 2FA запрос для администратора {admin_data.get('full_name', 'неизвестен')}"
                    )
                    return {
                        "success": False,
                        "message": "Уже есть активный 2FA запрос"
                    }
                else:
                    logger.error(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                        message=f"Ошибка микросервиса 2FA: {response.status_code} - {response.text}"
                    )
                    return {
                        "success": False,
                        "message": f"Ошибка сервиса 2FA: {response.status_code}"
                    }
                    
        except httpx.ConnectError:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Не удалось подключиться к микросервису 2FA по адресу {self.base_url}"
            )
            return {
                "success": False,
                "message": "Сервис 2FA недоступен"
            }
        except httpx.TimeoutException:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Таймаут при обращении к микросервису 2FA"
            )
            return {
                "success": False,
                "message": "Таймаут сервиса 2FA"
            }
        except Exception as e:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Неожиданная ошибка при обращении к микросервису 2FA: {str(e)}"
            )
            return {
                "success": False,
                "message": f"Ошибка сервиса 2FA: {str(e)}"
            }
    
    async def get_2fa_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус 2FA запроса
        
        Args:
            request_id: ID запроса
            
        Returns:
            Dict с статусом или None при ошибке
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/status/{request_id}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                        message=f"2FA запрос {request_id} не найден"
                    )
                    return None
                else:
                    logger.error(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                        message=f"Ошибка получения статуса 2FA: {response.status_code}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Ошибка получения статуса 2FA: {str(e)}"
            )
            return None
    
    async def check_health(self) -> bool:
        """
        Проверяет здоровье микросервиса 2FA
        
        Returns:
            True если сервис здоров, False иначе
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                
                if response.status_code == 200:
                    health_data = response.json()
                    is_healthy = (
                        health_data.get("status") == "healthy" and
                        health_data.get("database") == "connected" and
                        health_data.get("telegram_bot") == "connected"
                    )
                    
                    if not is_healthy:
                        logger.warning(
                            section=LogSection.SYSTEM,
                            subsection=LogSubsection.SYSTEM.MAINTENANCE,
                            message=f"Микросервис 2FA не здоров: {health_data}"
                        )
                    
                    return is_healthy
                else:
                    logger.error(
                        section=LogSection.SYSTEM,
                        subsection=LogSubsection.SYSTEM.MAINTENANCE,
                        message=f"Не удалось проверить здоровье микросервиса 2FA: {response.status_code}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.MAINTENANCE,
                message=f"Ошибка проверки здоровья микросервиса 2FA: {str(e)}"
            )
            return False


# Глобальный экземпляр клиента
twofa_client = TwoFAClient() 