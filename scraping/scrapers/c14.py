import time
from bs4 import BeautifulSoup

BASE_URL = "https://www.c14.co.il/article/"

def get_article_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    article_div = soup.find(
        "div",
        class_=lambda x: x and x.startswith("ArticleContent_articleContent")
    )

    paragraphs = []
    if article_div:
        for p in article_div.find_all("p"):
            txt = p.get_text(separator=" ", strip=True)
            if txt:
                paragraphs.append(txt)

    if not paragraphs:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            paragraphs.append(h1.get_text(strip=True))
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            paragraphs.append(meta_desc["content"])

    article_text = "\n".join(paragraphs).strip()

    return article_text if article_text else None

async def scrape_async(session, article_metadata):
    article_id = article_metadata["id"]
    date = article_metadata["date"]
    words_count = article_metadata["wordsCount"]
    author = article_metadata["author"]

    url = f"{BASE_URL}{article_id}"
    start = time.perf_counter()

    try:
        # chrome impersonation + solid jitter is enough as a workaround against the bot-blocking
        r = await session.get(url, impersonate="chrome110", timeout=15)
        elapsed = time.perf_counter() - start
        if r.status_code != 200:
            return None, elapsed, f"http_{r.status_code}_{r.reason}"

        html = r.text

        if not html:
            return None, elapsed, "empty_html"

        article_text = get_article_text(html)

        if not article_text:
            return None, elapsed, "parse_failed"

        return {
            "source": "c14",
            "date": date,
            "article_id": article_id,
            "wordsCount": words_count,
            "length": len(article_text),
            "author": author,
            "text": article_text
        }, elapsed, None

    except Exception as e:
        elapsed = time.perf_counter() - start
        return None, elapsed, f"error:{type(e).__name__}:{str(e)}"

# async def base_scrape_async(session, article_metadata):
#     article_id = article_metadata["id"]
#     date = article_metadata["date"]
#     words_count = article_metadata["wordsCount"]
#     author = article_metadata["author"]

#     url = f"{BASE_URL}{article_id}"

#     start = time.perf_counter()

#     try:
#         async with session.get(url, timeout=10) as r:
#             elapsed = time.perf_counter() - start

#             if r.status != 200:
#                 return None, elapsed

#             html = await r.text()
#             article_text = get_article_text(html)

#             if not article_text:
#                 return None, elapsed

#             return {
#                 "source": "c14",
#                 "date": date,
#                 "article_id": article_id,
#                 "wordsCount": words_count,
#                 "length": len(article_text),
#                 "author": author,
#                 "text": article_text
#             }, elapsed

#     except Exception:
#         elapsed = time.perf_counter() - start
#         return None, elapsed
