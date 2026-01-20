# Исправление системы загрузки медиафайлов

## Файлы для коммита (связанные с медиа-системой):

### 1. Backend изменения
- ✅ `backend/app/core/media_manager.py` - Исправлен путь и добавлена проверка сохранения
- ✅ `backend/init_folders.sh` - Улучшено создание папок с проверками

### 2. Nginx конфигурация
- ✅ `nginx/conf.d/frontend.dev.conf` - Увеличен client_max_body_size до 100MB
- ✅ `nginx/conf.d/frontend.prod.conf` - Увеличен client_max_body_size до 100MB

### 3. Новые файлы
- ✅ `init-media-folders.sh` - Скрипт инициализации структуры папок
- ✅ `start-dev.sh` - Скрипт запуска DEV окружения
- ✅ `start-prod.sh` - Скрипт запуска PROD окружения
- ✅ `MEDIA_DEPLOY.md` - Документация по развертыванию

## Ключевые исправления:

### 1. MediaManager (backend/app/core/media_manager.py)
```python
# БЫЛО:
project_root = Path(__file__).parent.parent.parent.parent  # = /
self.base_path = project_root / settings.MEDIA_BASE_PATH  # = /video_test

# СТАЛО:
project_root = Path(__file__).parent.parent.parent  # = /app
self.base_path = project_root / settings.MEDIA_BASE_PATH  # = /app/video_test
```

```python
# Добавлено:
await file.seek(0)  # Сброс курсора перед чтением
# Проверка физического создания файла
if not file_path.exists():
    raise Exception(f"Файл не был создан: {file_path}")
```

### 2. Nginx (frontend.dev.conf и frontend.prod.conf)
```nginx
# Добавлено в location /api/:
client_max_body_size 100M;
client_body_buffer_size 128k;
```

### 3. Автоматизация (новые скрипты)
- `init-media-folders.sh` - создает структуру папок автоматически
- `start-dev.sh` и `start-prod.sh` - запускают окружение с инициализацией

## Проверка перед деплоем в PROD:

1. Структура папок создается автоматически ✅
2. Nginx разрешает загрузку до 100MB ✅
3. MediaManager сохраняет файлы в правильную директорию ✅
4. Логируется физическое сохранение файла ✅
5. Есть проверка существования файла на диске ✅

## Команды для деплоя в PROD:

```bash
# 1. Инициализация папок
./init-media-folders.sh

# 2. Пересборка образов
docker-compose -f docker-compose.prod.yml build

# 3. Запуск
docker-compose -f docker-compose.prod.yml up -d

# 4. Проверка
docker logs royal_backend_prod --tail 50 | grep "физически сохранен"
docker exec royal_backend_prod ls -la /app/video_test/images/
```

## Что НЕ нужно коммитить:

- ❌ `.env` файлы (уже в .gitignore)
- ❌ `mongodb/` данные
- ❌ `rabbitmq/data/` данные
- ❌ `redis/data/` данные  
- ❌ `video_test/` медиафайлы
- ❌ Логи и временные файлы

## Рекомендуемый коммит:

```bash
git add backend/app/core/media_manager.py
git add backend/init_folders.sh
git add nginx/conf.d/frontend.dev.conf
git add nginx/conf.d/frontend.prod.conf
git add init-media-folders.sh
git add start-dev.sh
git add start-prod.sh
git add MEDIA_DEPLOY.md

git commit -m "Fix media upload system

- Fix MediaManager base_path calculation (/app/video_test instead of /video_test)
- Add file.seek(0) before saving to reset file cursor
- Add file existence verification after saving
- Increase nginx client_max_body_size to 100MB for both dev and prod
- Add init-media-folders.sh script for automatic folder structure creation
- Add start-dev.sh and start-prod.sh convenience scripts
- Add comprehensive media deployment documentation

Fixes:
- 413 Request Entity Too Large errors
- Files not being physically saved to disk
- Media files returning 404"
```
