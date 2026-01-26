#!/bin/bash
# Скрипт для настройки .env файлов в продакшене

echo "🔐 Настройка .env файлов для production..."

# Генерируем безопасный SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)
echo "🔑 Сгенерирован SECRET_KEY: $SECRET_KEY"

# BACKEND - только нужные переменные
cat > backend/.env << EOF
# MongoDB
MONGO_URI=
MONGO_DB_NAME=royal

# Security
SECRET_KEY=$SECRET_KEY
TELEGRAM_BOT_TOKEN=

# Admin
SUPER_ADMIN_IDS=1,2,3

# PDD Settings
pdd_categories=["A","B"]
max_file_size_mb=50
allowed_media_types=["image/jpeg","image/png","video/mp4","video/quicktime"]
PDD_SECTIONS=[{"id":1,"name":"Example"}]
DEFAULT_REFERRAL_RATE=10
REQUIRE_2FA=false

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=1
REDIS_MULTIPLAYER_DB=2

# Media
MEDIA_BASE_PATH=video_test
EOF
echo "✓ backend/.env создан"

# BACKEND_WS - WebSocket config
cat > backend_ws/.env << EOF
HOST=0.0.0.0
PORT=8002
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
MONGO_URI=
MONGO_DB_NAME=royal
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=Royal_Redis_1337
REDIS_DB=1
REDIS_MULTIPLAYER_DB=2
CORS_ORIGINS=https://royal-driving.cc
EOF
echo "✓ backend_ws/.env создан"

# BACKEND_2FA_ADMIN
cat > backend_2fa_admin/.env << EOF
TELEGRAM_BOT_TOKEN_2FA=
TELEGRAM_BOT_TOKEN=
SECRET_KEY=$SECRET_KEY
MONGO_URI=
MONGO_DB_NAME=royal
EOF
echo "✓ backend_2fa_admin/.env создан"

# QUESTION REPORTS BOT
cat > bot_question_reports/.env << EOF
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_WARNING_TOPIC=2
MONGO_URI=
EOF
echo "✓ bot_question_reports/.env создан"

echo "
✅ Все .env файлы созданы с одинаковым SECRET_KEY!

📝 SECRET_KEY сохранен во всех файлах: $SECRET_KEY

⚠️  ВАЖНО: Сохраните этот ключ в надежном месте!
"
