@echo off
REM ============================================
REM AI HOME AUTOMATION - RUN ALL SERVICES (Windows)
REM ============================================

echo 🚀 Starting AI Home Automation System
echo ======================================
echo.

REM Start Backend
echo Starting Backend (Port 8000^)...
start "Backend - AI Home Automation" cmd /k "cd backend && venv\Scripts\activate.bat && python main.py"

timeout /t 3 /nobreak

REM Start Frontend
echo Starting Frontend (Port 3000^)...
start "Frontend - AI Home Automation" cmd /k "cd frontend && npm start"

timeout /t 3 /nobreak

echo.
echo ======================================
echo ✅ Services started!
echo ======================================
echo.
echo Dashboard: http://localhost:3000
echo API Docs:  http://localhost:8000/docs
echo.
echo Note: Two new windows should have opened.
echo Close them to stop the services.
echo.

pause
