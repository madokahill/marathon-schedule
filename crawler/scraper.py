"""
마라톤 대회 정보 크롤러
- marathon.pe.kr (마라톤온라인)
"""
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "marathon.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS races (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT,
            location TEXT,
            distance TEXT,
            organizer TEXT,
            url TEXT,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def upsert_race(races: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for r in races:
        existing = c.execute(
            "SELECT id FROM races WHERE title=? AND date=?", (r["title"], r["date"])
        ).fetchone()
        if not existing:
            c.execute(
                "INSERT INTO races (title, date, location, distance, organizer, url, source) VALUES (?,?,?,?,?,?,?)",
                (r["title"], r["date"], r["location"], r["distance"], r["organizer"], r["url"], r["source"]),
            )
    conn.commit()
    conn.close()


def crawl_marathon_online():
    """마라톤온라인 (marathon.pe.kr) 대회 일정 크롤링"""
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        # 대회 목록 페이지
        url = "http://www.marathon.pe.kr/marathon_schedule.html"
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table tr")
        for row in rows[1:]:  # 헤더 제외
            cols = row.select("td")
            if len(cols) < 4:
                continue
            title = cols[0].get_text(strip=True)
            date = cols[1].get_text(strip=True)
            location = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            distance = cols[3].get_text(strip=True) if len(cols) > 3 else ""
            link_tag = cols[0].find("a")
            link = ("http://www.marathon.pe.kr/" + link_tag["href"]) if link_tag else url

            if title and date:
                results.append({
                    "title": title,
                    "date": date,
                    "location": location,
                    "distance": distance,
                    "organizer": "",
                    "url": link,
                    "source": "marathon.pe.kr",
                })
    except Exception as e:
        print(f"[marathon.pe.kr 크롤링 오류] {e}")

    return results


def crawl_sample_data():
    """크롤링이 실패할 경우를 대비한 샘플 데이터"""
    return [
        {
            "title": "2026 서울국제마라톤 (동아마라톤)",
            "date": "2026-03-15",
            "location": "서울 광화문",
            "distance": "풀/하프/10K",
            "organizer": "동아일보",
            "url": "https://www.donga.com/marathon",
            "source": "sample",
        },
        {
            "title": "2026 경주국제마라톤",
            "date": "2026-04-05",
            "location": "경북 경주",
            "distance": "풀/하프",
            "organizer": "경주시",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 춘천마라톤",
            "date": "2026-10-25",
            "location": "강원 춘천",
            "distance": "풀/하프/10K",
            "organizer": "조선일보",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 조선일보 춘천마라톤",
            "date": "2026-10-18",
            "location": "강원 춘천",
            "distance": "풀/하프",
            "organizer": "조선일보",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 JTBC 서울마라톤",
            "date": "2026-11-01",
            "location": "서울 잠실",
            "distance": "풀/하프/10K/5K",
            "organizer": "JTBC",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 대구마라톤",
            "date": "2026-04-19",
            "location": "대구 두류공원",
            "distance": "풀/하프/10K",
            "organizer": "매일신문",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 부산국제마라톤",
            "date": "2026-05-03",
            "location": "부산 해운대",
            "distance": "풀/하프",
            "organizer": "부산광역시",
            "url": "",
            "source": "sample",
        },
        {
            "title": "2026 인천마라톤",
            "date": "2026-09-20",
            "location": "인천 송도",
            "distance": "풀/하프/10K",
            "organizer": "인천시",
            "url": "",
            "source": "sample",
        },
    ]


def run():
    init_db()
    print("크롤링 시작...")

    races = crawl_marathon_online()
    print(f"marathon.pe.kr: {len(races)}건 수집")

    # 크롤링 결과가 없으면 샘플 데이터 사용
    if not races:
        races = crawl_sample_data()
        print(f"샘플 데이터 {len(races)}건 사용")

    upsert_race(races)
    print(f"DB 저장 완료: 총 {len(races)}건")


if __name__ == "__main__":
    run()
