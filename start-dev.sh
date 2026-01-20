#!/bin/bash
# Скрипт для запуска DEV окружения
# Автоматически инициализирует папки и запускает docker-compose

set -e

echo "🚀 Запуск DEV окружения..."
echo ""

# Переходим в директорию проекта
cd "$(dirname "${BASH_SOURCE[0]}")"

# Инициализируем структуру папок
echo "📁 Инициализация папок..."
./init-media-folders.sh

echo ""
echo "🐳 Запуск Docker контейнеров (DEV)..."
echo ""

# Запускаем docker compose (новый синтаксис Docker Compose V2)
docker compose -f docker-compose.dev.yml up -d

echo ""
echo "✅ DEV окружение запущено!"
echo ""
echo "📊 Доступные сервисы:"
echo "   - Frontend:        http://localhost"
echo "   - Admin Panel:     http://localhost/UDKeZNwbGVdH2iXEjkUFCkAuQb4Z1bbz/"
echo "   - Backend API:     http://localhost/api"
echo "   - WebSocket:       ws://localhost/ws"
echo "   - MongoDB:         mongodb://localhost:27017"
echo "   - Redis:           localhost:6379"
echo "   - RabbitMQ:        http://localhost:15672"
echo ""
echo "💡 Для просмотра логов: docker compose -f docker-compose.dev.yml logs -f"
echo "💡 Для остановки: docker compose -f docker-compose.dev.yml down"
echo ""
