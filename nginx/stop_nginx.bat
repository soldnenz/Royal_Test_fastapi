@echo off
echo ------------------------------
echo 🔻 Остановка всех процессов nginx...
echo ------------------------------

tasklist /FI "IMAGENAME eq nginx.exe" | find /I "nginx.exe" >nul
if %errorlevel%==0 (
    taskkill /F /IM nginx.exe >nul
    echo ✅ nginx.exe был остановлен
) else (
    echo ℹ️ nginx.exe не запущен
)

pause
