@echo off
echo ========================================
echo    Резервное копирование Redis
echo ========================================
echo.

REM Проверяем, установлен ли Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Docker не установлен!
    pause
    exit /b 1
)

REM Создаем папку для бэкапов если её нет
if not exist "backups" mkdir backups

REM Получаем текущую дату и время
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "datestamp=%YYYY%-%MM%-%DD%_%HH%-%Min%-%Sec%"

echo Создание резервной копии Redis...
echo Дата: %datestamp%
echo.

REM Проверяем, запущен ли Redis
docker-compose ps | findstr "redis" >nul
if errorlevel 1 (
    echo ОШИБКА: Redis не запущен!
    echo Запустите Redis командой: start_redis.bat
    pause
    exit /b 1
)

REM Создаем резервную копию
echo Создание RDB бэкапа...
docker exec royal_test_redis redis-cli -a Royal_Redis_1337 BGSAVE

REM Ждем завершения бэкапа
echo Ожидание завершения бэкапа...
timeout /t 5 /nobreak >nul

REM Копируем файлы данных
echo Копирование файлов данных...
copy "data\dump.rdb" "backups\dump_%datestamp%.rdb" >nul 2>&1
copy "data\appendonly.aof" "backups\appendonly_%datestamp%.aof" >nul 2>&1

REM Копируем конфигурацию
copy "redis.conf" "backups\redis_%datestamp%.conf" >nul 2>&1

echo.
echo ========================================
echo    Резервная копия создана!
echo ========================================
echo.
echo Файлы сохранены в папке: backups\
echo - dump_%datestamp%.rdb
echo - appendonly_%datestamp%.aof
echo - redis_%datestamp%.conf
echo.

REM Показываем список бэкапов
echo Существующие резервные копии:
dir backups\*.rdb /b 2>nul
if errorlevel 1 (
    echo Резервных копий не найдено
)

echo.
echo Для восстановления используйте файлы из папки backups\
echo.

pause 