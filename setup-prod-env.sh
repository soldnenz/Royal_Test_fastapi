#!/bin/bash
# Скрипт для настройки .env файлов в продакшене

echo "🔐 Настройка .env файлов для production..."

# Копируем .env.prod в нужные места
cp .env.prod backend/.env
echo "✓ backend/.env создан"

# Создаем .env для других сервисов из .env.prod
grep "TELEGRAM_BOT_TOKEN_2FA" .env.prod > backend_2fa_admin/.env
grep "TELEGRAM_BOT_TOKEN" .env.prod >> backend_2fa_admin/.env
grep "SECRET_KEY" .env.prod >> backend_2fa_admin/.env
grep "MONGO_URI" .env.prod >> backend_2fa_admin/.env
grep "MONGO_DB_NAME" .env.prod >> backend_2fa_admin/.env
echo "✓ backend_2fa_admin/.env создан"

# WebSocket config
grep "HOST" .env.prod > backend_ws/.env
grep "PORT" .env.prod >> backend_ws/.env
grep "SECRET_KEY" .env.prod >> backend_ws/.env
grep "ALGORITHM" .env.prod >> backend_ws/.env
grep "MONGO_URI" .env.prod >> backend_ws/.env
grep "MONGO_DB_NAME" .env.prod >> backend_ws/.env
grep "REDIS" .env.prod >> backend_ws/.env
echo "✓ backend_ws/.env создан"

# Question reports bot
grep "TELEGRAM" .env.prod > bot_question_reports/.env
grep "MONGO_URI" .env.prod >> bot_question_reports/.env
grep "MONGO_DB_NAME" .env.prod >> bot_question_reports/.env
echo "✓ bot_question_reports/.env создан"

echo "
✅ Все .env файлы созданы!

⚠️  ВАЖНО: Отредактируйте .env.prod и установите:
   - SECRET_KEY (уникальный ключ для JWT)
   - TELEGRAM_BOT_TOKEN (если используется)
   - Другие production параметры

Затем запустите этот скрипт снова для обновления всех .env файлов.
"
