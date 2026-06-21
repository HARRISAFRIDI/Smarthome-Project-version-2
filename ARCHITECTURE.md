# 🏠 AI Home Automation System — Architecture Diagram

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
│  │  🎙️ Voice Input │ Real-time Updates (5s polling)    │     │
│  │  Dark Mode │ Responsive Design │ Charts              │     │
│  │  🌙 Deep-Night Block │ 🏠 Home/Away Toggle           │     │
│  │                                                        │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                          │
            REST API (polling every 5s)
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
│  │  /devices/status      /device/control                 │     │
│  │  /voice/command 🎙️   /current-prediction             │     │
│  │  /analytics           /history                        │     │
│  │  /notifications/24h   /agent/status                   │     │
│  │  /settings/night-mode /home/status                    │     │
│  │  /weather/current     /system/status                  │     │
│  │                                                        │     │
│  └──┬───────────────────────────────┬────────────────┬───┘     │
│     │                               │                │         │
│     ▼                               ▼                ▼         │
│  ┌──────────────┐            ┌─────────────┐    ┌──────────┐  │
│  │  AI AGENT    │            │  ML MODEL   │    │ VOICE    │  │
│  │  (5-node)    │            │  (RF+joblib)│    │ PROCESSOR│  │
│  └──────────────┘            └─────────────┘    └──────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
          │                     │                    │
          │                     │                    │
          ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATA LAYER                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │          SQLite Database (home_automation.db)        │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │  • two_week_logs     (14-day device state history)   │     │
│  │  • agent_logs        (AI agent autonomous decisions) │     │
│  │  • notifications     (24h event log — persistent)   │     │
│  │  • custom_rules      (temperature-based rules)       │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram (5-Node Pipeline)

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
│   (RandomForest, 80%+ confidence)    │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   3. Apply Business Rules             │
│   (priority-ordered rule engine)     │
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
│   (for future learning)              │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   Notify Frontend (push notification) │
│   (real-time update via polling)     │
└──────────────────────────────────────┘
```

---

## Agent Rule Engine — Node 2 Priority Order

Each agent cycle (every 3 minutes) applies rules in this exact order:

| # | Rule | Device(s) | Condition | Action |
|---|------|-----------|-----------|--------|
| 1 | `STATE_UNCHANGED` | All | Already in predicted state | Skip |
| 2 | `LOW_CONFIDENCE` | All | Confidence < 80% | Block |
| 3 | `CUSTOM_RULE` | AC / Fan | Temp-range match in DB | Override |
| 4 | `SMART_PEAK_BLOCK` | AC | Peak hours defined in config | Block AC |
| 5 | `NIGHT_BLOCK` | Light, TV | 23:00–05:00 & deep-night mode ON | Block |
| 6 | `DAYLIGHT_BLOCK` | Light | Current time between sunrise–sunset | Block |
| 7 | `AWAY_MODE` | AC, Fan, Light, TV | User set status to Away | Block all 4 |

### DAYLIGHT_BLOCK Details

- **Source**: `backend/agents/nodes.py` → `node2_rule_engine()` (Rule 2c)
- **Default Location**: Mardan, Pakistan (lat 34.1925, lon 72.0285)
- **Weather source**: RapidAPI OpenWeather, cached every 10 minutes
- **Format**: Sunrise/sunset returned as 12-hour AM/PM (e.g. `"05:12 AM"`, `"07:47 PM"`)
- **Example reason string**: `"DAYLIGHT_BLOCK (Light OFF — natural daylight available, sunrise=05:00, sunset=19:00)"`

---

## Decision Priority System

```
Manual Override / Voice Command (Priority 100 — ABSOLUTE HIGHEST)
    │
    ├─ Yes → Execute immediately, create 30-min override lock
    └─ No lock active → AI agent decides:
         │
         ├─ Custom Rules (Priority 80)
         ├─ ML Prediction (Priority 60)
         ├─ History Pattern (Priority 40)
         └─ DEFAULT: OFF (Priority 0)
```

---

## Device Decision Tree

```
Device: AC
├─ IF temp > 30°C       → Rule: ON (custom rule)
├─ IF temp < 25°C       → Rule: OFF (custom rule)
├─ IF SMART_PEAK_BLOCK  → BLOCKED
├─ IF ML_predicts_ON (confidence > 80%) → ON
├─ User_override?       → USER_CHOICE
└─ DEFAULT              → OFF

