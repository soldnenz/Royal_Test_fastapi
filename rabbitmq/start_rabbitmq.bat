@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Запуск
echo ========================================

:: Проверяем наличие .env файла
if not exist .env (
    echo [ОШИБКА] Файл .env не найден!
    echo Скопируйте env_example.txt в .env и настройте переменные
    pause
    exit /b 1
)

:: Создаем необходимые директории
if not exist data mkdir data
if not exist logs mkdir logs
if not exist config mkdir config

echo [ИНФО] Проверка Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не установлен или не запущен!
    pause
    exit /b 1
)

echo [ИНФО] Проверка Docker Compose...
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker Compose не найден!
    pause
    exit /b 1
)

echo [ИНФО] Остановка существующих контейнеров...
docker compose down

echo [ИНФО] Запуск RabbitMQ...
docker compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ✅ RabbitMQ успешно запущен!
    echo.
    echo 📊 Management UI: http://localhost:15672
    echo 🔗 AMQP порт: localhost:5672
    echo 👤 Пользователь: royal_admin
    echo 🔑 Пароль: Royal_RabbitMQ_1337
    echo 🏠 Virtual Host: royal_vhost
    echo.
    echo ℹ️  Все настройки производительности управляются через config/rabbitmq.conf
    echo ℹ️  Deprecated переменные окружения удалены
    echo.
    echo [ИНФО] Проверка статуса...
    timeout /t 10 /nobreak >nul
    docker compose ps
    echo.
    echo [ИНФО] Логи контейнера:
    echo docker compose logs -f rabbitmq
) else (
    echo.
    echo ❌ Ошибка при запуске RabbitMQ!
    echo.
    echo [ИНФО] Логи ошибок:
    docker compose logs rabbitmq
)

echo.
pause 