from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup, Tag

AO3_BASE_URL = "https://archiveofourown.org"
SEARCH_URL = f"{AO3_BASE_URL}/works/search"

DEFAULT_HEADERS = {
    "User-Agent": (
        "AO3-Finder/0.1 "
        "(small personal metadata search tool; contact: local-user)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CACHE_TTL_SECONDS = 10 * 60
_MIN_SECONDS_BETWEEN_REQUESTS = 1.5

_CACHE: dict[str, tuple[datetime, str]] = {}
_LAST_REQUEST_AT = 0.0


@dataclass
class SearchOptions:
    query: str = ""
    fandom: str = ""
    relationships: str = ""
    include_tags: str = ""
    exclude_tags: str = ""
    rating: str = ""
    complete: str = ""
    min_words: str = ""
    max_words: str = ""
    sort_column: str = "kudos_count"
    sort_direction: str = "desc"
    pages: int = 1


def split_terms(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]+", value or "") if part.strip()]


def build_search_url(options: SearchOptions, page: int = 1) -> str:
    include_tags = split_terms(options.include_tags)
    exclude_tags = split_terms(options.exclude_tags)
    fandoms = split_terms(options.fandom)
    relationships = split_terms(options.relationships)

    tag_parts = include_tags + fandoms + relationships
    tag_names = ",".join(tag_parts)

    params: dict[str, Any] = {
        "commit": "Search",
        "page": page,
        "work_search[query]": options.query.strip(),
        "work_search[title]": "",
        "work_search[creators]": "",
        "work_search[revised_at]": "",
        "work_search[complete]": options.complete,
        "work_search[crossover]": "",
        "work_search[single_chapter]": "",
        "work_search[word_count]": _word_count_range(
            options.min_words, options.max_words
        ),
        "work_search[language_id]": "",
        "work_search[fandom_names]": ",".join(fandoms),
        "work_search[rating_ids]": _rating_id(options.rating),
        "work_search[category_ids]": "",
        "work_search[character_names]": "",
        "work_search[relationship_names]": ",".join(relationships),
        "work_search[freeform_names]": ",".join(include_tags),
        "work_search[hits]": "",
        "work_search[kudos_count]": "",
        "work_search[comments_count]": "",
        "work_search[bookmarks_count]": "",
        "work_search[sort_column]": options.sort_column or "kudos_count",
        "work_search[sort_direction]": options.sort_direction or "desc",
    }

    if tag_names:
        params["tag_id"] = tag_names

    if exclude_tags:
        exclusion_query = " ".join(f'-"{tag}"' for tag in exclude_tags)
        params["work_search[query]"] = " ".join(
            part for part in [params["work_search[query]"], exclusion_query] if part
        )

    return f"{SEARCH_URL}?{urlencode(params)}"


def _word_count_range(min_words: str, max_words: str) -> str:
    min_clean = _clean_int(min_words)
    max_clean = _clean_int(max_words)
    if min_clean and max_clean:
        return f"{min_clean}-{max_clean}"
    if min_clean:
        return f">{min_clean}"
    if max_clean:
        return f"<{max_clean}"
    return ""


def _clean_int(value: str) -> str:
    cleaned = re.sub(r"\D", "", value or "")
    return cleaned


def _rating_id(rating: str) -> str:
    rating_map = {
        "general": "10",
        "teen": "11",
        "mature": "12",
        "explicit": "13",
        "notrated": "9",
    }
    return rating_map.get((rating or "").lower(), "")


def fetch_html(url: str, *, session: requests.Session | None = None) -> str:
    global _LAST_REQUEST_AT

    cached = _CACHE.get(url)
    if cached:
        cached_at, html = cached
        if datetime.utcnow() - cached_at < timedelta(seconds=CACHE_TTL_SECONDS):
            return html

    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < _MIN_SECONDS_BETWEEN_REQUESTS:
        time.sleep(_MIN_SECONDS_BETWEEN_REQUESTS - elapsed)

    client = session or requests.Session()
    response = client.get(url, headers=DEFAULT_HEADERS, timeout=20)
    _LAST_REQUEST_AT = time.monotonic()

    response.raise_for_status()
    html = response.text
    _CACHE[url] = (datetime.utcnow(), html)
    return html


def search_works(options: SearchOptions) -> dict[str, Any]:
    pages = max(1, min(int(options.pages or 1), 5))
    all_works: list[dict[str, Any]] = []
    seen: set[str] = set()
    searched_urls: list[str] = []
    total_reported: str | None = None

    session = requests.Session()

    for page in range(1, pages + 1):
        url = build_search_url(options, page=page)
        searched_urls.append(url)
        html = fetch_html(url, session=session)
        soup = BeautifulSoup(html, "html.parser")

        if total_reported is None:
            total_reported = _parse_total(soup)

        works = parse_results_page(soup, options)
        for work in works:
            key = work.get("id") or work.get("url") or work.get("title")
            if key and key not in seen:
                seen.add(key)
                all_works.append(work)

        if not works:
            break

    all_works.sort(
        key=lambda work: (
            work.get("score", 0),
            _safe_int(work.get("kudos")),
            _safe_int(work.get("bookmarks")),
            _safe_int(work.get("hits")),
        ),
        reverse=True,
    )

    return {
        "searched_urls": searched_urls,
        "result_count": len(all_works),
        "total_reported": total_reported,
        "works": all_works,
    }


def parse_results_page(soup: BeautifulSoup, options: SearchOptions) -> list[dict[str, Any]]:
    result_nodes = soup.select("li.work.blurb")
    return [parse_work_blurb(node, options) for node in result_nodes]


def parse_work_blurb(node: Tag, options: SearchOptions) -> dict[str, Any]:
    heading = node.select_one("h4.heading")
    title_link = heading.select_one("a[href*='/works/']") if heading else None
    title = clean_text(title_link.get_text(" ", strip=True) if title_link else "")
    url = urljoin(AO3_BASE_URL, title_link.get("href", "")) if title_link else ""
    work_id = _extract_work_id(url)

    authors = [
        clean_text(link.get_text(" ", strip=True))
        for link in node.select("h4.heading a[rel='author']")
    ]

    fandoms = _extract_tag_list(node, "h5.fandoms a.tag")
    warnings = _extract_tag_list(node, "li.warnings a.tag")
    relationships = _extract_tag_list(node, "li.relationships a.tag")
    characters = _extract_tag_list(node, "li.characters a.tag")
    freeforms = _extract_tag_list(node, "li.freeforms a.tag")

    summary_node = node.select_one("blockquote.userstuff")
    summary = clean_text(summary_node.get_text(" ", strip=True) if summary_node else "")

    stats = _parse_stats(node)
    required_tags = [
        clean_text(tag.get_text(" ", strip=True))
        for tag in node.select("ul.required-tags li a, ul.required-tags li span")
        if clean_text(tag.get_text(" ", strip=True))
    ]

    score, score_notes = score_work(
        summary=summary,
        freeforms=freeforms,
        relationships=relationships,
        warnings=warnings,
        required_tags=required_tags,
        include_terms=split_terms(options.include_tags),
        exclude_terms=split_terms(options.exclude_tags),
        query=options.query,
    )

    return {
        "id": work_id,
        "title": title or "(Untitled)",
        "authors": authors or ["Anonymous"],
        "url": url,
        "fandoms": fandoms,
        "relationships": relationships,
        "characters": characters,
        "freeforms": freeforms,
        "warnings": warnings,
        "required_tags": required_tags,
        "summary": summary,
        "score": score,
        "score_notes": score_notes,
        **stats,
    }


def _parse_stats(node: Tag) -> dict[str, str]:
    stats: dict[str, str] = {}
    for dt in node.select("dl.stats dt"):
        label = clean_text(dt.get_text(" ", strip=True)).lower().rstrip(":")
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        value = clean_text(dd.get_text(" ", strip=True))
        key = label.replace(" ", "_")
        stats[key] = value

    date_node = node.select_one("p.datetime")
    if date_node:
        stats["updated"] = clean_text(date_node.get_text(" ", strip=True))

    return stats


def score_work(
    *,
    summary: str,
    freeforms: list[str],
    relationships: list[str],
    warnings: list[str],
    required_tags: list[str],
    include_terms: list[str],
    exclude_terms: list[str],
    query: str,
) -> tuple[int, list[str]]:
    haystack_tags = [*freeforms, *relationships, *warnings, *required_tags]
    haystack = " ".join([summary, *haystack_tags]).lower()
    notes: list[str] = []
    score = 0

    cozy_terms = {
        "fluff": 5,
        "domestic fluff": 5,
        "tooth-rotting fluff": 5,
        "established relationship": 4,
        "cuddling": 3,
        "kissing": 2,
        "slice of life": 3,
        "happy ending": 2,
        "polyamory": 2,
        "polyamorous relationship": 3,
        "comfort": 1,
    }

    heavy_terms = {
        "angst": -8,
        "heavy angst": -10,
        "hurt/comfort": -6,
        "hurt no comfort": -10,
        "major character death": -12,
        "break up": -7,
        "breakup": -7,
        "infidelity": -6,
        "trauma": -5,
        "grief": -5,
        "betrayal": -5,
        "misunderstanding": -3,
    }

    for term, points in cozy_terms.items():
        if term in haystack:
            score += points
            notes.append(f"+{points} {term}")

    for term, points in heavy_terms.items():
        if term in haystack:
            score += points
            notes.append(f"{points} {term}")

    for term in include_terms:
        if term.lower() in haystack:
            score += 2
            notes.append(f"+2 included: {term}")

    for term in exclude_terms:
        if term.lower() in haystack:
            score -= 10
            notes.append(f"-10 excluded: {term}")

    if query and any(part.strip('"').lower() in haystack for part in split_query_words(query)):
        score += 1
        notes.append("+1 query match")

    return score, notes


def split_query_words(query: str) -> list[str]:
    quoted = re.findall(r'"([^"]+)"', query or "")
    bare = re.sub(r'"[^"]+"', " ", query or "")
    bare_words = [
        word for word in re.split(r"\s+|OR|AND", bare, flags=re.IGNORECASE)
        if len(word.strip()) > 2 and not word.startswith("-")
    ]
    return quoted + bare_words


def _extract_tag_list(node: Tag, selector: str) -> list[str]:
    return [
        clean_text(tag.get_text(" ", strip=True))
        for tag in node.select(selector)
        if clean_text(tag.get_text(" ", strip=True))
    ]


def _parse_total(soup: BeautifulSoup) -> str | None:
    heading = soup.select_one("h2.heading")
    if not heading:
        return None
    text = clean_text(heading.get_text(" ", strip=True))
    match = re.search(r"([\d,]+)\s+Works?", text, flags=re.IGNORECASE)
    return match.group(1) if match else text or None


def _extract_work_id(url: str) -> str:
    match = re.search(r"/works/(\d+)", url or "")
    return match.group(1) if match else ""


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    cleaned = re.sub(r"\D", "", str(value))
    return int(cleaned) if cleaned else 0


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def as_public_dict(options: SearchOptions) -> dict[str, Any]:
    return asdict(options)
