#!/bin/bash
# Скрипт для инициализации папок при запуске контейнера
# Создает структуру папок даже если volume уже примонтирован

set -e

echo "🔧 Инициализация папок для медиа файлов..."

# Функция для безопасного создания папки
create_folder_safe() {
    local folder=$1
    if [ ! -d "$folder" ]; then
        mkdir -p "$folder" 2>/dev/null || true
        echo "   ✓ Создана: $folder"
    else
        echo "   ✓ Существует: $folder"
    fi
}

# Создание структуры папок для медиа
echo "📁 Проверка структуры медиа папок..."
create_folder_safe "/app/video_test"
create_folder_safe "/app/video_test/images"
create_folder_safe "/app/video_test/videos"
create_folder_safe "/app/video_test/audio"
create_folder_safe "/app/video_test/documents"

# Создание дополнительных папок
create_folder_safe "/app/static_media"
create_folder_safe "/app/logs"

# Установка прав (игнорируем ошибки если нет прав)
echo "🔐 Настройка прав доступа..."
chmod -R 755 /app/video_test 2>/dev/null || echo "   ⚠ Не удалось изменить права на /app/video_test (возможно уже примонтирован volume)"
chmod -R 755 /app/static_media 2>/dev/null || true
chmod -R 755 /app/logs 2>/dev/null || true

# Проверка наличия файлов
FILE_COUNT=$(find /app/video_test -type f 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "📊 Статистика медиа файлов: $FILE_COUNT файлов"

echo ""
echo "✅ Инициализация завершена успешно!"
echo ""

# Запуск основного приложения
exec "$@"