Device: Fan
├─ IF temp > 30°C       → Rule: ON (custom rule)
├─ IF humidity > 70%    → Rule: ON
├─ User_override?       → USER_CHOICE
└─ DEFAULT              → OFF

Device: Light
├─ IF DAYLIGHT_BLOCK (sunrise–sunset) → BLOCKED
├─ IF NIGHT_BLOCK (23:00–05:00)       → BLOCKED (if enabled)
├─ IF night (18:00–07:00) → ML predicts ON
├─ User_override?       → USER_CHOICE
└─ DEFAULT              → OFF

Device: TV
├─ IF NIGHT_BLOCK (23:00–05:00) → BLOCKED (if enabled)
├─ IF weekend AND (12:00–23:00) → ML prediction ON
├─ User_override?       → USER_CHOICE
└─ DEFAULT              → OFF

Device: Fridge
├─ IF AC is ON         → OFF (energy saving)
├─ IF peak hours (18:00–22:00) → OFF (demand management)
├─ IF temp < 25°C    → OFF (no cooling load)
├─ Compressor cycle: ON 20 min, OFF 10 min (realistic cycle)
└─ DEFAULT            → OFF
```

---

## File Structure & Dependencies

```
backend/main.py (FastAPI)
    │
    ├─ agents/
    │   ├─ nodes.py         (node1..node5 functions)
    │   ├─ agent_loop.py    (start_autonomous_agent)
    │   └─ __init__.py      (clean exports)
    │
    ├─ services/
    │   └─ voice_processor.py (Gemini AI NLP)
    │
    ├─ sqlite3 (Python built-in)
    │   └─→ home_automation.db
    │         • two_week_logs   (14-day history)
    │         • agent_logs      (AI decisions)
    │         • notifications   (24h event log)
    │         • custom_rules    (temperature-based rules)
    │
    ├─ joblib (load home_automation_model.pkl)
    ├─ numpy (feature engineering)
    └─ FastAPI + Uvicorn (ASGI server)

frontend/src/App.jsx (React)
    │
    ├─ Polling REST API every 5s (devices, system status)
    ├─ Notifications page polls every 3s
    └─ Voice widget: Web Speech API → /api/voice/command
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   LOCAL / SERVER                         │
│         (No database server installation needed)         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI Backend (Port 8000)                    │   │
│  │  python main.py                                 │   │
│  └────────────────────┬─────────────────────────────┘   │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  SQLite Database: home_automation.db             │   │
│  │  • two_week_logs  (14-day device history)        │   │
│  │  • agent_logs     (AI agent decisions)           │   │
│  │  • notifications  (24h event log — persistent)   │   │
│  │  • custom_rules   (temperature automation)       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Frontend: React (Port 3000 / npm start)        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoint Hierarchy

```
/api/
├── devices/
│   ├── status (GET)                 - All devices
│   └── {id} (GET)                   - Device detail + lock status
│
├── device/
│   ├── control (POST)               - Turn ON/OFF + set lock (5-60m)
│   └── override-duration (POST)     - Update AI lock without re-toggling
│
├── voice/
│   └── command (POST) 🎙️           - Natural language voice command
│
├── current-prediction (GET)         - Live RF model prediction
├── analytics (GET)                  - System-wide statistics
│
├── history (GET)                    - 14-day device log
├── history/daily (GET)              - Daily aggregated ON counts
│
├── notifications (GET)              - In-memory recent notifications
├── notifications/24h (GET)         - Last 24h from SQLite DB (persistent)
├── notifications/read-all (POST)   - Mark all read
├── notifications/unread-count (GET) - Badge count
│
├── rules (GET/POST/PUT/DELETE)      - Temperature-based rule management
│
├── agent/status (GET)               - Live agent cycle trace + manual locks
│
├── settings/
│   └── night-mode (GET/POST)        - Deep-night block on/off
│
├── home/
│   └── status (GET/POST)            - Home / Away presence mode
│
└── system/
    └── status (GET)                 - Health check (DB: SQLite)
```

---

## 🎙️ Voice Input — Summary

