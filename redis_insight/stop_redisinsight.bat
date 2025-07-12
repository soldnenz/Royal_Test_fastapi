@echo off
echo ========================================
echo    Остановка RedisInsight Docker Container
echo ========================================
echo.

REM Проверяем, установлен ли Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Docker не установлен или не запущен!
    echo Пожалуйста, установите Docker Desktop и запустите его.
    pause
    exit /b 1
)

REM Проверяем, запущен ли Docker
docker info >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Docker не запущен!
    echo Пожалуйста, запустите Docker Desktop.
    pause
    exit /b 1
)

REM Останавливаем контейнер
echo Остановка RedisInsight контейнера...
docker-compose down

REM Проверяем статус
timeout /t 2 /nobreak >nul
echo.
echo Проверка статуса...
docker-compose ps

echo.
echo ========================================
echo    RedisInsight успешно остановлен!
echo ========================================
echo.

pause 