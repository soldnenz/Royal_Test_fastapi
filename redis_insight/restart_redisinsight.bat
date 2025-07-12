@echo off
echo ========================================
echo    Перезапуск RedisInsight Docker Container
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

REM Запускаем RedisInsight
echo Запуск RedisInsight контейнера...
docker-compose up -d

REM Проверяем статус
timeout /t 3 /nobreak >nul
echo.
echo Проверка статуса RedisInsight...
docker-compose ps

echo.
echo ========================================
echo    RedisInsight успешно перезапущен!
echo ========================================
echo.
echo Веб-интерфейс доступен по адресу: http://localhost:8012
echo.

pause 