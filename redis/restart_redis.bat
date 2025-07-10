@echo off
echo ========================================
echo    Перезапуск Redis Docker Container
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
echo Запуск Redis контейнера...
docker-compose up -d

REM Проверяем статус
timeout /t 3 /nobreak >nul
echo.
echo Проверка статуса Redis...
docker-compose ps

echo.
echo ========================================
echo    Redis успешно перезапущен!
echo ========================================
echo.
echo Порт: 6379
echo Хост: localhost
echo Пароль: Royal_Redis_1337
echo.
echo Для подключения используйте:
echo redis-cli -h localhost -p 6379 -a Royal_Redis_1337
echo.

pause 