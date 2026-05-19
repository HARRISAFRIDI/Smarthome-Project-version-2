# 🏠 AI Home Automation System v4.0

> **Final Year Project**: AI-powered smart home automation using Machine Learning + Agentic AI + Real-time Dashboard

## ✨ Key Features

🤖 **5-Node Autonomous Agent** — RF Predict → Rule Engine → Override Check → Execute → Notify  
🧠 **Machine Learning** — Multi-output RandomForest model trained on 5000+ real scenarios  
📊 **Real-time Dashboard** — Device control, AI predictions, 14-day analytics, notifications  
🔔 **Notifications Page** — 24h persistent event log (Manual + AI actions) stored in SQLite  
🔒 **Smart Override** — User manually overrides AI; AI locked for configurable **5–60 min**  
⚡ **Per-device Lock Duration** — Each device has its own adjustable override timer (slider)  
🗄️ **SQLite Database** — Zero-config, file-based, no server needed (`home_automation.db`)  
📱 **Responsive UI** — Works on desktop, tablet, mobile  

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+  
- **No database server required** — uses SQLite (built into Python)

### 1. Train ML Model (if `home_automation_model.pkl` missing)

```bash
# Run Jupyter notebook
jupyter notebook 2024_dataset_training_model.ipynb
# This creates home_automation_model.pkl in root directory
```

### 2. Train ML Model (if not done)

```bash
# Run Jupyter notebook
jupyter notebook 2024_dataset_training_model.ipynb

# This creates model.pkl in root directory
```

### 3. Start Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Backend runs at**: http://localhost:8000  
**API Docs at**: http://localhost:8000/docs

### 4. Start Frontend

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
│          FRONTEND DASHBOARD (React)           │
│   Device Status | Control | Notifications     │
└───────────────────┬───────────────────────┘
                     │ REST API (polling)
                     ▼
┌────────────────────────────────────────────┐
│         BACKEND API (FastAPI v4.0)            │
│  5-Node Agent Loop (runs every 60s)           │
└──────────────┬──────────────────────┬─────────┘
                 │                      │
                 ▼                      ▼
         ┌──────────────┐        ┌──────────────┐
         │ RF ML MODEL   │        │ SQLite DB      │
         │ (.pkl joblib) │        │ home_auto.db   │
         └──────────────┘        └──────────────┘
```

---

## 🧠 AI Agent Architecture (LangGraph-style)

### Node Pipeline

```
1. HISTORY NODE
   └─ Fetch recent device usage from DB

2. PREDICT NODE  
   └─ ML model predicts ON/OFF with confidence

3. RULE ENGINE NODE
   └─ Apply  domain-specific rules


5. DECISION ENGINE
   └─ Combine all signals with priorities

6. CONTROL NODE
   └─ Update device state (simulate ON/OFF)

7. LOGGING NODE
   └─ Save decision to DB for learning
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

## 📊 Integrated Rule Engine (8 Rules)

```python
Rule 1:  temp > 30°C        → AC ON, Fan ON
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
| `/api/device/control` | POST | Turn ON/OFF + set lock duration |
| `/api/device/override-duration` | POST | Change per-device AI lock (5–60 min) |
| `/api/current-prediction` | GET | Live RF model prediction |
| `/api/analytics` | GET | System-wide analytics |
| `/api/history` | GET | 14-day device history (SQLite) |
| `/api/history/daily` | GET | Daily ON-count aggregation |
| `/api/notifications/24h` | GET | Last 24h events from SQLite |
| `/api/notifications/read-all` | POST | Mark all notifications read |
| `/api/notifications/unread-count` | GET | Unread badge count |
| `/api/agent/status` | GET | Agent cycle trace + manual locks |
| `/api/system/status` | GET | Health check (DB: SQLite) |

**Full Docs**: http://localhost:8000/docs (Swagger UI)

---

## 📈 Continuous Learning System

### Weekly Retraining Cycle

```
Collect Data (7 days)
    ↓
Compare Predictions vs Actions
    ↓
Calculate feedback signal
    ↓
Retrain model
    ↓
Evaluate accuracy
    ↓
Save improved model
    ↓
