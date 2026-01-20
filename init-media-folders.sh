#!/bin/bash
# Скрипт для инициализации структуры папок медиа файлов на хосте
# Запускается ПЕРЕД docker-compose up для гарантии наличия всех необходимых папок

set -e

echo "🔧 Инициализация структуры папок для медиа файлов..."

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для создания папки с проверкой
create_folder() {
    local folder=$1
    if [ ! -d "$folder" ]; then
        mkdir -p "$folder"
        echo -e "${GREEN}✓${NC} Создана папка: ${BLUE}$folder${NC}"
    else
        echo -e "${GREEN}✓${NC} Папка уже существует: ${BLUE}$folder${NC}"
    fi
}

# Базовая директория проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "📁 Создание структуры папок для медиа..."

# Создание структуры папок для медиа файлов
create_folder "$PROJECT_DIR/video_test"
create_folder "$PROJECT_DIR/video_test/images"
create_folder "$PROJECT_DIR/video_test/videos"
create_folder "$PROJECT_DIR/video_test/audio"
create_folder "$PROJECT_DIR/video_test/documents"

echo ""
echo "📁 Создание дополнительных папок..."

# Создание папки для статических файлов
create_folder "$PROJECT_DIR/static"

# Создание папок для логов (если нужно)
create_folder "$PROJECT_DIR/backend/logs"
create_folder "$PROJECT_DIR/nginx/logs"
create_folder "$PROJECT_DIR/redis/logs"
create_folder "$PROJECT_DIR/rabbitmq/logs"
create_folder "$PROJECT_DIR/rabbitmq_consumer/logs"

# Установка прав доступа
echo ""
echo "🔐 Настройка прав доступа..."

# Делаем папки доступными для записи
chmod -R 755 "$PROJECT_DIR/video_test" 2>/dev/null || true
chmod -R 755 "$PROJECT_DIR/static" 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Инициализация завершена успешно!${NC}"
echo ""
echo "📊 Структура папок медиа:"
echo "   video_test/"
echo "   ├── images/     (для изображений)"
echo "   ├── videos/     (для видео)"
echo "   ├── audio/      (для аудио)"
echo "   └── documents/  (для документов)"
echo ""
echo "💡 Теперь можно запустить: docker-compose up"
echo ""
