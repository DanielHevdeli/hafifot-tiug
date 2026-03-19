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

def scrape(session, article_metadata):
    article_id = article_metadata["id"]
    date = article_metadata["date"]
    words_count = article_metadata["wordsCount"]
    author = article_metadata["author"]

    try:
        start = time.perf_counter()
        r = session.get(f"{BASE_URL}{article_id}", timeout=10)
        elapsed = time.perf_counter() - start

        if r.status_code != 200:
            return None, elapsed

        article_text = get_article_text(r.text)
        if not article_text:
            return None, elapsed

        result = {
            "source": "c14",
            "date": date,
            "article_id": article_id,
            "wordsCount": words_count,
            "length": len(article_text),
            "author": author,
            "text": article_text
        }
        return result, elapsed

    except Exception:
        elapsed = time.perf_counter() - start
        return None, elapsed

# if __name__ == "__main__":
#     session = requests.Session()
#     article_data = scrape(session, {"id": "1501457", "date": "2024-01-01", "wordsCount": 100, "author": "משה כהן"}, 1)
#     print(article_data[0]["text"])