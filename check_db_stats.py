import sqlite3

conn = sqlite3.connect("home_automation.db")
c = conn.cursor()

# List all tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("=== TABLES IN DATABASE ===")
for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} rows")

print()

# Check two_week_logs
try:
    total = c.execute("SELECT COUNT(*) FROM two_week_logs").fetchone()[0]
    oldest = c.execute("SELECT MIN(timestamp) FROM two_week_logs").fetchone()[0]
    newest = c.execute("SELECT MAX(timestamp) FROM two_week_logs").fetchone()[0]
    per_device = c.execute("SELECT device_id, COUNT(*) FROM two_week_logs GROUP BY device_id").fetchall()
    print("=== two_week_logs ===")
    print(f"Total rows    : {total}")
    print(f"Oldest record : {oldest}")
    print(f"Newest record : {newest}")
    print("Per device:")
    for row in per_device:
        print(f"  Device {row[0]}: {row[1]} rows")
except Exception as e:
    print(f"two_week_logs error: {e}")

print()

# Check agent_logs
try:
    total2 = c.execute("SELECT COUNT(*) FROM agent_logs").fetchone()[0]
    oldest2 = c.execute("SELECT MIN(timestamp) FROM agent_logs").fetchone()[0]
    newest2 = c.execute("SELECT MAX(timestamp) FROM agent_logs").fetchone()[0]
    print("=== agent_logs ===")
    print(f"Total rows    : {total2}")
    print(f"Oldest record : {oldest2}")
    print(f"Newest record : {newest2}")
except Exception as e:
    print(f"agent_logs error: {e}")

conn.close()
