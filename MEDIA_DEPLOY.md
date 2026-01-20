# Инструкция по развертыванию медиа-системы

## Что было исправлено

### 1. MediaManager (backend/app/core/media_manager.py)
- ✅ Исправлен путь к папке медиа: `/app/video_test` вместо `/video_test`
- ✅ Добавлен `await file.seek(0)` перед сохранением файла
- ✅ Добавлена проверка физического сохранения файла на диск
- ✅ Добавлено подробное логирование процесса сохранения

### 2. Nginx конфигурация
- ✅ **DEV**: Увеличен `client_max_body_size` до 100MB в `nginx/conf.d/frontend.dev.conf`
- ✅ **PROD**: Увеличен `client_max_body_size` до 100MB в `nginx/conf.d/frontend.prod.conf`
- ✅ Добавлен `client_body_buffer_size 128k` для оптимизации

### 3. Структура папок
- ✅ Создан скрипт `init-media-folders.sh` для автоматического создания структуры папок
- ✅ Улучшен `backend/init_folders.sh` с безопасным созданием папок
- ✅ Созданы скрипты запуска `start-dev.sh` и `start-prod.sh`

## Запуск DEV окружения

```bash
# Вариант 1: Автоматический запуск с инициализацией папок
./start-dev.sh

# Вариант 2: Ручной запуск
./init-media-folders.sh
docker-compose -f docker-compose.dev.yml up -d
```

## Запуск PROD окружения

```bash
# Вариант 1: Автоматический запуск с инициализацией папок
./start-prod.sh

# Вариант 2: Ручной запуск
./init-media-folders.sh
docker-compose -f docker-compose.prod.yml up -d
```

## Структура папок медиа

```
video_test/
├── images/       # Изображения (PNG, JPG, WEBP, GIF)
├── videos/       # Видео файлы (MP4, AVI, MOV)
├── audio/        # Аудио файлы (MP3, WAV, OGG)
└── documents/    # Документы (PDF, DOCX)
```

## Лимиты загрузки

- **Nginx**: 100 MB
- **Backend**: 50 MB (настройка в `backend/app/core/config.py`)
- **Рекомендуемый размер**: до 10 MB для оптимальной производительности

## Проверка работоспособности

### 1. Проверка структуры папок
```bash
ls -la video_test/
# Должны быть папки: images/, videos/, audio/, documents/
```

### 2. Проверка nginx конфигурации
```bash
docker exec royal_nginx_prod nginx -t
```

### 3. Проверка логов backend
```bash
docker logs royal_backend_prod --tail 50 | grep "физически сохранен"
```

### 4. Проверка файлов на диске
```bash
# В DEV
docker exec royal_backend_dev ls -la /app/video_test/images/

# В PROD
docker exec royal_backend_prod ls -la /app/video_test/images/
```

## Troubleshooting

### Проблема: 413 Request Entity Too Large
**Решение**: Пересоберите nginx образ
```bash
docker-compose -f docker-compose.prod.yml build nginx
docker-compose -f docker-compose.prod.yml up -d nginx
```

### Проблема: Файл в БД но не на диске
**Решение**: Очистите БД от плохих записей
```bash
docker exec royal_backend_prod python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def cleanup():
    client = AsyncIOMotorClient('mongodb://admin:rd_royal_driving_1337@host.docker.internal:27017/?authSource=admin')
    db = client['royal']
    
    cursor = db.media_files.find({})
    deleted = []
    
    async for file_doc in cursor:
        file_path = f\"/app/video_test/{file_doc['relative_path']}\"
        if not os.path.exists(file_path):
            print(f\"Удаляем: {file_doc['_id']}\")
            await db.media_files.delete_one({'_id': file_doc['_id']})
            deleted.append(str(file_doc['_id']))
    
    if deleted:
        await db.questions.update_many(
            {},
            {'\$set': {'has_media': False},
             '\$unset': {'media_file_id': '', 'media_filename': ''}}
        )
    
    print(f\"Удалено {len(deleted)} записей\")
    client.close()

asyncio.run(cleanup())
"
```

### Проблема: Папки не создаются
**Решение**: Запустите скрипт инициализации вручную
```bash
./init-media-folders.sh
```

## Миграция на PROD

1. Убедитесь что все папки созданы:
```bash
./init-media-folders.sh
```

2. Пересоберите образы:
```bash
docker-compose -f docker-compose.prod.yml build
```

3. Запустите контейнеры:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

4. Проверьте логи:
```bash
docker-compose -f docker-compose.prod.yml logs -f backend nginx
```

## Важно!

- ⚠️ **Всегда запускайте** `./init-media-folders.sh` перед первым запуском
- ⚠️ **Не удаляйте** папку `video_test` - там хранятся все медиа файлы
- ⚠️ **Делайте бэкапы** папки `video_test` регулярно
- ⚠️ **Проверяйте логи** после загрузки файлов на фразу "физически сохранен"
