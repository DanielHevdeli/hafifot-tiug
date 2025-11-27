# hafifot-tiug

This repository contains a simple scraper used to collect long posts from askp.co.il and save them to CSV.

Updates:
- The scraper extracts posts from question pages
- Each CSV row contains: question_id, length, date, text.

Date parsing:
- The scraper attempts to parse the Hebrew timestamps (e.g. "כתבה את השאלה ב-17/11/25 בשעה 13:38") into an ISO-like string YYYY-MM-DD HH:MM.
- If parsing fails the raw date string is stored in the CSV.

Usage:
- Edit `START_ID`, `END_ID`, `MIN_LENGTH` and `TARGET_LONG_POSTS` in `scrape.py` as needed and run `python scrape.py`.