Monitor user overrides
```

### Performance Tracking

- **Stores**: Every prediction + actual outcome
- **Analyzes**: AI vs human behavior
- **Improves**: Weekly model retraining
- **Logs**: Training history with metrics

---

## 🎨 Dashboard Features

### Device Control Panel
- Real-time ON/OFF status
- Manual override buttons
- Energy consumption display
- Last updated timestamp

### Environmental Controls
- Temperature slider (0-40°C)
- Humidity slider (0-100%)
- AI prediction button

### Analytics Dashboard
- Device accuracy chart
- Energy consumption graph
- System stats (total devices, online count)
- Model performance metrics

### Real-time Updates
- WebSocket for live data
- 30-second refresh interval
- Connected client count
- Device status broadcasting

---

## 📁 Project Structure

```
Smarthome Project version 2/
│
├── database/
│   ├── schema.sql              # PostgreSQL database schema
│   └── db_manager.py           # Database utilities & managers
│
├── ml_agent/
│   ├── agent.py                # LangGraph-style agent
│   ├── continuous_learning.py  # Auto-retraining system
│   └── __init__.py
│
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Configuration
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main React component
│   │   ├── App.css             # Styling
│   │   └── index.js
│   ├── package.json            # Node dependencies
│   ├── .env                    # Configuration
│   └── public/
│
├── scripts/
│   ├── setup.sh                # One-time setup
│   └── run.sh                  # Start all services
│
├── 2024_dataset_training_model.ipynb  # ML training
├── home_automation_dataset_2024.csv   # Dataset
│
├── SETUP_GUIDE.md              # Detailed setup instructions
├── README.md                   # This file
└── .gitignore
```

---

## 🔧 Configuration

### Backend `.env`

```env
# Database
DB_HOST=localhost
DB_NAME=home_automation
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432

# API
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Model
MODEL_PATH=../model.pkl
RETRAIN_INTERVAL_DAYS=7

# Frontend
FRONTEND_URL=http://localhost:3000
```

### Frontend `.env`

```env
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

---

## 🧪 Testing

### Test Database Connection

```bash
cd backend
python -c "from database.db_manager import DatabaseConnection; db = DatabaseConnection(); db.connect()"
```

### Test ML Model

```bash
python -c "import joblib; model = joblib.load('../model.pkl'); print(model)"
```

### Test API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

### Test Frontend

```bash
npm test  # Run React tests
```

---

## 🐛 Troubleshooting

**Model not found?**
- Train using notebook first
- Ensure `home_automation_model.pkl` exists in root

**Port already in use?**
```bash
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

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for comprehensive troubleshooting.

---

## 📚 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed setup & installation
- **[SQL Schema](database/schema.sql)** - Database structure
- **[Agent Code](ml_agent/agent.py)** - AI agent architecture
- **[API Docs](http://localhost:8000/docs)** - Interactive API reference
- **Code Comments** - Comprehensive comments in all files

---

## 🎓 Learning Resources

### Machine Learning
- Dataset: 5000+ device usage samples
- Model: Multi-output RandomForest classifier
- Features: Time, temperature, humidity, day patterns
- Output: 5 devices (AC, Fan, Light, TV, Fridge)

### Agent Architecture
- LangGraph-inspired node design
- Priority-based decision making
- Fallback mechanisms
- Error handling & logging

### Web Stack
- **Frontend**: React 18 (Vite/CRA)
- **Backend**: FastAPI 4.0 + asyncio agent loop
- **Database**: **SQLite** (`home_automation.db`) — built-in Python, zero config
  - Tables: `two_week_logs`, `agent_logs`, `notifications`
- **ML**: Scikit-learn RandomForest + Joblib

---

## 🚀 Deployment

### Local Development (Current)
```bash
npm run dev      # Frontend with hot reload
python main.py  # Backend with auto-reload
```

### Production Build
```bash
# Frontend
cd frontend
npm run build
# Outputs to build/ folder

# Backend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Serve with nginx/Apache
```

### Cloud Deployment
```
Consider: AWS (EC2), Azure (App Service), GCP (Cloud Run)
Or: Docker + Kubernetes for scaling
```

---

## 📝 License & Credits

**Final Year Project** - Educational Purpose  
**Version**: 1.0.0  
**Status**: ✅ Complete Architecture  

---

## 🤝 Support

For issues or questions:
1. Check [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. Review code comments
3. Check API documentation at `/docs`
4. Inspect backend/frontend logs

---

**Built with ❤️ for intelligent home automation**

Last Updated: 2026-05-11 | Version 4.0.0
