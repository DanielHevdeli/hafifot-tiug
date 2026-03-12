import psutil
import speedtest
import requests
from bs4 import BeautifulSoup
import csv
import logging
import re
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import time
import os
# ===============================
# CONFIG
# ===============================

START_ID = 200000
END_ID = 999999
MIN_LENGTH = 500
NUM_DESIRED_POSTS = 1000

BASE_URL = "https://www.askp.co.il/question/"

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"logs/scrape_{timestamp}.log"
POSTS_CSV = "data/raw/posts.csv"
os.makedirs("data/raw", exist_ok=True)

REQUEST_TIMEOUT = 10

MAX_WORKERS = 20
MAX_IN_FLIGHT = 60   # bounded futures


# ===============================
# LOGGING
# ===============================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

# ===============================
# SESSION
# ===============================

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# ===============================
# DATE PARSER
# ===============================

def parse_hebrew_date(raw_text):

    if not raw_text:
        return None

    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2})", raw_text)
    t = re.search(r"(\d{1,2}:\d{2})", raw_text)

    if not m:
        return None

    day, month, yy = m.groups()
    hour_min = t.group(1) if t else "00:00"

    year = int(yy)
    year += 2000 if year <= 30 else 1900

    return f"{year:04d}-{int(month):02d}-{int(day):02d} {hour_min}"


# ===============================
# SCRAPER
# ===============================

def scrape_question(qid):
    start = time.perf_counter()
    try:

        r = session.get(f"{BASE_URL}{qid}", timeout=REQUEST_TIMEOUT)
        elaped = time.perf_counter() - start
        if r.status_code != 200:
            return None, elaped

        soup = BeautifulSoup(r.text, "html.parser")

        question_div = soup.find("div", class_="question_content")

        if not question_div:
            return None, elaped

        text = question_div.get_text("\n", strip=True)

        if len(text) < MIN_LENGTH:
            return None, elaped

        date_span = soup.find("span", id="spn_question_written_date")

        raw_date = date_span.get_text(" ", strip=True) if date_span else ""
        date = parse_hebrew_date(raw_date) or raw_date

        return {
            "question_id": qid,
            "length": len(text),
            "date": date,
            "text": text
        }, elaped

    except Exception as e:

        logging.warning(f"Error {qid}: {e}")
        return None, elaped


# ===============================
# MAIN
# ===============================

def main():

    logging.info("Starting scrape...")
    logging.info(f"CPU cores: {psutil.cpu_count()}")
    for i, pct in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        logging.info(f"Core {i} usage: {pct}%")
    logging.info(f"Available RAM (GB): {round(psutil.virtual_memory().available / 1e9, 2)}")
    logging.info(f"Download Mbps: {round(speedtest.Speedtest().download() / 1e6, 2)}")

    collected = 0
    requests_attempted = 0
    requests_time_sum = 0
    next_qid = START_ID

    total_start_time = time.perf_counter()

    with open(POSTS_CSV, "w", newline="", encoding="utf-8-sig") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=["question_id", "length", "date", "text"]
        )

        writer.writeheader()

        with ThreadPoolExecutor(MAX_WORKERS) as executor:

            futures = set()

            # fill initial window
            while len(futures) < MAX_IN_FLIGHT and next_qid <= END_ID:
                futures.add(executor.submit(scrape_question, next_qid))
                next_qid += 1

            while futures and collected < NUM_DESIRED_POSTS:

                done, futures = wait(
                    futures,
                    return_when=FIRST_COMPLETED
                )

                for future in done:

                    result, request_time = future.result()
                    requests_attempted += 1
                    requests_time_sum += request_time

                    if result:

                        writer.writerow(result)

                        collected += 1

                        logging.info(
                            f"Collected {result['question_id']} "
                            f"(length={result['length']}) total={collected}"
                        )

                        if collected >= NUM_DESIRED_POSTS:
                            break

                    # submit next task
                    if next_qid <= END_ID:
                        futures.add(
                            executor.submit(scrape_question, next_qid)
                        )
                        next_qid += 1

    total_end_time = time.perf_counter()
    logging.info(f"Finished. Collected {collected} posts.")
    total_runtime = total_end_time - total_start_time
    avg_request = requests_time_sum / requests_attempted if requests_attempted else 0
    req_per_sec = requests_attempted / total_runtime if total_runtime else 0
    logging.info("\n===== SCRAPER STATS =====")
    logging.info(f"Total runtime: {total_runtime:.2f} sec")
    logging.info(f"Requests attempted: {requests_attempted}")
    logging.info(f"Collected posts: {collected}")
    logging.info(f"Average request time: {avg_request:.3f} sec")
    logging.info(f"Requests/sec: {req_per_sec:.2f}")

if __name__ == "__main__":
    main()