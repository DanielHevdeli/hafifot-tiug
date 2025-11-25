import requests
from bs4 import BeautifulSoup
import json
from time import sleep
from random import uniform
import pandas as pd
import matplotlib.pyplot as plt

START_ID = 200000
END_ID = 999999
MIN_LENGTH = 800
TARGET_LONG_POSTS = 100

def get_question_text(question_id):
    url = f"https://www.askp.co.il/question/{question_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        question_div = soup.find('div', class_='question_content')
        return question_div.get_text(separator="\n").strip() if question_div else None
    except requests.RequestException as e:
        print(f"Error fetching {question_id}: {e}")
        return None

def main():
    posts_length = {}
    records = []
    num_posts = 0
    qid = START_ID

    while num_posts < TARGET_LONG_POSTS and qid <= END_ID:
        text = get_question_text(qid)
        if text and len(text) >= MIN_LENGTH:

            with open("scrape.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"Fetched LONG question {qid} (length {len(text)})\n")

            posts_length[qid] = len(text)
            num_posts += 1

            records.append({
                "question_id": qid,
                "length": len(text),
                "text": text
            })

        else:
            with open("scrape.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"Skipped question {qid} (too short or empty)\n")

        qid += 1
        # sleep(uniform(0.5, 1.5))

    df_csv = pd.DataFrame(records)
    df_csv.to_csv("posts.csv", index=False, encoding="utf-8-sig")
    print("Saved posts.csv with", len(df_csv), "rows.")

if __name__ == "__main__":
    main()
