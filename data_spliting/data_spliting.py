import os
import pandas as pd
from pathlib import Path
import time

# ===============================
# CONFIG
# ===============================

RAW_DATA_FILE = "data/raw/articles.csv"
DATA_FOLDER = Path("data/data_split")
os.makedirs("data/data_split", exist_ok=True)

FUTURE_RATIO = 0.30
BLACK_RATIO = 0.30
PRESENT_RATIO = 0.40

timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
LOG_FOLDER = f"logs/data_splitting"
os.makedirs(LOG_FOLDER, exist_ok=True)
LOG_FILE = f"{LOG_FOLDER}/data_splitting_{timestamp}.log"

# ===============================
# UTILITIES
# ===============================

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


# ===============================
# SPLIT FUNCTION
# ===============================

def split_data(input_file, data_folder):

    data_folder.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_file)

    check_data_quality(df)

    total_rows = len(df)
    log(f"Total rows: {total_rows}")

    df["date"] = pd.to_datetime(df["date"])

    df_sorted = df.sort_values(by="date", ascending=False).reset_index(drop=True)

    # --------------------------------
    # Compute dynamic split sizes
    # --------------------------------

    future_rows = int(total_rows * FUTURE_RATIO)
    black_rows = int(total_rows * BLACK_RATIO)

    # remainder goes to present
    present_rows = total_rows - future_rows - black_rows

    log(f"Future rows: {future_rows}")
    log(f"Black rows: {black_rows}")
    log(f"Present rows: {present_rows}")

    # --------------------------------
    # FUTURE (most recent posts)
    # --------------------------------
    future_df = df_sorted.head(future_rows)

    log(
        f"Future date range: {future_df['date'].min()} → {future_df['date'].max()}"
    )

    future_df.to_csv(data_folder / "future.csv", index=False)

    remaining_df = df_sorted.iloc[future_rows:]
    # --------------------------------
    # BLACK (random)
    # --------------------------------

    black_df = remaining_df.sample(n=black_rows, random_state=42)

    # --------------------------------
    # PRESENT (remaining)
    # --------------------------------

    present_df = remaining_df.drop(black_df.index)

    # --------------------------------
    # Save
    # --------------------------------

    black_df.to_csv(data_folder / "black.csv", index=False)
    present_df.to_csv(data_folder / "present.csv", index=False)

    log(f"Saved future: {len(future_df)} rows")
    log(f"Saved black: {len(black_df)} rows")
    log(f"Saved present: {len(present_df)} rows")

    log("Data splitting completed successfully.")


# ===============================
# MAIN
# ===============================

if __name__ == "__main__":
    split_data(RAW_DATA_FILE, DATA_FOLDER)