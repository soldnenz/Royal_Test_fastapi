@echo off
echo Starting 2FA Admin Service...
docker-compose up -d
echo Service started! Check logs with logs_2fa_admin.bat
pause 