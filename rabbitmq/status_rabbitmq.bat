@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Статус
echo ========================================

echo [ИНФО] Проверка Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не установлен или не запущен!
    pause
    exit /b 1
)

echo.
echo 🔍 Статус контейнеров:
echo ----------------------------------------
docker compose ps

echo.
echo 📊 Использование ресурсов:
echo ----------------------------------------
docker stats royal_rabbitmq --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

echo.
echo 🌐 Проверка портов:
echo ----------------------------------------
netstat -an | findstr ":5672 "
netstat -an | findstr ":15672 "

echo.
echo 🔗 Подключения:
echo ----------------------------------------
echo Management UI: http://localhost:15672
echo AMQP URL: amqp://royal_admin:Royal_RabbitMQ_1337@localhost:5672/royal_vhost

echo.
echo 📋 Команды для диагностики:
echo ----------------------------------------
echo docker compose logs rabbitmq          - Логи контейнера
echo docker exec royal_rabbitmq rabbitmq-diagnostics ping - Проверка RabbitMQ
echo docker exec royal_rabbitmq rabbitmqctl status      - Полный статус
echo docker exec royal_rabbitmq rabbitmqctl list_queues - Список очередей
echo docker exec royal_rabbitmq rabbitmqctl list_users  - Список пользователей

echo.
echo 💾 Информация о томах:
echo ----------------------------------------
docker volume ls | findstr rabbitmq

echo.
pause 