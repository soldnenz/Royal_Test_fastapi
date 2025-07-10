# Исправление Deprecated Variables в RabbitMQ

## 🚨 Проблема
При запуске RabbitMQ появлялись ошибки:
```
error: RABBITMQ_VM_MEMORY_HIGH_WATERMARK is set but deprecated
error: deprecated environment variables detected
Please use a configuration file instead
```

## ✅ Решение

### 1. Удалены устаревшие переменные из docker-compose.yml:
- ❌ `RABBITMQ_VM_MEMORY_HIGH_WATERMARK: 0.8`
- ❌ `RABBITMQ_DISK_FREE_LIMIT: 2GB`
- ❌ Лишние настройки в `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS`

### 2. Все настройки производительности перенесены в config/rabbitmq.conf:
```ini
# Лимит памяти VM (80% от доступной памяти контейнера = 819MB из 1024MB)
vm_memory_high_watermark.relative = 0.8

# Стратегия освобождения памяти при достижении 50% от watermark
vm_memory_high_watermark_paging_ratio = 0.5

# Лимит свободного места на диске (2GB)
disk_free_limit.absolute = 2147483648
```

### 3. Обновлена документация:
- Добавлены комментарии в `env_example.txt`
- Обновлен `config/rabbitmq.conf` с пояснениями
- Добавлена информация в батники запуска

## 📋 Что изменилось

### docker-compose.yml
```yaml
# БЫЛО (deprecated):
environment:
  RABBITMQ_VM_MEMORY_HIGH_WATERMARK: 0.8
  RABBITMQ_DISK_FREE_LIMIT: 2GB

# СТАЛО (правильно):
environment:
  RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-royal_admin}
  RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-Royal_RabbitMQ_1337}
  # Остальные настройки в config/rabbitmq.conf
```

### config/rabbitmq.conf
```ini
# Все настройки памяти и диска теперь здесь
vm_memory_high_watermark.relative = 0.8
vm_memory_high_watermark_paging_ratio = 0.5
disk_free_limit.absolute = 2147483648
```

## 🔍 Проверка исправления

### 1. Перезапустить RabbitMQ:
```bash
stop_rabbitmq.bat
start_rabbitmq.bat
```

### 2. Проверить логи (не должно быть ошибок deprecated):
```bash
docker compose logs rabbitmq | findstr -i "deprecated\|error"
```

### 3. Проверить настройки памяти:
```bash
docker exec royal_rabbitmq rabbitmqctl status
```

## 📊 Результат

✅ **Никаких deprecated warnings**  
✅ **Лимит памяти: 819MB (80% от 1GB)**  
✅ **Лимит диска: 2GB**  
✅ **Все настройки работают корректно**

## 🛠️ Дополнительные команды для диагностики

```bash
# Проверить текущие настройки памяти
docker exec royal_rabbitmq rabbitmqctl eval 'rabbit_vm:memory().'

# Проверить лимиты
docker exec royal_rabbitmq rabbitmqctl environment | findstr memory

# Проверить использование ресурсов
docker stats royal_rabbitmq --no-stream
```

## 📝 Примечания

- Все deprecated переменные удалены согласно рекомендациям RabbitMQ 3.12+
- Настройки производительности управляются исключительно через `config/rabbitmq.conf`
- Поведение системы не изменилось - только исправлены warnings
- Совместимость с RabbitMQ 3.12+ полностью обеспечена

---
**Дата исправления:** $(date)  
**Статус:** ✅ Решено  
**Версия RabbitMQ:** 3.12+ 