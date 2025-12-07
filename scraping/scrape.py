import requests
from bs4 import BeautifulSoup
import pandas as pd

START_ID = 100000
END_ID = 999999
MIN_LENGTH = 800
TARGET_LONG_POSTS = 10000

def get_question_posts(question_id):
    url = f"https://www.askp.co.il/question/{question_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        posts = []

        # Question text + date
        question_div = soup.find('div', class_='question_content')
        q_date_span = soup.find('span', id='spn_question_written_date')

        if question_div:
            q_text = question_div.get_text(separator="\n").strip()
            raw_q_date = q_date_span.get_text(separator=" ").strip() if q_date_span else ""
            parsed_q_date = _parse_hebrew_date(raw_q_date)

            posts.append({
                'text': q_text,
                'date': parsed_q_date or raw_q_date
            })

        return posts
    except requests.RequestException as e:
        print(f"Error fetching {question_id}: {e}")
        return []

def _parse_hebrew_date(raw_text):
    """Attempt to extract a date and time from the Hebrew timestamp text

    Example input: 'כתבה את השאלה ב-17/11/25 בשעה 13:38'
    We'll extract the date part (dd/mm/yy) and time (HH:MM) and return
    a simplified ISO-like string 'YYYY-MM-DD HH:MM' (assumes 20xx for yy).
    If parsing fails, return None.
    """
    import re

    if not raw_text:
        return None

    # Look for dd/mm/yy and optional HH:MM
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2})", raw_text)
    t = re.search(r"(\d{1,2}:\d{2})", raw_text)

    if not m:
        return None

    day, month, yy = m.groups()
    hour_min = t.group(1) if t else "00:00"

    # Normalize year to 4 digits. Assume 20xx for small year values.
    year = int(yy)
    if year <= 30:
        year += 2000
    else:
        # fallback heuristic for older posts
        year += 1900

    try:
        return f"{year:04d}-{int(month):02d}-{int(day):02d} {hour_min}"
    except Exception:
        return None

def main():
    posts_length = {}
    records = []
    num_posts = 0
    qid = START_ID

    while num_posts < TARGET_LONG_POSTS and qid <= END_ID:
        posts = get_question_posts(qid)

        # posts is a list of dicts (role, text, date). Save each post that
        # satisfies the length requirement as a separate row
        for idx, p in enumerate(posts):
            text = p.get('text', '')
            if text and len(text) >= MIN_LENGTH:
                with open("scrape.log", "a", encoding="utf-8") as log_file:
                    log_file.write(f"Fetched LONG post from {qid} (role={p.get('role')}, length={len(text)})\n")

                posts_length[f"{qid}-{idx}"] = len(text)
                num_posts += 1

                records.append({
                    "question_id": qid,
                    "length": len(text),
                    "date": p.get('date', ''),
                    "text": text
                })

        if not posts or all((not (p.get('text') and len(p.get('text')) >= MIN_LENGTH)) for p in posts):
            with open("scrape.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"Skipped question {qid} (no long posts or empty)\n")

        qid += 1

    df_csv = pd.DataFrame(records)
    df_csv.to_csv("posts.csv", index=False, encoding="utf-8-sig")
    print("Saved posts.csv with", len(df_csv), "rows.")

if __name__ == "__main__":
    main()
