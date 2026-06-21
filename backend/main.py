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

# ── Load .env variables ────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# ── Voice Command Processing ───────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from services.voice_processor import VoiceCommandProcessor
    VOICE_PROCESSOR = VoiceCommandProcessor()
    logger_placeholder = logging.getLogger(__name__)
    logger_placeholder.info("[OK] Local VoiceCommandProcessor imported")
except Exception as e:
    VOICE_PROCESSOR = None
    logger_placeholder = logging.getLogger(__name__)
    logger_placeholder.warning(f"[WARN] Could not load VoiceCommandProcessor: {e}")

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
    1: {"name": "AC", "type": "Air Conditioner", "status": False, "energy": 1200},
    2: {"name": "Fan", "type": "Cooling Device", "status": True, "energy": 30},
    3: {"name": "Light", "type": "Lighting", "status": True, "energy": 20},
    4: {"name": "TV", "type": "Entertainment", "status": False, "energy": 250},
    5: {"name": "Fridge", "type": "Refrigerator", "status": True, "energy": 400},
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
    "sunrise_unix": None,   # UTC unix timestamp from OpenWeather sys.sunrise
    "sunset_unix": None,    # UTC unix timestamp from OpenWeather sys.sunset
    "timezone_offset": 0,   # seconds offset from UTC (OpenWeather 'timezone' field)
    "sunrise_hour": None,   # Local hour (0-23) when sunrise occurs
    "sunset_hour": None,    # Local hour (0-23) when sunset occurs
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
    """Call RapidAPI OpenWeather, return (temp_c, description, city).
    Also caches sunrise, sunset, and timezone offset from the API response."""
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
        # Parse sunrise / sunset (UTC unix) + timezone offset (seconds)
        sys_block = data.get("sys", {})
        sunrise_unix  = sys_block.get("sunrise")   # int UTC epoch
        sunset_unix   = sys_block.get("sunset")    # int UTC epoch
        tz_offset     = data.get("timezone", 0)    # seconds east of UTC
        WEATHER_CACHE["sunrise_unix"]   = sunrise_unix
        WEATHER_CACHE["sunset_unix"]    = sunset_unix
        WEATHER_CACHE["timezone_offset"] = tz_offset
        logger.info(
            f"[WEATHER] {city}: {temp_c}\u00b0C ({desc}) | "
            f"tz_offset={tz_offset//3600:+d}h | sunrise/sunset cached"
        )
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
    predictions: List[Dict], now: datetime, temp: float, sunrise_hour: int = None, sunset_hour: int = None
) -> List[Dict]:
    """Node 2 — Apply rules: confidence threshold, smart peak hours, daylight block, night block, custom temp rules, state check."""
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

        # Rule 2c: Daylight hours block (Light) - don't turn on Light between sunrise and sunset
        elif (
            did == 3  # Light device
            and pred is True
            and sunrise_hour is not None
            and sunset_hour is not None
            and sunrise_hour <= hour < sunset_hour
        ):
            result["approved"] = False
            result["rule_reason"] = (
                f"DAYLIGHT_BLOCK (Light OFF — natural daylight available, "
                f"sunrise={sunrise_hour:02d}:00, sunset={sunset_hour:02d}:00)"
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
            sunrise_hour = WEATHER_CACHE.get("sunrise_hour")
            sunset_hour = WEATHER_CACHE.get("sunset_hour")
            rule_checked = node2_rule_engine(predictions, now, temp, sunrise_hour, sunset_hour)
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

    conn = get_db()
    c = conn.cursor()
    db_stats = {}
    try:
        rows = c.execute("""
            SELECT device_name,
                   COUNT(*) as total_actions,
                   AVG(confidence) as avg_confidence,
                   SUM(CAST(energy_used AS REAL)) as total_wh
            FROM device_logs
            GROUP BY device_name
        """).fetchall()
        for r in rows:
            name = r["device_name"]
            key_name = "Fridge" if name == "Refrigerator" else name
            db_stats[key_name] = {
                "total_actions": r["total_actions"],
                "avg_accuracy": r["avg_confidence"] or 0.90,
                "energy_total": (r["total_wh"] or 0.0) / 1000.0
            }
    except Exception as e:
        logger.error(f"Error in analytics db query: {e}")
    finally:
        conn.close()

    for did, d in DEVICES.items():
        name = d["name"]
        db_s = db_stats.get(name, {})
        s = DEVICE_STATS.get(did, {})
        on_count = s.get("on_count", 0)

        total_actions = db_s.get("total_actions", on_count + s.get("off_count", 0))
        avg_accuracy = db_s.get("avg_accuracy", s.get("accuracy", 0.90))
        energy = db_s.get("energy_total", (d["energy"] * on_count) / 1000.0)

        total_energy += energy
        analytics.append(
            {
                "device_id": did,
                "device_name": name,
                "type": d["type"],
                "total_actions": total_actions,
                "avg_accuracy": avg_accuracy,
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
                "SELECT * FROM two_week_logs ORDER BY timestamp DESC"
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
    """Return live temperature + sunrise/sunset for the active user's location."""
    temp = await asyncio.to_thread(get_live_temperature)

    # Build human-readable sunrise/sunset in location-local time (12-hour format with AM/PM)
    sunrise_str = sunset_str = None
    sunrise_unix = WEATHER_CACHE.get("sunrise_unix")
    sunset_unix  = WEATHER_CACHE.get("sunset_unix")
    tz_offset    = WEATHER_CACHE.get("timezone_offset", 0) or 0
    if sunrise_unix:
        import datetime as _dt
        sunrise_local = _dt.datetime.utcfromtimestamp(sunrise_unix + tz_offset)
        sunset_local  = _dt.datetime.utcfromtimestamp(sunset_unix  + tz_offset)
        sunrise_str   = sunrise_local.strftime("%I:%M %p")  # 12-hour format with AM/PM
        sunset_str    = sunset_local.strftime("%I:%M %p")   # 12-hour format with AM/PM
        # Cache sunrise/sunset hours for agent rule engine
        WEATHER_CACHE["sunrise_hour"] = sunrise_local.hour
        WEATHER_CACHE["sunset_hour"]  = sunset_local.hour

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
        # Sunrise / Sunset — dynamic, from live API, local time of the location
        "sunrise": sunrise_str,           # e.g. "05:12"
        "sunset": sunset_str,             # e.g. "19:47"
        "sunrise_unix": sunrise_unix,
        "sunset_unix": sunset_unix,
        "timezone_offset_sec": tz_offset,
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



# ── Voice Command (Gemini AI NLP) ─────────────────────────────
# ── Quota-Safe Design:
#    1. LOCAL-FIRST: well-known commands resolved without any API call (saves 80%+ tokens)
#    2. RESPONSE CACHE: identical commands re-use last Gemini response (no duplicate calls)
#    3. RATE LIMITER: max 20 Gemini calls / 60 s sliding window
#    4. GRACEFUL FALLBACK: on 429/quota, local VoiceCommandProcessor takes over seamlessly

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
)

VOICE_SYSTEM_PROMPT = """You are an intelligent Smart Home AI Assistant.

Your job is to understand natural language voice commands and convert them into structured device control actions.

Supported Devices: AC, Fan, Light, Refrigerator, TV

Rules:
1. Understand different ways users may speak the same command.
2. Detect the target device and intended action.
3. Return ONLY valid JSON — no extra text, no markdown, no explanation.
4. Action can be ON, OFF, STATUS, or UNKNOWN.
5. If the command is unclear, return {"device":"UNKNOWN","action":"UNKNOWN"}.
6. Ignore spelling mistakes and speech recognition errors.
7. Understand conversational language and context (e.g. "it's hot" → AC ON).
8. Support English commands only.

Examples:
User: Turn on the fan → {"device":"Fan","action":"ON"}
User: It's too hot in here → {"device":"AC","action":"ON"}
User: Switch off the television → {"device":"TV","action":"OFF"}
User: Can you make the room brighter? → {"device":"Light","action":"ON"}
User: Is the refrigerator running? → {"device":"Refrigerator","action":"STATUS"}
User: Turn everything off → {"device":"ALL","action":"OFF"}
User: What's currently on? → {"device":"ALL","action":"STATUS"}

Return ONLY valid JSON."""

DEVICE_NAME_MAP = {
    "ac": 1, "air conditioner": 1,
    "fan": 2,
    "light": 3, "lights": 3,
    "tv": 4, "television": 4,
    "refrigerator": 5, "fridge": 5,
}

# ── Quota management state ─────────────────────────────────────
import re as _re
import time as _time
from collections import deque as _deque

# LRU response cache: normalised-text → {"device":…,"action":…}
_VOICE_CACHE: Dict[str, dict] = {}
_VOICE_CACHE_MAX = 200          # keep up to 200 entries

# Rate-limiter: sliding window — timestamps of recent Gemini calls
_GEMINI_CALL_TIMES: "_deque[float]" = _deque()
_GEMINI_RATE_LIMIT   = 20       # max calls per window
_GEMINI_RATE_WINDOW  = 60.0     # seconds (1 minute)

# Track whether Gemini is in "quota cooldown" mode (after a 429)
_GEMINI_QUOTA_COOLDOWN_UNTIL: float = 0.0   # epoch time
_GEMINI_COOLDOWN_SECONDS    = 60            # back-off for 60 s after a 429

# ── Keyword-based LOCAL matcher ────────────────────────────────
# Handles the vast majority of clear, everyday commands locally
# so Gemini is only called for truly ambiguous / contextual speech.

_LOCAL_DEVICE_PATTERNS: List[tuple] = [
    # (regex, device_key)
    (_re.compile(r"\b(air\s*condition\w*|ac|aircon)\b", _re.I), "AC"),
    (_re.compile(r"\b(fan|ceiling\s*fan|blower)\b",           _re.I), "Fan"),
    (_re.compile(r"\b(light|lights?|lamp|bulb|illuminat\w*)\b", _re.I), "Light"),
    (_re.compile(r"\b(tv|television|telly|screen)\b",         _re.I), "TV"),
    (_re.compile(r"\b(fridge|refrigerat\w*|cooler)\b",        _re.I), "Refrigerator"),
    (_re.compile(r"\b(every(thing|one|body)|all\s*device|all\s*light)\b", _re.I), "ALL"),
]

_LOCAL_ON_PATTERNS = _re.compile(
    r"\b(turn\s+on|switch\s+on|power\s+on|start|enable|activate|open|on)\b", _re.I
)
_LOCAL_OFF_PATTERNS = _re.compile(
    r"\b(turn\s+off|switch\s+off|power\s+off|stop|disable|deactivate|shut|off)\b", _re.I
)
_LOCAL_STATUS_PATTERNS = _re.compile(
    r"\b(status|is\s+(on|off|running)|currently|check|tell\s+me|what.*(on|running|active))\b", _re.I
)


def _local_parse(text: str) -> Optional[dict]:
    """
    Fast keyword matcher — returns {device, action} for clear commands.
    Returns None if the command needs contextual AI understanding.
    """
    t = text.lower().strip()

    device = None
    for pattern, dev in _LOCAL_DEVICE_PATTERNS:
        if pattern.search(t):
            device = dev
            break

    if device is None:
        return None   # can't resolve device locally → send to Gemini

    # Determine action
    if _LOCAL_OFF_PATTERNS.search(t):
        action = "OFF"
    elif _LOCAL_STATUS_PATTERNS.search(t):
        action = "STATUS"
    elif _LOCAL_ON_PATTERNS.search(t):
        action = "ON"
    else:
        return None   # ambiguous action → send to Gemini

    return {"device": device, "action": action}


def _rate_limit_ok() -> bool:
    """Return True if we are within the allowed call rate."""
    now = _time.time()
    # Evict timestamps older than the window
    while _GEMINI_CALL_TIMES and now - _GEMINI_CALL_TIMES[0] > _GEMINI_RATE_WINDOW:
        _GEMINI_CALL_TIMES.popleft()
    return len(_GEMINI_CALL_TIMES) < _GEMINI_RATE_LIMIT


def _record_gemini_call():
    _GEMINI_CALL_TIMES.append(_time.time())


def _local_fallback(text: str) -> dict:
    """Use local VoiceCommandProcessor as last-resort fallback."""
    if VOICE_PROCESSOR:
        r = VOICE_PROCESSOR.process_command(text)
        return {
            "device": r.get("device", "UNKNOWN"),
            "action": r.get("action", "UNKNOWN"),
        }
    return {"device": "UNKNOWN", "action": "UNKNOWN"}


def _call_gemini_api(user_text: str) -> dict:
    """Raw Gemini API call. Raises urllib.error.HTTPError on failure."""
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": VOICE_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 64},
    }).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw[: raw.rfind("```")]
    return json.loads(raw.strip())


