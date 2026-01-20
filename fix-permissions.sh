#!/bin/bash
# Исправление прав доступа для Docker volumes

echo "🔐 Исправление прав доступа..."

# Redis
if [ -d "redis/data" ]; then
    sudo chmod -R 777 redis/data
    sudo chmod -R 777 redis/logs
    echo "✓ Redis права исправлены"
fi

# RabbitMQ - КРИТИЧНО: .erlang.cookie должен быть 600
if [ -d "rabbitmq/data" ]; then
    sudo chmod -R 777 rabbitmq/data
    sudo chmod -R 777 rabbitmq/logs
    # Исправляем .erlang.cookie если существует
    if [ -f "rabbitmq/data/.erlang.cookie" ]; then
        sudo chmod 600 rabbitmq/data/.erlang.cookie
        echo "✓ RabbitMQ .erlang.cookie исправлен на 600"
    fi
    echo "✓ RabbitMQ права исправлены"
fi

# MongoDB
if [ -d "mongodb/data" ]; then
    sudo chmod -R 777 mongodb/data
    echo "✓ MongoDB права исправлены"
fi

# Media files
if [ -d "video_test" ]; then
    sudo chmod -R 777 video_test
    echo "✓ Медиа файлы права исправлены"
fi

echo "
✅ Все права исправлены!

ВНИМАНИЕ: Если RabbitMQ все еще не стартует, удалите его data:
  sudo rm -rf rabbitmq/data/*
  docker compose -f docker-compose.prod.yml up -d rabbitmq
"
