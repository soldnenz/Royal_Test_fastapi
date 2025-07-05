# 2FA Microservice

Независимый микросервис для двухфакторной аутентификации через Telegram бота.

## Описание

Микросервис предоставляет API для отправки 2FA запросов администраторам через Telegram бота. Основной сервис может безопасно отправлять запросы на этот микросервис, который обрабатывает взаимодействие с Telegram.

## Структура проекта

```
backend_2fa_admin/
├── config.py              # Конфигурация
├── database.py            # Подключение к базе данных
├── api.py                 # FastAPI приложение
├── telegram_bot.py        # Telegram бот
├── schemas.py             # Pydantic схемы
├── main.py                # Точка входа
├── start.py               # Скрипт запуска
├── requirements.txt       # Зависимости
├── env_example.txt       # Пример конфигурации
├── Dockerfile            # Docker контейнер
├── log_system/           # Система логирования
│   ├── __init__.py
│   ├── log_models.py
│   ├── logger_setup.py
│   └── rabbitmq_handler.py
└── README.md             # Документация
```

## Установка и запуск

1. **Клонируйте проект и перейдите в директорию:**
   ```bash
   cd backend_2fa_admin
   ```

2. **Создайте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   venv\Scripts\activate     # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Создайте файл конфигурации:**
   ```bash
   cp env_example.txt .env
   ```

5. **Настройте .env файл:**
   ```env
   # Database Configuration
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB_NAME=royal_test
   
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   
   # Server Configuration
   HOST=0.0.0.0
   PORT=8001
   
   # Security
   SECRET_KEY=your_secret_key_here
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   # Logging
   LOG_LEVEL=INFO
   LOG_FILE=logs/2fa_service.log
   ```

6. **Запустите сервис:**
   ```bash
   python main.py
   ```

## API Endpoints

### POST /send-2fa
Отправляет 2FA запрос администратору через Telegram.

**Request Body:**
```json
{
  "admin_id": "507f1f77bcf86cd799439011",
  "admin_name": "Иван Иванов",
  "admin_email": "ivan@example.com",
  "telegram_id": "123456789",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "location": "Kazakhstan, Almaty"
}
```

**Response:**
```json
{
  "success": true,
  "message": "2FA запрос отправлен",
  "request_id": "507f1f77bcf86cd799439012",
  "expires_at": "2024-01-01T12:00:00Z"
}
```

### GET /status/{request_id}
Получает статус 2FA запроса.

**Response:**
```json
{
  "request_id": "507f1f77bcf86cd799439012",
  "status": "pending",
  "admin_id": "507f1f77bcf86cd799439011",
  "created_at": "2024-01-01T11:55:00Z",
  "expires_at": "2024-01-01T12:00:00Z",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0..."
}
```

### GET /health
Проверка здоровья сервиса.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "database": "connected",
  "telegram_bot": "connected"
}
```

### POST /cleanup
Ручная очистка истекших запросов.

## Интеграция с основным сервисом

В основном сервисе замените прямые вызовы Telegram бота на HTTP запросы к микросервису:

```python
import httpx

async def send_2fa_request_to_microservice(admin_data, ip, user_agent):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/send-2fa",
            json={
                "admin_id": str(admin_data["_id"]),
                "admin_name": admin_data["full_name"],
                "admin_email": admin_data.get("email"),
                "telegram_id": admin_data["telegram_id"],
                "ip_address": ip,
                "user_agent": user_agent
            }
        )
        return response.json()
```

## Безопасность

- Rate limiting (10 запросов в минуту с одного IP)
- Валидация входных данных
- Логирование всех операций
- Автоматическая очистка истекших запросов
- CORS настройки для продакшена

## Логирование

Сервис использует структурированное логирование с разделами:
- `auth` - аутентификация
- `2fa` - двухфакторная аутентификация
- `telegram` - взаимодействие с Telegram
- `security` - безопасность
- `api` - API запросы
- `system` - системные события

## Мониторинг

- Health check endpoint для проверки состояния
- Автоматическая очистка истекших запросов каждые 5 минут
- Детальное логирование всех операций

## Развертывание

### Docker (рекомендуется)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "main.py"]
```

### Systemd Service

```ini
[Unit]
Description=2FA Microservice
After=network.target

[Service]
Type=simple
User=2fa-service
WorkingDirectory=/opt/2fa-service
Environment=PATH=/opt/2fa-service/venv/bin
ExecStart=/opt/2fa-service/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Устранение неполадок

1. **Проверьте конфигурацию:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **Проверьте логи:**
   ```bash
   tail -f logs/2fa_service.log
   ```

3. **Проверьте подключение к базе данных:**
   ```bash
   mongo --eval "db.runCommand('ping')"
   ```

4. **Проверьте Telegram бота:**
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
   ``` 