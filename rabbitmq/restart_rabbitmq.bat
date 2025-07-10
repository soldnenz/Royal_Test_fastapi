@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Перезапуск
echo ========================================

echo [ИНФО] Проверка Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не установлен или не запущен!
    pause
    exit /b 1
)

echo [ИНФО] Остановка RabbitMQ...
docker compose down

timeout /t 3 /nobreak >nul

echo [ИНФО] Запуск RabbitMQ...
docker compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ✅ RabbitMQ успешно перезапущен!
    echo.
    echo 📊 Management UI: http://localhost:15672
    echo 🔗 AMQP порт: localhost:5672
    echo 👤 Пользователь: royal_admin
    echo 🔑 Пароль: Royal_RabbitMQ_1337
    echo.
    echo [ИНФО] Проверка статуса через 10 секунд...
    timeout /t 10 /nobreak >nul
    docker compose ps
) else (
    echo.
    echo ❌ Ошибка при перезапуске RabbitMQ!
    echo.
    echo [ИНФО] Логи ошибок:
    docker compose logs rabbitmq
)

echo.
pause 