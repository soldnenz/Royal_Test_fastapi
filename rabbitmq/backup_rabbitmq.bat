@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Резервное копирование
echo ========================================

:: Получаем текущую дату и время для имени бэкапа
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "SS=%dt:~12,2%"
set "timestamp=%YYYY%%MM%%DD%_%HH%%Min%%SS%"

echo [ИНФО] Создание резервной копии RabbitMQ...
echo Время: %timestamp%

if not exist backups mkdir backups

echo [ИНФО] Проверка контейнера...
docker ps | findstr royal_rabbitmq >nul
if %errorlevel% neq 0 (
    echo [ОШИБКА] Контейнер RabbitMQ не запущен!
    echo Запустите RabbitMQ перед созданием бэкапа
    pause
    exit /b 1
)

echo [ИНФО] Экспорт определений...
docker exec royal_rabbitmq rabbitmqctl export_definitions /tmp/backup_definitions.json

echo [ИНФО] Копирование файла определений...
docker cp royal_rabbitmq:/tmp/backup_definitions.json backups/definitions_%timestamp%.json

echo [ИНФО] Архивирование данных...
docker exec royal_rabbitmq tar -czf /tmp/rabbitmq_data_%timestamp%.tar.gz -C /var/lib/rabbitmq .

echo [ИНФО] Копирование архива данных...
docker cp royal_rabbitmq:/tmp/rabbitmq_data_%timestamp%.tar.gz backups/

echo [ИНФО] Создание архива конфигурации...
if exist config (
    powershell Compress-Archive -Path "config\*" -DestinationPath "backups\config_%timestamp%.zip" -Force
)

echo [ИНФО] Очистка временных файлов...
docker exec royal_rabbitmq rm -f /tmp/backup_definitions.json
docker exec royal_rabbitmq rm -f /tmp/rabbitmq_data_%timestamp%.tar.gz

echo.
echo ✅ Резервное копирование завершено!
echo.
echo 📁 Созданные файлы:
echo ----------------------------------------
if exist backups\definitions_%timestamp%.json echo   ✓ definitions_%timestamp%.json
if exist backups\rabbitmq_data_%timestamp%.tar.gz echo   ✓ rabbitmq_data_%timestamp%.tar.gz  
if exist backups\config_%timestamp%.zip echo   ✓ config_%timestamp%.zip

echo.
echo 📋 Восстановление из бэкапа:
echo ----------------------------------------
echo 1. Остановите RabbitMQ: stop_rabbitmq.bat
echo 2. Очистите данные: docker volume rm rabbitmq_rabbitmq_data
echo 3. Запустите RabbitMQ: start_rabbitmq.bat
echo 4. Импортируйте определения:
echo    docker cp backups\definitions_%timestamp%.json royal_rabbitmq:/tmp/
echo    docker exec royal_rabbitmq rabbitmqctl import_definitions /tmp/definitions_%timestamp%.json

echo.
echo 📊 Размер файлов бэкапа:
if exist backups\definitions_%timestamp%.json for %%i in (backups\definitions_%timestamp%.json) do echo Definitions: %%~zi bytes
if exist backups\rabbitmq_data_%timestamp%.tar.gz for %%i in (backups\rabbitmq_data_%timestamp%.tar.gz) do echo Data: %%~zi bytes
if exist backups\config_%timestamp%.zip for %%i in (backups\config_%timestamp%.zip) do echo Config: %%~zi bytes

echo.
pause 