#!/bin/bash
# Исправление прав доступа для Docker volumes

echo "🔐 Исправление прав доступа..."

# Redis
if [ -d "redis/data" ]; then
    chmod -R 777 redis/data
    chmod -R 777 redis/logs
    echo "✓ Redis права исправлены"
fi

# RabbitMQ
if [ -d "rabbitmq/data" ]; then
    chmod -R 777 rabbitmq/data
    chmod -R 777 rabbitmq/logs
    echo "✓ RabbitMQ права исправлены"
fi

# MongoDB
if [ -d "mongodb/data" ]; then
    chmod -R 777 mongodb/data
    echo "✓ MongoDB права исправлены"
fi

# Media files
if [ -d "video_test" ]; then
    chmod -R 777 video_test
    echo "✓ Медиа файлы права исправлены"
fi

echo "✅ Все права исправлены!"
