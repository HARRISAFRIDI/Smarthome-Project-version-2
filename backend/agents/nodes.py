# ══════════════════════════════════════════════════════════════
# AUTONOMOUS AGENT: 5-NODE ARCHITECTURE
# Node 1: RF Model Prediction
# Node 2: Rule Engine
# Node 3: Manual Override Check
# Node 4: Execute Actions
# Node 5: Notify User
# ══════════════════════════════════════════════════════════════

import logging
import numpy as np
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


def node1_rf_predict(
    now: datetime, temp: float, rf_model, target_names: dict, feature_cols: list
) -> List[Dict]:
    """
    Node 1 — Run RF Model and get raw predictions for all devices.
    
    Args:
        now: Current datetime
        temp: Current temperature (°C)
        rf_model: Loaded RandomForest model
        target_names: Device name mapping {1: "AC", 2: "Fan", ...}
        feature_cols: Feature column names for model
    
    Returns:
        List of predictions with confidence scores
    """
    if rf_model is None:
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
        preds = rf_model.predict(features)[0]
        try:
            probas = rf_model.predict_proba(features)
            confs = [max(p[0]) for p in probas]
        except Exception:
            confs = [0.9] * 5

        results = []
        for i, did in enumerate(range(1, 6)):
            results.append(
                {
                    "device_id": did,
                    "device_name": target_names[did],
                    "predicted": bool(preds[i]),
                    "confidence": float(confs[i]),
                }
            )
        return results
    except Exception as e:
        logger.error(f"[Node1] RF predict error: {e}")
        return []


def node2_rule_engine(
    predictions: List[Dict],
    now: datetime,
    temp: float,
    devices: dict,
    deep_night_enabled: bool,
    is_home: bool,
    away_blocked: set,
    peak_hours: list,
    peak_hours_data: dict,
    target_names: dict,
    confidence_threshold: float,
    get_custom_rules_func,
    sunrise_hour: int = None,
    sunset_hour: int = None,
) -> List[Dict]:
    """
    Node 2 — Apply business rules to filter/modify predictions.
    
    Rules applied:
    - Confidence threshold
    - Daylight hours blocking (Light) - don't turn on between sunrise and sunset
    - Night-time blocking (Light, TV)
    - Smart peak hours (AC)
    - Away mode blocking
    - Custom temperature-based rules
    - State unchanged detection
    """
    NIGHT_HOURS = set(range(23, 24)) | set(range(0, 4))  # 23, 0, 1, 2, 3
    NIGHT_BLOCK_DEVS = {3, 4}  # Light, TV

    approved = []
    for p in predictions:
        did = p["device_id"]
        pred = p["predicted"]
        conf = p["confidence"]
        hour = now.hour
        result = dict(p)
        result["approved"] = True
        result["rule_reason"] = "APPROVED"

        # Rule 0: Check state unchanged
        if devices[did]["status"] == pred:
            result["approved"] = False
            result["rule_reason"] = "STATE_UNCHANGED"

        # Rule 1: Confidence threshold
        elif conf < confidence_threshold:
            result["approved"] = False
            result["rule_reason"] = (
                f"LOW_CONFIDENCE ({conf*100:.0f}% < {confidence_threshold*100:.0f}%)"
            )

        # Rule 1.5: Custom temperature rules
        elif result["approved"]:
            custom_rules = get_custom_rules_func(did, temp)
            if custom_rules:
                rule = custom_rules[0]
                rule_action = bool(rule["action"])
                if pred != rule_action:
                    result["predicted"] = rule_action
                    if devices[did]["status"] == rule_action:
                        result["approved"] = False
                        result["rule_reason"] = "STATE_UNCHANGED"
                    else:
                        result["rule_reason"] = (
                            f"CUSTOM_RULE (temp={temp:.1f}°C: {target_names[did]}, "
                            f"desc={rule.get('description', '')})"
                        )
                        logger.info(
                            f"[CUSTOM_RULE] {target_names[did]} (temp={temp:.1f}°C): "
                            f"AI predicted {pred} but rule says {rule_action}"
                        )
                else:
                    if devices[did]["status"] == result["predicted"]:
                        result["approved"] = False
                        result["rule_reason"] = "STATE_UNCHANGED"

        # Rule 2a: Smart peak hours (AC)
        elif did == 1 and pred is True and peak_hours and hour in peak_hours:
            on_rate = peak_hours_data.get(hour, 0)
            result["approved"] = False
            result["rule_reason"] = (
                f"SMART_PEAK_BLOCK (hour={hour}, avg_on_rate={on_rate:.0%})"
            )

        # Rule 2b: Night hours block
        elif (
            deep_night_enabled
            and did in NIGHT_BLOCK_DEVS
            and pred is True
            and hour in NIGHT_HOURS
        ):
            result["approved"] = False
            result["rule_reason"] = (
                f"NIGHT_BLOCK ({target_names[did]} OFF — sleep hours, blocked 23:00-03:59)"
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

        # Rule 3: Away mode
        elif not is_home and did in away_blocked and pred is True:
            result["approved"] = False
            result["rule_reason"] = "AWAY_MODE (user not home — device blocked)"

        approved.append(result)

    return approved


def node3_override_check(
    approved_list: List[Dict], is_manually_locked_func
) -> List[Dict]:
    """
    Node 3 — Skip devices manually locked by user.
    
    Checks if user manually controlled device in last N minutes.
    """
    final = []
    for item in approved_list:
        if not item["approved"]:
            final.append(item)
            continue

        did = item["device_id"]
        lock_mins = is_manually_locked_func(did)

        if lock_mins is not None:
            item["approved"] = False
            item["rule_reason"] = f"MANUAL_LOCK ({lock_mins}m remaining)"

        final.append(item)

    return final


def node4_execute(
    final_list: List[Dict],
    devices: dict,
    log_agent_action_func,
) -> List[Dict]:
    """
    Node 4 — Execute approved actions on devices.
    
    Final safety check: skip if device already in target state.
    """
    actions_taken = []

    for item in final_list:
        if not item["approved"]:
            continue

        did = item["device_id"]
        action = item["predicted"]
        conf = item["confidence"]

        # Guard: device already in target state
        if devices[did]["status"] == action:
            continue

        # Execute
        devices[did]["status"] = action
        log_agent_action_func(did, action, conf, item["rule_reason"])
        actions_taken.append(item)

    return actions_taken


def node5_notify(
    actions_taken: List[Dict],
    push_notification_func,
) -> None:
    """
    Node 5 — Send notifications for executed actions.
    """
    for item in actions_taken:
        push_notification_func(
            device_name=item["device_name"],
            action=item["predicted"],
            reason=item["rule_reason"],
            confidence=item["confidence"],
            node="Agent Auto-Control",
        )
