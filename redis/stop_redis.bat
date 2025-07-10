@echo off
echo ========================================
echo    Остановка Redis Docker Container
echo ========================================
echo.

REM Проверяем, установлен ли Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Docker не установлен!
    pause
    exit /b 1
)

echo Остановка Redis контейнера...
docker-compose down

echo.
echo Проверка статуса контейнеров...
docker-compose ps

echo.
echo ========================================
echo    Redis остановлен!
echo ========================================
echo.
echo Данные сохранены в папке: data\
echo Логи сохранены в папке: logs\
echo.
echo Для запуска используйте: start_redis.bat
echo.

pause 