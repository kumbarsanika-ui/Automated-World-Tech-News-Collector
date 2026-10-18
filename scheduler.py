from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from briefing_service import build_briefing, format_briefing
from config import NEWS_SCHEDULE_HOUR, NEWS_SCHEDULE_MINUTE, NEWS_TIMEZONE
from database import (
    BriefingStorageError,
    NewsStorageError,
    ScheduleStorageError,
    connect_to_mongodb,
    find_recent_news,
    load_scheduler_settings,
    save_briefing,
    save_news,
    save_scheduler_settings,
)
from news_service import NewsServiceError, fetch_news

JOB_ID = "daily_tech_news_briefing"
ALLOWED_INTERVAL_MINUTES = {1, 5, 60, 1440}


def run_daily_job():
    client = None

    try:
        fetched_articles = fetch_news()
        unique_articles = list(
            {article["url"]: article for article in reversed(fetched_articles)}.values()
        )

        client, database, news_collection, briefing_collection = connect_to_mongodb()
        save_results = save_news(unique_articles, news_collection)

        generated_at = datetime.now(timezone.utc)
        recent_articles = find_recent_news(
            news_collection, generated_at - timedelta(days=7)
        )
        briefing = build_briefing(recent_articles, generated_at=generated_at)
        save_briefing(briefing, briefing_collection)
        print(format_briefing(briefing))

        return {
            "fetched": len(fetched_articles),
            **save_results,
            "briefing_date": briefing["briefing_date"],
            "total_news": briefing["total_news"],
        }
    except (NewsServiceError, ConnectionError, NewsStorageError, BriefingStorageError) as error:
        print(f"Daily news job failed: {error}")
        return {"error": str(error)}
    finally:
        if client is not None:
            client.close()


def start_scheduler():
    scheduler = BackgroundScheduler(timezone=NEWS_TIMEZONE)
    try:
        settings = load_scheduler_settings()
    except (ConnectionError, ScheduleStorageError) as error:
        print(f"Could not load saved scheduler settings; using 6:00 default: {error}")
        settings = None

    interval_minutes = settings.get("interval_minutes") if settings else None
    job_options = {
        "id": JOB_ID,
        "replace_existing": True,
        "max_instances": 1,
        "coalesce": True,
    }
    if interval_minutes in ALLOWED_INTERVAL_MINUTES:
        scheduler.add_job(
            run_daily_job,
            trigger="interval",
            minutes=interval_minutes,
            **job_options,
        )
    else:
        scheduler.add_job(
            run_daily_job,
            trigger="cron",
            hour=NEWS_SCHEDULE_HOUR,
            minute=NEWS_SCHEDULE_MINUTE,
            **job_options,
        )
    scheduler.start()
    return scheduler


def get_schedule_status(scheduler):
    job = scheduler.get_job(JOB_ID)
    if job is None:
        raise RuntimeError("Daily news job is not registered.")

    interval = getattr(job.trigger, "interval", None)
    interval_minutes = (
        int(interval.total_seconds() // 60) if interval is not None else 1440
    )
    return {
        "interval_minutes": interval_minutes,
        "next_run_time": job.next_run_time,
        "allowed_intervals": sorted(ALLOWED_INTERVAL_MINUTES),
    }


def update_schedule(scheduler, interval_minutes):
    if interval_minutes not in ALLOWED_INTERVAL_MINUTES:
        raise ValueError("Choose 1, 5, 60, or 1440 minutes.")

    save_scheduler_settings(interval_minutes)
    scheduler.reschedule_job(JOB_ID, trigger="interval", minutes=interval_minutes)
    return get_schedule_status(scheduler)