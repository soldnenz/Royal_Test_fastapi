#!/usr/bin/env python3
"""
Обновленный пример интеграции RabbitMQ с системой логирования Royal Test Project
Интегрируется с новой инфраструктурой RabbitMQ Docker
"""

import json
import pika
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Импорты из системы логирования проекта
try:
    from backend.app.logging.logger_setup import get_logger
    from backend.app.logging.log_models import LogSection
except ImportError:
    print("ПРЕДУПРЕЖДЕНИЕ: Не удалось импортировать систему логирования проекта")
    print("Убедитесь, что запускаете из корня проекта или адаптируйте пути")


class RoyalRabbitMQLogger:
    """
    Обновленная интеграция RabbitMQ с системой логирования Royal Test Project
    Использует новую инфраструктуру Docker с безопасными настройками
    """
    
    def __init__(self, 
                 host: str = 'localhost',
                 port: int = 5672,
                 username: str = 'royal_logger',
                 password: str = 'Royal_Logger_Pass',
                 vhost: str = 'royal_logs'):
        """
        Инициализация подключения к RabbitMQ с новыми настройками
        
        Args:
            host: Хост RabbitMQ (localhost для локальной разработки)
            port: Порт RabbitMQ (5672)
            username: Пользователь для логирования (royal_logger)
            password: Пароль (должен быть изменен в production)
            vhost: Virtual host для логов (royal_logs)
        """
        # Получаем настройки из переменных окружения или используем defaults
        self.host = os.getenv('RABBITMQ_HOST', host)
        self.port = int(os.getenv('RABBITMQ_PORT', port))
        self.username = os.getenv('RABBITMQ_USER', username)
        self.password = os.getenv('RABBITMQ_PASSWORD', password)
        self.vhost = os.getenv('RABBITMQ_VHOST', vhost)
        
        self.connection_params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=pika.PlainCredentials(self.username, self.password),
            heartbeat=600,
            blocked_connection_timeout=300,
        )
        
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        
        # Получаем логгер из системы проекта
        try:
            self.logger = get_logger(
                section=LogSection.REDIS,
                subsection="RABBITMQ_INTEGRATION"
            )
        except Exception:
            # Fallback если система логирования недоступна
            import logging
            self.logger = logging.getLogger("RoyalRabbitMQ")
            self.logger.setLevel(logging.INFO)
    
    def connect(self) -> bool:
        """
        Установка соединения с RabbitMQ
        
        Returns:
            True если соединение успешно, False иначе
        """
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            
            # Объявляем exchange для логов (должен соответствовать Docker настройкам)
            self.channel.exchange_declare(
                exchange='logs_exchange',
                exchange_type='topic',
                durable=True
            )
            
            # Проверяем существование основных очередей
            self._check_queues()
            
            self.logger.info(f"Успешное подключение к RabbitMQ: {self.host}:{self.port}/{self.vhost}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка подключения к RabbitMQ: {str(e)}")
            return False
    
    def _check_queues(self):
        """Проверяет существование очередей, созданных Docker настройками"""
        try:
            # Эти очереди должны быть созданы автоматически через definitions.json
            queues_to_check = ['logs_main', 'logs_error']
            
            for queue_name in queues_to_check:
                try:
                    # Пытаемся объявить очередь (passive=True не создает, только проверяет)
                    self.channel.queue_declare(queue=queue_name, passive=True)
                    self.logger.info(f"Очередь {queue_name} найдена")
                except pika.exceptions.ChannelClosedByBroker:
                    # Очередь не существует, создаем новое соединение
                    self.connection.close()
                    self.connection = pika.BlockingConnection(self.connection_params)
                    self.channel = self.connection.channel()
                    self.logger.warning(f"Очередь {queue_name} не найдена, будет использована автоматическая маршрутизация")
                    break
                    
        except Exception as e:
            self.logger.warning(f"Не удалось проверить очереди: {str(e)}")
    
    def send_log(self, 
                 level: str,
                 section: str,
                 subsection: str,
                 message: str,
                 user_id: Optional[str] = None,
                 ip_address: Optional[str] = None) -> bool:
        """
        Отправка лога в RabbitMQ с новой структурой routing keys
        
        Args:
            level: Уровень лога (INFO, WARNING, ERROR, etc.)
            section: Секция (REDIS, SECURITY, APPLICATION, etc.)
            subsection: Подсекция
            message: Сообщение лога
            user_id: ID пользователя (опционально)
            ip_address: IP адрес (опционально)
            
        Returns:
            True если отправка успешна, False иначе
        """
        
        if not self.connection or not self.channel:
            if not self.connect():
                return False
        
        try:
            # Формируем сообщение в формате системы логирования проекта
            log_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'log_id': f"rabbitmq_{datetime.utcnow().timestamp()}",
                'level': level.upper(),
                'section': section.upper(),
                'subsection': subsection.upper(),
                'message': message,
                'user_id': user_id,
                'ip_address': ip_address,
                'source': 'royal_rabbitmq_logger'
            }
            
            # Определяем routing key на основе уровня и секции (новая структура)
            if level.upper() in ['ERROR', 'CRITICAL']:
                routing_key = f'logs.error.{section.lower()}'
            else:
                routing_key = f'logs.info.{section.lower()}'
            
            # Отправляем сообщение
            self.channel.basic_publish(
                exchange='logs_exchange',
                routing_key=routing_key,
                body=json.dumps(log_data, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Делаем сообщение persistent
                    content_type='application/json',
                    content_encoding='utf-8',
                    timestamp=int(datetime.utcnow().timestamp()),
                    headers={
                        'level': level.upper(),
                        'section': section.upper(),
                        'routing_pattern': routing_key
                    }
                )
            )
            
            self.logger.info(f"Лог отправлен: {routing_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки лога в RabbitMQ: {str(e)}")
            return False
    
    def send_rate_limit_log(self,
                           route: str,
                           current_requests: int,
                           max_requests: int,
                           ip_address: str,
                           user_id: Optional[str] = None,
                           severity: str = "WARNING") -> bool:
        """
        Специализированный метод для логов rate limiter с обновленной структурой
        
        Args:
            route: Маршрут API
            current_requests: Текущее количество запросов
            max_requests: Максимальное количество запросов
            ip_address: IP адрес
            user_id: ID пользователя (опционально)
            severity: Серьезность (WARNING, ERROR)
            
        Returns:
            True если отправка успешна, False иначе
        """
        
        percentage = (current_requests / max_requests) * 100
        
        message = (f"Rate limit для {route}: использовано {current_requests}/{max_requests} "
                  f"запросов ({percentage:.1f}%), IP: {ip_address}")
        
        level = "ERROR" if severity == "ERROR" else "WARNING"
        
        return self.send_log(
            level=level,
            section="REDIS",
            subsection="RATE_LIMIT",
            message=message,
            user_id=user_id,
            ip_address=ip_address
        )
    
    def close(self):
        """Закрытие соединения с RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                self.logger.info("Соединение с RabbitMQ закрыто")
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии соединения RabbitMQ: {str(e)}")
    
    def __enter__(self):
        """Контекстный менеджер для автоматического управления соединением"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие соединения при выходе из контекста"""
        self.close()


