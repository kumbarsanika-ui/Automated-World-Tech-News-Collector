from datetime import datetime
from typing import TypedDict


class NewsArticle(TypedDict):
    title: str
    description: str
    source: str
    author: str | None
    url: str
    category: str
    published_at: datetime | None
    collected_at: datetime


class ScoredArticle(NewsArticle):
    importance_score: int


class BriefingArticle(ScoredArticle):
    summary: str
    why_it_matters: str


class DailyBriefing(TypedDict):
    briefing_date: str
    generated_at: datetime
    total_news: int
    categories: dict[str, int]
    top_news: list[BriefingArticle]
    learning_of_the_day: str
    career_opportunity: list[str]