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
🎙️ **Voice Control** — Natural language commands via Google Gemini AI (e.g. "Turn off the fan")  
☀️ **Daylight Block** — AI blocks Light from turning on during sunrise-to-sunset hours  
🌙 **Deep-Night Block** — User-toggleable: blocks Light/TV between 23:00–05:00  
🏠 **Home/Away Mode** — User-toggleable: away mode turns off AC/Fan/Light/TV automatically  
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
jupyter notebook train_model_5months.ipynb
```

### 2. Start Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
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
│  Device Control | Predictions | Analytics   │
│  Notifications | Voice 🎙️ | Settings       │
└───────────────────┬─────────────────────────┘
                     │ REST API (5s polling)
                     ▼
┌────────────────────────────────────────────┐
│         BACKEND API (FastAPI v4.0)          │
│  5-Node Agent Loop (runs every 3 min)       │
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

## 🤖 Agent Rule Engine (Node 2)

Rules are applied in this priority order each agent cycle:

| Priority | Rule | Trigger | Effect |
|----------|------|---------|--------|
| 1 | `STATE_UNCHANGED` | Device already in predicted state | Skip action |
| 2 | `LOW_CONFIDENCE` | Confidence < 80% | Block prediction |
| 3 | `CUSTOM_RULE` | User-defined temp rule matches | Override ML |
| 4 | `SMART_PEAK_BLOCK` | AC during peak hours | Block AC |
| 5 | `NIGHT_BLOCK` | Light/TV between 23:00–05:00 (if enabled) | Block |
| 6 | `DAYLIGHT_BLOCK` | Light predicted ON between sunrise–sunset | Block |
| 7 | `AWAY_MODE` | User marked as Away | Block AC/Fan/Light/TV |

---

## 🌡️ Temperature Rules System

Custom rules stored in the `custom_rules` SQLite table override AI predictions:

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

## ⚡ Device Power Consumption

| Device | Wattage |
|--------|---------|
| AC (Air Conditioner) | 2500 W |
| Fan | 150 W |
| Light | 100 W |
| TV | 120 W |
| Refrigerator (Fridge) | 200 W |

---

## 📁 Project Structure

```
Smarthome Project version 2/
│
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── nodes.py            # 5-Node AI pipeline
│   │   ├── agent_loop.py       # Autonomous loop runner
│   │   └── README.md           # Agent documentation
│   ├── services/
│   │   └── voice_processor.py  # Gemini AI voice NLP
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Configuration (API keys, paths)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main React application
│   │   ├── App.css             # Styling
│   │   ├── AuthPage.jsx        # Login / Signup
│   │   ├── PowerConsumption.jsx # Energy analytics charts
│   │   └── index.js
│   ├── package.json
│   └── .env
│
├── home_automation.db                  # SQLite database (auto-created)
├── home_automation_model.pkl           # Trained ML model
├── home_automation_dataset_5months.csv # Training dataset (5 months)
├── train_model_5months.ipynb           # ML training notebook
│
├── README.md           # This file — project overview
├── SETUP_GUIDE.md      # Detailed setup & troubleshooting
├── ARCHITECTURE.md     # System architecture diagrams & data flows
└── VOICE_INPUT.md      # Voice control feature documentation
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
- Wait for next agent cycle (every 3 minutes)
- Check backend logs for `[CUSTOM_RULE]` messages

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for comprehensive troubleshooting.

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| [README.md](README.md) | Project overview (this file) |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Detailed setup, installation & troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture diagrams & data flows |
| [VOICE_INPUT.md](VOICE_INPUT.md) | Voice control feature: API, examples, config |

---

## 🎓 Tech Stack

- **Frontend**: React 18 (Create React App)
- **Backend**: FastAPI + asyncio agent loop (every 3 min)
- **Database**: SQLite (`home_automation.db`) — built-in Python, zero config
  - Tables: `two_week_logs`, `device_logs`, `agent_logs`, `notifications`, `custom_rules`, `peak_hours`
- **ML**: Scikit-learn RandomForest + Joblib
- **Voice NLP**: Google Gemini 2.0 Flash AI
- **Weather API**: RapidAPI OpenWeather (live temp, sunrise, sunset)

---

## 📝 License & Credits

**Final Year Project** — Educational Purpose  
**Version**: 4.0.0  
**Status**: ✅ Complete  

Last Updated: 2026-06-21
