import requests
import re
import json
import asyncio
import aiohttp
from tqdm.asyncio import tqdm_asyncio
import logging

BASE_URL = "https://www.c14.co.il"
ARTICLE_URL = "https://www.c14.co.il/wp-json/now14-api/v1/articles"

def get_html(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.text

def extract_archives_from_html(html):
    archive_ids = set()
    
    for match in re.findall(r'href="/archive/(\d+)"', html):
        archive_ids.add(int(match))
    
    # Also look for embedded JSON that might contain archive references
    for jm in re.findall(r'\{.*?"type":"archive".*?\}', html):
        try:
            data = json.loads(jm)
            archive_ids.add(int(data["object_id"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    
    return archive_ids

def crawl_all_archives():
    all_archives = set()

    main_html = get_html(BASE_URL)
    primary_archives = extract_archives_from_html(main_html)
    all_archives.update(primary_archives)

    for archive_id in list(primary_archives):
        url = f"{BASE_URL}/archive/{archive_id}"
        try:
            html = get_html(url)
            sub_archives = extract_archives_from_html(html)
            all_archives.update(sub_archives)
        except requests.RequestException:
            continue
    
    return sorted(all_archives)

async def fetch_articles_batch_async(session, archive_id, offset=0, number=50):
    params = {"archive": archive_id, "offset": offset, "number": number}
    try:
        async with session.get(ARTICLE_URL, params=params, timeout=20) as response:
            response.raise_for_status()
            text = await response.text()
            if not text.strip():
                logging.warning(f"Empty response for archive {archive_id}, offset {offset}")
                return []
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logging.warning(f"Failed to decode JSON for archive {archive_id}, offset {offset}")
                return []
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []

async def fetch_all_articles_async(archive_ids, step=500, max_concurrency=10):
    articles_dict = {}
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch_archive(archive_id):
        offset = 0
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                while True:
                    batch = await fetch_articles_batch_async(session, archive_id, offset, step)
                    if not batch:
                        break

                    for article in batch:
                        aid = article['id']
                        if aid not in articles_dict:
                            articles_dict[aid] = {
                                "date": article.get("date"),
                                "wordsCount": article.get("wordsCount"),
                                "author": article.get("author", {}).get("name"),
                                "archive_ids": [archive_id]
                            }
                        else:
                            if archive_id not in articles_dict[aid]["archive_ids"]:
                                articles_dict[aid]["archive_ids"].append(archive_id)
                    
                    offset += len(batch)

    tasks = [fetch_archive(aid) for aid in archive_ids]
    await tqdm_asyncio.gather(*tasks, desc="Archives", unit="archive")
    return articles_dict

def get_all_articles_metadata():
    archive_ids = crawl_all_archives()
    logging.info(f"Number of archives found: {len(archive_ids)}")
    logging.info("Found archive IDs: %s", archive_ids)

    articles_dict = asyncio.run(fetch_all_articles_async(archive_ids))
    logging.info(f"\nTotal unique articles in C14: {len(articles_dict)}")

    return articles_dict
