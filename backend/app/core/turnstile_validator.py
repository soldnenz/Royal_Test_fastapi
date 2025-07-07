import httpx
import asyncio
from typing import Optional
from ..core.config import settings
from ..logging import get_logger, LogSection, LogSubsection

class TurnstileValidator:
    """Валидатор Cloudflare Turnstile токенов"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or settings.TURNSTILE_SECRET_KEY
        self.siteverify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        self.logger = get_logger(__name__)
    
    async def verify_token(self, token: str, remote_ip: str = None) -> tuple[bool, Optional[str]]:
        """
        Проверяет токен Turnstile
        
        Args:
            token: Токен для проверки
            remote_ip: IP адрес пользователя (опционально)
            
        Returns:
            tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
        """
        if not token:
            self.logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.TURNSTILE,
                message="Токен Turnstile отсутствует"
            )
            return False, "Токен Turnstile отсутствует"
        
        if not self.secret_key:
            self.logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.TURNSTILE,
                message="TURNSTILE_SECRET_KEY не настроен, пропускаем проверку"
            )
            return True, None
        
        try:
            # Подготавливаем данные для проверки
            data = {
                "secret": self.secret_key,
                "response": token
            }
            
            if remote_ip:
                data["remoteip"] = remote_ip
            
            # Отправляем запрос к Cloudflare
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.siteverify_url, data=data)
                response.raise_for_status()
                
                result = response.json()
                
                self.logger.info(
                    section=LogSection.SECURITY,
                    subsection=LogSubsection.SECURITY.TURNSTILE,
                    message=f"Ответ Turnstile для IP {remote_ip or 'неизвестен'}: {str(result)}"
                )
                
                if result.get("success"):
                    self.logger.info(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.TURNSTILE,
                        message=f"Turnstile токен успешно проверен для IP {remote_ip or 'неизвестен'}"
                    )
                    return True, None
                else:
                    error_codes = result.get("error-codes", [])
                    error_msg = f"Ошибка проверки Turnstile: {', '.join(error_codes)}"
                    self.logger.warning(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.TURNSTILE,
                        message=f"Turnstile токен не прошел проверку для IP {remote_ip or 'неизвестен'}: {error_msg}"
                    )
                    return False, error_msg
                    
        except httpx.RequestError as e:
            error_msg = f"Ошибка сети при проверке Turnstile: {str(e)}"
            self.logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.TURNSTILE,
                message=f"Ошибка сети при проверке Turnstile для IP {remote_ip or 'неизвестен'}: {str(e)}"
            )
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка при проверке Turnstile: {str(e)}"
            self.logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.TURNSTILE,
                message=f"Неожиданная ошибка при проверке Turnstile для IP {remote_ip or 'неизвестен'}: {str(e)} (тип: {type(e).__name__})"
            )
            return False, error_msg

# Создаем глобальный экземпляр валидатора
turnstile_validator = TurnstileValidator()

async def validate_turnstile_token(token: str, remote_ip: str = None) -> tuple[bool, Optional[str]]:
    """
    Удобная функция для валидации токена Turnstile
    
    Args:
        token: Токен для проверки
        remote_ip: IP адрес пользователя (опционально)
        
    Returns:
        tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
    """
    return await turnstile_validator.verify_token(token, remote_ip) 