# Backend Project Structure

```
backend/
├── agents/                      # Autonomous Agent Module
│   ├── __init__.py              # Clean exports
│   ├── nodes.py                 # 5-Node architecture (Node1–Node5)
│   ├── agent_loop.py            # Main agent loop runner (every 3 min)
│   └── py.typed                 # Type hints marker
│
├── services/                    # Business Logic Services
│   └── voice_processor.py       # Gemini AI NLP for voice commands
│
├── models/                      # (Reserved) ML models & Pydantic schemas
│   └── __init__.py
│
├── utils/                       # (Reserved) Helper utilities
│   └── __init__.py
│
├── main.py                      # FastAPI Application Entry Point
├── requirements.txt             # Python Dependencies
└── .env                         # Environment variables (API keys, paths)
```

---

## Architecture

### Autonomous Agent (5-Node Design)

The agent runs **every 3 minutes** with this pipeline:

| Node | Name | Responsibility |
|------|------|---------------|
| 1 | `node1_rf_predict` | RandomForest model predicts ON/OFF for all 5 devices |
| 2 | `node2_rule_engine` | Apply priority-ordered business rules (see below) |
| 3 | `node3_override_check` | Skip devices manually locked by the user |
| 4 | `node4_execute` | Apply state changes to DEVICES dict + DB |
| 5 | `node5_notify` | Push notification to frontend + log to SQLite |

### Node 2 — Rule Engine Priority Order

Rules are checked in this exact order per device per cycle:

1. `STATE_UNCHANGED` — Device already in predicted state → skip
2. `LOW_CONFIDENCE` — Confidence < 80% → block
3. `CUSTOM_RULE` — Temperature range matches a rule in `custom_rules` table → override
4. `SMART_PEAK_BLOCK` — AC during peak hours → block
5. `NIGHT_BLOCK` — Light/TV between 23:00–05:00 (if deep-night mode enabled) → block
6. `DAYLIGHT_BLOCK` — Light predicted ON during sunrise–sunset → block
7. `AWAY_MODE` — User marked as Away → block AC/Fan/Light/TV

### How to Import

```python
from agents import (
    node1_rf_predict,
    node2_rule_engine,
    node3_override_check,
    node4_execute,
    node5_notify,
    start_autonomous_agent,
)
```

### Integration with main.py

The agent is initialized in `main.py` at startup:

```python
@app.on_event("startup")
async def startup_agent():
    asyncio.create_task(
        start_autonomous_agent(
            agent_status=AGENT_STATUS,
            get_temp_func=get_live_temperature,
            devices=DEVICES,
            rf_model=RF_MODEL,
            target_names=TARGET_NAMES,
            feature_cols=FEATURE_COLS,
            deep_night_enabled=DEEP_NIGHT_MODE_ENABLED,
            is_home=IS_HOME,
            away_blocked=AWAY_BLOCKED_DEVICES,
            peak_hours=PEAK_HOURS,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            get_custom_rules_func=get_applicable_custom_rules,
            is_manually_locked_func=is_manually_locked,
            log_agent_action_func=log_agent_action_to_db,
            push_notification_func=push_notification,
            weather_cache=WEATHER_CACHE,   # provides sunrise_hour, sunset_hour
        )
    )
```

---

## Extending the Agent

**To add new business rules to Node 2:**
1. Edit `agents/nodes.py` → `node2_rule_engine()` function
2. Add new rule condition with descriptive `rule_reason` string
3. Insert it in the correct priority position

**To add a new node type:**
1. Create a function in `agents/nodes.py`
2. Export it from `agents/__init__.py`
3. Call it from `agents/agent_loop.py`

---

**Last Updated**: 2026-06-19
