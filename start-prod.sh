#!/bin/bash
# Скрипт для запуска PROD окружения
# Автоматически инициализирует папки и запускает docker-compose

set -e

echo "🚀 Запуск PROD окружения..."
echo ""

# Переходим в директорию проекта
cd "$(dirname "${BASH_SOURCE[0]}")"

# Инициализируем структуру папок
echo "📁 Инициализация папок..."
./init-media-folders.sh

echo ""
echo "🐳 Запуск Docker контейнеров (PROD)..."
echo ""

# Запускаем docker-compose
docker-compose -f docker-compose.prod.yml up -d

echo ""
echo "✅ PROD окружение запущено!"
echo ""
echo "📊 Доступные сервисы:"
echo "   - Frontend:        http://localhost"
echo "   - Backend API:     http://localhost/api"
echo "   - WebSocket:       ws://localhost/ws"
echo "   - Redis:           localhost:6379"
echo "   - RabbitMQ:        http://localhost:15672"
echo ""
echo "💡 Для просмотра логов: docker-compose -f docker-compose.prod.yml logs -f"
echo "💡 Для остановки: docker-compose -f docker-compose.prod.yml down"
echo ""
