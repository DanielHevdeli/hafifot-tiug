import asyncio
import logging
from datetime import datetime
import random
import os
import openai
from .utils.io_utils import append_jsonl
from .utils.text_utils import normalize_label, truncate_text

openai.api_key = os.getenv("LITELLM_API_KEY")

class GenericLLMAnnotator:
    def __init__(self, model_name, results_path, errors_path, concurrency=5, timeout=30, max_retries=3):
        self.model_name = model_name
        self.results_path = results_path
        self.errors_path = errors_path
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(model_name)

    async def call_openai(model: str, messages: list, max_tokens: int = 50, timeout: int = 30):
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            request_timeout=timeout
        )
        outputs = response.choices[0].message.content.split("\n")
        return outputs

    async def dummy_call(model: str, messages: list, max_tokens: int = 50, timeout: int = 30):
        await asyncio.sleep(random.uniform(0.1, 0.5))
        user_messages = [m["content"] for m in messages if m["role"] == "user"]

        outputs = []
        for i, msg in enumerate(user_messages, start=1):
            label = random.choice(["FACT", "OPINION"])
            outputs.append(f"{label} - dummy response for article {i}")
        return outputs

    async def annotate_articles_batch(self, articles, prompt: str):
        messages = [{"role": "system", "content": prompt}]
        for article in articles:
            article["text"] = truncate_text(article["text"])
            messages.append({"role": "user", "content": article["text"]})
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:
                    outputs = await self.dummy_call(self.model_name, messages, timeout=self.timeout)

                for article, raw_output in zip(articles, outputs):
                    label = normalize_label(raw_output)
                    record = {
                        "article_id": article["article_id"],
                        "model": self.model_name,
                        "label": label,
                        "raw_output": raw_output,
                        "status": "success",
                        "timestamp": datetime.utcnow().isoformat(),
                        # "prompt_version": PROMPT_VERSION
                    }
                    append_jsonl(self.results_path, record)
                return


            except Exception as e:
                self.logger.error(f"Batch failed attempt {attempt}: {e}")
                if attempt == self.max_retries:
                    for article in articles:
                        append_jsonl(self.errors_path, {"article_id": article["article_id"], "error": str(e)})
                else:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff
