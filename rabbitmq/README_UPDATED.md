# RabbitMQ для Royal Test Project - Обновленная интеграция

Обновленная безопасная и масштабируемая конфигурация RabbitMQ в Docker с полной интеграцией в существующую систему логирования проекта.

## 🔄 Что изменилось в обновлении

### ✅ Интеграция с существующими системами
- **Обновлены хендлеры** в `backend/app/logging/rabbitmq_handler.py`
- **Обновлены хендлеры** в `backend_2fa_admin/log_system/rabbitmq_handler.py`
- **Обновлены консьюмеры** в `rabbitmq_consumer/`
- **Новые routing keys** для лучшей маршрутизации логов

### 🔧 Новая архитектура routing keys
```
Старая система:          Новая система:
application.logs   →     logs.info.application
2fa.logs          →     logs.info.2fa
auth.logs         →     logs.info.redis
                        logs.error.application
                        logs.error.2fa  
                        logs.error.redis
```

## 🚀 Быстрый старт для обновления

### 1. Обновление инфраструктуры
```bash
cd rabbitmq
stop_rabbitmq.bat     # Остановить старую версию
start_rabbitmq.bat    # Запустить обновленную версию
```

### 2. Проверка работы
```bash
status_rabbitmq.bat   # Проверить статус
```

### 3. Тестирование интеграции
```bash
python integration_example_updated.py test
```

## 🔗 Новые настройки подключения

### Для основного приложения (backend)
```python
# Файл: backend/app/logging/rabbitmq_handler.py
RABBITMQ_URL = "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs"
EXCHANGE_NAME = "logs_exchange"
ROUTING_KEY = "logs.info.application"  # Динамически определяется
```

### Для 2FA микросервиса
```python
# Файл: backend_2fa_admin/log_system/rabbitmq_handler.py  
RABBITMQ_URL = "amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs"
EXCHANGE_NAME = "logs_exchange"
ROUTING_KEY = "logs.info.2fa"  # Динамически определяется
```

### Переменные окружения
```bash
# Добавьте в .env или environment
RABBITMQ_URL=amqp://royal_logger:Royal_Logger_Pass@localhost:5672/royal_logs
RABBITMQ_EXCHANGE=logs_exchange
RABBITMQ_ROUTING_KEY=logs.info.application
```

## 📊 Новая структура routing keys

### Информационные логи (WARNING+)
- `logs.info.application` - Основное приложение
- `logs.info.2fa` - Микросервис 2FA  
- `logs.info.redis` - Redis и rate limiter
- `logs.info.security` - Безопасность
- `logs.info.*` - Все информационные логи

### Логи ошибок (ERROR, CRITICAL)
- `logs.error.application` - Ошибки приложения
- `logs.error.2fa` - Ошибки 2FA
- `logs.error.redis` - Ошибки Redis
- `logs.error.security` - Критичные ошибки безопасности
- `logs.error.*` - Все логи ошибок

## 🏗️ Архитектура системы

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Backend App     │    │ 2FA Microservice │    │ Rate Limiter    │
│ (FastAPI)       │    │ (FastAPI)        │    │ (Redis)         │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          │ logs.info.application │ logs.info.2fa         │ logs.info.redis
          │ logs.error.application│ logs.error.2fa        │ logs.error.redis
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │     RabbitMQ Docker      │
                    │   logs_exchange (topic)  │
                    │                          │
                    │  ┌─────────────────────┐ │
                    │  │ royal_logs vhost    │ │
                    │  │ ├─ logs_main queue  │ │
                    │  │ └─ logs_error queue │ │
                    │  └─────────────────────┘ │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Log Consumer          │
                    │  (rabbitmq_consumer/)    │
                    │                          │
                    │ ┌─ Консоль с цветами    │
                    │ ├─ Файлы логов          │
                    │ ├─ База данных          │
                    │ └─ Уведомления          │
                    └──────────────────────────┘
```

## 👥 Пользователи и права (обновлено)

| Пользователь | Пароль | VHost | Права | Назначение |
|--------------|--------|-------|-------|------------|
| `royal_admin` | `Royal_RabbitMQ_1337` | royal_vhost, royal_logs | Администратор | Управление |
| `royal_logger` | `Royal_Logger_Pass` | royal_logs | Только логи | Отправка логов |
| `royal_app` | `Royal_App_1337` | royal_vhost | Приложение | Основная работа |

## 📋 Очереди и биндинги (обновлено)

### Очередь `logs_main`
- **TTL**: 7 дней
- **Max Length**: 50,000 сообщений
- **Routing Keys**: `logs.info.*`
- **Приоритет**: Обычный

### Очередь `logs_error`  
- **TTL**: 14 дней
- **Max Length**: 25,000 сообщений
- **Routing Keys**: `logs.error.*`
- **Приоритет**: Высокий (5)

## 🔧 Интеграция с существующим кодом

### Rate Limiter Integration
```python
# В rate_limiter.py уже обновлен для отправки в RabbitMQ
from backend.app.logging.rabbitmq_handler import get_rabbitmq_publisher

