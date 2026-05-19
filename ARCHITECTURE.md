# 🏠 AI Home Automation System - Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │         REACT DASHBOARD (Port 3000)                   │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │                                                        │     │
│  │  Device Cards │ Controls │ Analytics │ Predictions   │     │
│  │  Real-time Updates via WebSocket                      │     │
│  │  Dark Mode │ Responsive Design │ Charts              │     │
│  │                                                        │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                          │
            REST API + WebSocket Connection
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │          FASTAPI SERVER (Port 8000)                   │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │                                                        │     │
│  │  Endpoints:                                           │     │
│  │  /devices/status      /device/control                 │     │
│  │  /predictions         /analytics                      │     │
│  │  /model/retrain       /system/status                  │     │
│  │  /ws (WebSocket)                                      │     │
│  │                                                        │     │
│  └──┬───────────────────────────────┬────────────────┬───┘     │
│     │                               │                │         │
│     ▼                               ▼                ▼         │
│  ┌──────────────┐            ┌─────────────┐    ┌─────────┐   │
│  │   SERVICE    │            │   SERVICE   │    │SERVICE  │   │
│  └──────────────┘            └─────────────┘    └─────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │                     │                    │
          │                     │                    │
          ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BUSINESS LOGIC LAYER                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │         AI AGENT (6-Node Pipeline)                   │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │                                                       │      │
│  │  1. HistoryNode ──┐                                 │      │
│  │                   │                                 │      │
│  │  2. PredictNode ──┤ (⭐ Learns overrides)          │      │
│  │                   ├─→ Decision Engine ──┐           │      │
│  │  3. RuleEngine ───┤   (Priority-based)  ├─→ Output │      │
│  │                   │                     │           │      │
│  │  4. DecisionEngine│                     │           │      │
│  │  5. ControlNode   │                     │           │      │
│  │  6. LoggingNode   │                     │           │      │
│  │                                                       │      │
│  │               │      │
│  │                                                       │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │        MACHINE LEARNING MODEL                        │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │                                                       │      │
│  │  Multi-Output RandomForest Classifier               │      │
│  │  Predicts: AC, Fan, Light, TV, Fridge               │      │
│  │  Features: Time, Temp, Humidity, Day patterns       │      │
│  │                                                       │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │     CONTINUOUS LEARNING SYSTEM                       │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │                                                       │      │
│  │  Weekly Retraining Cycle:                           │      │
│  │  Collect → Analyze → Train → Evaluate → Improve     │      │
│  │                                                       │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATA LAYER                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │          SQLite Database (home_automation.db)        │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │                                                        │     │
│  │  Tables:                                             │     │
│  │  • two_week_logs          (14-day device history)     │     │
│  │  • agent_logs             (AI agent action log)       │     │
│  │  • notifications          (24h event store, NEW)      │     │
│  │                                                        │     │
│  │  Key columns in notifications:                       │     │
│  │    id, timestamp, device, action, reason,            │     │
│  │    confidence, node, read                            │     │
│  │                                                        │     │
│  │  File: home_automation.db (root directory)           │     │
│  │  Driver: sqlite3 (Python built-in, no server needed) │     │
│  │                                                        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram (6-Node Pipeline)

```
DEVICE STATE
    │
    ▼
┌──────────────────────────────────────┐
│   Backend receives current state      │
│   (Temperature, Humidity, Time, etc)  │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   1. Fetch History (past 24h)        │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   2. ML Model Prediction              │
│   (⭐ Already learns user overrides)  │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   3. Apply Business Rules             │
│   (temperature, time, humidity, etc)  │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   4. Make Final Decision              │
│   (priority-based resolution)         │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   5. Update Device State              │
│   (write to DB)                       │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   6. Log Decision to Database         │
│   (for learning)                      │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   Broadcast to Frontend via WebSocket │
│   (real-time update)                  │
└──────────────────────────────────────┘
```

---

## Decision Priority System (6-Node Pipeline)

