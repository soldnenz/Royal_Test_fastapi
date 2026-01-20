# Инструкция по развертыванию на сервере

## 📋 Предварительные требования на сервере

1. **Docker и Docker Compose**
2. **Git**
3. **Открытые порты**: 80, 443, 8000, 8002, 27017, 6379, 5672, 15672

## 🚀 Первоначальное развертывание (Production)

### Шаг 1: Клонирование репозитория

```bash
# Подключитесь к серверу по SSH
ssh user@your-server-ip

# Перейдите в директорию для проектов
cd /opt  # или любую другую директорию

# Клонируйте репозиторий
git clone https://github.com/soldnenz/Royal_Test_fastapi.git
cd Royal_Test_fastapi
```

### Шаг 2: Инициализация структуры папок

```bash
# Запустите скрипт инициализации
chmod +x init-media-folders.sh start-prod.sh
./init-media-folders.sh
```

### Шаг 3: Проверка .env файлов

```bash
# Проверьте что все .env файлы на месте
ls -la backend/.env
ls -la .env.prod

# При необходимости отредактируйте .env файлы
nano backend/.env
```

### Шаг 4: Запуск Production окружения

```bash
# Вариант 1: Используя готовый скрипт (рекомендуется)
./start-prod.sh

# Вариант 2: Вручную
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### Шаг 5: Проверка запуска

```bash
# Проверьте что все контейнеры запущены
docker compose -f docker-compose.prod.yml ps

# Проверьте логи
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
```

## 🔄 Обновление (Pull новых изменений)

### Быстрое обновление

```bash
cd /opt/Royal_Test_fastapi

# Остановите контейнеры
docker compose -f docker-compose.prod.yml down

# Подтяните изменения
git pull origin master

# Инициализируйте папки (если нужно)
./init-media-folders.sh

# Пересоберите и запустите
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Проверьте логи
docker compose -f docker-compose.prod.yml logs -f
```

### Обновление без остановки (zero-downtime)

```bash
cd /opt/Royal_Test_fastapi

# Подтяните изменения
git pull origin master

# Пересоберите образы
docker compose -f docker-compose.prod.yml build

# Перезапустите контейнеры по одному
docker compose -f docker-compose.prod.yml up -d --no-deps backend
docker compose -f docker-compose.prod.yml up -d --no-deps nginx
```

## 🛠️ Полезные команды

### Просмотр логов

```bash
# Все логи
docker compose -f docker-compose.prod.yml logs -f

# Логи конкретного сервиса
docker logs royal_backend_prod -f
docker logs royal_nginx_prod -f

# Последние 100 строк
docker logs royal_backend_prod --tail 100
```

### Перезапуск сервисов

```bash
# Перезапустить всё
docker compose -f docker-compose.prod.yml restart

# Перезапустить конкретный сервис
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml restart nginx
```

### Остановка и удаление

```bash
# Остановить всё
docker compose -f docker-compose.prod.yml stop

# Остановить и удалить контейнеры
docker compose -f docker-compose.prod.yml down

# Удалить всё включая volumes (ОСТОРОЖНО!)
docker compose -f docker-compose.prod.yml down -v
```

### Проверка системы

```bash
# Проверка места на диске
df -h

# Проверка используемого места Docker
docker system df

# Очистка неиспользуемых образов
docker system prune -a

# Проверка папок медиа
ls -lah video_test/images/
ls -lah video_test/videos/
```

## 🔐 Безопасность

### Изменение паролей в .env

После первого развертывания обязательно измените:

```bash
# Отредактируйте backend/.env
nano backend/.env
```

Измените:
- `SECRET_KEY` - секретный ключ для JWT
- `MONGO_URI` - пароль MongoDB
- `REDIS_PASSWORD` - пароль Redis
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота

### Настройка файрвола (UFW)

```bash
# Разрешите необходимые порты
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

## 📊 Мониторинг

### Проверка работоспособности

```bash
# Проверка HTTP
curl http://localhost/api/

# Проверка медиа
docker logs royal_backend_prod --tail 50 | grep "физически сохранен"

# Проверка 2FA
docker logs royal_backend_prod --tail 50 | grep -i "2fa"
```

### Проверка ресурсов

```bash
# Использование CPU и RAM контейнерами
docker stats

# Проверка места на диске
du -sh video_test/*
```

## 🆘 Troubleshooting

### Проблема: Контейнер не запускается

```bash
# Смотрим логи
docker logs royal_backend_prod

# Проверяем конфигурацию
docker compose -f docker-compose.prod.yml config

# Пересоздаем контейнер
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### Проблема: 502 Bad Gateway

```bash
# Проверяем что backend запущен
docker ps | grep backend

# Смотрим логи nginx
docker logs royal_nginx_prod

# Перезапускаем nginx
docker compose -f docker-compose.prod.yml restart nginx
```

### Проблема: Медиа не загружаются

```bash
# Проверяем папки
ls -la video_test/

# Инициализируем заново
./init-media-folders.sh

# Перезапускаем backend
docker compose -f docker-compose.prod.yml restart backend
```

## 📝 Backup

### Резервное копирование медиа

```bash
# Создать архив медиа
tar -czf backup_media_$(date +%Y%m%d).tar.gz video_test/

# Копировать на другой сервер
scp backup_media_*.tar.gz user@backup-server:/backups/
```

### Резервное копирование MongoDB

```bash
# Экспорт базы данных
docker exec royal_mongodb_prod mongodump --out=/backup

# Копировать бэкап
docker cp royal_mongodb_prod:/backup ./mongodb_backup
```

## 🔄 Автоматическое обновление (cron)

Создайте скрипт автоматического обновления:

```bash
# Создайте скрипт
nano /opt/update-royal.sh
```

Добавьте:

```bash
#!/bin/bash
cd /opt/Royal_Test_fastapi
git pull origin master
./init-media-folders.sh
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

Сделайте исполняемым и добавьте в cron:

```bash
chmod +x /opt/update-royal.sh

# Добавьте в cron (каждый день в 3 утра)
crontab -e
# Добавьте строку:
# 0 3 * * * /opt/update-royal.sh >> /var/log/royal-update.log 2>&1
```
