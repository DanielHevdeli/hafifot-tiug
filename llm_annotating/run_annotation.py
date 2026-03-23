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
import json

from curl_cffi.requests import AsyncSession
import aiohttp

from .annotators.llm import annotate_async

QUEUE_SIZE = 50
SERVER_MAX_CONCURRENCY = 5
NUM_ANNOTATORS = 10

SET_TYPE = "d"
ARTICLES_JSONL = "d"
ANNOTATED_CSV = "d"
MODEL_NAME = "d"
LOG_FILE = "d"

def read_articles():
    if not os.path.exists(ARTICLES_JSONL):
        logging.error("Articles JSONL not found, exiting...")
        exit(1)
    else:
        logging.info("Articles JSONL found, reading articles...")
        articles = []
        with open(ARTICLES_JSONL, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:  # skip empty lines
                    articles.append(json.loads(line))
        return articles

def filter_non_annotated_articles(all_articles, annotated_csv):
    if not os.path.exists(annotated_csv):
        logging.info("Annotated articles CSV not found.")
        return all_articles

    annotated_df = pd.read_csv(annotated_csv, encoding="utf-8-sig")
    annotated_ids = set(annotated_df["article_id"].astype(str))
    logging.info(f"Found {len(annotated_ids)} annotated articles. Skipping them...")
    return [a for a in all_articles if str(a["article_id"]) not in annotated_ids]

def determine_articles_to_annotate(
        all_articles: list, 
        annotated_csv: str, 
        desired: int | str
    ) -> tuple[list, int | None]:
    # ASSUMING desired=="full" or an int.
    total_articles = len(all_articles)

    if isinstance(desired, int) and desired > total_articles:
        logging.error(
            f"NUM_DESIRED_ARTICLES ({desired}) is greater than total articles ({total_articles}). Exiting."
        )
        return [], 0

    # Filter out articles already annotated
    non_annotated_articles = filter_non_annotated_articles(all_articles, annotated_csv)
    non_annotated_len = len(non_annotated_articles)
    annotated_len = total_articles - non_annotated_len

    if isinstance(desired, int):
        if annotated_len >= desired:
            logging.info(
                f"Already have {annotated_len} articles, which is >= NUM_DESIRED_ARTICLES ({desired}). Exiting."
            )
            return [], 0
        else:
            actual_num_to_annotate = desired - annotated_len
            logging.info(f"LIMITED MODE: Will annotate {actual_num_to_annotate} articles. (desired - annotated = {desired} - {annotated_len}).")
            return non_annotated_articles, actual_num_to_annotate

    else:    # desired is str and desired == "full" by assumption
        actual_num_to_annotate = total_articles - annotated_len
        logging.info(f"FULL MODE: Will annotate {actual_num_to_annotate} articles. (total - annotated = {total_articles} - {annotated_len}).")
        return non_annotated_articles, None

def print_machine_stats():
    logging.info("Starting annotate...")
    logging.info("===== MACHINE STATS =====")
    logging.info(f"CPU cores: {psutil.cpu_count()}")
    for i, pct in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        logging.info(f"Core {i} usage: {pct}%")
    logging.info(f"Available RAM (GB): {round(psutil.virtual_memory().available / 1e9, 2)}")
    # logging.info(f"Download Mbps: {round(speedtest.Speedtest().download() / 1e6, 2)}")
    logging.info("==========================")

def print_annotator_config(desired):
    logging.info("===== ANNOTATOR CONFIG =====")
    logging.info(f"SET_TYPE: {SET_TYPE}")
    logging.info(f"MODEL_NAME: {MODEL_NAME}")
    logging.info(f"QUEUE_SIZE: {QUEUE_SIZE}")
    logging.info(f"NUM_ANNOTATORS: {NUM_ANNOTATORS}")
    logging.info(f"SERVER_MAX_CONCURRENCY: {SERVER_MAX_CONCURRENCY}")
    logging.info(f"NUM_DESIRED_ARTICLES: {desired}")
    logging.info("==========================")

def print_annotate_stats(stats, total_time):
    logging.info("===== ANNOTATOR STATS =====")
    logging.info(f"Runtime: {total_time:.2f}s")
    logging.info(f"Attempted: {stats['attempted']}")
    logging.info(f"Annotated: {stats['annotated']}")

    if stats["attempted"] > 0:
        success_rate = stats["annotated"] / stats["attempted"]
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
        target: int | None,
        model_name: str
    ):
    try:
        while True:
            if stop_event.is_set() and queue.empty():
                break

            article = await queue.get()

            try:
                await asyncio.sleep(random.uniform(1.0, 3.0))  # jitter
                async with semaphore:
                    result, req_time, error = await annotate_async(
                        session, article, model_name
                    )

                async with lock:
                    stats["attempted"] += 1
                    stats["time_sum"] += req_time
                    if result:
                        writer.writerow(result)
                        stats["annotated"] += 1
                        logging.info(
                            f"{name}: Annotated {result['source']}:{result['article_id']} "
                            f"total={stats['annotated']}"
                        )
                        if target is not None and stats["annotated"] >= target:
                            stop_event.set()
                    else: # result is None
                        logging.error(f"FAILED: article_id: {article["article_id"]}, status: {error}")
                        stats["errors"][error] = stats["errors"].get(error, 0) + 1

            finally:
                queue.task_done()

    except asyncio.CancelledError:
        print(f"[{name}] cancelled")
        raise

