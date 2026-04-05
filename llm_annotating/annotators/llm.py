import time
import asyncio
import random
import os
import json
from dotenv import load_dotenv

from ..prompt import SYSTEM_PROMPT, LABELS

URL = "https://OPENAI_COMPATIBLE_API/v1/chat/completions"

load_dotenv()
bearer_token = os.getenv("API_KEY")

def get_label(data):
    try:
        obj = json.loads(data)
        content = obj["choices"][0]["message"]["content"].lower()

        for label in LABELS.values():
            if label in content:
                return label

        return "unknown"

    except Exception:
        return None

async def annotate_async(session, article, model_name):
    source = article["source"]
    article_id = article["article_id"]
    text = article["text"]

    start = time.perf_counter()

    try:
        # jitter helps avoid rate-limit / bot heuristics
        # await asyncio.sleep(random.uniform(0.3, 1.0))

        payload = {
            "model": model_name,
            "temperature": 0,
            # "max_tokens": 1000,
            "messages": [
                {
                    "role": "system",
                    "content": f"{SYSTEM_PROMPT}"
                },
                {
                    "role": "user",
                    "content": f"{text}"
                }
            ]
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}"
        }

        async with session.post(
            URL,
            # impersonate="chrome110",
            # timeout=30,
            json=payload,
            headers=headers,
        ) as res:
            
            elapsed = time.perf_counter() - start

            if res.status != 200:
                return None, elapsed, f"http_{res.status}"

            data = await res.text()

            if not data:
                return None, elapsed, "empty_response"

            label = get_label(data)
            # print(f'{article_id}:{label}')

            if not label:
                return None, elapsed, "label_parse_failed"

            return {
                "source": source,
                "article_id": article_id,
                "label": label
            }, elapsed, None

    except Exception as e:
        elapsed = time.perf_counter() - start
        return None, elapsed, f"error:{type(e).__name__}:{str(e)}"
