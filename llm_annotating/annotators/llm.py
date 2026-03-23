import time
import asyncio
import random
import os
import json

from ..prompt import SYSTEM_PROMPT, LABELS

URL = f"https://[]/v1/chat/completions"
API_KEY = os.environ.get("LITELLM_API_KEY", "DEFAULT_KEY")

def get_label(data):
    try:
        obj = json.loads(data)
        content = obj["choices"][0]["message"]["content"].lower()

        for label in LABELS.values():
            if label in content:
                return label

        return "UNKNOWN"

    except Exception:
        return None

async def annotate_async(session, article, model_name):
    source = article["source"]
    article_id = article["article_id"]
    text = article["text"]

    start = time.perf_counter()

    try:
        # jitter helps avoid rate-limit / bot heuristics
        await asyncio.sleep(random.uniform(0.3, 1.0))

        # payload = {
        #     "model": model_name,
        #     "temperature": 0,
        #     "messages": [
        #         {
        #             "role": "system",
        #             "content": SYSTEM_PROMPT
        #         },
        #         {
        #             "role": "user",
        #             "content": text
        #         }
        #     ]
        # }

        # headers = {
        #     "Authorization": f"Bearer {API_KEY}",
        #     "Content-Type": "application/json"
        # }

        # res = await session.post(
        #     URL,
        #     impersonate="chrome110",
        #     timeout=30,
        #     json=payload,
        #     headers=headers,
        # )
        elapsed = time.perf_counter() - start

        # if res.status_code != 200:
        #     return None, elapsed, f"http_{res.status_code}"

        # data = res.text

        # if not data:
        #     return None, elapsed, "empty_response"

        # label = get_label(data)

        label = "UNKNOWN"
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