def smart_parse_command(user_text: str) -> tuple:
    """
    Quota-safe command parser.

    Priority chain:
      1. Response cache   → free, instant
      2. Local matcher    → free, handles clear commands
      3. Rate limiter     → skips Gemini if already at 20 req/min
      4. Quota cooldown   → skips Gemini for 60 s after a 429
      5. Gemini API       → only for truly ambiguous speech
      6. Local fallback   → always works even if Gemini is down

    Returns (result_dict, source_label).
    """
    global _GEMINI_QUOTA_COOLDOWN_UNTIL

    # ── 1. Normalise for cache key ──────────────────────────────
    cache_key = " ".join(user_text.lower().split())

    if cache_key in _VOICE_CACHE:
        logger.info(f"[VOICE] Cache hit: '{cache_key}'")
        return _VOICE_CACHE[cache_key], "cache"

    # ── 2. Local keyword matcher ────────────────────────────────
    local_result = _local_parse(user_text)
    if local_result:
        logger.info(
            f"[VOICE] Local match: device={local_result['device']}, action={local_result['action']}"
        )
        # Store in cache so repeat commands stay free
        if len(_VOICE_CACHE) >= _VOICE_CACHE_MAX:
            _VOICE_CACHE.pop(next(iter(_VOICE_CACHE)))
        _VOICE_CACHE[cache_key] = local_result
        return local_result, "local"

    # ── 3. Rate-limiter check ───────────────────────────────────
    if not _rate_limit_ok():
        logger.warning(
            f"[VOICE] Rate limit reached ({_GEMINI_RATE_LIMIT} calls/{_GEMINI_RATE_WINDOW}s) "
            "— using local fallback"
        )
        result = _local_fallback(user_text)
        return result, "local_rate_limited"

    # ── 4. Quota cooldown check ─────────────────────────────────
    now = _time.time()
    if now < _GEMINI_QUOTA_COOLDOWN_UNTIL:
        remaining = int(_GEMINI_QUOTA_COOLDOWN_UNTIL - now)
        logger.warning(f"[VOICE] Gemini quota cooldown — {remaining}s left — using local fallback")
        result = _local_fallback(user_text)
        return result, "local_quota_cooldown"

    # ── 5. Call Gemini ──────────────────────────────────────────
    try:
        _record_gemini_call()
        result = _call_gemini_api(user_text)
        logger.info(
            f"[VOICE] Gemini: device={result.get('device')}, action={result.get('action')} "
            f"| calls this minute: {len(_GEMINI_CALL_TIMES)}/{_GEMINI_RATE_LIMIT}"
        )
        # Cache the Gemini response
        if len(_VOICE_CACHE) >= _VOICE_CACHE_MAX:
            _VOICE_CACHE.pop(next(iter(_VOICE_CACHE)))
        _VOICE_CACHE[cache_key] = result
        return result, "gemini"

    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Quota exhausted — enter cooldown and use local processor
            _GEMINI_QUOTA_COOLDOWN_UNTIL = _time.time() + _GEMINI_COOLDOWN_SECONDS
            logger.warning(
                f"[VOICE] Gemini 429 quota exceeded — local fallback active for "
                f"{_GEMINI_COOLDOWN_SECONDS}s"
            )
        else:
            logger.warning(f"[VOICE] Gemini HTTP {e.code}: {e.reason}")
        result = _local_fallback(user_text)
        return result, "local_fallback"

    except Exception as e:
        logger.warning(f"[VOICE] Gemini error: {e} — using local fallback")
        result = _local_fallback(user_text)
        return result, "local_fallback"


