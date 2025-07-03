# Структурированная система логирования

Новая централизованная система логирования для Royal Test API с единым стандартом и структурированным форматом.

## 🚀 Особенности

- **Структурированные JSON логи** с GMT+5 временем
- **Уникальный ID** для каждого лога
- **Стандартизированные разделы и подразделы**
- **Автоматическая ротация** файлов логов
- **Отдельные файлы** для обычных логов и событий безопасности
- **Утилитарные функции** для быстрого логирования
- **Отправка логов в RabbitMQ** через FastStream для WARNING, ERROR, CRITICAL

## 📁 Структура модуля

```
app/logging/
├── __init__.py              # Экспорты модуля
├── log_models.py            # Модели данных и енумы
├── logger_setup.py          # Основная настройка логирования
├── rabbitmq_handler.py      # RabbitMQ хендлер через FastStream
├── rabbitmq_example.py      # Примеры RabbitMQ логирования
├── utils.py                # Утилитарные функции
├── examples.py             # Примеры использования
└── README.md               # Эта документация
```

## 🔧 Настройка

### Переменные окружения

```bash
# .env файл
LOG_LEVEL=INFO                      # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FILE=logs/application.log       # Основной файл логов
SECURITY_LOG_FILE=logs/security.log # Файл логов безопасности
CONSOLE_LOGGING=true                # Вывод в консоль (true/false)
LOG_MAX_BYTES=10485760             # Максимальный размер файла (10 MB)
LOG_BACKUP_COUNT=5                 # Количество архивных файлов

# RabbitMQ настройки
RABBITMQ_LOGGING=true              # Включить отправку в RabbitMQ (true/false)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/  # URL подключения к RabbitMQ
RABBITMQ_EXCHANGE=logs             # Имя exchange в RabbitMQ
RABBITMQ_ROUTING_KEY=application.logs  # Routing key для сообщений
```

### Инициализация в main.py

```python
from app.logging import setup_application_logging

# Инициализация системы логирования
setup_application_logging()
```

## 📝 Базовое использование

```python
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection

# Получаем логгер
logger = get_structured_logger("auth.login")

# Логируем событие
logger.info(
    section=LogSection.AUTH,
    subsection=LogSubsection.AUTH.LOGIN,
    message="Пользователь успешно вошел в систему",
    user_id="507f1f77bcf86cd799439011",
    ip_address="192.168.1.100",
    extra_data={
        "login_method": "email",
        "session_duration": 3600
    }
)
```

## 🛠️ Утилитарные функции

### Аутентификация

```python
from app.logging.utils import log_auth_event

log_auth_event(
    subsection=LogSubsection.AUTH.LOGIN,
    message="Аутентификация пользователя прошла успешно",
    user_id=user_id,
    request=request,
    success=True,
    extra_data={"auth_method": "password"}
)
```

### Безопасность

```python
from app.logging.utils import log_security_event

log_security_event(
    subsection=LogSubsection.SECURITY.INJECTION_ATTEMPT,
    message="Обнаружена попытка SQL инъекции",
    severity="critical",
    request=request,
    threat_data={
        "payload": "'; DROP TABLE users; --",
        "parameter": "username"
    }
)
```

### WebSocket события

```python
from app.logging.utils import log_websocket_event

log_websocket_event(
    subsection=LogSubsection.WEBSOCKET.CONNECTION,
    message="Пользователь подключился к лобби",
    lobby_id=lobby_id,
    user_id=user_id,
    connection_info={
        "total_connections": 5
    }
)
```

### API запросы

```python
from app.logging.utils import log_api_request

log_api_request(
    request=request,
    response_status=200,
    processing_time_ms=45.2,
    user_id=user_id
)
```

## 📋 Разделы системы (LogSection)

- `AUTH` - Аутентификация и авторизация
- `USER` - Пользовательские операции
- `ADMIN` - Административные функции
- `WEBSOCKET` - WebSocket соединения
- `FILES` - Работа с файлами
- `LOBBY` - Лобби и игровые сессии
- `TEST` - Тестирование и вопросы
- `PAYMENT` - Платежи и подписки
- `SECURITY` - События безопасности
- `DATABASE` - Операции с БД
- `SYSTEM` - Системные события
- `API` - API запросы

## 🔍 Подразделы (LogSubsection)

### AUTH
- `LOGIN`, `LOGOUT`, `REGISTRATION`
- `TOKEN_VALIDATION`, `PASSWORD_RESET`, `TWO_FA`

### SECURITY
- `RATE_LIMIT`, `INJECTION_ATTEMPT`
- `UNAUTHORIZED_ACCESS`, `TOKEN_SECURITY`, `AUDIT`

### WEBSOCKET
- `CONNECTION`, `DISCONNECTION`, `MESSAGE`
- `PING_PONG`, `LOBBY_EVENTS`

### FILES
- `UPLOAD`, `DOWNLOAD`, `ACCESS_CHECK`, `VALIDATION`

## 📊 Формат лога

```json
{
    "timestamp": "2024-01-15 14:30:45 +05",
    "log_id": "a7b3c5d1",
    "level": "INFO",
    "section": "auth",
    "subsection": "login",
    "message": "Пользователь успешно вошел в систему",
    "user_id": "507f1f77bcf86cd799439011",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "extra_data": {
        "login_method": "email",
        "session_duration": 3600,
        "method": "POST",
        "endpoint": "/auth/login"
    }
}
```

## 🔄 Миграция со старой системы

### Было:
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"Пользователь {user_id} вошел в систему")
```

### Стало:
```python
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection

