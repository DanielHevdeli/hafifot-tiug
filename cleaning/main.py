import pandas as pd
import re
import logging
from pathlib import Path
import time
import os

DEFAULT_AUTHOR = "מערכת C14"

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
INPUT_FILE = "data/raw/articles.csv"
OUTPUT_FILE = "data/raw/articles_clean.jsonl"
CHUNK_SIZE = 10000

EXPECTED_COLUMNS = [
    "source",
    "date",
    "article_id",
    "wordsCount",
    "length",
    "author",
    "text"
]

os.makedirs("logs/cleaning", exist_ok=True)

logging.basicConfig(
    filename=f"logs/cleaning/clean_{timestamp}.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger()

def clean_text(text: str) -> str:
    if pd.isna(text):
        return ""

    text = str(text)
    text = text.replace("\x00", "")
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def clean_csv_to_jsonl():
    logger.info("Starting CSV cleaning...")
    logger.info(f"Input file: {INPUT_FILE}")

    if Path(OUTPUT_FILE).exists():
        Path(OUTPUT_FILE).unlink()

    total_rows = 0
    kept_rows = 0
    duplicate_ids = set()
    first_chunk = True

    for chunk_idx, chunk in enumerate(
        pd.read_csv(
            INPUT_FILE,
            encoding="utf-8",
            dtype=str,
            chunksize=CHUNK_SIZE,
            on_bad_lines="skip"
        )
    ):
        logger.info(f"Processing chunk {chunk_idx}")
        total_rows += len(chunk)

        chunk.columns = [c.strip().lower() for c in chunk.columns]
        chunk = chunk[[c for c in EXPECTED_COLUMNS if c in chunk.columns]]

        before_drop = len(chunk)

        chunk = chunk.dropna(subset=["article_id", "text"])
        removed_missing = before_drop - len(chunk)

        chunk["text"] = chunk["text"].apply(clean_text)

        chunk["author"] = chunk["author"].fillna(DEFAULT_AUTHOR)

        before_empty = len(chunk)
        chunk = chunk[chunk["text"].str.len() > 0]
        removed_empty = before_empty - len(chunk)

        before_dup = len(chunk)
        chunk = chunk[~chunk["article_id"].isin(duplicate_ids)]
        duplicate_ids.update(chunk["article_id"])
        removed_dup = before_dup - len(chunk)

        kept_rows += len(chunk)

        logger.info(
            f"Chunk {chunk_idx}: "
            f"rows={len(chunk)} "
            f"removed_missing={removed_missing} "
            f"removed_empty={removed_empty} "
            f"removed_duplicates={removed_dup}"
        )

        chunk.to_json(
            OUTPUT_FILE,
            orient="records",
            lines=True,
            force_ascii=False,
            mode="w" if first_chunk else "a"
        )

        first_chunk = False

    logger.info("Cleaning finished")
    logger.info(f"Total rows read: {total_rows}")
    logger.info(f"Total rows kept: {kept_rows}")

if __name__ == "__main__":
    clean_csv_to_jsonl()
