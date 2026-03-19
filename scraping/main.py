import psutil
import speedtest
import requests
import csv
import logging
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import time
import os

from .scrapers.c14 import scrape as scrape_c14
from .all_archives import get_all_articles_metadata

MIN_LENGTH = 500
NUM_DESIRED_ARTICLES = 10

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

LOG_FILE = f"logs/scraping/scrape_{timestamp}.log"
ARTICLES_CSV = "data/raw/articles.csv"
METADATA_CSV = "data/raw/articles_metadata.csv"

os.makedirs("data/raw", exist_ok=True)
os.makedirs("logs/scraping", exist_ok=True)

MAX_WORKERS = 10
MAX_IN_FLIGHT = 30

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

def scrape_article(article_metadata):
    return scrape_c14(session, article_metadata)

def read_metadata():
    if not os.path.exists(METADATA_CSV):
        logging.info("Metadata CSV not found, fetching metadata...")
        articles_dict = get_all_articles_metadata()
        # save metadata after fetching
        with open(METADATA_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "date", "wordsCount", "author", "archive_ids"])
            writer.writeheader()
            for aid, meta in articles_dict.items():
                row = {
                    "id": aid,
                    "date": meta.get("date"),
                    "wordsCount": meta.get("wordsCount"),
                    "author": meta.get("author"),
                    # Convert list to comma-separated string
                    "archive_ids": ",".join(map(str, meta.get("archive_ids", [])))
                }
                writer.writerow(row)
        # return the metadata as a list of dicts for scraping. ignore the archive_ids field since we won't use it for scraping.
        return [
            {
                "id": aid,
                "date": meta.get("date"),
                "wordsCount": meta.get("wordsCount"),
                "author": meta.get("author")
            }
            for aid, meta in articles_dict.items()
        ]
    else:
        logging.info("Metadata CSV found, reading metadata...")
        articles = []
        with open(METADATA_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row.pop("archive_ids", None)
                articles.append(row)
        return articles

def main():
    logging.info("Starting scrape...")
    logging.info(f"CPU cores: {psutil.cpu_count()}")
    for i, pct in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        logging.info(f"Core {i} usage: {pct}%")
    logging.info(f"Available RAM (GB): {round(psutil.virtual_memory().available / 1e9, 2)}")
    logging.info(f"Download Mbps: {round(speedtest.Speedtest().download() / 1e6, 2)}")
    logging.info(f"MAX_WORKERS: {MAX_WORKERS}")
    logging.info(f"MIN_LENGTH: {MIN_LENGTH}")
    logging.info(f"NUM_DESIRED_ARTICLES: {NUM_DESIRED_ARTICLES}")

    all_articles_metadata = read_metadata()
    
    collected = 0
    requests_attempted = 0
    requests_time_sum = 0

    total_start_time = time.perf_counter()

    with open(ARTICLES_CSV, "w", newline="", encoding="utf-8-sig") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=["source", "date", "article_id", "wordsCount", "length", "author", "text"]
        )

        writer.writeheader()

        with ThreadPoolExecutor(MAX_WORKERS) as executor:
            futures = set()
            articles_iter = iter(all_articles_metadata)

            while len(futures) < MAX_IN_FLIGHT:
                article_metadata = next(articles_iter, None)
                if article_metadata is None:
                    break
                futures.add(executor.submit(scrape_article, article_metadata))

            while futures and collected < NUM_DESIRED_ARTICLES:
                done, futures = wait(
                    futures,
                    return_when=FIRST_COMPLETED
                )

                for future in done:
                    result, request_time = future.result()
                    requests_attempted += 1
                    requests_time_sum += request_time

                    if result:
                        if result["length"] < MIN_LENGTH:
                            logging.info(
                                f"Skipping {result['source']}:{result['article_id']} "
                                f"Too short (length={result['length']})"
                            )
                        else:
                            writer.writerow(result)
                            collected += 1
                            logging.info(
                                f"Collected {result['source']}:{result['article_id']} "
                                f"(length={result['length']}) total={collected}"
                            )

                        if collected >= NUM_DESIRED_ARTICLES:
                            break

                    article_metadata = next(articles_iter, None)
                    if article_metadata is not None:
                        futures.add(
                            executor.submit(scrape_article, article_metadata)
                        )

    total_runtime = time.perf_counter() - total_start_time

    avg_request = requests_time_sum / requests_attempted if requests_attempted else 0
    req_per_sec = requests_attempted / total_runtime if total_runtime else 0

    logging.info("===== SCRAPER STATS =====")
    logging.info(f"Total runtime: {total_runtime:.2f} sec")
    logging.info(f"Requests attempted: {requests_attempted}")
    logging.info(f"Collected articles: {collected}")
    logging.info(f"Average request time: {avg_request:.3f} sec")
    logging.info(f"Requests/sec: {req_per_sec:.2f}")

if __name__ == "__main__":
    main()
