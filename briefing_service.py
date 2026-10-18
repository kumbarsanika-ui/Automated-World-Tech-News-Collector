from collections import Counter
from datetime import date, datetime, timezone
import re

from models import BriefingArticle, DailyBriefing, NewsArticle, ScoredArticle


MAX_BRIEFING_ARTICLES = 15
MAX_ARTICLES_PER_SECTION = 3

SECTION_CATEGORIES = {
    "1. AI": ("AI",),
    "2. AGENTIC AI": ("Agentic AI",),
    "3. QUANTUM COMPUTING": ("Quantum Computing",),
    "4. CLOUD & SOFTWARE": ("Cloud", "Programming", "Developer Tools"),
    "5. CYBERSECURITY": ("Cybersecurity",),
    "6. TECHNOLOGY BUSINESS & TRENDS": (
        "Startups",
        "Technology Companies",
        "Other Technology",
    ),
}

PRIORITY_CATEGORIES = {"AI", "Agentic AI", "Quantum Computing", "Cybersecurity"}
IMPACT_KEYWORDS = (
    "breakthrough",
    "vulnerability",
    "data breach",
    "ransomware",
    "outage",
    "acquisition",
    "regulation",
    "funding",
    "launch",
)

WHY_IT_MATTERS = {
    "AI": "AI developments can change how people work and how companies build products.",
    "Agentic AI": "More capable agents make reliability, evaluation, and human oversight important.",
    "Quantum Computing": "Quantum progress matters to scientific computing and long-term cryptography.",
    "Cloud": "Cloud changes can affect service cost, reliability, and deployment choices.",
    "Cybersecurity": "Security developments can affect data, services, and incident response plans.",
    "Programming": "Programming changes influence software compatibility and developer skills.",
    "Developer Tools": "Developer tools shape everyday workflows and software quality.",
    "Startups": "Startup news can signal where investment, talent, and competition are shifting.",
    "Technology Companies": "Major company moves can affect products, platforms, and the wider market.",
    "Other Technology": "Emerging technology trends can create new opportunities and risks.",
}

LEARNING_TOPICS = {
    "AI": "Learn how to evaluate a machine-learning model with a held-out test set.",
    "Agentic AI": "Study tool calling, task boundaries, and human approval in AI agents.",
    "Quantum Computing": "Review qubits, superposition, and why quantum error correction matters.",
    "Cloud": "Compare cloud regions, availability zones, and basic service monitoring.",
    "Cybersecurity": "Practice identifying phishing indicators and reviewing account security.",
    "Programming": "Practice writing and testing a small Python function with clear inputs and outputs.",
    "Developer Tools": "Explore how a debugger uses breakpoints to inspect program state.",
    "Startups": "Learn how a startup validates a customer problem before building a product.",
    "Technology Companies": "Compare how two technology companies describe their products and markets.",
    "Other Technology": "Choose one technology term from today's headlines and read its documentation.",
}

CAREER_SKILLS = {
    "AI": "Python, data analysis, and model evaluation; relevant role: machine-learning engineer.",
    "Agentic AI": "Python, API integration, and testing; relevant role: AI application developer.",
    "Quantum Computing": "Linear algebra and quantum programming; relevant role: quantum software researcher.",
    "Cloud": "Cloud fundamentals, deployment, and monitoring; relevant role: cloud engineer.",
    "Cybersecurity": "Networking, Linux, and incident analysis; relevant role: security analyst.",
    "Programming": "Programming fundamentals and testing; relevant role: backend developer.",
    "Developer Tools": "Developer workflow and automation; relevant role: developer tools engineer.",
    "Startups": "Product research and business analysis; relevant role: technology product analyst.",
    "Technology Companies": "Product strategy and market analysis; relevant role: technology business analyst.",
    "Other Technology": "Research, communication, and technical fundamentals; relevant role: technology analyst.",
}


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def score_article(article: NewsArticle, now: datetime | None = None) -> int:
    if now is None:
        now = datetime.now(timezone.utc)
    now = _as_utc(now)

    score = 3 if article.get("category") in PRIORITY_CATEGORIES else 0
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    impact_matches = sum(
        bool(re.search(rf"\b{re.escape(keyword)}\b", text))
        for keyword in IMPACT_KEYWORDS
    )
    score += min(impact_matches, 3) * 2

    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        age_hours = (now - _as_utc(published_at)).total_seconds() / 3600
        if 0 <= age_hours <= 24:
            score += 3
        elif 0 <= age_hours <= 72:
            score += 2
        elif 0 <= age_hours <= 168:
            score += 1

    return score