def test_new_infrastructure():
    """
    Тестирование интеграции с новой инфраструктурой RabbitMQ Docker
    """
    print("=== Тестирование новой инфраструктуры RabbitMQ ===")
    print("Убедитесь, что RabbitMQ запущен: start_rabbitmq.bat")
    print()
    
    # Тестируем с новыми настройками
    try:
        with RoyalRabbitMQLogger() as rabbit_logger:
            
            # Тест 1: Информационный лог приложения
            success = rabbit_logger.send_log(
                level="INFO",
                section="APPLICATION",
                subsection="STARTUP",
                message="Приложение успешно запущено",
                ip_address="127.0.0.1"
            )
            print(f"✅ INFO лог приложения отправлен: {success}")
            
            # Тест 2: Лог ошибки Redis
            success = rabbit_logger.send_log(
                level="ERROR",
                section="REDIS",
                subsection="CONNECTION",
                message="Ошибка подключения к Redis",
                user_id="user_123",
                ip_address="192.168.1.100"
            )
            print(f"✅ ERROR лог Redis отправлен: {success}")
            
            # Тест 3: Rate limit warning
            success = rabbit_logger.send_rate_limit_log(
                route="/api/test",
                current_requests=85,
                max_requests=100,
                ip_address="192.168.1.50",
                user_id="user_456",
                severity="WARNING"
            )
            print(f"✅ Rate limit WARNING отправлен: {success}")
            
            # Тест 4: Критический rate limit
            success = rabbit_logger.send_rate_limit_log(
                route="/api/payment",
                current_requests=100,
                max_requests=100,
                ip_address="10.0.0.5",
                user_id="user_789",
                severity="ERROR"
            )
            print(f"✅ Rate limit ERROR отправлен: {success}")
            
            # Тест 5: 2FA лог
            success = rabbit_logger.send_log(
                level="WARNING",
                section="2FA",
                subsection="FAILED_ATTEMPT",
                message="Неудачная попытка 2FA авторизации",
                user_id="user_999",
                ip_address="203.0.113.1"
            )
            print(f"✅ 2FA WARNING отправлен: {success}")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {str(e)}")
        return False
    
    print("\n=== Тестирование завершено ===")
    print("🔍 Проверьте логи:")
    print("  1. RabbitMQ Management UI: http://localhost:15672")
    print("     Логин: royal_admin, Пароль: Royal_RabbitMQ_1337")
    print("  2. Очереди: logs_main (info), logs_error (errors)")
    print("  3. Запустите консьюмер: python rabbitmq_consumer/consumer.py")
    print()
    print("📊 Routing Keys:")
    print("  logs.info.application - Информационные логи приложения")
    print("  logs.info.redis - Информационные логи Redis")
    print("  logs.info.2fa - Информационные логи 2FA")
    print("  logs.error.application - Ошибки приложения")
    print("  logs.error.redis - Ошибки Redis")
    print("  logs.error.2fa - Ошибки 2FA")
    
    return True


