import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
import glob
import time

DB_PATH = os.environ.get("DB_PATH", "/data/app.db")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backup")

app = Flask(__name__)

# ---------- DB helpers ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ---------- Routes ----------

@app.get("/")
def hello():
    init_db()
    return jsonify(status="Bonjour tout le monde !")


@app.get("/health")
def health():
    init_db()
    return jsonify(status="ok")

@app.get("/add")
def add():
    init_db()

    msg = request.args.get("message", "hello")
    ts = datetime.utcnow().isoformat() + "Z"

    conn = get_conn()
    conn.execute(
        "INSERT INTO events (ts, message) VALUES (?, ?)",
        (ts, msg)
    )
    conn.commit()
    conn.close()

    return jsonify(
        status="added",
        timestamp=ts,
        message=msg
    )

@app.get("/consultation")
def consultation():
    init_db()

    conn = get_conn()
    cur = conn.execute(
        "SELECT id, ts, message FROM events ORDER BY id DESC LIMIT 50"
    )

    rows = [
        {"id": r[0], "timestamp": r[1], "message": r[2]}
        for r in cur.fetchall()
    ]

    conn.close()

    return jsonify(rows)

@app.get("/count")
def count():
    init_db()

    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) FROM events")
    n = cur.fetchone()[0]
    conn.close()

    return jsonify(count=n)

#__________AJOUT_____________________

def get_count():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # ⚠️ adapte le nom de table si besoin (ex: events/messages)
    cur.execute("SELECT COUNT(*) FROM events;")
    count = cur.fetchone()[0]
    conn.close()
    return count


# ---------- Status (Atelier 1) ----------

def get_last_backup_info():
    # on cherche les backups dans /backup (PVC pra-backup si monté)
    pattern = os.path.join(BACKUP_DIR, "*.db")
    files = glob.glob(pattern)

    if not files:
        return None, None

    last_file = max(files, key=os.path.getmtime)
    age_seconds = int(time.time() - os.path.getmtime(last_file))
    return os.path.basename(last_file), age_seconds


@app.get("/status")
def status():
    init_db()

    # count en base
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) FROM events")
    n = cur.fetchone()[0]
    conn.close()

    # infos backup
    last_backup_file, backup_age_seconds = get_last_backup_info()

    return jsonify(
        count=n,
        last_backup_file=last_backup_file,
        backup_age_seconds=backup_age_seconds
    )



# ---------- Main ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