```
INPUT: Device context (current time, temperature, humidity, etc)
   │
   ├─────────────────────────────────────────────┐
   │                                              │
   ▼                                              │
Apply Rule Engine (Priority 80 - HIGHEST)        │
   │                                              │
   ├─ Rule Match → USE IT ─────────────────────┤ │
   │                                             │ │
   └─ No Match ──────────┐                       │ │
                         │                       │ │
                         ▼                       │ │
                ML Prediction (Priority 60)      │ │
                         │                       │ │
                         ├─ Use It                │ │
                         │                       │ │
                         └─┬─────────────────┐   │ │
                           │                 │   │ │
                           ▼                 │   │ │
                History Pattern (Priority 40)│   │ │
                           │                 │   │ │
                           ├─ Use It         │   │ │
                           │                 │   │ │
                           └─┬──────┬────────┘   │ │
                             │      │            │ │
                             ▼      │            │ │
                    DEFAULT: OFF (0) │            │ │
                             │      │            │ │
                             └──────┴────────────┘ │
                                    │              │
                                    ▼              │
                           FINAL DECISION OUTPUT   │
                                    │<─────────────┘
                                    
NOTE: User overrides are learned by ML model during
      nightly retraining. No explicit override node needed.
```

---

## Device Decision Tree

```
Device: AC
├─ IF temp > 30°C → Decision: ON
├─ IF temp < 25°C → Decision: OFF
├─ IF working_hours (9-6, weekday) → Decision: ON
├─ IF ML_predicts_ON (confidence > 0.6) → Decision: ON
├─ User_override? → Decision: USER_CHOICE
└─ DEFAULT → Decision: OFF

Device: Fan
├─ IF temp > 30°C → Decision: ON
├─ IF humidity > 70% → Decision: ON
├─ User_override? → Decision: USER_CHOICE
└─ DEFAULT → Decision: OFF

Device: Light
├─ IF night (18:00-07:00) → Decision: ON
├─ IF day (07:00-18:00) → Decision: OFF
├─ User_override? → Decision: USER_CHOICE
└─ DEFAULT → Decision: OFF

Device: TV
├─ IF weekend AND (12:00-23:00) → Decision: ON
├─ IF late_night (23:00-06:00) → Decision: OFF
├─ User_override? → Decision: USER_CHOICE
└─ DEFAULT → Decision: OFF

Device: Fridge
└─ ALWAYS → Decision: ON
```

---

## File Structure & Dependencies

```
backend/main.py (FastAPI)
    │
    ├─ sqlite3 (Python built-in — no external DB server needed)
    │   └─→ home_automation.db (3 tables: two_week_logs, agent_logs, notifications)
    │
    ├─ joblib (load home_automation_model.pkl)
    │
    ├─ numpy (feature engineering)
    │
    └─ FastAPI + Uvicorn (ASGI server)

frontend/src/App.jsx (React)
    │
    ├─ Polling REST API every 5s (devices, system status)
    │
    ├─ Notifications page polls /api/notifications/24h every 15s
    │
    └─ API calls to localhost:8000
```

---

## Deployment Architecture

```
PRODUCTION DEPLOYMENT

┌─────────────────────────────────────────────────────────┐
│                   LOCAL / SERVER                         │
│         (No database server installation needed)         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI Backend (Port 8000)                    │   │
│  │  uvicorn main:app --host 0.0.0.0 --port 8000    │   │
│  └────────────────────┬─────────────────────────────┘   │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  SQLite Database: home_automation.db             │   │
│  │  • two_week_logs  (14-day device history)        │   │
│  │  • agent_logs     (AI agent decisions)           │   │
│  │  • notifications  (24h event log — persistent)   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Frontend: React (Port 3000 / npm run start)    │   │
│  │  (or npm run build for static production files) │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Continuous Learning Pipeline

```
WEEK 1-4: DATA COLLECTION
├─ Collect all device predictions
├─ Track actual user actions
├─ Record manual overrides
└─ Store ground truth in database

WEEK 5: RETRAINING TRIGGER
├─ Check: enough new data? > 1000 samples
├─ Fetch training data from DB
├─ Prepare features (time, temp, humidity, patterns)
└─ Split train/test sets

