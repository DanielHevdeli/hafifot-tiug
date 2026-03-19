import json
import csv
import pathlib
from typing import Dict, Any, Generator

def read_jsonl(file_path: pathlib.Path):
    if not file_path.exists():
        return
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

def append_jsonl(file_path: pathlib.Path, record: Dict[str, Any]):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_csv_articles(file_path: pathlib.Path) -> Generator[Dict, None, None]:
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        return

    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield  {
                "article_id": row["article_id"],
                "text": row["text"],
                "source": row["source"],
                "date": row["date"],
                "length": int(row["length"])
            }
