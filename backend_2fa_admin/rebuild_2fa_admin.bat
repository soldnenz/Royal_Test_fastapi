@echo off
echo Rebuilding 2FA Admin Service...
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo Service rebuilt and started! Check logs with logs_2fa_admin.bat
pause 