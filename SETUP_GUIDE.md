# 🏠 AI Home Automation System - Complete Setup Guide

## Project Overview

This is a **Final Year Project** for an AI-powered home automation system with:
- **Machine Learning** for predictive device control
- **Agentic AI** with LangGraph-style node architecture
- **Hybrid Decision Making** (Rules + ML predictions + User overrides)
- **Real-time Dashboard** with live device control
- **Continuous Learning** system for model improvement
- **PostgreSQL** backend for data persistence

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites & Installation](#prerequisites--installation)
3. [Database Setup](#database-setup)
4. [Backend Setup](#backend-setup)
5. [Frontend Setup](#frontend-setup)
6. [Running the System](#running-the-system)
7. [API Documentation](#api-documentation)
8. [System Features](#system-features)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND DASHBOARD                      │
│              (React + Chart.js + WebSocket)             │
└──────────────────┬──────────────────────────────────────┘
                   │
         ┌─────────▼────────┐
         │  FastAPI Backend │ (Port 8000)
         │  REST + WebSocket│
         └─────────┬────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
     ▼             ▼             ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│  Agent  │  │ ML Model │  │ Database │
│ (Nodes) │  │ (joblib) │  │ PostgreSQL
└─────────┘  └──────────┘  └──────────┘
```

---

## Prerequisites & Installation

### System Requirements
- Python 3.9+
- Node.js 16+
- PostgreSQL 12+
- 2GB RAM minimum

### Install Python Dependencies

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Install Node.js Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

---

## Database Setup

### 1. Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE home_automation;

# Exit
\q
```

### 2. Apply Schema

```bash
# Connect to the new database
psql -U postgres -d home_automation -f ../database/schema.sql
```

Or run SQL commands directly:

```sql
-- Copy contents of database/schema.sql and execute
```

### 3. Verify Setup

```bash
psql -U postgres -d home_automation

# Check tables
\dt

# Check if devices are initialized
SELECT * FROM devices;

# Exit
\q
```

### 4. Update Database Connection

Edit `backend/.env`:

```env
DB_HOST=localhost
DB_NAME=home_automation
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
```

---

## Backend Setup

### 1. Configure Environment

Edit `backend/.env`:

```env
DB_HOST=localhost
DB_NAME=home_automation
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
API_HOST=0.0.0.0
API_PORT=8000
MODEL_PATH=../model.pkl
RETRAIN_INTERVAL_DAYS=7
```

### 2. Verify ML Model

The system expects a trained ML model at the root: `model.pkl`

**If you haven't trained the model yet:**

```bash
# Run the Jupyter notebook to train:
# 2024_dataset_training_model.ipynb

# After training, the model.pkl will be created
```

### 3. Start Backend Server

```bash
cd backend

# Activate virtual environment (if not already)
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Run server
python main.py

# Or use uvicorn directly:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**
```
✅ All services initialized
🔄 Starting continuous agent loop
📚 API documentation: http://localhost:8000/docs
```

---

## Frontend Setup

### 1. Configure Environment

Edit `frontend/.env`:

```env
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

### 2. Start Development Server

```bash
cd frontend

# Start React development server
npm start

# Browser should open automatically at http://localhost:3000
```

**Expected Output:**
```
On Your Network: http://192.x.x.x:3000
Compiled successfully!
```

### 3. Build for Production

```bash
npm run build

# Output will be in build/ directory
```

---

## Running the System

### Start Services in Order

#### Terminal 1: PostgreSQL (if not running as service)
```bash
# For development, PostgreSQL should be running
# Check service status or use your PostgreSQL client
```

#### Terminal 2: Backend API
```bash
cd backend
source venv/bin/activate
python main.py
```

#### Terminal 3: Frontend Dashboard
```bash
cd frontend
npm start
```

### Verify All Services

1. **Database**: 
   ```bash
   psql -U postgres -d home_automation -c "SELECT COUNT(*) FROM devices;"
   ```

2. **Backend API**:
   - Visit: http://localhost:8000/docs (Swagger UI)
   - Visit: http://localhost:8000/health

3. **Frontend**:
   - Visit: http://localhost:3000
   - Should show device cards and controls

---

## API Documentation

### Base URL
```
http://localhost:8000/api
```

### Key Endpoints

#### Get Device Status
```
GET /devices/status
Response: [{id, name, type, status, energy_consumption}, ...]
```

#### Control Device
```
POST /device/control
Body: {device_id: 1, action: true, reason: "Manual"}
```

#### Get Predictions
```
POST /predictions
Body: {temperature: 25.0, humidity: 60.0}
Response: [{device_id, device_name, predicted_action, confidence}, ...]
```

#### Get Analytics
```
GET /analytics
Response: {total_devices, total_energy_consumed, devices: [...]}
```

#### Retrain Model
```
POST /model/retrain
Response: {success: true, message: "..."}
```

#### System Status
```
GET /system/status
Response: {status, devices, model}
```

### Interactive API Docs
```
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
```

---

## System Features

### 🤖 AI Agent (Node Architecture)

1. **History Node**: Fetches recent device usage
2. **Predict Node**: Uses ML model for predictions
3. **Rule Engine Node**: Applies 8 domain rules
4. **Override Node**: Checks for user manual override
5. **Decision Engine**: Combines all signals with priorities
6. **Control Node**: Applies final device state
7. **Logging Node**: Records decision for learning

### 📊 Rule Engine (8 Rules)

```
1. If temp > 30°C → Fan ON
2. If temp < 25°C → AC OFF
3. If night (6PM-7AM) → Lights ON
4. If day (7AM-6PM) → Lights OFF
5. If humidity > 70% → Fan ON
6. Working hours (9AM-6PM) → AC ON
7. Weekend + time 12PM-11PM → TV more flexible
8. Fridge always ON
```

### 📈 Continuous Learning

- Stores all predictions and actual user actions
- Weekly model retraining
- Tracks accuracy improvement
- Learns user preferences

### 🎯 Priority System

```
Manual Override    (Priority 100)
  ↓
Rule Engine        (Priority 80)
  ↓
ML Prediction      (Priority 60)
  ↓
History Pattern    (Priority 40)
  ↓
Default (OFF)      (Priority 0)
```

### 📊 Dashboard Features

- **Device Control**: ON/OFF buttons with real-time status
- **Environmental Data**: Temperature & humidity sliders
- **AI Predictions**: Shows ML predictions with confidence
- **Analytics**: Charts for device usage and energy
- **Model Performance**: Accuracy trends and training cycles
- **Dark Mode**: Theme toggle for comfortable viewing
- **Real-time Updates**: WebSocket connection for live data

---

## Troubleshooting

### Backend Issues

**Error: Database connection failed**
```
Solution: Check PostgreSQL is running and credentials in .env are correct
psql -U postgres -c "SELECT version();"
```

**Error: Model not found**
```
Solution: Train the model using the notebook first
jupyter notebook 2024_dataset_training_model.ipynb
Then ensure model.pkl exists in root directory
```

**Error: Port 8000 already in use**
```bash
# Linux/Mac: Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Windows: Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use different port
python main.py --port 8001
```

### Frontend Issues

**Error: Cannot connect to backend**
```
Solution: Check backend is running and API_URL in .env is correct
Run: http://localhost:8000/health in browser
```

**Error: npm install takes too long**
```bash
# Try clearing cache
npm cache clean --force
npm install
```

**Error: Port 3000 already in use**
```bash
# Linux/Mac
lsof -ti:3000 | xargs kill -9

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Or run on different port
PORT=3001 npm start
```

### Database Issues

**Error: Cannot create database**
```bash
# Check PostgreSQL service
# Windows: Services → PostgreSQL
# Linux: sudo systemctl status postgresql

# Mac: brew services list | grep postgres
```

**Error: Permission denied**
```bash
# Create database with correct permissions
createdb home_automation
```

---

## Project Structure

```
Smarthome Project version 2/
├── database/
│   ├── schema.sql                    # PostgreSQL schema
│   └── db_manager.py                 # Database utilities
├── ml_agent/
│   ├── agent.py                      # LangGraph-style agent
│   └── continuous_learning.py        # Retraining system
├── backend/
│   ├── main.py                       # FastAPI app
│   ├── requirements.txt              # Python dependencies
│   └── .env                          # Configuration
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   # Main React component
│   │   └── App.css                   # Styles
│   ├── package.json                  # Node dependencies
│   └── .env                          # Configuration
├── scripts/
│   ├── setup.sh                      # Setup script
│   └── run_all.sh                    # Run all services
├── 2024_dataset_training_model.ipynb # ML training
└── home_automation_dataset_2024.csv  # Training data
```

---

## Next Steps

### 1. Deploy Locally
- [ ] Setup PostgreSQL
- [ ] Train ML model
- [ ] Start backend
- [ ] Start frontend
- [ ] Test device controls

### 2. Enhance System
- [ ] Add real hardware integration (GPIO, sensors)
- [ ] Implement user authentication
- [ ] Add notification system
- [ ] Create mobile app
- [ ] Add voice control

### 3. Production Deployment
- [ ] Deploy to cloud (AWS, Azure, GCP)
- [ ] Setup SSL/TLS
- [ ] Configure proper logging
- [ ] Setup monitoring
- [ ] Create backup system

---

## Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **Backend Logs**: See terminal output
- **Database Queries**: Use `psql`
- **Frontend Debug**: Browser DevTools (F12)

---

## License

This is a Final Year Project for educational purposes.

---

**Created**: Project Version 2
**Status**: Complete System Architecture ✅

