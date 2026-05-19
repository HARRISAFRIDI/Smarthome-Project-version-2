import sqlite3, os, sys

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

db = r'd:\progress 2 FYP\Smarthome Project version 2\home_automation.db'

if not os.path.exists(db):
    print('Database file does NOT exist yet.')
    print('Start the backend first: python backend/main.py')
else:
    size_kb = os.path.getsize(db) / 1024
    print(f'[OK] Database file found ({size_kb:.1f} KB)')
    print()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f'Tables found: {len(tables)}')
    print('-' * 45)

    for t in tables:
        name = t[0]
        count = conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
        print(f'  {name:<25} -> {count:>6} rows')

    # Show sample rows from each table
    for t in tables:
        name = t[0]
        print(f'\nSample from [{name}] (last 3 rows):')
        rows = conn.execute(f'SELECT * FROM {name} ORDER BY rowid DESC LIMIT 3').fetchall()
        if rows:
            print('  Columns:', list(rows[0].keys()))
            for r in rows:
                print(' ', dict(r))
        else:
            print('  (empty - no data yet)')

    conn.close()
