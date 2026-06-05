# ============================================
# AI HOME AUTOMATION - FASTAPI BACKEND v4.0
# Autonomous 5-Node Agent Loop
# RF Model → Rule Engine → Override Check → Execute → Notify
# ============================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging, sys, csv, os, sqlite3, asyncio, hashlib, json
import urllib.request, urllib.error
import numpy as np
import joblib

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "home_automation.db")
MODEL_PATH = os.path.join(PROJECT_DIR, "home_automation_model.pkl")
CSV_PATH = os.path.join(PROJECT_DIR, "home_automation_dataset_2024.csv")

# ── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Home Automation API",
    description="Autonomous 5-Node Agent: RF Predict → Rule Engine → Override Check → Execute → Notify",
    version="4.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ───────────────────────────────────────────────
RF_MODEL = None

DEVICES = {
    1: {"name": "AC", "type": "Air Conditioner", "status": False, "energy": 2500},
    2: {"name": "Fan", "type": "Cooling Device", "status": True, "energy": 150},
    3: {"name": "Light", "type": "Lighting", "status": True, "energy": 100},
    4: {"name": "TV", "type": "Entertainment", "status": False, "energy": 200},
    5: {"name": "Fridge", "type": "Refrigerator", "status": True, "energy": 500},
}

DEVICE_STATS = {
    1: {"on_count": 450, "off_count": 550, "accuracy": 0.92},
    2: {"on_count": 680, "off_count": 320, "accuracy": 0.89},
    3: {"on_count": 750, "off_count": 250, "accuracy": 0.95},
    4: {"on_count": 280, "off_count": 720, "accuracy": 0.88},
    5: {"on_count": 900, "off_count": 100, "accuracy": 0.96},
}

# Manual override registry: device_id → datetime when user manually acted
MANUAL_OVERRIDES: Dict[int, datetime] = {}
DEVICE_OVERRIDE_MINUTES: Dict[int, int] = {}  # per-device cooldown 5-60 min
DEFAULT_OVERRIDE_MINUTES = 30  # default lock duration

# In-memory notification store (last 200)
NOTIFICATIONS: List[Dict] = []

# ── Live Weather (RapidAPI OpenWeather) ───────────────────────
RAPIDAPI_KEY = "72d9b384a2msh407fcb35f3f0838p144ddajsn4affb93e9778"
RAPIDAPI_HOST = "open-weather13.p.rapidapi.com"
WEATHER_CACHE_MINUTES = 10  # re-fetch from API every 10 min

WEATHER_CACHE: Dict = {
    "temp_c": None,
    "description": None,
    "city": None,
    "fetched_at": None,
    "latitude": None,
    "longitude": None,
}

# Active user location (updated on login/signup; default = Mardan)
CURRENT_LOCATION: Dict = {
    "latitude": 34.19251361001708,
    "longitude": 72.02845291100556,
}

# Agent state tracking
AGENT_STATUS = {
    "running": False,
    "last_cycle": None,
    "cycle_count": 0,
    "last_actions": [],  # actions from most recent cycle
    "node_log": [],  # trace of most recent cycle nodes
}

FEATURE_COLS = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "weekday",
    "is_weekend",
    "temp_c",
]
TARGET_NAMES = {1: "AC", 2: "Fan", 3: "Light", 4: "TV", 5: "Fridge"}
CONFIDENCE_THRESHOLD = 0.80

# Deep-night mode: when True, AI will NOT auto-turn ON Light/TV between 11 PM–5 AM
# Can be toggled by the user from the frontend Settings page
DEEP_NIGHT_MODE_ENABLED: bool = True

# ── Home / Away Mode ───────────────────────────────────────────
# When IS_HOME is False the AI is blocked from turning ON any of the
# AWAY_BLOCKED_DEVICES.  They are also immediately turned OFF on transition.
IS_HOME: bool = True
AWAY_BLOCKED_DEVICES: set = {
    1,
    2,
    3,
    4,
}  # AC, Fan, Light, TV  (Fridge=5 always stays ON)

# Dynamic peak hours — computed from DB usage data (top 30% busiest hours)
# Format: {hour(int): avg_on_rate(float)}   e.g. {18: 0.82, 19: 0.79, ...}
PEAK_HOURS_DATA: Dict[int, float] = {}  # populated by compute_peak_hours()
PEAK_HOURS: list = []  # list of peak hour integers for quick lookup


# ── Pydantic Models ────────────────────────────────────────────
class DeviceStatus(BaseModel):
    id: int
    name: str
    type: str
    status: bool
    last_updated: str
    energy_consumption: float


class DeviceControl(BaseModel):
    device_id: int
    action: bool
    reason: Optional[str] = None
    duration_minutes: Optional[int] = None  # 5-60 min override cooldown


class PredictionRequest(BaseModel):
    temperature: float
    humidity: float


class UserSignup(BaseModel):
    name: str
    email: str
    password: str
    latitude: float
    longitude: float


class UserLogin(BaseModel):
    email: str
    password: str


class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


class NightModeToggle(BaseModel):
    enabled: bool


class HomeStatusUpdate(BaseModel):
    is_home: bool


class CustomRule(BaseModel):
    id: Optional[int] = None
    device_id: int
    temp_min: float
    temp_max: float
    action: bool
    enabled: bool = True
    description: Optional[str] = None


class RuleList(BaseModel):
    rules: List[CustomRule]


# ── Helpers ────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def fetch_weather_sync(lat: float, lon: float):
    """Call RapidAPI OpenWeather, return (temp_c, description, city)."""
    url = f"https://{RAPIDAPI_HOST}/latlon" f"?latitude={lat}&longitude={lon}&lang=EN"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",  # required to bypass Cloudflare
            "Accept": "application/json",
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        temp_raw = float(data["main"]["temp"])
        # API returns Kelvin → convert to Celsius
        temp_c = round(temp_raw - 273.15, 2)
        desc = data.get("weather", [{}])[0].get("description", "")
        city = data.get("name", "Unknown")
        logger.info(f"[WEATHER] {city}: {temp_c}°C ({desc})")
        return temp_c, desc, city
    except Exception as e:
        logger.warning(f"[WEATHER] API error: {e}")
        return None, None, None


