# 🏠 AI Home Automation System v4.0

> **Final Year Project**: AI-powered smart home automation using Machine Learning + Agentic AI + Real-time Dashboard

## ✨ Key Features

🤖 **5-Node Autonomous Agent** — RF Predict → Rule Engine → Override Check → Execute → Notify  
🧠 **Machine Learning** — Multi-output RandomForest model trained on 5000+ real scenarios  
📊 **Real-time Dashboard** — Device control, AI predictions, 14-day analytics, notifications  
🔔 **Notifications Page** — 24h persistent event log (Manual + AI actions) stored in SQLite  
🔒 **Smart Override** — User manually overrides AI; AI locked for configurable **5–60 min**  
⚡ **Per-device Lock Duration** — Each device has its own adjustable override timer (slider)  
🌡️ **Temperature-Based Rules** — Custom rules DB enforces device actions per temperature range  
🗄️ **SQLite Database** — Zero-config, file-based, no server needed (`home_automation.db`)  
📱 **Responsive UI** — Works on desktop, tablet, mobile  

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+  
- **No database server required** — uses SQLite (built into Python)

### 1. Train ML Model (first time only)

```bash
# Run the Jupyter notebook to generate home_automation_model.pkl
jupyter notebook 2024_dataset_training_model.ipynb
```

### 2. Start Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
python main.py
```

**Backend runs at**: http://localhost:8000  
**API Docs at**: http://localhost:8000/docs

### 3. Start Frontend

```bash
cd frontend
npm install
npm start
```

**Frontend runs at**: http://localhost:3000

---

## 📋 System Architecture

```
┌────────────────────────────────────────────┐
│          FRONTEND DASHBOARD (React)         │
│   Device Status | Control | Notifications   │
└───────────────────┬─────────────────────────┘
                     │ REST API (polling)
                     ▼
┌────────────────────────────────────────────┐
│         BACKEND API (FastAPI v4.0)          │
│  5-Node Agent Loop (runs every 60s)         │
└──────────────┬──────────────────────┬───────┘
               │                      │
               ▼                      ▼
       ┌──────────────┐        ┌──────────────┐
       │ RF ML MODEL  │        │ SQLite DB     │
       │ (.pkl joblib)│        │ home_auto.db  │
       └──────────────┘        └──────────────┘
```

---

## 🧠 AI Agent Architecture

### Node Pipeline

```
1. HISTORY NODE     → Fetch recent device usage from DB
2. PREDICT NODE     → ML model predicts ON/OFF with confidence
3. RULE ENGINE      → Apply temperature-based + domain rules
4. DECISION ENGINE  → Combine all signals with priorities
5. CONTROL NODE     → Update device state
6. LOGGING NODE     → Save decision to DB for learning
```

### Priority System

```
Manual Override    100  ← User always wins
Rule Engine         80
ML Prediction       60
History Pattern     40
Default OFF          0
```

---

## 🌡️ Temperature Rules System

Custom rules are stored in the `custom_rules` SQLite table and override AI predictions:

| Temperature | AC | Fan | Reason |
|-------------|-----|-----|--------|
| 0–25°C | OFF | OFF | Comfortable |
| 25–30°C | OFF | OFF | Slightly warm |
| 30–40°C | OFF | ON | Fan-only (energy efficient) |
| 40–50°C | ON | ON | Full cooling |
| 50°C+ | ON | ON | Extreme heat |

Manage rules via REST API:
```
GET    /api/rules              → View all rules
POST   /api/rules              → Create rule
PUT    /api/rules/{id}         → Update rule
DELETE /api/rules/{id}         → Delete rule
```

---

## 📊 Integrated Rule Engine (8 Rules)

```python
Rule 1:  temp > 30°C        → AC ON, Fan ON (baseline; custom rules may override)
Rule 2:  temp < 25°C        → AC OFF
Rule 3:  18:00-07:00 (night) → Lights ON
Rule 4:  07:00-18:00 (day)  → Lights OFF
Rule 5:  humidity > 70%     → Fan ON
Rule 6:  9AM-6PM (work)     → AC ON
Rule 7:  Weekend 12PM-11PM  → TV flexible
Rule 8:  Always             → Fridge ON
```

---

## 🎯 REST API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/devices/status` | GET | All device states |
| `/api/devices/{id}` | GET | Device detail + lock info |
| `/api/device/control` | POST | Turn ON/OFF + set lock duration (5–60 min) |
| `/api/device/override-duration` | POST | Change per-device AI lock |
| `/api/current-prediction` | GET | Live RF model prediction |
| `/api/analytics` | GET | System-wide analytics |
| `/api/history` | GET | 14-day device history |
| `/api/history/daily` | GET | Daily ON-count aggregation |
| `/api/notifications/24h` | GET | Last 24h events from SQLite |
| `/api/notifications/read-all` | POST | Mark all notifications read |
| `/api/notifications/unread-count` | GET | Unread badge count |
| `/api/rules` | GET/POST/PUT/DELETE | Temperature-based rule management |
| `/api/agent/status` | GET | Agent cycle trace + manual locks |
| `/api/system/status` | GET | Health check (DB: SQLite) |