class VoiceCommandRequest(BaseModel):
    text: str


def execute_voice_action(device: str, action: str) -> dict:
    """Apply a parsed voice command to the DEVICES state."""
    action = action.upper()
    device_lower = device.lower()

    # Handle ALL devices
    if device_lower == "all":
        if action == "OFF":
            changed = []
            for did, d in DEVICES.items():
                if d["status"]:
                    d["status"] = False
                    MANUAL_OVERRIDES[did] = datetime.now()
                    DEVICE_OVERRIDE_MINUTES[did] = 30
                    push_notification(d["name"], False, "VOICE — turn everything off", 1.0, "Voice Command")
                    changed.append(d["name"])
            return {"applied": True, "changed": changed, "action": "OFF", "device": "ALL"}
        elif action in ("ON", "STATUS"):
            statuses = {d["name"]: d["status"] for d in DEVICES.values()}
            return {"applied": action == "STATUS", "statuses": statuses, "action": action, "device": "ALL"}
        return {"applied": False, "device": "ALL", "action": action}

    if action == "STATUS":
        did = DEVICE_NAME_MAP.get(device_lower)
        if did:
            name = DEVICES[did]["name"]
            return {"applied": True, "device": name, "action": "STATUS", "status": DEVICES[did]["status"]}
        return {"applied": False, "device": device, "action": "STATUS", "error": "Device not found"}

    if action in ("ON", "OFF"):
        did = DEVICE_NAME_MAP.get(device_lower)
        if not did:
            return {"applied": False, "device": device, "action": action, "error": "Device not found"}
        new_state = action == "ON"
        DEVICES[did]["status"] = new_state
        MANUAL_OVERRIDES[did] = datetime.now()
        DEVICE_OVERRIDE_MINUTES[did] = 30
        push_notification(
            DEVICES[did]["name"], new_state,
            f"VOICE COMMAND — {action}", 1.0, "Voice Command"
        )
        logger.info(f"[VOICE] {DEVICES[did]['name']} → {action}")
        return {"applied": True, "device": DEVICES[did]["name"], "action": action}

    return {"applied": False, "device": device, "action": action, "error": "Unknown action"}


