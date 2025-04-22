@echo off
setlocal

echo ------------------------------
echo 🔄 Перезапуск nginx...
echo ------------------------------

REM Шаг 1: Остановить nginx
echo 🛑 Остановка nginx...
tasklist /FI "IMAGENAME eq nginx.exe" | find /I "nginx.exe" >nul
if %errorlevel%==0 (
    taskkill /F /IM nginx.exe >nul
    echo ✅ nginx.exe был остановлен
) else (
    echo ℹ️ nginx.exe не был запущен
)

REM Шаг 2: Переход в нужную директорию
cd /d %~dp0
set BASE_DIR=%cd%

echo ------------------------------
echo 🔍 BASE DIR: %BASE_DIR%
echo ------------------------------

REM Проверка наличия nginx.exe
if exist "%BASE_DIR%\nginx.exe" (
    echo ✅ Found nginx.exe
) else (
    echo ❌ nginx.exe not found in %BASE_DIR%
    echo ❗ Please place this .bat file inside the folder with nginx.exe
    pause
    exit /b 1
)

REM Проверка конфигурационного файла
if exist "%BASE_DIR%\conf\nginx.conf" (
    echo ✅ Found nginx.conf at %BASE_DIR%\conf\nginx.conf
) else (
    echo ❌ nginx.conf not found at %BASE_DIR%\conf\nginx.conf
    pause
    exit /b 1
)

echo ------------------------------
echo 🚀 Запуск nginx...
echo ------------------------------
nginx.exe -p "%BASE_DIR%" -c conf/nginx.conf

echo ------------------------------
echo 📜 Tail logs (access and error):
echo ------------------------------

REM Показываем последние строки логов
if exist "%BASE_DIR%\logs\access.log" (
    echo --- access.log ---
    type "%BASE_DIR%\logs\access.log"
) else (
    echo (access.log not found)
)

if exist "%BASE_DIR%\logs\error.log" (
    echo --- error.log ---
    type "%BASE_DIR%\logs\error.log"
) else (
    echo (error.log not found)
)

echo ------------------------------
echo ✅ Перезапуск завершён.
pause
