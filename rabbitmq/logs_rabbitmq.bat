@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Логи
echo ========================================

echo [ИНФО] Проверка контейнера...
docker ps | findstr royal_rabbitmq >nul
if %errorlevel% neq 0 (
    echo [ОШИБКА] Контейнер RabbitMQ не запущен!
    echo Запустите RabbitMQ для просмотра логов
    pause
    exit /b 1
)

echo.
echo Выберите тип логов:
echo ----------------------------------------
echo 1. Последние логи (tail)
echo 2. Все логи
echo 3. Логи с фильтром ошибок
echo 4. Логи в реальном времени (follow)
echo 5. Логи RabbitMQ внутри контейнера
echo 6. Выход
echo.

set /p choice="Ваш выбор (1-6): "

if "%choice%"=="1" (
    echo [ИНФО] Показываем последние 50 строк логов...
    docker compose logs --tail=50 rabbitmq
) else if "%choice%"=="2" (
    echo [ИНФО] Показываем все логи...
    docker compose logs rabbitmq
) else if "%choice%"=="3" (
    echo [ИНФО] Показываем логи с ошибками...
    docker compose logs rabbitmq | findstr /i "error\|exception\|fail\|crash"
) else if "%choice%"=="4" (
    echo [ИНФО] Показываем логи в реальном времени (Ctrl+C для остановки)...
    docker compose logs -f rabbitmq
) else if "%choice%"=="5" (
    echo [ИНФО] Показываем внутренние логи RabbitMQ...
    echo.
    echo 📁 Файлы логов RabbitMQ:
    docker exec royal_rabbitmq ls -la /var/log/rabbitmq/
    echo.
    echo 📋 Основной лог:
    docker exec royal_rabbitmq tail -20 /var/log/rabbitmq/rabbit.log
) else if "%choice%"=="6" (
    exit /b 0
) else (
    echo [ОШИБКА] Неверный выбор!
    pause
    exit /b 1
)

echo.
echo 📋 Дополнительные команды:
echo ----------------------------------------
echo docker exec royal_rabbitmq rabbitmq-diagnostics log_tail        - Хвост лога
echo docker exec royal_rabbitmq rabbitmq-diagnostics log_tail_stream - Лог в реальном времени
echo docker exec royal_rabbitmq rabbitmqctl eval 'rabbit_log:error("Test error").' - Тестовое сообщение

echo.
pause 