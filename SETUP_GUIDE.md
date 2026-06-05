# 🏠 AI Home Automation System — Complete Setup Guide

## Project Overview

This is a **Final Year Project** for an AI-powered home automation system with:
- **Machine Learning** — Predictive device control (RandomForest)
- **Agentic AI** — LangGraph-style 5-node pipeline architecture
- **Hybrid Decision Making** — Rules + ML predictions + User overrides
- **Real-time Dashboard** — React with live device control
- **Continuous Learning** — Automatic weekly model retraining
- **SQLite Database** — Zero-config, file-based, no server installation needed

---

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Database Setup](#database-setup)
4. [Backend Setup](#backend-setup)
5. [Frontend Setup](#frontend-setup)
6. [Running the System](#running-the-system)
7. [Temperature Rules Configuration](#temperature-rules-configuration)
8. [Troubleshooting](#troubleshooting)

---

## System Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.9+ |
| Node.js | 16+ |
| RAM | 2 GB |
| Storage | 500 MB |
| Database | **None** — SQLite is built into Python |

---

## Installation

### Step 1 — Clone / Open Project

Open the project folder:
```
d:\progress 2 FYP\Smarthome Project version 2\
```

### Step 2 — Train ML Model (first time only)

The ML model must be trained before starting the backend:

```bash
# Open and run the Jupyter notebook
jupyter notebook 2024_dataset_training_model.ipynb
```

This generates `home_automation_model.pkl` in the project root.  
**Skip this step if `home_automation_model.pkl` already exists.**

### Step 3 — One-click Setup (Windows)

```batch
scripts\setup.bat
```

Or continue to manual steps below.

---

## Database Setup

> ✅ **No setup required.** The project uses **SQLite** — a file-based database built into Python.

The database file `home_automation.db` is **auto-created** the first time the backend runs.

### Tables Created Automatically

| Table | Purpose |
|-------|---------|
| `two_week_logs` | 14-day device state history |
| `agent_logs` | AI agent autonomous decisions |
| `notifications` | 24h event log (manual + AI actions) |
| `custom_rules` | Temperature-based automation rules |

### Inspect the Database

```bash
# From project root
python check_db.py
```

---

## Backend Setup

### 1. Create & Activate Virtual Environment

```bash
cd backend

# Create venv
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Edit `backend/.env`:

```env
# Database — SQLite (file-based, no server needed)
DB_PATH=../home_automation.db

# API server
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# ML model
MODEL_PATH=../home_automation_model.pkl
RETRAIN_INTERVAL_DAYS=7
```

### 4. Start Backend

```bash
python main.py
```

**Expected output:**
```
✅ Database initialized (SQLite)
✅ ML Model loaded
🔄 Starting agent loop (every 60s)
📚 API docs: http://localhost:8000/docs
```

**Access points:**
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

---

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Edit `frontend/.env`:

```env
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

### 3. Start Development Server

```bash
npm start
```

**Access:** http://localhost:3000

---

## Running the System

### Option A — Automated (Recommended, Windows)

```batch
# One-time setup
scripts\setup.bat

# Start all services
scripts\run.bat
```

### Option B — Manual (Two Terminals)

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate
python main.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm start
```

### Verify Everything is Working

```bash
# Test backend health
curl http://localhost:8000/health

# Test database
python check_db.py

# Check API docs
# Open in browser: http://localhost:8000/docs
```

---

## Temperature Rules Configuration

The system includes a **custom rules engine** stored in the `custom_rules` SQLite table.  
These rules override AI predictions based on the current temperature.

### Default Rules

| Temperature | AC | Fan | Effect |
|-------------|-----|-----|--------|
| 0–25°C | OFF | OFF | Comfortable — no cooling |
| 25–30°C | OFF | OFF | Slightly warm |
| 30–40°C | **OFF** | **ON** | Fan-only (saves ~2350W vs AC) |
| 40–50°C | ON | ON | Full cooling |
| 50°C+ | ON | ON | Extreme heat |

### Manage Rules via API

```bash
# View all rules
curl http://localhost:8000/api/rules

# Create a rule (example: AC OFF at 30-40°C)
curl -X POST http://localhost:8000/api/rules \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1, "temp_min": 30, "temp_max": 40, "action": false, "description": "AC OFF moderate heat"}'

# Update a rule
curl -X PUT http://localhost:8000/api/rules/1 \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1, "temp_min": 35, "temp_max": 50, "action": true}'

# Delete a rule
curl -X DELETE http://localhost:8000/api/rules/1
```

### How Rules Are Applied

```
Agent Cycle:
1. Fetch current temperature
2. ML model predicts device states
3. Rule engine checks custom_rules table:
   → If matching rule found: override ML prediction
   → Log reason as "CUSTOM_RULE"
4. Apply manual override check
5. Execute final decisions
```

Backend logs will show:
```
[CUSTOM_RULE] AC (temp=35.0°C): AI predicted True but rule says False
```

---

## Troubleshooting

### Backend Issues

**`home_automation_model.pkl` not found**
```
Train the model first using the Jupyter notebook:
jupyter notebook 2024_dataset_training_model.ipynb
```

**Port 8000 already in use**
```powershell
# Windows PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```
```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

**Database error**
```bash
# SQLite is Python built-in — no server to check
# Verify the DB file:
python check_db.py

# Confirm sqlite3 works:
python -c "import sqlite3; print('sqlite3 version:', sqlite3.sqlite_version)"
```

**Rules not applying after backend restart**
```bash
# Check rules exist in DB
curl http://localhost:8000/api/rules

# Wait 1+ minute for next agent cycle, then check:
curl http://localhost:8000/api/agent/status
```

---

### Frontend Issues

**Cannot connect to backend**
```
1. Ensure backend is running: curl http://localhost:8000/health
2. Check frontend/.env → REACT_APP_API_URL=http://localhost:8000/api
```

**Port 3000 already in use**
```powershell
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```
```bash
# Linux/Mac
lsof -ti:3000 | xargs kill -9
```

**npm install fails**
```bash
npm cache clean --force
npm install
```

---

### Dashboard Issues

**Notifications page empty**
- The `notifications` table auto-creates on first backend run
- Events are stored for the last 24h only
- Wait for the agent to run at least once (up to 60 seconds)

**Override lock not expiring**
- Default lock duration: 30 minutes
- Use the ⏱ slider on each device card to set 5–60 min
- Check active locks: `curl http://localhost:8000/api/agent/status`

**Charts not loading**
- Analytics require at least some history in `two_week_logs`
- Let the system run for a few agent cycles (60s each)

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices/status` | GET | All device states |
| `/api/devices/{id}` | GET | Single device + lock info |
| `/api/device/control` | POST | Turn ON/OFF + set lock duration |
| `/api/device/override-duration` | POST | Change AI lock (5–60 min) |
| `/api/current-prediction` | GET | Live ML prediction |
| `/api/analytics` | GET | System-wide stats |
| `/api/history` | GET | 14-day history |
| `/api/history/daily` | GET | Daily aggregation |
| `/api/notifications/24h` | GET | Last 24h notifications |
| `/api/notifications/read-all` | POST | Mark all read |
| `/api/notifications/unread-count` | GET | Badge count |
| `/api/rules` | GET | View temperature rules |
| `/api/rules` | POST | Create rule |
| `/api/rules/{id}` | PUT | Update rule |
| `/api/rules/{id}` | DELETE | Delete rule |
| `/api/agent/status` | GET | Agent trace + locks |
| `/api/system/status` | GET | Health check |

Full interactive docs: http://localhost:8000/docs

---

## Documentation

- **[README.md](README.md)** — Project overview & features
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** — This file — installation & troubleshooting
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System architecture diagrams & data flows

---

**Final Year Project** — Educational Purpose  
**Version**: 4.0.0 | **Database**: SQLite | **Status**: ✅ Complete