logger = get_structured_logger("auth.login")
logger.info(
    section=LogSection.AUTH,
    subsection=LogSubsection.AUTH.LOGIN,
    message="Пользователь успешно вошел в систему",
    user_id=user_id
)
```

## ⚡ Быстрые алиасы

```python
from app.logging.logger_setup import (
    get_auth_logger,
    get_websocket_logger,
    get_security_logger,
    get_api_logger,
    get_admin_logger
)

# Быстрое получение специализированных логгеров
auth_logger = get_auth_logger()
ws_logger = get_websocket_logger()
```

## 🎯 Декорatorы

```python
from app.logging.utils import log_function_call

@log_function_call(LogSection.TEST, LogSubsection.TEST.VALIDATION)
def validate_test_answers(test_id: str, answers: dict):
    """Функция с автоматическим логированием"""
    # Логика валидации
    pass
```

## 📁 Файлы логов

- **`logs/application.log`** - Основные логи приложения
- **`logs/security.log`** - События безопасности (WARNING+ уровень)
- **`logs/application.log.1`** - Архивные файлы (ротация)

## 🚨 Важные замечания

1. **Всегда используйте структурированные логи** вместо старых `logging.getLogger()`
2. **Указывайте правильные section/subsection** для категоризации
3. **Не логируйте чувствительные данные** (пароли, токены)
4. **Используйте extra_data** для дополнительной информации
5. **События безопасности** автоматически попадают в отдельный файл
6. **Логи WARNING, ERROR, CRITICAL** автоматически отправляются в RabbitMQ

## 🐰 RabbitMQ логирование

Система автоматически отправляет логи уровня WARNING, ERROR и CRITICAL в RabbitMQ через FastStream для централизованного мониторинга и обработки.

### Настройка RabbitMQ

1. **Установите RabbitMQ**:
```bash
# Docker
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:management

# Или установите локально
# https://www.rabbitmq.com/download.html
```

2. **Настройте переменные окружения**:
```bash
RABBITMQ_LOGGING=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_EXCHANGE=logs
RABBITMQ_ROUTING_KEY=application.logs
```

### Использование

Логи автоматически отправляются в RabbitMQ при использовании структурированного логгера:

```python
from app.logging import get_structured_logger, LogSection

logger = get_structured_logger("example")

# Этот лог НЕ будет отправлен в RabbitMQ (INFO уровень)
logger.info(
    section=LogSection.SYSTEM,
    subsection="startup",
    message="Приложение запущено"
)

# Этот лог БУДЕТ отправлен в RabbitMQ (WARNING уровень)
logger.warning(
    section=LogSection.API,
    subsection="rate_limit",
    message="Превышен лимит запросов",
    extra_data={"user_id": "123", "requests_per_minute": 150}
)

# Этот лог БУДЕТ отправлен в RabbitMQ (ERROR уровень)
logger.error(
    section=LogSection.DATABASE,
    subsection="connection",
    message="Ошибка подключения к БД",
    extra_data={"database": "mongodb", "error": "Connection timeout"}
)
```

### Прямое использование издателя

```python
from app.logging.rabbitmq_handler import get_rabbitmq_publisher
from app.logging.log_models import StructuredLogEntry, LogLevel, LogSection

# Получаем издателя
publisher = get_rabbitmq_publisher()

# Создаем структурированный лог
log_entry = StructuredLogEntry(
    level=LogLevel.ERROR,
    section=LogSection.SECURITY,
    subsection="injection_attempt",
    message="Попытка SQL инъекции",
    extra_data={"query": "SELECT * FROM users; DROP TABLE users;"},
    ip_address="10.0.0.1"
)

# Отправляем в RabbitMQ
success = await publisher.publish_log(log_entry)
```

### Мониторинг в RabbitMQ

1. Откройте веб-интерфейс RabbitMQ: `http://localhost:15672`
2. Логин: `guest`, пароль: `guest`
3. Перейдите в раздел "Exchanges" → "logs"
4. Просматривайте сообщения в очереди

### Формат сообщений в RabbitMQ

```json
{
    "timestamp": "2024-01-15 14:30:45 +05",
    "log_id": "a7b3c5d1",
    "level": "ERROR",
    "section": "security",
    "subsection": "injection_attempt",
    "message": "Попытка SQL инъекции",
    "extra_data": {
        "query": "SELECT * FROM users; DROP TABLE users;",
        "source_file": "auth_router.py",
        "source_function": "login",
        "source_line": 45
    },
    "user_id": null,
    "ip_address": "10.0.0.1",
    "user_agent": null,
    "source": "structured_logger"
}
```

### Обработка сообщений

Создайте потребителя для обработки логов:

```python
from faststream import FastStream
from faststream.rabbit import RabbitBroker

app = FastStream(RabbitBroker("amqp://guest:guest@localhost:5672/"))

@app.subscriber("logs", "application.logs")
async def handle_logs(log_data: dict):
    """Обработчик логов из RabbitMQ"""
    print(f"Получен лог: {log_data['level']} - {log_data['message']}")
    
    # Ваша логика обработки
    if log_data['level'] == 'CRITICAL':
        # Отправить уведомление администратору
        pass
    elif log_data['level'] == 'ERROR':
        # Записать в базу данных
        pass
```

## 🔧 Устранение неполадок

### Логи не создаются
- Проверьте права доступа к директории `logs/`
- Убедитесь что `LOG_LEVEL` установлен правильно

### Файлы логов слишком большие
- Уменьшите `LOG_MAX_BYTES`
- Увеличьте `LOG_BACKUP_COUNT`

### Проблемы с часовым поясом
- Проверьте что `pytz` установлен
- Время автоматически устанавливается в GMT+5

### Проблемы с RabbitMQ
- Убедитесь что RabbitMQ запущен и доступен
- Проверьте настройки подключения в переменных окружения
- Проверьте логи подключения в консоли приложения

## 📚 Примеры

Смотрите файл `examples.py` для подробных примеров использования всех функций системы логирования. 