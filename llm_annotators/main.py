# run using python -m llm_annotators.main

import asyncio
from pathlib import Path
import logging
from .config import DATA_FILE, RESULTS_DIR, LOGS_DIR, ERRORS_DIR, MODELS_CONFIG
from .prompts.v1 import prompt as PROMPT
from .utils.io_utils import read_jsonl, read_csv_articles
from .annotator import GenericLLMAnnotator

def setup_logger(name, log_file):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


async def run_model(model_name: str, prompt: str):
    cfg = MODELS_CONFIG[model_name]

    results_file = RESULTS_DIR / f"{model_name}.jsonl"
    errors_file = ERRORS_DIR / f"{model_name}_errors.jsonl"
    logger = setup_logger(model_name, LOGS_DIR / f"{model_name}.log")

    processed_ids = set()
    if results_file.exists():
        for record in read_jsonl(results_file):
            processed_ids.add(record["article_id"])

    articles = []
    for article in read_csv_articles(DATA_FILE): 
        if article["article_id"] not in processed_ids:
            articles.append(article)
    logger.info(f"{len(articles)} articles to process for {model_name}")

    annotator = GenericLLMAnnotator(
        model_name=model_name,
        results_path=results_file,
        errors_path=errors_file,
        concurrency=cfg["concurrency"],
        timeout=cfg["timeout"],
        max_retries=cfg["max_retries"]
    )

    batch_size = cfg["batch_size"]

    total = len(articles)
    for i in range(0, total, batch_size):
        if i + batch_size > total: # handle last batch
            batch_size = total - i
        batch = articles[i:i + batch_size]
        await annotator.annotate_articles_batch(batch, prompt)
        logger.info(f"{min(i+batch_size, total)} / {total} processed for {model_name}")

# ===========================
# main
# ===========================
async def main():
    tasks = [run_model(model_name, PROMPT) for model_name in MODELS_CONFIG.keys()]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())