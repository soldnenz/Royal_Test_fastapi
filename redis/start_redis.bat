@echo off
echo ========================================
echo    Запуск Redis Docker Container
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

REM Создаем необходимые директории
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo Создание директорий для данных и логов...
echo.

REM Останавливаем существующий контейнер если он запущен
echo Остановка существующего контейнера Redis...
docker-compose down

REM Запускаем Redis
echo Запуск Redis контейнера...
docker-compose up -d

REM Проверяем статус
timeout /t 3 /nobreak >nul
echo.
echo Проверка статуса Redis...
docker-compose ps

echo.
echo ========================================
echo    Redis успешно запущен!
echo ========================================
echo.
echo Порт: 6379
echo Хост: localhost
echo Пароль: Royal_Redis_1337
echo.
echo Для подключения используйте:
echo redis-cli -h localhost -p 6379 -a Royal_Redis_1337
echo.
echo Для просмотра логов: logs\redis.log
echo Для остановки: stop_redis.bat
echo.

pause 