def _published_timestamp(article: NewsArticle) -> float:
    published_at = article.get("published_at")
    if not isinstance(published_at, datetime):
        return 0
    return _as_utc(published_at).timestamp()


def _section_for_category(category: str) -> str:
    for section, categories in SECTION_CATEGORIES.items():
        if category in categories:
            return section
    return "6. TECHNOLOGY BUSINESS & TRENDS"


def select_top_news(
    articles: list[NewsArticle],
    now: datetime | None = None,
    limit: int = MAX_BRIEFING_ARTICLES,
) -> list[ScoredArticle]:
    ranked_articles = sorted(
        articles,
        key=lambda article: (
            -score_article(article, now),
            -_published_timestamp(article),
            article.get("title", "").lower(),
        ),
    )

    selected = []
    section_counts = Counter()
    for article in ranked_articles:
        section = _section_for_category(article.get("category"))
        if section_counts[section] >= MAX_ARTICLES_PER_SECTION:
            continue

        selected.append({**article, "importance_score": score_article(article, now)})
        section_counts[section] += 1
        if len(selected) >= limit:
            break

    return selected


def _summary(description):
    if not isinstance(description, str) or not description.strip():
        return "No description was provided by the news source."
    sentences = re.split(r"(?<=[.!?])\s+", description.strip())
    return " ".join(sentences[:3])


def build_briefing(
    articles: list[NewsArticle],
    briefing_date: str | date | None = None,
    generated_at: datetime | None = None,
) -> DailyBriefing:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    generated_at = _as_utc(generated_at)

    selected = select_top_news(articles, now=generated_at)
    top_news = []
    for article in selected:
        category = article.get("category", "Other Technology")
        top_news.append(
            {
                **article,
                "summary": _summary(article.get("description")),
                "why_it_matters": WHY_IT_MATTERS.get(category, WHY_IT_MATTERS["Other Technology"]),
            }
        )

    counts = Counter(article.get("category", "Other Technology") for article in articles)
    leading_category = top_news[0].get("category") if top_news else "Other Technology"
    career_opportunities = []
    for article in top_news:
        category = article.get("category", "Other Technology")
        opportunity = CAREER_SKILLS.get(category, CAREER_SKILLS["Other Technology"])
        if opportunity not in career_opportunities:
            career_opportunities.append(opportunity)
        if len(career_opportunities) == 3:
            break

    if isinstance(briefing_date, date):
        briefing_date = briefing_date.isoformat()
    if briefing_date is None:
        briefing_date = generated_at.date().isoformat()

    return {
        "briefing_date": briefing_date,
        "generated_at": generated_at,
        "total_news": len(articles),
        "categories": dict(counts),
        "top_news": top_news,
        "learning_of_the_day": LEARNING_TOPICS.get(
            leading_category, LEARNING_TOPICS["Other Technology"]
        ),
        "career_opportunity": career_opportunities,
    }


def format_briefing(briefing: DailyBriefing) -> str:
    lines = [
        "DAILY GLOBAL TECH BRIEFING",
        f"Date: {briefing['briefing_date']}",
        f"Articles reviewed: {briefing['total_news']}",
        "",
    ]

    for section, categories in SECTION_CATEGORIES.items():
        lines.append(section)
        section_articles = [
            article
            for article in briefing["top_news"]
            if article.get("category") in categories
        ]
        if not section_articles:
            lines.append("- No relevant articles collected.")
        for article in section_articles:
            lines.extend(
                [
                    f"- {article['title']}",
                    f"  Summary: {article['summary']}",
                    f"  Why it matters: {article['why_it_matters']}",
                    f"  Source: {article.get('source', 'Unknown')} | {article['url']}",
                    f"  Relevance score: {article['importance_score']}",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "7. LEARNING OF THE DAY",
            f"- {briefing['learning_of_the_day']}",
            "",
            "8. CAREER OPPORTUNITY",
        ]
    )
    if briefing["career_opportunity"]:
        lines.extend(f"- {opportunity}" for opportunity in briefing["career_opportunity"])
    else:
        lines.append("- Follow the technology topics covered in today's briefing.")

    return "\n".join(lines)