@echo off
echo ========================================
echo    Запуск RedisInsight Docker Container
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

echo Создание директорий для данных...
echo.

REM Останавливаем существующий контейнер если он запущен
echo Остановка существующего контейнера RedisInsight...
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
echo    RedisInsight успешно запущен!
echo ========================================
echo.
echo Веб-интерфейс доступен по адресу: http://localhost:8012
echo.
echo Для подключения к Redis используйте:
echo Хост: host.docker.internal (для доступа к локальному Redis)
echo Порт: 6379
echo.
echo Для остановки: stop_redisinsight.bat
echo.

pause 