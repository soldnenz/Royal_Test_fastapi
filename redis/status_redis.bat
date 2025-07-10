@echo off
echo ========================================
echo    Статус Redis Docker Container
echo ========================================
echo.

REM Проверяем, установлен ли Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Docker не установлен!
    pause
    exit /b 1
)

echo Статус контейнеров Redis:
docker-compose ps

echo.
echo ========================================
echo    Детальная информация
echo ========================================
echo.

echo Логи контейнера:
docker-compose logs --tail=20 redis

echo.
echo Использование ресурсов:
docker stats --no-stream royal_test_redis

echo.
echo Информация о контейнере:
docker inspect royal_test_redis --format='{{.State.Status}}' 2>nul
if errorlevel 1 (
    echo Контейнер не найден или не запущен
) else (
    echo Контейнер запущен
)

echo.
echo ========================================
echo    Полезные команды
echo ========================================
echo.
echo Подключение к Redis CLI:
echo docker exec -it royal_test_redis redis-cli -a Royal_Redis_1337
echo.
echo Просмотр логов в реальном времени:
echo docker-compose logs -f redis
echo.
echo Остановка: stop_redis.bat
echo Перезапуск: restart_redis.bat
echo.

pause 