async def main_async(all_articles: list, desired: int | str):
    queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    semaphore = asyncio.Semaphore(SERVER_MAX_CONCURRENCY)
    stop_event = asyncio.Event()
    lock = asyncio.Lock()

    stats = {
        "attempted": 0,
        "annotated": 0,
        "time_sum": 0,
        "errors": {}
    }

    non_annotated_articles, target = determine_articles_to_annotate(
        all_articles=all_articles,
        annotated_csv=ANNOTATED_CSV,
        desired=desired
    )

    if target is not None and target == 0:
        return stats  # nothing to annotate, return empty stats

    # timeout = aiohttp.ClientTimeout(total=15)
    # async with aiohttp.ClientSession(timeout=timeout) as session:
    async with AsyncSession() as session:
        with open(ANNOTATED_CSV, "a", newline="", encoding="utf-8-sig") as f:

            writer = csv.DictWriter(
                f,
                fieldnames=["source", "article_id", "label"]
            )
            
            # write header only if file is new/empty
            if f.tell() == 0:
                writer.writeheader()

            producer_task = asyncio.create_task(
                producer(tasks=non_annotated_articles, 
                         queue=queue, 
                         stop_event=stop_event
                )
            )

            consumers = [
                asyncio.create_task(
                    consumer(
                        name=f"Annotator-{i}",
                        queue=queue,
                        session=session,
                        writer=writer,
                        stats=stats,
                        semaphore=semaphore,
                        lock=lock,
                        stop_event=stop_event,
                        target=target,
                        model_name=MODEL_NAME
                    )
                )
                for i in range(NUM_ANNOTATORS)
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
    desired = input(f"Enter number of articles to annotate (or 'full' for all): ")
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

def main(set_type: str, model_name: str, desired=None, timestamp=None):
    global MODEL_NAME, SET_TYPE, ARTICLES_JSONL, ANNOTATED_CSV, LOG_FILE

    MODEL_NAME = model_name
    SET_TYPE = set_type
    ARTICLES_JSONL = f"data/data_split/{set_type}/articles.jsonl"
    ANNOTATED_CSV = f"data/data_split/{set_type}/annotations/{model_name}.csv"
    model_first_name = model_name.split("/")[0] if "/" in model_name else model_name
    os.makedirs(f"data/data_split/{set_type}/annotations/{model_first_name}", exist_ok=True)

    if timestamp == None:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE = f"logs/annotating/{SET_TYPE}/{MODEL_NAME}/{timestamp}.log"
    os.makedirs(f"logs/annotating/{SET_TYPE}/{MODEL_NAME}", exist_ok=True)
    
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(message)s"
    )
    
    if desired == None:
        desired = get_num_desired_articles()

    print_machine_stats()
    print_annotator_config(desired)

    all_articles = read_articles()

    start = time.perf_counter()
    stats = asyncio.run(main_async(all_articles, desired))
    total_time = time.perf_counter() - start

    print_annotate_stats(stats, total_time)

if __name__ == "__main__":
    model_name = "shalom/lachem"
    set_type = "black"
    main(set_type=set_type, model_name=model_name)
