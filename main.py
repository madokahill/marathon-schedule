from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import subprocess
import sys

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "marathon.db")


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


@app.route("/")
def index():
    if not os.path.exists(DB_PATH):
        scraper = os.path.join(BASE_DIR, "crawler", "scraper.py")
        subprocess.run([sys.executable, scraper])
    races = get_races()
    return render_template("index.html", races=races, total=len(races))


@app.route("/api/races")
def api_races():
    search = request.args.get("search", "")
    distance = request.args.get("distance", "")
    month = request.args.get("month", "")
    races = get_races(search=search, distance=distance, month=month)
    return jsonify({"races": races, "total": len(races)})


@app.route("/api/crawl", methods=["POST"])
def trigger_crawl():
    scraper = os.path.join(BASE_DIR, "crawler", "scraper.py")
    result = subprocess.run([sys.executable, scraper], capture_output=True, text=True)
    return jsonify({"status": "ok", "output": result.stdout, "error": result.stderr})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