WEEK 6: MODEL TRAINING
├─ Train RandomForest on new data
├─ Evaluate on test set
├─ Compare to previous accuracy
├─ Log metrics to database
└─ Save improved model (model.pkl)

WEEK 7: VALIDATION
├─ Run predictions on live data
├─ Monitor accuracy in real-time
├─ Compare AI vs user decisions
└─ Identify drift or degradation

WEEK 8: FEEDBACK LOOP
├─ Extract user preferences from overrides
├─ Adjust rules based on patterns
├─ Update feature importance weights
└─ Back to Week 1 - continuous cycle
```

---

## API Endpoint Hierarchy

```
/api/
├── devices/
│   ├── status (GET)              - All devices
│   └── {id} (GET)               - Device detail + lock status
│
├── device/
│   ├── control (POST)           - Turn ON/OFF + set lock duration (5-60m)
│   └── override-duration (POST) - Update AI lock duration without re-toggling
│
├── current-prediction (GET)     - Live RF model prediction
│
├── analytics (GET)              - System-wide statistics
│
├── history (GET)                - 14-day device log (two_week_logs)
├── history/daily (GET)          - Daily aggregated ON counts
│
├── notifications (GET)          - In-memory recent notifications
├── notifications/24h (GET)      - Last 24h from SQLite DB (persistent)
├── notifications/read-all (POST)- Mark all read (memory + DB)
├── notifications/unread-count (GET) - Badge count
│
├── agent/status (GET)           - Live agent cycle trace + manual locks
│
└── system/
    └── status (GET)             - Health check (DB type: SQLite)
```

---

## Component Interaction Sequence

```
User Interaction:
├─ Opens http://localhost:3000
├─ Frontend loads React app
├─ Calls GET /api/devices/status
├─ Displays device cards
├─ Sets up WebSocket connection
└─ Listens for real-time updates

User Action (Toggle Device):
├─ Clicks device ON button
├─ Frontend calls POST /api/device/control
├─ Backend receives request
├─ Updates devices table in DB
├─ Broadcasts update via WebSocket
├─ Frontend receives update
├─ UI refreshes instantly
└─ Process repeats every action

Background (Every 5 minutes):
├─ Backend runs agent loop
├─ Gets current temp/humidity
├─ Processes all devices through agent
├─ Updates device states
├─ Logs decisions to DB
├─ Broadcasts to all connected clients
└─ Frontend updates in real-time

Weekly (Retraining):
├─ Check if enough data collected
├─ Fetch training data from DB
├─ Train new model
├─ Evaluate performance
├─ Save improved model
├─ Log metrics
└─ Continue serving predictions
```

---

This architecture provides:
✅ **Scalability** - Horizontal scaling of backend
✅ **Reliability** - SQLite file persistence (no DB server needed)
✅ **Performance** - Indexed queries, in-memory notification cache
✅ **Learning** - Continuous model improvement
✅ **Real-time** - 5s polling for device states, 15s for notifications
✅ **User Control** - Manual override with configurable 5–60 min AI lock
✅ **Monitoring** - Full logging: agent_logs + notifications table in SQLite
✅ **Notifications** - Persistent 24h event history (User Manual + AI Auto)

---

## 🗄️ Database: SQLite

**Why SQLite?**
- Zero configuration — no server, no install, runs on any machine
- File-based: `home_automation.db` in project root
- Python built-in `sqlite3` module (no extra dependencies)
- Sufficient for FYP scale (~14 days × 5 devices = ~3,500 records)

**Tables:**

| Table | Purpose | Key Columns |
|---|---|---|
| `two_week_logs` | 14-day device state history | device_id, device_name, timestamp, action, energy_wh |
| `agent_logs` | AI agent autonomous decisions | device_id, action, confidence, reason, timestamp |
| `notifications` | 24h event log (manual + AI) — **NEW** | device, action, reason, node, confidence, read, timestamp |

**Override Lock System:**
- Default AI lock after manual override: **30 minutes**
- Configurable per device: **5 – 60 minutes** (slider in Device Control page)
- Lock is stored in memory (`MANUAL_OVERRIDES` dict); notification is persisted to DB
