@echo off
chcp 65001 >nul
echo ========================================
echo   RabbitMQ Royal Test - Первоначальная настройка
echo ========================================

echo [ИНФО] Создание необходимых директорий...

:: Создаем основные директории
if not exist data mkdir data
if not exist logs mkdir logs
if not exist backups mkdir backups
if not exist config mkdir config

echo ✅ Директории созданы:
echo   📁 data/     - для хранения данных RabbitMQ
echo   📁 logs/     - для логов RabbitMQ
echo   📁 backups/  - для резервных копий
echo   📁 config/   - для конфигурационных файлов

echo.
echo [ИНФО] Проверка конфигурационных файлов...

:: Проверяем наличие основных конфигурационных файлов
set files_missing=0

if not exist config\rabbitmq.conf (
    echo ❌ Отсутствует: config\rabbitmq.conf
    set files_missing=1
)

if not exist config\enabled_plugins (
    echo ❌ Отсутствует: config\enabled_plugins
    set files_missing=1
)

if not exist config\definitions.json (
    echo ❌ Отсутствует: config\definitions.json
    set files_missing=1
)

if not exist .env (
    if exist env_example.txt (
        echo [ИНФО] Создание .env файла из примера...
        copy env_example.txt .env >nul
        echo ✅ Файл .env создан из env_example.txt
        echo ⚠️  ВАЖНО: Измените пароли в .env файле для production!
    ) else (
        echo ❌ Отсутствует: env_example.txt
        set files_missing=1
    )
) else (
    echo ✅ Файл .env найден
)

if %files_missing%==1 (
    echo.
    echo ❌ ОШИБКА: Некоторые файлы отсутствуют!
    echo Убедитесь, что все файлы конфигурации созданы.
    pause
    exit /b 1
)

echo.
echo [ИНФО] Установка прав доступа для директорий...

:: Устанавливаем права для Windows (делаем директории доступными для записи)
icacls data /grant Everyone:(OI)(CI)F >nul 2>&1
icacls logs /grant Everyone:(OI)(CI)F >nul 2>&1
icacls backups /grant Everyone:(OI)(CI)F >nul 2>&1

echo ✅ Права доступа установлены

echo.
echo [ИНФО] Проверка Docker...

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker не найден или не запущен!
    echo Установите Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
) else (
    echo ✅ Docker найден
)

docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose не найден!
    echo Обновите Docker Desktop до последней версии
    pause
    exit /b 1
) else (
    echo ✅ Docker Compose найден
)

echo.
echo [ИНФО] Проверка портов...

:: Проверяем доступность портов
netstat -an | findstr ":5672 " >nul
if %errorlevel%==0 (
    echo ⚠️  Порт 5672 уже используется другим процессом
    echo   Остановите существующий RabbitMQ или измените порт в .env
)

netstat -an | findstr ":15672 " >nul  
if %errorlevel%==0 (
    echo ⚠️  Порт 15672 уже используется другим процессом
    echo   Остановите существующий RabbitMQ Management или измените порт в .env
)

echo.
echo [ИНФО] Проверка свободного места на диске...

:: Получаем информацию о свободном месте (требуется минимум 5GB)
for /f "tokens=3" %%a in ('dir /-c ^| findstr "bytes free"') do set free_space=%%a
if defined free_space (
    echo ✅ Проверка места на диске завершена
) else (
    echo ⚠️  Не удалось проверить свободное место на диске
)

echo.
echo ✅ Первоначальная настройка завершена!
echo.
echo 📋 Следующие шаги:
echo ----------------------------------------
echo 1. Проверьте настройки в .env файле
echo 2. При необходимости измените пароли
echo 3. Запустите RabbitMQ: start_rabbitmq.bat
echo 4. Проверьте статус: status_rabbitmq.bat
echo 5. Откройте Management UI: http://localhost:15672

echo.
echo 🔧 Доступные команды:
echo ----------------------------------------
echo start_rabbitmq.bat      - Запуск RabbitMQ
echo stop_rabbitmq.bat       - Остановка RabbitMQ
echo restart_rabbitmq.bat    - Перезапуск RabbitMQ
echo status_rabbitmq.bat     - Проверка статуса
echo logs_rabbitmq.bat       - Просмотр логов
echo backup_rabbitmq.bat     - Резервное копирование

echo.
echo 📁 Структура файлов:
echo ----------------------------------------
dir /b

echo.
pause 