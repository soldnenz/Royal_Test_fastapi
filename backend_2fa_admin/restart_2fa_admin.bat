@echo off
echo Restarting 2FA Admin Service...
docker-compose down
timeout /t 5
docker-compose up -d
echo Service restarted! Check logs with logs_2fa_admin.bat
pause 