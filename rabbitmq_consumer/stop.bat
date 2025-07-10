@echo off
setlocal enabledelayedexpansion

echo [%time%] Stopping RabbitMQ Consumer service...

:: Check if Docker is running
docker info > nul 2>&1
if errorlevel 1 (
    echo [%time%] Error: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

:: Check if docker-compose.yml exists
if not exist "docker-compose.yml" (
    echo [%time%] Error: docker-compose.yml not found in current directory.
    pause
    exit /b 1
)

:: Stop and remove containers, networks, volumes, and images
echo [%time%] Running docker-compose down...
docker-compose down --rmi local -v --remove-orphans
if errorlevel 1 (
    echo [%time%] Error: Failed to stop the service.
    pause
    exit /b 1
)

:: Verify service is stopped
timeout /t 2 /nobreak > nul
docker-compose ps | findstr "Up" > nul
if errorlevel 1 (
    echo [%time%] Service stopped successfully.
    echo [%time%] All containers, networks, and volumes have been removed.
) else (
    echo [%time%] Warning: Service might still be running.
    echo [%time%] Check status with: docker-compose ps
)

pause 