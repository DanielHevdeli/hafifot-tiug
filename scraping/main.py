import asyncio
import psutil
import speedtest
import csv
import logging
import time
import os
import pandas as pd
from tqdm import tqdm
import random

from curl_cffi.requests import AsyncSession
import aiohttp

from .scrapers.c14 import scrape_async
from .fetch_articles_metadata import main as fetch_all_articles_metadata

ARTICLE_MIN_LENGTH = 300

QUEUE_SIZE = 50
SERVER_MAX_CONCURRENCY = 5
NUM_SCRAPERS = 10

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

LOG_FILE = f"logs/scraping/scrape_{timestamp}.log"
ARTICLES_CSV = "data/raw/articles.csv"
METADATA_CSV = "data/raw/articles_metadata.csv"

os.makedirs("data/raw", exist_ok=True)
os.makedirs("logs/scraping", exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

def read_metadata():
    if not os.path.exists(METADATA_CSV):
        logging.info("Metadata CSV not found, fetching metadata...")
        articles_dict = fetch_all_articles_metadata()
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

def filter_non_scraped_articles(all_articles_metadata, scraped_csv):
    if not os.path.exists(scraped_csv):
        logging.info("Scraped articles CSV not found.")
        return all_articles_metadata

    scraped_df = pd.read_csv(scraped_csv, encoding="utf-8-sig")
    scraped_ids = set(scraped_df["article_id"].astype(str))
    logging.info(f"Found {len(scraped_ids)} scraped articles. Skipping them...")
    return [meta for meta in all_articles_metadata if str(meta["id"]) not in scraped_ids]

def determine_articles_to_scrape(
        all_articles_metadata: list, 
        scraped_csv: str, 
        desired: int | str
    ) -> tuple[list, int | None]:
    # ASSUMING desired=="full" or an int.
    total_articles = len(all_articles_metadata)

    if isinstance(desired, int) and desired > total_articles:
        logging.error(
            f"NUM_DESIRED_ARTICLES ({desired}) is greater than total articles ({total_articles}). Exiting."
        )
        return [], 0

    # Filter out articles already scraped
    non_scraped_articles_metadata = filter_non_scraped_articles(all_articles_metadata, scraped_csv)
    non_scraped_len = len(non_scraped_articles_metadata)
    scraped_len = total_articles - non_scraped_len

    if isinstance(desired, int):
        if scraped_len >= desired:
            logging.info(
                f"Already have {scraped_len} articles, which is >= NUM_DESIRED_ARTICLES ({desired}). Exiting."
            )
            return [], 0
        else:
            actual_num_to_scrape = desired - scraped_len
            logging.info(f"LIMITED MODE: Will scrape {actual_num_to_scrape} articles. (desired - scraped = {desired} - {scraped_len}).")
            return non_scraped_articles_metadata, actual_num_to_scrape

    else:    # desired is str and desired == "full" by assumption
        actual_num_to_scrape = total_articles - scraped_len
        logging.info(f"FULL MODE: Will scrape {actual_num_to_scrape} articles. (total - scraped = {total_articles} - {scraped_len}).")
        return non_scraped_articles_metadata, None

def print_machine_stats():
    logging.info("Starting scrape...")
    logging.info("===== MACHINE STATS =====")
    logging.info(f"CPU cores: {psutil.cpu_count()}")
    for i, pct in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        logging.info(f"Core {i} usage: {pct}%")
    logging.info(f"Available RAM (GB): {round(psutil.virtual_memory().available / 1e9, 2)}")
    # logging.info(f"Download Mbps: {round(speedtest.Speedtest().download() / 1e6, 2)}")
    logging.info("==========================")

def print_scraper_config(desired):
    logging.info("===== SCRAPER CONFIG =====")
    logging.info(f"QUEUE_SIZE: {QUEUE_SIZE}")
    logging.info(f"NUM_SCRAPERS: {NUM_SCRAPERS}")
    logging.info(f"SERVER_MAX_CONCURRENCY: {SERVER_MAX_CONCURRENCY}")
    logging.info(f"ARTICLE_MIN_LENGTH: {ARTICLE_MIN_LENGTH}")
    logging.info(f"NUM_DESIRED_ARTICLES: {desired}")
    logging.info("==========================")

def print_scrape_stats(stats, total_time):
    logging.info("===== SCRAPER STATS =====")
    logging.info(f"Runtime: {total_time:.2f}s")
    logging.info(f"Attempted: {stats['attempted']}")
    logging.info(f"Collected: {stats['collected']}")

    if stats["attempted"] > 0:
        success_rate = stats["collected"] / stats["attempted"]
        error_rate = 1 - success_rate

        logging.info(f"Success rate: {success_rate*100:.2f}%")
        logging.info(f"Error rate: {error_rate*100:.2f}%")
        if stats["errors"]:
            logging.info("===== ERROR BREAKDOWN =====")
            total_errors = sum(stats["errors"].values())
            for k, v in sorted(stats["errors"].items(), key=lambda x: -x[1]):
                pct = (v / stats["attempted"]) * 100 if stats["attempted"] else 0
                logging.info(f"{k}: {v} ({pct:.2f}%)")
            logging.info("===========================")

    if stats['attempted'] == 0:
        logging.info("Avg request: N/A (no attempts)")
    else:
        logging.info(f"Avg request: {stats['time_sum']/stats['attempted']:.3f}s")
    logging.info(f"Req/sec: {stats['attempted']/total_time:.2f}")
    logging.info("==========================")

async def producer(
        tasks: list, 
        queue: asyncio.Queue, 
        stop_event: asyncio.Event
    ):
    try:
        for task in tqdm(tasks):
            if stop_event.is_set():
                print("[PRODUCER] stopping early")
                break

            await queue.put(task)

    except asyncio.CancelledError:
        print("[PRODUCER] cancelled")
        raise

async def consumer(
        name: str,
        queue: asyncio.Queue, 
        session: aiohttp.ClientSession, 
        writer: csv.DictWriter, 
        stats: dict, 
        semaphore: asyncio.Semaphore, 
        lock: asyncio.Lock, 
        stop_event: asyncio.Event,
        article_min_length: int,
        target: int | None
    ):
    try:
        while True:
            if stop_event.is_set() and queue.empty():
                break

            article_metadata = await queue.get()

            try:
                await asyncio.sleep(random.uniform(1.0, 3.0))  # jitter
                async with semaphore:
                    result, req_time, error = await scrape_async(session, article_metadata)

                async with lock:
                    stats["attempted"] += 1
                    stats["time_sum"] += req_time
                    if result and result["length"] >= article_min_length:
                        writer.writerow(result)
                        stats["collected"] += 1
                        logging.info(
                            f"{name}: Collected {result['source']}:{result['article_id']} "
                            f"(length={result['length']}) total={stats['collected']}"
                        )
                        if target is not None and stats["collected"] >= target:
                            stop_event.set()
                    elif result:
                        logging.info(
                            f"{name}: Skipping {result['source']}:{result['article_id']} "
                            f"Too short (length={result['length']})"
                        )
                        stats["errors"]["too_short"] = stats["errors"].get("too_short", 0) + 1

                    else: # result is None
                        logging.error(f"FAILED: article_id: {article_metadata["id"]}, status: {error}")
                        stats["errors"][error] = stats["errors"].get(error, 0) + 1

            finally:
                queue.task_done()

    except asyncio.CancelledError:
        print(f"[{name}] cancelled")
        raise

async def main_async(all_articles_metadata: list, desired: int | str):
    queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    semaphore = asyncio.Semaphore(SERVER_MAX_CONCURRENCY)
    stop_event = asyncio.Event()
    lock = asyncio.Lock()

    stats = {
        "attempted": 0,
        "collected": 0,
        "time_sum": 0,
        "errors": {}
    }

    non_scraped_articles_metadata, target = determine_articles_to_scrape(
        all_articles_metadata=all_articles_metadata,
        scraped_csv=ARTICLES_CSV,
        desired=desired
    )

    if target is not None and target == 0:
        return stats  # nothing to scrape, return empty stats

    # timeout = aiohttp.ClientTimeout(total=15)
    # async with aiohttp.ClientSession(timeout=timeout) as session:
    async with AsyncSession() as session:
        with open(ARTICLES_CSV, "a", newline="", encoding="utf-8-sig") as f:

            writer = csv.DictWriter(
                f,
                fieldnames=["source", "date", "article_id", "wordsCount", "length", "author", "text"]
            )
            
            # write header only if file is new/empty
            if f.tell() == 0:
                writer.writeheader()

            producer_task = asyncio.create_task(
                producer(tasks=non_scraped_articles_metadata, 
                         queue=queue, 
                         stop_event=stop_event
                )
            )

            consumers = [
                asyncio.create_task(
                    consumer(
                        name=f"Scraper-{i}",
                        queue=queue,
                        session=session,
                        writer=writer,
                        stats=stats,
                        semaphore=semaphore,
                        lock=lock,
                        stop_event=stop_event,
                        article_min_length=ARTICLE_MIN_LENGTH,
                        target=target
                    )
                )
                for i in range(NUM_SCRAPERS)
            ]

            if target is None:
                # FULL MODE: process everything
                await producer_task
                await queue.join()  # wait until all tasks are done

                stop_event.set() # stop consumers nicely
                for c in consumers:
                    c.cancel()  # cancel in case they are waiting on queue

            else:
                # LIMIT MODE: stop when target reached
                await stop_event.wait() # wait until target is reached
                print(f"[MAIN] reached target ({target} articles), stopping early")
                producer_task.cancel()
                for c in consumers:
                    c.cancel()

            await asyncio.gather(producer_task, *consumers, return_exceptions=True)

    return stats

def get_num_desired_articles():
    desired = input(f"Enter number of articles to scrape (or 'full' for all): ")
    if desired.strip().lower() == "full":
        return "full"
    else:
        try:
            num = int(desired)
            if num < 0:
                raise ValueError("Number must be non-negative.")
            return num
        except ValueError as e:
            print(f"Invalid input for number of articles: {e}. Exiting.")
            exit(1)

def main():

    desired = get_num_desired_articles()

    print_machine_stats()
    print_scraper_config(desired)

    all_articles_metadata = read_metadata()

    start = time.perf_counter()
    stats = asyncio.run(main_async(all_articles_metadata, desired))
    total_time = time.perf_counter() - start

    print_scrape_stats(stats, total_time)

if __name__ == "__main__":
    main()
