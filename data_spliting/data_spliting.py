import os
import pandas as pd
from pathlib import Path
import time

RAW_ARTICLES_FILE = "data/raw/articles_clean.jsonl"
RAW_METADATA_FILE = "data/raw/articles_metadata.csv"

DATA_FOLDER = Path("data/data_split")

FUTURE_RATIO = 0.30
BLACK_RATIO = 0.30
# present: 40%

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

LOG_FOLDER = "logs/data_splitting"
os.makedirs(LOG_FOLDER, exist_ok=True)

LOG_FILE = f"{LOG_FOLDER}/data_splitting_{timestamp}.log"

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def check_data_quality(df):
    if df.isnull().values.any():
        raise ValueError("Data contains missing values.")
    if df.duplicated().any():
        raise ValueError("Data contains duplicate rows.")
    log("Data quality check passed: No missing values or duplicates.")

def split_data(articles_file, metadata_file, data_folder):

    data_folder.mkdir(parents=True, exist_ok=True)
    log("Loading datasets...")

    articles_df = pd.read_json(articles_file, lines=True)
    metadata_df = pd.read_csv(metadata_file, encoding="utf-8")

    check_data_quality(articles_df)

    if "article_id" not in articles_df.columns:
        raise ValueError("articles_clean.jsonl must contain 'article_id' column")

    if "id" not in metadata_df.columns:
        raise ValueError("metadata.csv must contain 'id' column")

    total_rows = len(articles_df)

    log(f"Total articles: {total_rows}")
    log(f"Total metadata rows: {len(metadata_df)}")

    articles_df["date"] = pd.to_datetime(articles_df["date"])

    # --------------------------------
    # Sort by newest first
    # --------------------------------
    df_sorted = articles_df.sort_values(by="date", ascending=False)

    future_rows = int(total_rows * FUTURE_RATIO)
    black_rows = int(total_rows * BLACK_RATIO)
    present_rows = total_rows - future_rows - black_rows

    log(f"Future rows: {future_rows}")
    log(f"Black rows: {black_rows}")
    log(f"Present rows: {present_rows}")

    # --------------------------------
    # FUTURE (most recent)
    # --------------------------------
    future_df = df_sorted.head(future_rows)
    remaining_df = df_sorted.iloc[future_rows:]
    log(f"Future date range: {future_df['date'].min()} → {future_df['date'].max()}")

    # --------------------------------
    # BLACK (random)
    # --------------------------------
    black_df = remaining_df.sample(n=black_rows, random_state=42)

    # --------------------------------
    # PRESENT (remaining)
    # --------------------------------
    present_df = remaining_df.drop(black_df.index)

    splits = {
        "future": future_df,
        "black": black_df,
        "present": present_df,
    }

    # --------------------------------
    # Count unused metadata rows
    # --------------------------------
    unused_metadata = metadata_df[~metadata_df["id"].isin(articles_df["article_id"])]
    log(f"Unused metadata rows (ignored): {len(unused_metadata)}")

    # --------------------------------
    # Save splits (articles as JSONL, metadata as CSV)
    # --------------------------------
    for split_name, articles_split in splits.items():

        split_dir = data_folder / split_name
        split_dir.mkdir(parents=True, exist_ok=True)

        split_ids = articles_split["article_id"]
        metadata_split = metadata_df[metadata_df["id"].isin(split_ids)]

        articles_path = split_dir / "articles.jsonl"
        metadata_path = split_dir / "articles_metadata.csv"

        articles_split.to_json(
            articles_path,
            orient="records",   # each row is a json
            lines=True,
            force_ascii=False   # keep Hebrew and imojiis
        )

        metadata_split.to_csv(metadata_path, index=False, encoding="utf-8")

        log(f"{split_name} saved:")
        log(f"  articles: {len(articles_split)}")
        log(f"  metadata: {len(metadata_split)}")

    log("Data splitting completed successfully.")

if __name__ == "__main__":

    split_data(
        RAW_ARTICLES_FILE,
        RAW_METADATA_FILE,
        DATA_FOLDER,
    )
