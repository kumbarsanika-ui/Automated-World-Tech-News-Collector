from datetime import datetime, timezone
import re

import requests

from config import GNEWS_API_KEY, GNEWS_API_URL
from models import NewsArticle


CATEGORY_KEYWORDS = {
    "Agentic AI": ("agentic ai", "ai agent", "ai agents", "autonomous agent"),
    "AI": (
        "artificial intelligence",
        "generative ai",
        "machine learning",
        "large language model",
        "llm",
    ),
    "Quantum Computing": ("quantum computing", "quantum computer", "qubit"),
    "Cloud": ("cloud computing", "cloud service", "cloud platform"),
    "Cybersecurity": ("cybersecurity", "cyber attack", "data breach", "ransomware"),
    "Programming": ("programming", "programming language", "python", "javascript"),
    "Developer Tools": ("developer tool", "developer platform", "code editor", "ide"),
    "Startups": ("startup", "start-up", "venture capital", "funding round"),
    "Technology Companies": (
        "apple",
        "google",
        "microsoft",
        "amazon",
        "meta",
        "nvidia",
    ),
}


class NewsServiceError(Exception):
    """Raised when the news provider cannot return usable news."""


def categorize_article(title, description):
    text = f"{title} {description}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            return category

    return "Other Technology"


def _parse_published_at(value):
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_article(article: dict) -> NewsArticle | None:
    if not isinstance(article, dict):
        return None

    title = article.get("title")
    url = article.get("url")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(url, str) or not url.strip():
        return None

    source = article.get("source")
    if not isinstance(source, dict):
        source = {}

    description = article.get("description") or ""
    if not isinstance(description, str):
        description = ""

    return {
        "title": title.strip(),
        "description": description.strip(),
        "source": source.get("name") or "Unknown",
        "author": article.get("author"),
        "url": url.strip(),
        "category": categorize_article(title, description),
        "published_at": _parse_published_at(article.get("publishedAt")),
        "collected_at": datetime.now(timezone.utc),
    }


def fetch_news() -> list[NewsArticle]:
    if not GNEWS_API_URL or not GNEWS_API_KEY:
        raise NewsServiceError("Set GNEWS_API_URL and GNEWS_API_KEY in your .env file.")

    try:
        response = requests.get(
            GNEWS_API_URL,
            params={
                "q": "technology OR artificial intelligence OR quantum computing "
                "OR cybersecurity OR cloud computing OR developer tools OR startup",
                "lang": "en",
                "sortby": "publishedAt",
                "max": 10,
                "apikey": GNEWS_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as error:
        raise NewsServiceError("The GNews request timed out.") from error
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code in (401, 403):
            message = "GNews rejected the key or request. Check GNEWS_API_KEY and your plan."
        elif status_code == 429:
            message = "GNews rate limit reached. Check your plan and try again later."
        else:
            message = "GNews returned an HTTP error. Check the endpoint and request limits."
        raise NewsServiceError(message) from error
    except ValueError as error:
        raise NewsServiceError("GNews returned invalid JSON.") from error
    except requests.RequestException as error:
        raise NewsServiceError("Could not connect to GNews.") from error

    if not isinstance(payload, dict):
        raise NewsServiceError("GNews returned an invalid response.")

    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise NewsServiceError("GNews response did not contain an article list.")

    return [
        normalized
        for article in articles
        if (normalized := _normalize_article(article)) is not None
    ]