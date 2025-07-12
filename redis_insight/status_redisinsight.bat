@echo off
echo ========================================
echo    Проверка статуса RedisInsight Docker Container
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

REM Проверяем статус контейнера
echo Проверка статуса RedisInsight контейнера...
echo.
docker-compose ps

REM Проверяем логи контейнера
echo.
echo Последние логи RedisInsight:
echo.
docker-compose logs --tail=20

echo.
echo ========================================
echo    Проверка завершена
echo ========================================
echo.
echo Веб-интерфейс доступен по адресу: http://localhost:8012
echo.

pause 