@app.post("/api/voice/command")
async def voice_command(req: VoiceCommandRequest):
    """
    Accept a natural language text command, parse it with the quota-safe engine,
    and apply the resulting device action.

    Quota-safe flow:
      cache → local matcher → rate-limiter → cooldown guard → Gemini API → local fallback
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty command text")

    text = req.text.strip()
    logger.info(f"[VOICE] Received command: '{text}'")

    # Parse via quota-safe engine
    parsed, source = await asyncio.to_thread(smart_parse_command, text)
    device = parsed.get("device", "UNKNOWN")
    action = parsed.get("action", "UNKNOWN")

    logger.info(f"[VOICE] Parsed via [{source}]: device={device}, action={action}")

    if device == "UNKNOWN" or action == "UNKNOWN":
        return {
            "success": False,
            "original_text": text,
            "device": device,
            "action": action,
            "message": "Sorry, I didn't understand that command. Please try again.",
            "applied": False,
            "source": source,
        }

    result = execute_voice_action(device, action)

    return {
        "success": True,
        "original_text": text,
        "device": device,
        "action": action,
        "message": f"{'✅' if result.get('applied') else '⚠️'} {device} → {action}",
        "applied": result.get("applied", False),
        "details": result,
        "source": source,   # tells frontend which engine handled this command
    }


# ── Electricity Bill Estimator ────────────────────────────────

def calc_bill_rs(units: float) -> float:
    """Progressive Pakistani electricity tariff calculation."""
    if units <= 0:
        return 0.0
    if units <= 100:
        return units * 20
    if units <= 200:
        return 100 * 20 + (units - 100) * 30
    return 100 * 20 + 100 * 30 + (units - 200) * 35


def build_bill_breakdown(units: float) -> list:
    """Return slab-by-slab breakdown list."""
    breakdown = []
    remaining = units
    if remaining <= 0:
        return breakdown
    # Slab 1: first 100 units @ Rs.20
    slab1 = min(remaining, 100.0)
    breakdown.append({
        "slab": "First 100 Units",
        "units": round(slab1, 2),
        "rate": 20,
        "amount": round(slab1 * 20, 2),
    })
    remaining -= slab1
    if remaining <= 0:
        return breakdown
    # Slab 2: next 100 units @ Rs.30
    slab2 = min(remaining, 100.0)
    breakdown.append({
        "slab": f"Next {round(slab2, 2)} Units (101–200)",
        "units": round(slab2, 2),
        "rate": 30,
        "amount": round(slab2 * 30, 2),
    })
    remaining -= slab2
    if remaining <= 0:
        return breakdown
    # Slab 3: above 200 units @ Rs.35
    breakdown.append({
        "slab": f"Above 200 Units ({round(remaining, 2)} units)",
        "units": round(remaining, 2),
        "rate": 35,
        "amount": round(remaining * 35, 2),
    })
    return breakdown


@app.get("/api/electricity/bill")
async def get_electricity_bill(target_units: float = 200.0):
    """
    Calculate the current-month electricity bill from device energy records.
    Reads device_logs.energy_used (Wh) for the current calendar month.
    Falls back to two_week_logs.energy_wh if device_logs has no data.
    Applies progressive tariff: Rs.20/unit (≤100), Rs.30/unit (101-200), Rs.35/unit (>200).
    """
    try:
        now = datetime.now()
        # Billing period: 1st of current month to today
        month_start = datetime(now.year, now.month, 1)
        month_start_str = month_start.strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")

        # Days in current month
        import calendar
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_passed = now.day  # today counts

        conn = get_db()
        c = conn.cursor()

        # ── Try device_logs first ─────────────────────────────
        device_rows = c.execute("""
            SELECT device_name,
                   SUM(CAST(energy_used AS REAL)) as total_wh,
                   COUNT(*) as cnt
            FROM device_logs
            WHERE timestamp >= ?
            GROUP BY device_name
        """, (month_start_str,)).fetchall()

        total_wh_from_device_logs = sum(r["total_wh"] or 0 for r in device_rows)

        # ── Fall back to two_week_logs if needed ──────────────
        use_fallback = (total_wh_from_device_logs == 0)
        if use_fallback:
            device_rows = c.execute("""
                SELECT device_name,
                       SUM(CAST(energy_wh AS REAL)) as total_wh,
                       COUNT(*) as cnt
                FROM two_week_logs
                WHERE timestamp >= ?
                GROUP BY device_name
            """, (month_start_str,)).fetchall()

        conn.close()

        # ── Aggregate per-device kWh ──────────────────────────
        device_breakdown = []
        total_wh = 0.0
        for row in device_rows:
            wh = row["total_wh"] or 0.0
            total_wh += wh
            kwh = round(wh / 1000.0, 3)
            device_breakdown.append({
                "device": row["device_name"],
                "kwh": kwh,
                "rs": round(calc_bill_rs(kwh), 2),
            })
        device_breakdown.sort(key=lambda x: x["kwh"], reverse=True)

        total_kwh = round(total_wh / 1000.0, 3)
        current_bill = round(calc_bill_rs(total_kwh), 2)
        breakdown = build_bill_breakdown(total_kwh)

        # ── Projection ────────────────────────────────────────
        avg_daily_kwh = round(total_kwh / max(days_passed, 1), 3)
        projected_monthly_kwh = round(avg_daily_kwh * days_in_month, 3)
        projected_monthly_bill = round(calc_bill_rs(projected_monthly_kwh), 2)

        # ── Progress vs target ────────────────────────────────
        pct_of_target = round((total_kwh / max(target_units, 1)) * 100, 1)

        return {
            "billing_period": {
                "start": month_start_str,
                "end": today_str,
                "days_passed": days_passed,
                "days_in_month": days_in_month,
                "days_remaining": days_in_month - days_passed,
            },
            "total_units_kwh": total_kwh,
            "current_bill_rs": current_bill,
            "bill_breakdown": breakdown,
            "avg_daily_kwh": avg_daily_kwh,
            "projected_monthly_kwh": projected_monthly_kwh,
            "projected_monthly_bill_rs": projected_monthly_bill,
            "target_units": target_units,
            "pct_of_target": pct_of_target,
            "device_breakdown": device_breakdown,
            "data_source": "two_week_logs (fallback)" if use_fallback else "device_logs",
        }
    except Exception as e:
        logger.error(f"[BILL] Error calculating bill: {e}")
        raise HTTPException(500, str(e))


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
