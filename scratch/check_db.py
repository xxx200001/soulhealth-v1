import sqlite3
import json

conn = sqlite3.connect('data/soulhealth.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print("=== SQLite Tables ===")
for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Table '{t}': {count} rows")

print("\n=== Recent Users / Profiles ===")
try:
    for row in c.execute("SELECT id, username, created_at FROM users LIMIT 5"):
        print("User:", row)
except Exception as e:
    print("Users err:", e)

try:
    for row in c.execute("SELECT id, user_id, real_name, created_at FROM profiles LIMIT 5"):
        print("Profile:", row)
except Exception as e:
    print("Profiles err:", e)

print("\n=== Recent Reports ===")
try:
    for row in c.execute("SELECT id, profile_id, report_date, status, created_at FROM reports ORDER BY created_at DESC LIMIT 5"):
        print("Report:", row)
except Exception as e:
    print("Reports err:", e)

print("\n=== Recent Conversations / Ask ===")
try:
    for row in c.execute("SELECT id, profile_id, created_at FROM conversations ORDER BY created_at DESC LIMIT 5"):
        print("Conversation:", row)
except Exception as e:
    print("Conversations err:", e)
