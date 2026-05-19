#!/usr/bin/env python3
"""
Generate 2 weeks of realistic device data using the trained RandomForest model
and store it in SQLite (home_automation.db)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import sqlite3
import numpy as np
import joblib
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "home_automation.db")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "home_automation_model.pkl")

DEVICES = {
    0: {"id": 1, "name": "AC",     "watt": 2500},
    1: {"id": 2, "name": "Fan",    "watt": 150},
    2: {"id": 3, "name": "Light",  "watt": 100},
    3: {"id": 4, "name": "TV",     "watt": 200},
    4: {"id": 5, "name": "Fridge", "watt": 500},
}

FEATURE_COLS = ["year", "month", "day", "hour", "minute", "weekday", "is_weekend", "temp_c"]


def load_model():
    print("[INFO] Loading RandomForest model...")
    try:
        model = joblib.load(MODEL_PATH)
        print("[OK] Model loaded successfully")
        return model
    except FileNotFoundError:
        print("[WARN] Model not found - training a new one...")
        return train_model()


def train_model():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.multioutput import MultiOutputClassifier
    from sklearn.model_selection import train_test_split

    np.random.seed(42)
    n = 8000
    data_hour = np.random.randint(0, 24, n)
    data_temp = np.random.uniform(15, 40, n)
    data_weekend = np.random.choice([0, 1], n)

    import pandas as pd
    df = pd.DataFrame({
        "year": [2024] * n,
        "month": np.random.randint(1, 13, n),
        "day": np.random.randint(1, 29, n),
        "hour": data_hour,
        "minute": np.random.randint(0, 60, n),
        "weekday": np.random.randint(0, 7, n),
        "is_weekend": data_weekend,
        "temp_c": data_temp,
    })
    df["ac"]     = ((df["temp_c"] > 26) & df["hour"].isin(range(9, 23))).astype(int)
    df["fan"]    = (df["temp_c"] > 22).astype(int)
    df["light"]  = ((df["hour"] >= 18) | (df["hour"] <= 6)).astype(int)
    df["tv"]     = ((df["hour"] >= 19) & (df["hour"] <= 23) & (df["is_weekend"] == 1)).astype(int)
    df["fridge"] = 1

    X = df[FEATURE_COLS]
    y = df[["ac", "fan", "light", "tv", "fridge"]]

    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    model = MultiOutputClassifier(clf, n_jobs=-1)
    model.fit(X_train, y_train)

    joblib.dump(model, MODEL_PATH)
    print("[OK] Model trained and saved")
    return model


def init_db(conn):
    c = conn.cursor()

    # Keep existing tables, just add two_week_logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS two_week_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            device_id   INTEGER NOT NULL,
            device_name TEXT NOT NULL,
            action      INTEGER NOT NULL,
            temperature REAL NOT NULL,
            hour        INTEGER NOT NULL,
            weekday     INTEGER NOT NULL,
            is_weekend  INTEGER NOT NULL,
            energy_wh   REAL NOT NULL,
            UNIQUE(timestamp, device_id)
        )
    """)

    # Also ensure devices table has our 5 devices
    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id                 INTEGER PRIMARY KEY,
            name               TEXT UNIQUE,
            type               TEXT,
            status             BOOLEAN,
            energy_consumption FLOAT,
            last_updated       TIMESTAMP
        )
    """)

    default_devices = [
        (1, "AC",     "Air Conditioner", 0, 2500.0),
        (2, "Fan",    "Cooling Device",  1, 150.0),
        (3, "Light",  "Lighting",        1, 100.0),
        (4, "TV",     "Entertainment",   0, 200.0),
        (5, "Fridge", "Refrigerator",    1, 500.0),
    ]
    for d in default_devices:
        c.execute("""
            INSERT OR IGNORE INTO devices (id, name, type, status, energy_consumption, last_updated)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, d)

    conn.commit()
    print("[OK] Database schema ready")


def generate_timestamps():
    """Every 30 minutes for last 14 days"""
    start = datetime.now() - timedelta(days=14)
    ts = []
    current = start.replace(second=0, microsecond=0)
    # round to nearest 30 min
    current -= timedelta(minutes=current.minute % 30)
    while current <= datetime.now():
        ts.append(current)
        current += timedelta(minutes=30)
    return ts


def run():
    model = load_model()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    timestamps = generate_timestamps()
    print(f"[INFO] Generating {len(timestamps)} time points over 14 days...")

    # Build feature matrix
    rows = []
    for ts in timestamps:
        hour = ts.hour
        temp = 18 + 12 * np.sin(hour * np.pi / 12) + np.random.normal(0, 1.5)
        rows.append([
            ts.year, ts.month, ts.day, ts.hour, ts.minute,
            ts.weekday(), 1 if ts.weekday() >= 5 else 0,
            round(temp, 2)
        ])

    import numpy as np_inner
    X = np_inner.array(rows)
    preds = model.predict(X)  # shape: (N, 5)

    print(f"[INFO] Model predicted {len(preds)} x 5 device states - inserting into SQLite...")

    c = conn.cursor()
    # Clear old 2-week logs
    c.execute("DELETE FROM two_week_logs")

    records = []
    for i, ts in enumerate(timestamps):
        hour = int(rows[i][3])
        weekday = int(rows[i][5])
        is_weekend = int(rows[i][6])
        temp = float(rows[i][7])

        for dev_idx in range(5):
            dev = DEVICES[dev_idx]
            action = int(preds[i][dev_idx])
            energy = dev["watt"] * 0.5 * action  # 30-min slot → 0.5 h

            records.append((
                ts.isoformat(sep=" ", timespec="seconds"),
                dev["id"],
                dev["name"],
                action,
                temp,
                hour,
                weekday,
                is_weekend,
                energy,
            ))

    c.executemany("""
        INSERT OR IGNORE INTO two_week_logs
        (timestamp, device_id, device_name, action, temperature, hour, weekday, is_weekend, energy_wh)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()

    total = c.execute("SELECT COUNT(*) FROM two_week_logs").fetchone()[0]
    print(f"[OK] Inserted {len(records)} records  |  Total in DB: {total}")

    # Update device status to latest prediction
    for dev_idx in range(5):
        dev = DEVICES[dev_idx]
        latest_action = int(preds[-1][dev_idx])
        c.execute("""
            UPDATE devices SET status=?, last_updated=datetime('now') WHERE id=?
        """, (latest_action, dev["id"]))
    conn.commit()

    conn.close()
    print("\n[DONE] SQLite database populated with 2 weeks of RF model predictions.")
    print(f"   Database: {DB_PATH}")
    print(f"   Records : {len(records):,}")


if __name__ == "__main__":
    print("=" * 60)
    print("  AI Home Automation - 2-Week Data Generator (SQLite)")
    print("=" * 60)
    run()