def get_live_temperature() -> float:
    """Return cached temp or fetch fresh from RapidAPI. Falls back to sine."""
    now = datetime.now()
    lat = CURRENT_LOCATION["latitude"]
    lon = CURRENT_LOCATION["longitude"]
    cache_ok = (
        WEATHER_CACHE["temp_c"] is not None
        and WEATHER_CACHE["fetched_at"] is not None
        and WEATHER_CACHE["latitude"] == lat
        and WEATHER_CACHE["longitude"] == lon
        and (now - WEATHER_CACHE["fetched_at"]).total_seconds()
        < WEATHER_CACHE_MINUTES * 60
    )
    if cache_ok:
        return WEATHER_CACHE["temp_c"]
    temp_c, desc, city = fetch_weather_sync(lat, lon)
    if temp_c is not None:
        WEATHER_CACHE.update(
            {
                "temp_c": temp_c,
                "description": desc,
                "city": city,
                "fetched_at": now,
                "latitude": lat,
                "longitude": lon,
            }
        )
        return temp_c
    # Fallback
    fallback = round(18 + 12 * np.sin(now.hour * np.pi / 12), 2)
    logger.warning(f"[WEATHER] Fallback sine-wave temp: {fallback}°C")
    return fallback


def compute_peak_hours():
    """Dynamically determine peak hours from 14-day historical data.
    Calculates the average ON-rate per hour across all devices.
    Hours in the top 30% of activity are marked as peak."""
    global PEAK_HOURS, PEAK_HOURS_DATA
    try:
        conn = get_db()
        c = conn.cursor()
        tbl = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='two_week_logs'"
        ).fetchone()
        if not tbl:
            conn.close()
            logger.warning(
                "[PEAK] No two_week_logs table yet — peak hours not computed"
            )
            return
        rows = c.execute("""
            SELECT CAST(substr(timestamp, 12, 2) AS INTEGER) as hr,
                   AVG(CAST(action AS REAL)) as on_rate,
                   COUNT(*) as cnt
            FROM two_week_logs
            GROUP BY hr
            HAVING cnt >= 5
            ORDER BY hr
        """).fetchall()
        conn.close()
        if not rows:
            logger.warning("[PEAK] Not enough data to compute peak hours")
            return
        hour_rates = {int(r["hr"]): float(r["on_rate"]) for r in rows}
        if not hour_rates:
            return
        # Threshold = top 30% activity level
        rates = sorted(hour_rates.values())
        cutoff_idx = int(len(rates) * 0.70)  # 70th percentile
        cutoff = rates[cutoff_idx] if cutoff_idx < len(rates) else rates[-1]
        PEAK_HOURS_DATA = hour_rates
        PEAK_HOURS = [h for h, r in hour_rates.items() if r >= cutoff]
        logger.info(
            f"[PEAK] Computed peak hours from DB: {sorted(PEAK_HOURS)} "
            f"(threshold on-rate >= {cutoff:.2f})"
        )
    except Exception as e:
        logger.error(f"[PEAK] Error computing peak hours: {e}")


def _patch_njobs(model):
    """Set n_jobs=1 everywhere to avoid joblib ast.Num crash on Python 3.14+"""
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1
    if hasattr(model, "estimators_"):
        for est in model.estimators_:
            _patch_njobs(est)
    if hasattr(model, "estimators"):  # unfitted attribute
        for est in model.estimators:
            _patch_njobs(est)


def load_rf_model():
    global RF_MODEL
    try:
        RF_MODEL = joblib.load(MODEL_PATH)
        # Patch n_jobs=1 on all estimators to bypass joblib parallel
        # dispatch (ast.Num removed in Python 3.14 breaks joblib)
        _patch_njobs(RF_MODEL)
        logger.info("[OK] RandomForest model loaded (n_jobs patched to 1)")
    except Exception as e:
        logger.warning(f"[WARN] Model not loaded: {e}")
        RF_MODEL = None


def load_device_data_from_csv():
    if not os.path.exists(CSV_PATH):
        return
    try:
        counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total = 0
        with open(CSV_PATH) as f:
            for row in csv.DictReader(f):
                total += 1
                if row.get("ac") == "1":
                    counts[1] += 1
                if row.get("fan") == "1":
                    counts[2] += 1
                if row.get("light") == "1":
                    counts[3] += 1
                if row.get("tv") == "1":
                    counts[4] += 1
                if row.get("fridge") == "1":
                    counts[5] += 1
        for did in DEVICE_STATS:
            DEVICE_STATS[did]["on_count"] = counts[did]
            DEVICE_STATS[did]["off_count"] = total - counts[did]
        logger.info(f"[OK] CSV loaded: {total} rows")
    except Exception as e:
        logger.error(f"[ERROR] CSV: {e}")


def sync_device_status_from_db():
    try:
        conn = get_db()
        c = conn.cursor()
        for did in DEVICES:
            row = c.execute(
                "SELECT action FROM two_week_logs WHERE device_id=? ORDER BY timestamp DESC LIMIT 1",
                (did,),
            ).fetchone()
            if row:
                DEVICES[did]["status"] = bool(row["action"])
        conn.close()
    except Exception as e:
        logger.warning(f"[WARN] DB sync: {e}")


