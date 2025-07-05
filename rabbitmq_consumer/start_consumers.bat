@echo off
echo 🎯 RabbitMQ Consumer Manager
echo ================================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Убедитесь, что Python установлен и добавлен в PATH
    pause
    exit /b 1
)

REM Проверяем наличие requirements.txt
if not exist "requirements.txt" (
    echo ❌ Файл requirements.txt не найден
    pause
    exit /b 1
)

REM Устанавливаем зависимости
echo 📦 Устанавливаем зависимости...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей
    pause
    exit /b 1
)

echo.
echo ✅ Зависимости установлены
echo.

REM Запускаем потребителей
echo 🚀 Запускаем всех потребителей...
python start_consumers.py

echo.
echo 👋 Потребители остановлены
pause 