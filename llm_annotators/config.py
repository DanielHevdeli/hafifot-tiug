import pathlib

LABELS = {
    "opinion": 0,
    "fact": 1
}

DATA_FILE = pathlib.Path("./data/split_data/present.csv")
RESULTS_DIR = pathlib.Path("./data/labels/present")
LOGS_DIR = pathlib.Path("./logs/annotator-logs")      
ERRORS_DIR = pathlib.Path("./logs/annotator-errors")

MODELS_CONFIG = {
    "openai/gpt-oss-120b": {
        "concurrency": 10,
        "batch_size": 5,
        "timeout": 30,
        "max_retries": 3
    },
    "meta-llama/llama4-scout": {
        "concurrency": 5,
        "batch_size": 3,
        "timeout": 45,
        "max_retries": 3
    },
    "mimotron/some-model": {
        "concurrency": 8,
        "batch_size": 4,
        "timeout": 40,
        "max_retries": 3
    }
}
