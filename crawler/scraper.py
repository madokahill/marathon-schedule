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
            reg_start TEXT,
            reg_end TEXT,
            reg_url TEXT,
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
                "INSERT INTO races (title, date, location, distance, organizer, url, source, reg_start, reg_end, reg_url) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["title"], r["date"], r["location"], r["distance"], r["organizer"], r["url"], r["source"],
                 r.get("reg_start",""), r.get("reg_end",""), r.get("reg_url","")),
            )
    conn.commit()
    conn.close()


def crawl_marathon_online():
    """roadrun.co.kr (마라톤온라인 데이터) 대회 일정 크롤링"""
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    import re
    from datetime import datetime

    try:
        url = "http://www.roadrun.co.kr/schedule/list.php"
        res = requests.get(url, headers=headers, timeout=15, verify=False)
        try:
            text = res.content.decode("utf-8")
        except:
            text = res.content.decode("euc-kr", errors="ignore")

        soup = BeautifulSoup(text, "html.parser")
        rows = soup.select("table tr")

        current_year = datetime.now().year
        data_started = False

        for row in rows:
            cols = row.select("td")
            txt = row.get_text(" | ", strip=True)

            # 데이터 시작 감지 (날짜 | 대회명 | 장소 | 주최 헤더 이후)
            if "날짜" in txt and "대회명" in txt and "장소" in txt:
                data_started = True
                continue

            if not data_started:
                continue

            # 날짜/대회명/장소/주최 파싱
            # 행 텍스트에서 날짜 패턴 찾기 (예: 5/2, 10/25)
            parts = [p.strip() for p in txt.split("|") if p.strip()]
            if len(parts) < 3:
                continue

            # 첫 번째 요소가 날짜인지 확인 (M/D 형식)
            date_match = re.match(r'^(\d{1,2})/(\d{1,2})$', parts[0])
            if not date_match:
                continue

            month = int(date_match.group(1))
            day = int(date_match.group(2))

            # 연도 결정 (현재 월보다 작으면 내년)
            now = datetime.now()
            year = current_year
            if month < now.month - 1:
                year = current_year + 1

            date_str = f"{year}-{month:02d}-{day:02d}"

            # 요일 제거 후 나머지 파싱
            idx = 1
            if idx < len(parts) and re.match(r'^\([월화수목금토일]\)$', parts[idx]):
                idx += 1

            if idx >= len(parts):
                continue

            title = parts[idx] if idx < len(parts) else ""
            distance = parts[idx+1] if idx+1 < len(parts) else ""
            location = parts[idx+2] if idx+2 < len(parts) else ""
            organizer = parts[idx+3] if idx+3 < len(parts) else ""
            # 전화번호 제거
            organizer = re.sub(r'☎.*', '', organizer).strip()

            # 링크 찾기 (javascript:open_window('win','view.php?no=12345',...) 파싱)
            link_tag = row.find("a")
            link = ""
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                # javascript:open_window 형태에서 no 추출
                no_match = re.search(r"view\.php\?no=(\d+)", href)
                if no_match:
                    link = f"http://www.roadrun.co.kr/schedule/view.php?no={no_match.group(1)}"
                elif href.startswith("http"):
                    link = href
                elif not href.startswith("javascript"):
                    link = "http://www.roadrun.co.kr/" + href.lstrip("/")

            if title and date_str:
                results.append({
                    "title": title,
                    "date": date_str,
                    "location": location,
                    "distance": distance,
                    "organizer": organizer,
                    "url": link,
                    "reg_start": "",
                    "reg_end": "",
                    "reg_url": link,
                    "source": "roadrun.co.kr",
                })

    except Exception as e:
        print(f"[roadrun.co.kr 크롤링 오류] {e}")

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
            "reg_start": "2026-01-05",
            "reg_end": "2026-02-28",
            "reg_url": "https://www.donga.com/marathon",
            "source": "sample",
        },
        {
            "title": "2026 경주국제마라톤",
            "date": "2026-04-05",
            "location": "경북 경주",
            "distance": "풀/하프",
            "organizer": "경주시",
            "url": "https://www.gyeongjumarathon.com",
            "reg_start": "2026-01-15",
            "reg_end": "2026-03-15",
            "reg_url": "https://www.gyeongjumarathon.com",
            "source": "sample",
        },
        {
            "title": "2026 대구마라톤",
            "date": "2026-04-19",
            "location": "대구 두류공원",
            "distance": "풀/하프/10K",
            "organizer": "매일신문",
            "url": "",
            "reg_start": "2026-02-01",
            "reg_end": "2026-03-31",
            "reg_url": "",
            "source": "sample",
        },
        {
            "title": "2026 부산국제마라톤",
            "date": "2026-05-03",
            "location": "부산 해운대",
            "distance": "풀/하프",
            "organizer": "부산광역시",
            "url": "",
            "reg_start": "2026-02-15",
            "reg_end": "2026-04-10",
            "reg_url": "",
            "source": "sample",
        },
        {
            "title": "2026 인천마라톤",
            "date": "2026-09-20",
            "location": "인천 송도",
            "distance": "풀/하프/10K",
            "organizer": "인천시",
            "url": "",
            "reg_start": "2026-07-01",
            "reg_end": "2026-08-31",
            "reg_url": "",
            "source": "sample",
        },
        {
            "title": "2026 춘천마라톤",
            "date": "2026-10-25",
            "location": "강원 춘천",
            "distance": "풀/하프/10K",
            "organizer": "조선일보",
            "url": "https://www.chuncheonmarathon.com",
            "reg_start": "2026-07-15",
            "reg_end": "2026-09-30",
            "reg_url": "https://www.chuncheonmarathon.com",
            "source": "sample",
        },
        {
            "title": "2026 JTBC 서울마라톤",
            "date": "2026-11-01",
            "location": "서울 잠실",
            "distance": "풀/하프/10K/5K",
            "organizer": "JTBC",
            "url": "",
            "reg_start": "2026-08-01",
            "reg_end": "2026-10-01",
            "reg_url": "",
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
