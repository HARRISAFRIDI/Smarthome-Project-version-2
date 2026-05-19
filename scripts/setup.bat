@echo off
REM ============================================
REM AI HOME AUTOMATION - SETUP (Windows)
REM ============================================

echo 🚀 AI Home Automation System Setup
echo ====================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.9+
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js not found. Please install Node.js 16+
    exit /b 1
)

echo ✅ Prerequisites found
echo.

REM Setup Backend
echo 🔧 Setting up Backend...
cd backend

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python packages...
pip install -r requirements.txt -q

echo Configuring .env...
(
    echo DB_HOST=localhost
    echo DB_NAME=home_automation
    echo DB_USER=postgres
    echo DB_PASSWORD=your_password
    echo DB_PORT=5432
    echo API_HOST=0.0.0.0
    echo API_PORT=8000
    echo LOG_LEVEL=INFO
    echo MODEL_PATH=../model.pkl
    echo RETRAIN_INTERVAL_DAYS=7
) > .env

echo ✅ Backend setup complete
echo.

REM Setup Frontend
cd ..\frontend

echo 🎨 Setting up Frontend...
echo Installing Node packages...
call npm install -q

echo ✅ Frontend setup complete
echo.

cd ..\

echo ====================================
echo ✅ SETUP COMPLETE!
echo ====================================
echo.
echo Next steps:
echo 1. Train ML model (if not done^):
echo    jupyter notebook 2024_dataset_training_model.ipynb
echo.
echo 2. Start backend (Command Prompt 1^):
echo    cd backend
echo    venv\Scripts\activate.bat
echo    python main.py
echo.
echo 3. Start frontend (Command Prompt 2^):
echo    cd frontend
echo    npm start
echo.
echo 4. Open dashboard:
echo    http://localhost:3000
echo.
echo API Documentation: http://localhost:8000/docs
echo.

pause