# Отправка rate limit лога
publisher = get_rabbitmq_publisher()
await publisher.publish_log(log_entry)
```

### Обычные логи приложения
```python
from backend.app.logging.logger_setup import get_logger

logger = get_logger(section=LogSection.SECURITY, subsection="AUTH")
logger.warning("Подозрительная активность")  # Автоматически в RabbitMQ
```

### 2FA логи
```python
from backend_2fa_admin.log_system.logger_setup import get_logger

logger = get_logger(section="2FA", subsection="TOKEN")
logger.error("Ошибка генерации токена")  # Автоматически в RabbitMQ
```

## 🔍 Мониторинг и отладка

### Проверка подключения
```bash
# Проверить статус RabbitMQ
status_rabbitmq.bat

# Проверить логи RabbitMQ
logs_rabbitmq.bat

# Проверить очереди в Management UI
# http://localhost:15672 (royal_admin / Royal_RabbitMQ_1337)
```

### Запуск консьюмера для отладки
```bash
# Простой консьюмер с выводом в консоль
cd rabbitmq_consumer
python consumer.py

# Или более детальный
python log_consumer.py
```

### Тестирование интеграции
```bash
# Тест всей системы
python rabbitmq/integration_example_updated.py test

# Информация о подключении
python rabbitmq/integration_example_updated.py info
```

## 🐛 Диагностика проблем

### Частые проблемы после обновления

| Проблема | Решение |
|----------|---------|
| Логи не доходят в RabbitMQ | Проверьте переменные окружения RABBITMQ_URL |
| Ошибки аутентификации | Убедитесь что пользователь `royal_logger` создан |
| Очереди пустые | Проверьте routing keys и биндинги |
| Consumer не получает сообщения | Обновите ROUTING_KEYS в консьюмере |

### Команды диагностики
```bash
# Проверить пользователей
docker exec royal_rabbitmq rabbitmqctl list_users

# Проверить очереди 
docker exec royal_rabbitmq rabbitmqctl list_queues -p royal_logs

# Проверить биндинги
docker exec royal_rabbitmq rabbitmqctl list_bindings -p royal_logs

# Проверить соединения
docker exec royal_rabbitmq rabbitmqctl list_connections
```

## 🔄 Миграция со старой версии

### 1. Сохранение данных
```bash
backup_rabbitmq.bat  # Создать резервную копию
```

### 2. Обновление конфигурации
```bash
# Остановить старую версию
docker-compose down

# Обновить файлы (уже сделано)
# Запустить новую версию
start_rabbitmq.bat
```

### 3. Проверка работы
```bash
# Проверить что все сервисы подключаются
python integration_example_updated.py test

# Проверить что консьюмер получает сообщения
python rabbitmq_consumer/consumer.py
```

## 📈 Производительность

### Новые оптимизации
- **Умная маршрутизация**: Автоматическое определение routing key
- **Приоритеты сообщений**: Ошибки обрабатываются первыми
- **TTL оптимизация**: Разные сроки хранения для разных типов логов
- **Батчинг**: Улучшенная обработка массовых логов

### Мониторинг производительности
```bash
# Статистика очередей
docker exec royal_rabbitmq rabbitmqctl list_queues -p royal_logs messages_ready messages_unacknowledged

# Использование памяти
docker stats royal_rabbitmq --no-stream
```

## 🔐 Безопасность

### Обновленные меры безопасности
- ✅ Отдельный пользователь для логирования (`royal_logger`)
- ✅ Изолированный vhost для логов (`royal_logs`)
- ✅ Ограниченные права доступа
- ✅ Обновленные пароли (измените в production!)

### Рекомендации для production
1. **Измените все пароли** в `config/definitions.json`
2. **Используйте TLS** для внешних подключений
3. **Настройте мониторинг** логов безопасности
4. **Регулярно обновляйте** Docker образы

## 📞 Поддержка

### При проблемах с интеграцией
1. Проверьте логи: `logs_rabbitmq.bat`
2. Проверьте статус: `status_rabbitmq.bat`
3. Запустите тесты: `python integration_example_updated.py test`
4. Проверьте консьюмер: `python rabbitmq_consumer/consumer.py`

### Полезные команды
```bash
# Перезапуск всей системы
restart_rabbitmq.bat

# Просмотр конфигурации
docker exec royal_rabbitmq rabbitmqctl environment

# Очистка очередей (осторожно!)
docker exec royal_rabbitmq rabbitmqctl purge_queue logs_main -p royal_logs
```

---

**Версия:** 2.0 (Интеграционная)  
**Совместимость:** RabbitMQ 3.12+, Docker Compose 3.8+, Royal Test Project  
**Последнее обновление:** $(date)  
**Автор:** Royal Test Project Team 