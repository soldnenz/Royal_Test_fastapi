@echo off
setlocal enabledelayedexpansion

echo [%time%] Restarting RabbitMQ Consumer service...

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
echo [%time%] Stopping service...
docker-compose down --rmi local -v --remove-orphans
if errorlevel 1 (
    echo [%time%] Error: Failed to stop the service.
    pause
    exit /b 1
)

:: Wait a moment before rebuilding
echo [%time%] Waiting for cleanup to complete...
timeout /t 3 /nobreak > nul

:: Build the service with no cache
echo [%time%] Building service (no cache)...
docker-compose build --no-cache
if errorlevel 1 (
    echo [%time%] Error: Failed to build the service.
    pause
    exit /b 1
)

:: Start the service with force recreation
echo [%time%] Starting service...
docker-compose up -d --force-recreate
if errorlevel 1 (
    echo [%time%] Error: Failed to start the service.
    pause
    exit /b 1
)

:: Check if service is running
timeout /t 5 /nobreak > nul
docker-compose ps | findstr "Up" > nul
if errorlevel 1 (
    echo [%time%] Warning: Service might not have started properly.
    echo [%time%] Check logs with: docker-compose logs
    pause
) else (
    echo [%time%] Service restarted successfully.
    echo [%time%] Use 'docker-compose logs -f' to view logs.
)

pause 