def push_notification(
    device_name: str, action: bool, reason: str, confidence: float, node: str
):
    notif = {
        "id": len(NOTIFICATIONS) + 1,
        "timestamp": datetime.now().isoformat(),
        "device": device_name,
        "action": "ON" if action else "OFF",
        "reason": reason,
        "confidence": round(confidence * 100, 1),
        "node": node,
        "read": False,
    }
    NOTIFICATIONS.insert(0, notif)
    if len(NOTIFICATIONS) > 200:
        NOTIFICATIONS.pop()
    # Persist to DB
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device TEXT,
                action TEXT,
                reason TEXT,
                confidence REAL,
                node TEXT,
                read INTEGER DEFAULT 0
            )
        """)
        c.execute(
            "INSERT INTO notifications (timestamp,device,action,reason,confidence,node,read) VALUES (?,?,?,?,?,?,0)",
            (
                notif["timestamp"],
                device_name,
                notif["action"],
                reason,
                notif["confidence"],
                node,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[NOTIFY-DB] {e}")
    logger.info(
        f"[NOTIFY] {device_name} -> {notif['action']} | {reason} | conf={notif['confidence']}%"
    )


def is_manually_locked(device_id: int) -> Optional[int]:
    """Returns minutes remaining in lock, or None if not locked."""
    if device_id not in MANUAL_OVERRIDES:
        return None
    locked_at = MANUAL_OVERRIDES[device_id]
    duration = DEVICE_OVERRIDE_MINUTES.get(device_id, DEFAULT_OVERRIDE_MINUTES)
    elapsed = datetime.now() - locked_at
    remaining = duration * 60 - elapsed.total_seconds()
    if remaining > 0:
        return int(remaining // 60)
    else:
        del MANUAL_OVERRIDES[device_id]
        if device_id in DEVICE_OVERRIDE_MINUTES:
            del DEVICE_OVERRIDE_MINUTES[device_id]
        return None


def log_agent_action_to_db(
    device_id: int, action: bool, confidence: float, reason: str
):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id INTEGER,
                device_name TEXT,
                action INTEGER,
                confidence REAL,
                reason TEXT
            )
        """)
        c.execute(
            "INSERT INTO agent_logs (timestamp, device_id, device_name, action, confidence, reason) VALUES (?,?,?,?,?,?)",
            (
                datetime.now().isoformat(),
                device_id,
                TARGET_NAMES[device_id],
                int(action),
                confidence,
                reason,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[ERROR] DB log: {e}")


def get_applicable_custom_rules(device_id: int, temp: float) -> List[Dict]:
    """Get all active custom rules for a device at a given temperature."""
    try:
        conn = get_db()
        c = conn.cursor()
        rows = c.execute(
            """
            SELECT id, device_id, temp_min, temp_max, action, description
            FROM custom_rules
            WHERE device_id=? AND enabled=1 AND temp_min <= ? AND ? <= temp_max
            ORDER BY id
        """,
            (device_id, temp, temp),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def init_custom_rules_table():
    """Initialize custom_rules table on startup."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS custom_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                temp_min REAL NOT NULL,
                temp_max REAL NOT NULL,
                action INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                description TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        logger.info("[OK] Custom rules table initialized")
    except Exception as e:
        logger.warning(f"[WARN] Custom rules table: {e}")


# ══════════════════════════════════════════════════════════════
#  AGENT NODES
# ══════════════════════════════════════════════════════════════


def node1_rf_predict(now: datetime, temp: float) -> List[Dict]:
    """Node 1 — Run RF Model and get raw predictions for all devices."""
    if RF_MODEL is None:
        return []
    features = np.array(
        [
            [
                now.year,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.weekday(),
                1 if now.weekday() >= 5 else 0,
                temp,
            ]
        ]
    )
    try:
        preds = RF_MODEL.predict(features)[0]
        try:
            probas = RF_MODEL.predict_proba(features)
            confs = [max(p[0]) for p in probas]
        except Exception:
            confs = [0.9] * 5
        results = []
        for i, did in enumerate(range(1, 6)):
            results.append(
                {
                    "device_id": did,
                    "device_name": TARGET_NAMES[did],
                    "predicted": bool(preds[i]),
                    "confidence": float(confs[i]),
                }
            )
        return results
    except Exception as e:
        logger.error(f"[Node1] RF predict error: {e}")
        return []


def node2_rule_engine(
    predictions: List[Dict], now: datetime, temp: float
) -> List[Dict]:
    """Node 2 — Apply rules: confidence threshold, smart peak hours, night block, custom temp rules, state check."""
    # Deep-night hours: 11 PM (23) → 4 AM (3).  No one turns on Light/TV during sleep hours
    # unless the user has DISABLED the deep-night block from Settings.
    NIGHT_HOURS = set(range(23, 24)) | set(range(0, 4))  # 23, 0, 1, 2, 3
    NIGHT_BLOCK_DEVS = {3, 4}  # Light, TV  — AC/Fan/Fridge exempt (climate/necessity)

    approved = []
    for p in predictions:
        did = p["device_id"]
        pred = p["predicted"]
        conf = p["confidence"]
        hour = now.hour
        result = dict(p)
        result["approved"] = True
        result["rule_reason"] = "APPROVED"

        # ⭐ PRIORITY 0: Check if device already in target state (NO CHANGE NEEDED)
        # This MUST be checked first before any other rules!
        # If TV is already OFF and model predicts OFF → Don't execute, don't notify
        if DEVICES[did]["status"] == pred:
            result["approved"] = False
            result["rule_reason"] = "STATE_UNCHANGED"

        # Rule 1: Confidence must be above threshold
        elif conf < CONFIDENCE_THRESHOLD:
            result["approved"] = False
            result["rule_reason"] = (
                f"LOW_CONFIDENCE ({conf*100:.0f}% < {CONFIDENCE_THRESHOLD*100:.0f}%)"
            )

        # Rule 1.5: CHECK CUSTOM TEMPERATURE-BASED RULES (Priority: HIGH - overrides AI prediction)
        elif result["approved"]:
            custom_rules = get_applicable_custom_rules(did, temp)
            if custom_rules:
                rule = custom_rules[0]  # Take first matching rule
                rule_action = bool(rule["action"])
                if pred != rule_action:
                    # Custom rule says different action than AI predicted
                    result["predicted"] = rule_action
                    # KEY FIX: check if device is ALREADY in the rule-forced state
                    # (e.g. AC already OFF and rule says OFF → no action, no notification)
                    if DEVICES[did]["status"] == rule_action:
                        result["approved"] = False
                        result["rule_reason"] = "STATE_UNCHANGED"
                    else:
                        result["rule_reason"] = (
                            f"CUSTOM_RULE (temp={temp:.1f}C: {TARGET_NAMES[did]}->{rule_action}, desc={rule.get('description','')})"
                        )
                        logger.info(
                            f"[CUSTOM_RULE] {TARGET_NAMES[did]} (temp={temp:.1f}C): AI predicted {pred} but rule says {rule_action}"
                        )
                else:
                    # Custom rule matches prediction — still re-check STATE_UNCHANGED
                    if DEVICES[did]["status"] == result["predicted"]:
                        result["approved"] = False
                        result["rule_reason"] = "STATE_UNCHANGED"

        # Rule 2a: Don't turn ON AC during SMART peak hours (computed from DB history)
        elif did == 1 and pred is True and PEAK_HOURS and hour in PEAK_HOURS:
            on_rate = PEAK_HOURS_DATA.get(hour, 0)
            result["approved"] = False
            result["rule_reason"] = (
                f"SMART_PEAK_BLOCK (hour={hour}, avg_on_rate={on_rate:.0%})"
            )

        # Rule 2b: Night-hours block — only applied when DEEP_NIGHT_MODE_ENABLED is True
        elif (
            DEEP_NIGHT_MODE_ENABLED
            and did in NIGHT_BLOCK_DEVS
            and pred is True
            and hour in NIGHT_HOURS
        ):
            result["approved"] = False
            result["rule_reason"] = (
                f"NIGHT_BLOCK ({TARGET_NAMES[did]} OFF — sleep hours {hour:02d}:xx, "
                f"auto-on blocked 23:00-03:59)"
            )

        # Rule 3: Away mode — block AC/Fan/Light/TV from auto-turning ON
        elif not IS_HOME and did in AWAY_BLOCKED_DEVICES and pred is True:
            result["approved"] = False
            result["rule_reason"] = "AWAY_MODE (user not home — device blocked)"

        approved.append(result)
    return approved


def node3_override_check(approved_list: List[Dict]) -> List[Dict]:
    """Node 3 — Skip devices that user manually set in last 20 minutes."""
    final = []
    for item in approved_list:
        if not item["approved"]:
            final.append(item)
            continue
        did = item["device_id"]
        lock_mins = is_manually_locked(did)
        if lock_mins is not None:
            item["approved"] = False
            item["rule_reason"] = f"MANUAL_LOCK ({lock_mins}m remaining)"
        final.append(item)
    return final


def node4_execute(final_list: List[Dict]) -> List[Dict]:
    """Node 4 — Execute approved actions on devices.
    Final safety guard: skip (no action, no notification) if device is
    already in the target state, regardless of what earlier nodes decided.
    """
    actions_taken = []
    for item in final_list:
        if not item["approved"]:
            continue
        did    = item["device_id"]
        action = item["predicted"]
        conf   = item["confidence"]
        # Guard: device is already in this state — nothing to do
        if DEVICES[did]["status"] == action:
            continue
        DEVICES[did]["status"] = action
        log_agent_action_to_db(did, action, conf, item["rule_reason"])
        actions_taken.append(item)
    return actions_taken


def node5_notify(actions_taken: List[Dict]):
    """Node 5 — Push notifications for every action performed."""
    for item in actions_taken:
        push_notification(
            device_name=item["device_name"],
            action=item["predicted"],
            reason=item["rule_reason"],
            confidence=item["confidence"],
            node="Agent Auto-Control",
        )


# ══════════════════════════════════════════════════════════════
#  AGENT LOOP — runs every 60 seconds in background
# ══════════════════════════════════════════════════════════════


async def agent_loop():
    AGENT_STATUS["running"] = True
    logger.info("[AGENT] Autonomous agent loop started (180s / 3-minute interval)")
    await asyncio.sleep(10)  # Wait 10s for startup to settle

    while True:
        try:
            now = datetime.now()
            temp = await asyncio.to_thread(
                get_live_temperature
            )  # live from RapidAPI (cached 10 min)

            node_log = []

            # ── Node 1: RF Predict ─────────────────────────────
            predictions = node1_rf_predict(now, temp)
            node_log.append(
                {
                    "node": "1 - RF Model Predict",
                    "output": f"{len(predictions)} device predictions generated",
                }
            )

            # ── Node 2: Rule Engine ────────────────────────────
            rule_checked = node2_rule_engine(predictions, now, temp)
            approved_count = sum(1 for r in rule_checked if r["approved"])
            node_log.append(
                {
                    "node": "2 - Rule Engine",
                    "output": f"{approved_count}/{len(rule_checked)} passed rules",
                }
            )

            # ── Node 3: Override Check ─────────────────────────
            final_list = node3_override_check(rule_checked)
            exec_count = sum(1 for r in final_list if r["approved"])
            locked = sum(
                1 for r in final_list if "MANUAL_LOCK" in r.get("rule_reason", "")
            )
            node_log.append(
                {
                    "node": "3 - Manual Override Check",
                    "output": f"{exec_count} to execute, {locked} locked by user",
                }
            )

            # ── Node 4: Execute ────────────────────────────────
            actions = node4_execute(final_list)
            node_log.append(
                {
                    "node": "4 - Execute Actions",
                    "output": (
                        f"{len(actions)} devices changed"
                        if actions
                        else "No changes needed"
                    ),
                }
            )

            # ── Node 5: Notify ─────────────────────────────────
            node5_notify(actions)
            node_log.append(
                {
                    "node": "5 - Notify User",
                    "output": (
                        f"{len(actions)} notifications sent"
                        if actions
                        else "Nothing to notify"
                    ),
                }
            )

            # Update agent status
            AGENT_STATUS["last_cycle"] = now.isoformat()
            AGENT_STATUS["cycle_count"] += 1
            AGENT_STATUS["node_log"] = node_log
            AGENT_STATUS["last_actions"] = [
                {
                    "device": a["device_name"],
                    "action": "ON" if a["predicted"] else "OFF",
                    "confidence": round(a["confidence"] * 100, 1),
                }
                for a in actions
            ]

            if actions:
                logger.info(
                    f"[AGENT] Cycle #{AGENT_STATUS['cycle_count']}: {len(actions)} action(s) taken"
                )

        except Exception as e:
            logger.error(f"[AGENT] Loop error: {e}")

        await asyncio.sleep(180)  # wait 3 minutes (180s) before next cycle


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════


@app.get("/")
async def root():
    return {
        "message": "AI Home Automation API v4.0 — Autonomous Agent Active",
        "agent_running": AGENT_STATUS["running"],
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": RF_MODEL is not None,
        "agent_running": AGENT_STATUS["running"],
    }


# ── Devices ────────────────────────────────────────────────────


@app.get("/api/devices/status", response_model=List[DeviceStatus])
async def get_devices_status():
    return [
        DeviceStatus(
            id=did,
            name=d["name"],
            type=d["type"],
            status=d["status"],
            last_updated=datetime.now().isoformat(),
            energy_consumption=d["energy"],
        )
        for did, d in DEVICES.items()
    ]


@app.get("/api/devices/{device_id}")
async def get_device(device_id: int):
    if device_id not in DEVICES:
        raise HTTPException(404, "Device not found")
    d = DEVICES[device_id]
    s = DEVICE_STATS.get(device_id, {})
    lock_mins = is_manually_locked(device_id)
    return {
        "device_id": device_id,
        "device_name": d["name"],
        "type": d["type"],
        "status": d["status"],
        "on_count": s.get("on_count", 0),
        "off_count": s.get("off_count", 0),
        "avg_accuracy": s.get("accuracy", 0.90),
        "manually_locked": lock_mins is not None,
        "lock_minutes_remaining": lock_mins,
    }


@app.post("/api/device/control")
async def control_device(control: DeviceControl):
    if control.device_id not in DEVICES:
        raise HTTPException(404, "Device not found")

    # Determine override duration (5-60 min, default 30)
    duration = (
        control.duration_minutes
        if control.duration_minutes
        else DEFAULT_OVERRIDE_MINUTES
    )
    duration = max(5, min(60, int(duration)))
    DEVICE_OVERRIDE_MINUTES[control.device_id] = duration
    MANUAL_OVERRIDES[control.device_id] = datetime.now()
    DEVICES[control.device_id]["status"] = control.action
    action_text = "ON" if control.action else "OFF"

    push_notification(
        device_name=DEVICES[control.device_id]["name"],
        action=control.action,
        reason=f"MANUAL by user — AI locked for {duration}m",
        confidence=1.0,
        node="User Manual Control",
    )
    logger.info(
        f"[MANUAL] {DEVICES[control.device_id]['name']} -> {action_text} | locked for {duration}m"
    )

    return {
        "success": True,
        "device_id": control.device_id,
        "device_name": DEVICES[control.device_id]["name"],
        "action": action_text,
        "timestamp": datetime.now().isoformat(),
        "ai_locked_minutes": duration,
    }


class OverrideDuration(BaseModel):
    device_id: int
    minutes: int  # 5-60


@app.post("/api/device/override-duration")
async def set_override_duration(req: OverrideDuration):
    """Update the AI-lock duration for a device that is already manually overridden."""
    if req.device_id not in DEVICES:
        raise HTTPException(404, "Device not found")
    minutes = max(5, min(60, req.minutes))
    DEVICE_OVERRIDE_MINUTES[req.device_id] = minutes
    # Reset the lock start time so countdown restarts from now
    if req.device_id in MANUAL_OVERRIDES:
        MANUAL_OVERRIDES[req.device_id] = datetime.now()
    remaining = is_manually_locked(req.device_id)
    return {
        "success": True,
        "device_id": req.device_id,
        "device_name": DEVICES[req.device_id]["name"],
        "override_minutes": minutes,
        "minutes_remaining": remaining,
    }


# ── Analytics ──────────────────────────────────────────────────


@app.get("/api/analytics")
async def get_analytics():
    analytics = []
    total_energy = 0.0
    for did, d in DEVICES.items():
        s = DEVICE_STATS.get(did, {})
        on = s.get("on_count", 0)
        energy = d["energy"] * (on / 100) if on > 0 else 0
        total_energy += energy
        analytics.append(
            {
                "device_id": did,
                "device_name": d["name"],
                "type": d["type"],
                "total_actions": on + s.get("off_count", 0),
                "on_count": on,
                "off_count": s.get("off_count", 0),
                "avg_accuracy": s.get("accuracy", 0.90),
                "energy_total": energy,
            }
        )
    return {
        "timestamp": datetime.now().isoformat(),
        "total_devices": len(analytics),
        "total_energy_consumed": total_energy,
        "devices": analytics,
    }


# ── NEW: Agent Status ──────────────────────────────────────────


@app.get("/api/agent/status")
async def get_agent_status():
    """Live agent status — current cycle, node trace, last actions."""
    overrides = {}
    for did, locked_at in list(MANUAL_OVERRIDES.items()):
        duration = DEVICE_OVERRIDE_MINUTES.get(did, DEFAULT_OVERRIDE_MINUTES)
        remaining = duration * 60 - (datetime.now() - locked_at).total_seconds()
        if remaining > 0:
            overrides[did] = {
                "device": TARGET_NAMES[did],
                "minutes_remaining": int(remaining // 60),
            }
    return {
        "agent_running": AGENT_STATUS["running"],
        "cycle_count": AGENT_STATUS["cycle_count"],
        "last_cycle": AGENT_STATUS["last_cycle"],
        "node_trace": AGENT_STATUS["node_log"],
        "last_actions": AGENT_STATUS["last_actions"],
        "manual_locks": overrides,
        "interval_seconds": 180,
    }


# ── NEW: Notifications ─────────────────────────────────────────


@app.get("/api/notifications")
async def get_notifications(limit: int = 50):
    return {"total": len(NOTIFICATIONS), "notifications": NOTIFICATIONS[:limit]}


@app.get("/api/notifications/24h")
async def get_notifications_24h():
    """Return notifications from DB for the last 24 hours."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, device TEXT, action TEXT,
                reason TEXT, confidence REAL, node TEXT, read INTEGER DEFAULT 0
            )
        """)
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        rows = c.execute(
            "SELECT * FROM notifications WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,),
        ).fetchall()
        conn.close()
        return {"total": len(rows), "notifications": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/notifications/read-all")
async def mark_all_read():
    for n in NOTIFICATIONS:
        n["read"] = True
    try:
        conn = get_db()
        conn.execute("UPDATE notifications SET read=1")
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"success": True}


@app.get("/api/notifications/unread-count")
async def unread_count():
    return {"count": sum(1 for n in NOTIFICATIONS if not n["read"])}


# ── Current Prediction ─────────────────────────────────────────


@app.get("/api/current-prediction")
async def current_prediction():
    now = datetime.now()
    # Use live weather temperature (cached from RapidAPI); fallback to sine-wave only if unavailable
    live_temp = WEATHER_CACHE.get("temp_c")
    temp = (
        live_temp
        if live_temp is not None
        else round(18 + 12 * np.sin(now.hour * np.pi / 12), 2)
    )
    temp_source = "RapidAPI Live" if live_temp is not None else "Fallback (sine-wave)"

    if RF_MODEL is None:
        return {"error": "Model not loaded"}
    features = np.array(
        [
            [
                now.year,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.weekday(),
                1 if now.weekday() >= 5 else 0,
                temp,
            ]
        ]
    )
    preds = RF_MODEL.predict(features)[0]
    try:
        probas = RF_MODEL.predict_proba(features)
        confs = [max(p[0]) for p in probas]
    except Exception:
        confs = [0.9] * 5

    result = []
    for i, did in enumerate(range(1, 6)):
        lock_mins = is_manually_locked(did)
        result.append(
            {
                "device_id": did,
                "device_name": TARGET_NAMES[did],
                "predicted_action": bool(preds[i]),
                "confidence": round(float(confs[i]), 4),
                "manually_locked": lock_mins is not None,
                "lock_minutes_remaining": lock_mins,
            }
        )
    return {
        "timestamp": now.isoformat(),
        "hour": now.hour,
        "temperature": round(temp, 2),
        "temp_source": temp_source,
        "weather_city": WEATHER_CACHE.get("city"),
        "weather_desc": WEATHER_CACHE.get("description"),
        "model": "RandomForest",
        "peak_hours": sorted(PEAK_HOURS),
        "predictions": result,
    }


# ── History ────────────────────────────────────────────────────


@app.get("/api/history")
async def get_history(device_id: Optional[int] = None, days: int = 14):
    try:
        conn = get_db()
        c = conn.cursor()
        tbl = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='two_week_logs'"
        ).fetchone()
        if not tbl:
            conn.close()
            return {"data": [], "summary": {}}
        if device_id:
            rows = c.execute(
                "SELECT * FROM two_week_logs WHERE device_id=? ORDER BY timestamp DESC LIMIT ?",
                (device_id, days * 48),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM two_week_logs ORDER BY timestamp DESC LIMIT ?",
                (days * 48 * 5,),
            ).fetchall()
        data = [dict(r) for r in rows]
        conn.close()
        summary = {}
        for row in data:
            did = row["device_id"]
            if did not in summary:
                summary[did] = {
                    "device_id": did,
                    "device_name": row["device_name"],
                    "total_on": 0,
                    "total_off": 0,
                    "total_energy_wh": 0.0,
                }
            if row["action"]:
                summary[did]["total_on"] += 1
            else:
                summary[did]["total_off"] += 1
            summary[did]["total_energy_wh"] += row["energy_wh"]
        for did in summary:
            t = summary[did]["total_on"] + summary[did]["total_off"]
            summary[did]["on_percentage"] = (
                round(summary[did]["total_on"] / t * 100, 1) if t else 0
            )
        return {
            "total_records": len(data),
            "data": data,
            "summary": list(summary.values()),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/history/daily")
async def get_daily():
    try:
        conn = get_db()
        c = conn.cursor()
        tbl = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='two_week_logs'"
        ).fetchone()
        if not tbl:
            conn.close()
            return {"daily": []}
        rows = c.execute("""
            SELECT substr(timestamp,1,10) as day, device_id, device_name,
                   SUM(action) as on_count, COUNT(*) as total, SUM(energy_wh) as energy_wh
            FROM two_week_logs GROUP BY day, device_id ORDER BY day, device_id
        """).fetchall()
        conn.close()
        return {"daily": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── System Status ──────────────────────────────────────────────


@app.get("/api/system/status")
async def system_status():
    online = sum(1 for d in DEVICES.values() if d["status"])
    acc = sum(s.get("accuracy", 0.9) for s in DEVICE_STATS.values()) / len(DEVICE_STATS)
    db_rec = 0
    try:
        conn = get_db()
        db_rec = conn.execute("SELECT COUNT(*) FROM two_week_logs").fetchone()[0]
        conn.close()
    except Exception:
        pass
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "devices": {
            "total": len(DEVICES),
            "online": online,
            "offline": len(DEVICES) - online,
        },
        "model": {
            "type": "RandomForest",
            "loaded": RF_MODEL is not None,
            "accuracy": round(acc, 4),
            "trend": "improving",
        },
        "agent": {
            "running": AGENT_STATUS["running"],
            "cycles": AGENT_STATUS["cycle_count"],
            "last_cycle": AGENT_STATUS["last_cycle"],
        },
        "energy": {
            "total_consumed": round(
                sum(d["energy"] * 0.5 for d in DEVICES.values()), 2
            ),
            "unit": "kWh",
        },
        "database": {"type": "SQLite", "records": db_rec},
        "weather": {
            "temp_c": WEATHER_CACHE.get("temp_c"),
            "description": WEATHER_CACHE.get("description"),
            "city": WEATHER_CACHE.get("city"),
            "source": "RapidAPI OpenWeather",
        },
    }


# ── Auth ───────────────────────────────────────────────────────


@app.post("/api/auth/signup")
async def signup(user: UserSignup):
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO users (name,email,password_hash,latitude,longitude,created_at) VALUES (?,?,?,?,?,?)",
            (
                user.name,
                user.email,
                hash_password(user.password),
                user.latitude,
                user.longitude,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id,name,email,latitude,longitude,created_at FROM users WHERE email=?",
            (user.email,),
        ).fetchone()
        conn.close()
        # Activate this user's location
        CURRENT_LOCATION["latitude"] = user.latitude
        CURRENT_LOCATION["longitude"] = user.longitude
        WEATHER_CACHE["fetched_at"] = None  # invalidate cache
        logger.info(
            f"[SIGNUP] {user.name} registered. Location: ({user.latitude}, {user.longitude})"
        )
        return {"success": True, "user": dict(row)}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Email already registered")
        raise HTTPException(500, str(e))


@app.post("/api/auth/login")
async def login(creds: UserLogin):
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        row = conn.execute(
            "SELECT id,name,email,latitude,longitude,created_at FROM users WHERE email=? AND password_hash=?",
            (creds.email, hash_password(creds.password)),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(401, "Invalid email or password")
        user = dict(row)
        CURRENT_LOCATION["latitude"] = user["latitude"]
        CURRENT_LOCATION["longitude"] = user["longitude"]
        WEATHER_CACHE["fetched_at"] = None  # force fresh fetch for new location
        logger.info(
            f"[LOGIN] {user['name']} | Location: ({user['latitude']}, {user['longitude']})"
        )
        return {"success": True, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/user/location")
async def update_location(loc: LocationUpdate):
    """Update the active user location and invalidate weather cache."""
    CURRENT_LOCATION["latitude"] = loc.latitude
    CURRENT_LOCATION["longitude"] = loc.longitude
    WEATHER_CACHE["fetched_at"] = None
    logger.info(f"[LOCATION] Updated to ({loc.latitude}, {loc.longitude})")
    return {"success": True, "latitude": loc.latitude, "longitude": loc.longitude}


@app.get("/api/weather/current")
async def get_current_weather():
    """Return live temperature for the active user's location."""
    temp = await asyncio.to_thread(get_live_temperature)
    return {
        "temp_c": temp,
        "description": WEATHER_CACHE.get("description"),
        "city": WEATHER_CACHE.get("city"),
        "latitude": CURRENT_LOCATION["latitude"],
        "longitude": CURRENT_LOCATION["longitude"],
        "fetched_at": (
            WEATHER_CACHE["fetched_at"].isoformat()
            if WEATHER_CACHE.get("fetched_at")
            else None
        ),
        "source": "RapidAPI OpenWeather",
    }


# ── Settings: Deep-Night Mode ─────────────────────────────────


@app.get("/api/settings/night-mode")
async def get_night_mode():
    """Return the current deep-night mode state."""
    return {
        "enabled": DEEP_NIGHT_MODE_ENABLED,
        "description": "When enabled, AI will NOT auto-turn ON Light/TV between 23:00 and 05:59",
    }


@app.post("/api/settings/night-mode")
async def set_night_mode(body: NightModeToggle):
    """Enable or disable the deep-night block rule from the frontend."""
    global DEEP_NIGHT_MODE_ENABLED
    DEEP_NIGHT_MODE_ENABLED = body.enabled
    state = "ENABLED" if body.enabled else "DISABLED"
    logger.info(f"[SETTINGS] Deep-night mode {state} by user")
    return {
        "success": True,
        "enabled": DEEP_NIGHT_MODE_ENABLED,
        "message": f"Deep-night block is now {state}",
    }


# ── Home / Away Mode ──────────────────────────────────────────


@app.get("/api/home/status")
async def get_home_status():
    """Return whether the user is currently home or away."""
    return {
        "is_home": IS_HOME,
        "status_label": "Home" if IS_HOME else "Away",
        "away_blocked_devices": sorted(AWAY_BLOCKED_DEVICES),
    }


@app.post("/api/home/status")
async def set_home_status(body: HomeStatusUpdate):
    """Toggle Home/Away mode.
    Away  → AC, Fan, Light, TV immediately turned OFF; AI cannot turn them back on.
    Home  → Normal AI control restored for all devices.
    """
    global IS_HOME
    IS_HOME = body.is_home

    if not IS_HOME:
        # Immediately shut off all away-blocked devices
        for did in AWAY_BLOCKED_DEVICES:
            if DEVICES[did]["status"]:  # only act if currently ON
                DEVICES[did]["status"] = False
                # Clear any manual lock so away-mode takes immediate effect
                MANUAL_OVERRIDES.pop(did, None)
                DEVICE_OVERRIDE_MINUTES.pop(did, None)
                push_notification(
                    device_name=DEVICES[did]["name"],
                    action=False,
                    reason="AWAY_MODE — user left home, auto-shutdown",
                    confidence=1.0,
                    node="Away Mode",
                )
        logger.info("[HOME] User set AWAY — AC / Fan / Light / TV turned OFF")
    else:
        push_notification(
            device_name="System",
            action=True,
            reason="HOME_MODE — user returned home, AI control restored",
            confidence=1.0,
            node="Home Mode",
        )
        logger.info("[HOME] User returned HOME — normal AI control restored")

    return {
        "success": True,
        "is_home": IS_HOME,
        "status_label": "Home" if IS_HOME else "Away",
    }


# ── Custom Rules Management ────────────────────────────────────


@app.get("/api/rules", response_model=RuleList)
async def get_rules():
    """Get all active custom rules."""
    try:
        conn = get_db()
        c = conn.cursor()
        rows = c.execute("""
            SELECT id, device_id, temp_min, temp_max, action, enabled, description
            FROM custom_rules ORDER BY device_id, temp_min
        """).fetchall()
        conn.close()
        rules = [
            {
                "id": r["id"],
                "device_id": r["device_id"],
                "temp_min": r["temp_min"],
                "temp_max": r["temp_max"],
                "action": bool(r["action"]),
                "enabled": bool(r["enabled"]),
                "description": r["description"],
            }
            for r in rows
        ]
        return {"rules": rules}
    except Exception as e:
        logger.error(f"[RULES] Get error: {e}")
        return {"rules": []}


@app.post("/api/rules")
async def create_rule(rule: CustomRule):
    """Create a new temperature-based rule.
    Example: At temp 30-40°C, turn Fan ON but ensure AC stays OFF.
    """
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO custom_rules (device_id, temp_min, temp_max, action, enabled, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                rule.device_id,
                rule.temp_min,
                rule.temp_max,
                int(rule.action),
                1,
                rule.description,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        logger.info(
            f"[RULES] Created rule #{new_id}: {TARGET_NAMES[rule.device_id]} -> {rule.action} at {rule.temp_min}-{rule.temp_max}C"
        )
        return {"success": True, "id": new_id, "message": "Rule created"}
    except Exception as e:
        logger.error(f"[RULES] Create error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/rules/{rule_id}")
async def update_rule(rule_id: int, rule: CustomRule):
    """Update an existing rule."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """
            UPDATE custom_rules
            SET device_id=?, temp_min=?, temp_max=?, action=?, enabled=?, description=?
            WHERE id=?
        """,
            (
                rule.device_id,
                rule.temp_min,
                rule.temp_max,
                int(rule.action),
                int(rule.enabled),
                rule.description,
                rule_id,
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"[RULES] Updated rule #{rule_id}")
        return {"success": True, "message": "Rule updated"}
    except Exception as e:
        logger.error(f"[RULES] Update error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: int):
    """Delete a rule."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM custom_rules WHERE id=?", (rule_id,))
        conn.commit()
        conn.close()
        logger.info(f"[RULES] Deleted rule #{rule_id}")
        return {"success": True, "message": "Rule deleted"}
    except Exception as e:
        logger.error(f"[RULES] Delete error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ── Startup ────────────────────────────────────────────────────


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 55)
    logger.info("  AI Home Automation v4.0 — Autonomous Agent")
    logger.info("=" * 55)
    load_rf_model()
    load_device_data_from_csv()
    sync_device_status_from_db()
    compute_peak_hours()  # smart peak hours from DB history
    # Pre-create notifications table and load recent into memory
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, device TEXT, action TEXT,
                reason TEXT, confidence REAL, node TEXT, read INTEGER DEFAULT 0
            )
        """)
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        rows = c.execute(
            "SELECT * FROM notifications WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 200",
            (since,),
        ).fetchall()
        for r in rows:
            NOTIFICATIONS.append(
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "device": r["device"],
                    "action": r["action"],
                    "reason": r["reason"],
                    "confidence": r["confidence"],
                    "node": r["node"],
                    "read": bool(r["read"]),
                }
            )
        conn.commit()
        conn.close()
        logger.info(f"[OK] Loaded {len(NOTIFICATIONS)} recent notifications from DB")
    except Exception as e:
        logger.warning(f"[WARN] Notifications table: {e}")
    # Init users table
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        # Load last logged-in user's location
        last = conn.execute(
            "SELECT latitude, longitude, name FROM users ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if last:
            CURRENT_LOCATION["latitude"] = last["latitude"]
            CURRENT_LOCATION["longitude"] = last["longitude"]
            logger.info(
                f"[OK] Restored location for {last['name']}: ({last['latitude']}, {last['longitude']})"
            )
        conn.close()
    except Exception as e:
        logger.warning(f"[WARN] Users table: {e}")
    # Init custom rules table
    init_custom_rules_table()

    # Prefetch weather in background (non-blocking)
    async def prefetch_weather():
        try:
            await asyncio.to_thread(get_live_temperature)
            logger.info(
                f"[OK] Weather pre-fetched: {WEATHER_CACHE.get('temp_c')}°C in {WEATHER_CACHE.get('city')}"
            )
        except Exception as e:
            logger.warning(f"[WARN] Weather pre-fetch skipped: {e}")

    asyncio.create_task(prefetch_weather())
    # Start autonomous agent loop as background task
    asyncio.create_task(agent_loop())
    logger.info("[OK] Autonomous agent started (3-min cycle)")
    logger.info("[OK] API ready at http://localhost:8000")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