**Full Docs**: http://localhost:8000/docs (Swagger UI)

---

## 📁 Project Structure

```
Smarthome Project version 2/
│
├── backend/
│   ├── main.py                 # FastAPI application (5-Node Agent)
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Configuration
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main React component
│   │   ├── App.css             # Styling
│   │   ├── AuthPage.jsx        # Login/Signup page
│   │   ├── PowerConsumption.jsx # Energy analytics
│   │   └── index.js
│   ├── package.json            # Node dependencies
│   └── .env                    # Configuration
│
├── scripts/
│   ├── setup.bat / setup.sh    # One-time setup
│   └── run.bat / run.sh        # Start all services
│
├── home_automation.db                  # SQLite database (auto-created)
├── home_automation_model.pkl           # Trained ML model
├── home_automation_dataset_2024.csv    # Dataset
├── 2024_dataset_training_model.ipynb   # ML training notebook
├── generate_realistic_data.py          # Data generation script
├── check_db.py                         # Database inspector utility
│
├── README.md                   # This file — project overview
├── SETUP_GUIDE.md              # Detailed setup & troubleshooting
├── ARCHITECTURE.md             # System architecture diagrams
└── .gitignore
```

---

## 🔧 Configuration

### Backend `.env`

```env
# Database (SQLite — file-based, no server needed)
DB_PATH=../home_automation.db

# API
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Model
MODEL_PATH=../home_automation_model.pkl
RETRAIN_INTERVAL_DAYS=7
```

### Frontend `.env`

```env
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

---

## 🐛 Troubleshooting

**Model not found?**
- Train using notebook first: `jupyter notebook 2024_dataset_training_model.ipynb`
- Ensure `home_automation_model.pkl` exists in root

**Port already in use?**
```powershell
# Windows PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

**Notifications empty?**
- The `notifications` table is created automatically on first run
- It stores events from the last 24h persistently in `home_automation.db`

**Override not working?**
- After toggling a device, AI is locked for default 30 min
- Use the ⏱ button on a device card to change the lock to 5–60 min
- Check `GET /api/agent/status` for `manual_locks` dict

**Rules not applying?**
- Verify rules exist: `curl http://localhost:8000/api/rules`
- Wait 1+ minutes for next agent cycle
- Check backend logs for `[CUSTOM_RULE]` messages

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for comprehensive troubleshooting.

---

## 📚 Documentation

- **[README.md](README.md)** — Project overview (this file)
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** — Detailed setup & installation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System architecture diagrams & data flows

---

## 🎓 Tech Stack

- **Frontend**: React 18 (Create React App)
- **Backend**: FastAPI + asyncio agent loop
- **Database**: SQLite (`home_automation.db`) — built-in Python, zero config
  - Tables: `two_week_logs`, `agent_logs`, `notifications`, `custom_rules`
- **ML**: Scikit-learn RandomForest + Joblib

---

## 📝 License & Credits

**Final Year Project** — Educational Purpose  
**Version**: 4.0.0  
**Status**: ✅ Complete  

Last Updated: 2026-06-05
