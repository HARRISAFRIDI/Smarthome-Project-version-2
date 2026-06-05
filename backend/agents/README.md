# Backend Project Structure

```
backend/
├── agents/                      # Autonomous Agent Module
│   ├── __init__.py
│   ├── nodes.py                # 5-Node architecture (Node1-5)
│   ├── agent_loop.py          # Main agent loop runner
│   └── py.typed               # Type hints marker
│
├── models/                      # ML Models & Data Models
│   └── __init__.py
│
├── services/                    # Business Logic Services
│   └── __init__.py
│
├── utils/                       # Utility Functions
│   └── __init__.py
│
├── main.py                      # FastAPI Application Entry Point
├── requirements.txt             # Python Dependencies
└── README.md
```

## Architecture

### Autonomous Agent (5-Node Design)

The agent runs every 3 minutes with this pipeline:

1. **Node 1 - RF Predict**: RandomForest model predicts device states
2. **Node 2 - Rule Engine**: Apply business rules (confidence, night mode, peak hours, custom rules)
3. **Node 3 - Override Check**: Skip manually locked devices
4. **Node 4 - Execute**: Change device states
5. **Node 5 - Notify**: Send user notifications

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
            # ... other parameters
        )
    )
```

## Extending the Agent

To add new business rules to Node 2:
1. Edit `agents/nodes.py` → `node2_rule_engine()` function
2. Add new rule condition with descriptive `rule_reason`

To add new node types:
1. Create function in `agents/nodes.py`
2. Export from `agents/__init__.py`
3. Call from `agents/agent_loop.py`