def show_connection_info():
    """Показывает информацию о подключении"""
    print("=== Информация о подключении RabbitMQ ===")
    print()
    print("🔗 Подключение:")
    print(f"  Host: {os.getenv('RABBITMQ_HOST', 'localhost')}")
    print(f"  Port: {os.getenv('RABBITMQ_PORT', '5672')}")
    print(f"  User: {os.getenv('RABBITMQ_USER', 'royal_logger')}")
    print(f"  VHost: {os.getenv('RABBITMQ_VHOST', 'royal_logs')}")
    print()
    print("📊 Management UI:")
    print(f"  URL: http://localhost:{os.getenv('RABBITMQ_MANAGEMENT_PORT', '15672')}")
    print(f"  Admin User: royal_admin")
    print(f"  Admin Password: Royal_RabbitMQ_1337")
    print()
    print("🏗️ Архитектура:")
    print("  Exchange: logs_exchange (topic)")
    print("  Queues: logs_main, logs_error")
    print("  VHosts: royal_vhost (app), royal_logs (logging)")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_new_infrastructure()
        elif sys.argv[1] == "info":
            show_connection_info()
        else:
            print("Неизвестная команда. Используйте: test или info")
    else:
        print("=== Royal RabbitMQ Logger - Обновленная версия ===")
        print()
        print("Команды:")
        print("  python integration_example_updated.py test  - запуск тестов")
        print("  python integration_example_updated.py info  - информация о подключении")
        print()
        print("Пример использования в коде:")
        print("""
from rabbitmq.integration_example_updated import RoyalRabbitMQLogger

# Использование с контекстным менеджером
with RoyalRabbitMQLogger() as logger:
    logger.send_log(
        level="WARNING",
        section="SECURITY", 
        subsection="AUTH_FAILED",
        message="Неудачная попытка авторизации",
        user_id="123",
        ip_address="192.168.1.1"
    )
        """)
        print()
        show_connection_info() 