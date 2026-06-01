# AO3 Finder

A small local web app for searching Archive of Our Own (AO3) using AO3's public search pages, then scoring and sorting the visible metadata for vibe-based fic discovery.

This is designed for searches like:

- Polytrix / Polyamorous Huntrix fluff
- ship searches with excluded angst tags
- quick filtering by rating, completion status, word count, kudos, and tags

## Important notes

AO3 does **not** provide a normal official public API. This app uses AO3's own public search/result pages and parses the metadata displayed there. That makes it more like the unofficial AO3 libraries and scrapers discussed earlier than a true API client.

The app is intentionally read-only and conservative:

- no login support
- no automated kudos, comments, bookmarks, or downloads
- small page limits
- short local caching
- polite request pacing

## What it can analyze

The app can collect and display metadata visible on AO3 result cards, including:

- title
- author
- work URL
- fandoms
- relationships
- characters
- additional tags
- rating/warnings/category/completion badges when visible
- summary
- words/chapters/kudos/comments/bookmarks/hits when visible
- updated date

It also computes a simple "cozy score" from included and excluded tags/phrases, so fluffy results can rise above darker or angstier-looking ones.

## What it cannot guarantee

AO3 tags are author-entered and inconsistent. A fic can omit `Angst` while still being emotionally heavy, or tag `Fluff` while still having conflict. The score is a helpful guess based on metadata, not a promise about the actual story.

Locked works, adult warning interstitials, deleted works, Cloudflare/rate limits, and AO3 layout changes may affect results.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Suggested Polytrix starter search

Use these fields in the UI:

```text
Fandom: KPop Demon Hunters
Relationship/ship tags: Mira/Rumi/Zoey, Polyamorous Huntrix
Include tags: Fluff, Domestic Fluff, Established Relationship
Exclude tags: Angst, Hurt/Comfort, Major Character Death, Break Up, Heavy Angst
Keyword search: polytrix OR "Polyamorous Huntrix"
```

Start with 2 pages, then increase if the results look useful.

## Project structure

```text
app.py              Flask backend routes
ao3_client.py       AO3 search URL builder, fetcher, parser, and scorer
templates/index.html
static/app.js
static/style.css
```
