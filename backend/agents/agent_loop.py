# ══════════════════════════════════════════════════════════════
# AUTONOMOUS AGENT LOOP
# Runs every 3 minutes (180 seconds)
# ══════════════════════════════════════════════════════════════

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, Any

from .nodes import (
    node1_rf_predict,
    node2_rule_engine,
    node3_override_check,
    node4_execute,
    node5_notify,
)

logger = logging.getLogger(__name__)


async def start_autonomous_agent(
    agent_status: Dict[str, Any],
    get_temp_func: Callable,
    devices: Dict,
    rf_model,
    target_names: Dict,
    feature_cols: list,
    deep_night_enabled: bool,
    is_home: bool,
    away_blocked: set,
    peak_hours: list,
    peak_hours_data: dict,
    confidence_threshold: float,
    get_custom_rules_func: Callable,
    is_manually_locked_func: Callable,
    log_agent_action_func: Callable,
    push_notification_func: Callable,
) -> None:
    """
    Main autonomous agent loop.
    
    Runs continuously every 180 seconds (3 minutes):
    1. Fetch current temperature
    2. Node 1: Predict device states using RF model
    3. Node 2: Apply business rules
    4. Node 3: Check manual overrides
    5. Node 4: Execute approved actions
    6. Node 5: Notify user
    
    Args:
        agent_status: Shared dict to track agent state
        get_temp_func: Function to get current temperature
        devices: Device state dictionary
        rf_model: Trained RandomForest model
        target_names: Device name mapping
        feature_cols: Model feature columns
        deep_night_enabled: Enable night-time blocking
        is_home: User home status
        away_blocked: Set of device IDs to block when away
        peak_hours: List of peak hours
        peak_hours_data: Peak hours data with on-rates
        confidence_threshold: Minimum prediction confidence
        get_custom_rules_func: Function to get custom rules
        is_manually_locked_func: Function to check manual locks
        log_agent_action_func: Function to log actions to DB
        push_notification_func: Function to send notifications
    """
    agent_status["running"] = True
    logger.info("[AGENT] Autonomous agent loop started (180s / 3-minute interval)")
    await asyncio.sleep(10)  # Wait for startup

    while True:
        try:
            now = datetime.now()
            temp = await asyncio.to_thread(get_temp_func)

            node_log = []

            # ── Node 1: RF Predict ─────────────────────────────
            predictions = node1_rf_predict(now, temp, rf_model, target_names, feature_cols)
            node_log.append(
                {
                    "node": "1 - RF Model Predict",
                    "output": f"{len(predictions)} device predictions generated",
                }
            )

            # ── Node 2: Rule Engine ────────────────────────────
            rule_checked = node2_rule_engine(
                predictions,
                now,
                temp,
                devices,
                deep_night_enabled,
                is_home,
                away_blocked,
                peak_hours,
                peak_hours_data,
                target_names,
                confidence_threshold,
                get_custom_rules_func,
            )
            approved_count = sum(1 for r in rule_checked if r["approved"])
            node_log.append(
                {
                    "node": "2 - Rule Engine",
                    "output": f"{approved_count}/{len(rule_checked)} passed rules",
                }
            )

            # ── Node 3: Override Check ─────────────────────────
            final_list = node3_override_check(rule_checked, is_manually_locked_func)
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
            actions = node4_execute(final_list, devices, log_agent_action_func)
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
            node5_notify(actions, push_notification_func)
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
            agent_status["last_cycle"] = now.isoformat()
            agent_status["cycle_count"] += 1
            agent_status["node_log"] = node_log
            agent_status["last_actions"] = [
                {
                    "device": a["device_name"],
                    "action": "ON" if a["predicted"] else "OFF",
                    "confidence": round(a["confidence"] * 100, 1),
                }
                for a in actions
            ]

            if actions:
                logger.info(
                    f"[AGENT] Cycle #{agent_status['cycle_count']}: {len(actions)} action(s) taken"
                )

        except Exception as e:
            logger.error(f"[AGENT] Loop error: {e}", exc_info=True)

        await asyncio.sleep(180)  # 3 minutes between cycles
