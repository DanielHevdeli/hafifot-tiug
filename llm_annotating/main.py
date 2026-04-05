import time
from multiprocessing import Process

from .run_annotation import main as run_annotation

DESIRED = "full"

SET_TYPES = [
    # "present",
    # "black",
    "future"
]

MODELS = [
    # "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    # "openai/gpt-oss-120b",
    "nvidia/nemotron-3-nano-30b-a3b-bf16"
]

def main():

    processes = []

    for model in MODELS:
        for set_type in SET_TYPES:
            p = Process(
                target=run_annotation,
                kwargs={
                    "set_type": set_type,
                    "model_name": model,
                    "desired": DESIRED
                }
            )
            p.start()
            processes.append(p)

    for p in processes:
        p.join()
    print("All processes finished.")

if __name__ == "__main__":
    main()
    # run with python -m llm_annotating.main