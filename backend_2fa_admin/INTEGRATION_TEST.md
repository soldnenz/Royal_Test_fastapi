# Тестирование интеграции backend_2fa_admin + rabbitmq_consumer

## 🎯 Цель
Проверить что логи из `backend_2fa_admin` корректно отправляются в RabbitMQ и принимаются `rabbitmq_consumer`.

## 🔧 Исправленные проблемы

1. **Exchange name**: изменен с `logs` на `logs_exchange`
2. **Routing keys**: используются `logs.info.2fa` и `logs.error.2fa`
3. **JSON сериализация**: timestamp и enum значения корректно сериализуются
4. **Уровень логирования**: INFO логи теперь отправляются в RabbitMQ
5. **Source поле**: убран префикс `2fa_` для совместимости

## 🚀 Запуск тестов

### 1. Запустите RabbitMQ Consumer
```bash
cd rabbitmq_consumer
python log_consumer.py
```

### 2. Запустите тест интеграции
```bash
cd backend_2fa_admin
python test_rabbitmq_integration.py
```

## 📊 Ожидаемый результат

В consumer вы должны увидеть:
- INFO логи с routing key `logs.info.2fa`
- WARNING/ERROR/CRITICAL логи с routing key `logs.error.2fa`
- Правильный формат JSON с полями:
  - `timestamp` (ISO format)
  - `level` (string)
  - `section` и `subsection` (string)
  - `message`
  - `source: "structured_logger"`

## 🔍 Структура логов

```json
{
  "timestamp": "2024-01-01T12:00:00.123456+05:00",
  "log_id": "uuid",
  "level": "INFO",
  "section": "2fa", 
  "subsection": "request_sent",
  "message": "Лог сообщение",
  "extra_data": {...},
  "user_id": "user123",
  "ip_address": "192.168.1.1",
  "user_agent": "Browser/1.0",
  "source": "structured_logger"
}
```

## ✅ Критерии успеха

- [ ] Consumer получает логи всех уровней (INFO, WARNING, ERROR, CRITICAL)
- [ ] Routing keys соответствуют ожидаемым
- [ ] JSON формат корректный
- [ ] Поля timestamp и enum значения правильно сериализованы
- [ ] Нет ошибок подключения к RabbitMQ 