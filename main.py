from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import subprocess
import sys
import atexit
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "crawler"))
from scraper import init_db

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "marathon.db")

init_db()

# marathon.db lives on Render's ephemeral disk and resets to this git-committed
# state on every deploy, so picks can't be stored in the DB - list the exact
# race titles to feature here instead.
PICKED_RACE_TITLES = [
    "2026 YTN 서울투어마라톤",
    "2026 파주북시티마라톤",
    "2026 서울오픈마라톤",
    "2026 서울레이스",
    "2026 가민런 코리아",
    "2026 MBN 서울마라톤",
]


def run_scraper():
    scraper = os.path.join(BASE_DIR, "crawler", "scraper.py")
    return subprocess.run([sys.executable, scraper], capture_output=True, text=True)


scheduler = BackgroundScheduler()
scheduler.add_job(run_scraper, "cron", hour=6, minute=0, id="daily_crawl")
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


def get_races(search="", distance="", month=""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM races WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR location LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if distance:
        query += " AND distance LIKE ?"
        params.append(f"%{distance}%")
    if month:
        query += " AND date LIKE ?"
        params.append(f"%-{month.zfill(2)}-%")

    query += " ORDER BY date ASC"
    rows = c.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_picks():
    if not PICKED_RACE_TITLES:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    today = date.today().isoformat()
    placeholders = ",".join("?" * len(PICKED_RACE_TITLES))
    rows = c.execute(
        f"SELECT * FROM races WHERE title IN ({placeholders}) AND date >= ? ORDER BY date ASC",
        (*PICKED_RACE_TITLES, today),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_news(limit=15):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    rows = c.execute("SELECT * FROM news ORDER BY id ASC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def group_by_month(races):
    groups = []
    current_key = None
    for race in races:
        key = race["date"][:7]
        if key != current_key:
            year, month = key.split("-")
            groups.append({"year": int(year), "month": int(month), "races": []})
            current_key = key
        groups[-1]["races"].append(race)
    return groups


@app.route("/")
def index():
    if not os.path.exists(DB_PATH):
        run_scraper()
    races = get_races()
    today = date.today().isoformat()
    upcoming = [r for r in races if r["date"] >= today]
    month_groups = group_by_month(upcoming)
    news = get_news()
    picks = get_picks()
    return render_template(
        "index.html", races=races, month_groups=month_groups, total=len(upcoming),
        today=today, news=news, picks=picks
    )


@app.route("/api/races")
def api_races():
    search = request.args.get("search", "")
    distance = request.args.get("distance", "")
    month = request.args.get("month", "")
    races = get_races(search=search, distance=distance, month=month)
    return jsonify({"races": races, "total": len(races)})


@app.route("/api/crawl", methods=["POST"])
def trigger_crawl():
    result = run_scraper()
    return jsonify({"status": "ok", "output": result.stdout, "error": result.stderr})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