Voice input is processed by Gemini AI NLP. Full documentation: **[VOICE_INPUT.md](VOICE_INPUT.md)**

```
User types/speaks → /api/voice/command → Gemini 2.0 Flash parses command
    → Device identified → State updated → 30-min override lock set
    → Notification logged → Frontend updates
```

**Supported devices**: AC, Fan, Light, TV, Fridge  
**Supported actions**: ON, OFF, STATUS, ALL  

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

## 🗄️ Database: SQLite

**Why SQLite?**
- Zero configuration — no server, no install, runs on any machine
- File-based: `home_automation.db` in project root
- Python built-in `sqlite3` module (no extra dependencies)
- Sufficient for FYP scale (~20 days × 5 devices = ~8,700+ records)

**Tables:**

| Table | Purpose | Key Columns | Current Data |
|---|---|---|---|
| `two_week_logs` | Rolling device state history | device_id, device_name, timestamp, action, energy_wh | 8,763 rows (Jun 1–20, 2026) |
| `device_logs` | Per-event device log with temperature | device_name, timestamp, action, temperature, hour, energy_used | 8,763 rows (Jun 1–20, 2026) |
| `agent_logs` | AI agent autonomous decisions | device_id, action, confidence, reason, timestamp | 152 rows |
| `notifications` | 24h event log (manual + AI) | device, action, reason, node, confidence, read, timestamp | 187 rows |
| `custom_rules` | Temperature-based automation rules | device_id, temp_min, temp_max, action, enabled, description | 7 rules |
| `peak_hours` | Hourly energy usage aggregates | hour, energy_usage, is_peak | 24 rows (hours 15–18 are peak) |
| `devices` | Device registry | id, name, type, status, energy_consumption | 5 devices |
| `users` | User accounts | id, name, email, latitude, longitude | 2 users |

**Override Lock System:**
- Default AI lock after manual override: **30 minutes**
- Configurable per device: **5 – 60 minutes** (slider in Device Control page)
- Lock stored in memory (`MANUAL_OVERRIDES` dict); notification persisted to DB

---

## Continuous Learning Pipeline

```
DATA COLLECTION (ongoing)
├─ Collect all device predictions
├─ Track actual user actions
├─ Record manual overrides
└─ Store ground truth in two_week_logs

RETRAINING TRIGGER (weekly)
├─ Check: enough new data? > 1000 samples
├─ Fetch training data from DB
└─ Split train/test sets

MODEL TRAINING
├─ Train RandomForest on new data
├─ Evaluate on test set
├─ Compare to previous accuracy
└─ Save improved model (model.pkl)

FEEDBACK LOOP
├─ Extract user preferences from overrides
├─ Adjust rules based on patterns
└─ Back to data collection
```

---

## Component Interaction Sequence

```
User Action (Toggle Device):
├─ Clicks device ON button
├─ Frontend calls POST /api/device/control
├─ Backend updates DEVICES dict
├─ Refreshes device list → Frontend updates instantly
└─ Notification logged to DB

Background (Every 3 minutes):
├─ Agent loop runs all 5 nodes
├─ Gets current temp/humidity/sunrise/sunset
├─ Processes all devices through agent
├─ Updates device states
├─ Logs decisions to DB
└─ Frontend picks up changes on next 5s poll

Voice Command:
├─ User speaks → Web Speech API transcript
├─ Frontend POSTs to /api/voice/command
├─ Gemini AI parses device + action
├─ Device state updated + 30-min lock set
└─ Notification appears in real-time
```

---

This architecture provides:
✅ **Scalability** - Horizontal scaling of backend  
✅ **Reliability** - SQLite file persistence (no DB server needed)  
✅ **Performance** - Indexed queries, in-memory notification cache  
✅ **Learning** - Continuous model improvement  
✅ **Real-time** - 5s polling for device states, 3s for notifications  
✅ **User Control** - Manual override with configurable 5–60 min AI lock  
✅ **Monitoring** - Full logging: agent_logs + notifications table in SQLite  
✅ **Voice Control** - Gemini AI NLP for natural language commands  
✅ **Smart Rules** - Daylight block, deep-night block, home/away mode  

---

**Status**: ✅ Production Ready  
**Last Updated**: 2026-06-21  
**Maintained By**: Smart Home Development Team
