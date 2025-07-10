@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Остановка
echo ========================================

echo [ИНФО] Проверка Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не установлен или не запущен!
    pause
    exit /b 1
)

echo [ИНФО] Остановка RabbitMQ контейнера...
docker compose down

if %errorlevel% equ 0 (
    echo.
    echo ✅ RabbitMQ успешно остановлен!
    echo.
    echo [ИНФО] Статус контейнеров:
    docker compose ps -a
) else (
    echo.
    echo ❌ Ошибка при остановке RabbitMQ!
    echo.
    echo [ИНФО] Текущие контейнеры:
    docker ps -a | findstr rabbitmq
)

echo.
pause 