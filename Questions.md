## 1. Explain the Complete Project Flow

1. The FastAPI application starts and creates the APScheduler job. It reads the saved schedule from MongoDB; if no custom interval has been saved, it uses the default schedule from `.env` (6:00 AM UTC).
2. When the scheduled job runs, APScheduler calls `run_daily_job()`. The same function can be started manually from the dashboard's **Collect latest** button or with `POST /collect`.
3. `news_service.py` sends a request to GNews and reads its JSON `articles` array. It normalizes fields such as title, description, source, URL, and publication date, then assigns a category.
4. `scheduler.py` removes repeated URLs from the fetched batch. `database.py` inserts new articles into MongoDB; a unique index on `news.url` rejects URLs already stored.
5. The job reads articles collected during the previous seven days, scores them, selects relevant stories, generates the daily briefing, saves it in MongoDB, and prints it in the terminal.
6. The dashboard and Postman call FastAPI endpoints. FastAPI reads articles or briefings from MongoDB, serializes MongoDB ObjectIds as strings, and returns JSON.

## 2. Why Use a Scheduler, and How Does It Trigger Python?

A scheduler runs the collection automatically, so a person does not need to start the job every day. At application startup, `start_scheduler()` registers the Python function `run_daily_job` with APScheduler. Registering a function does not execute it immediately; APScheduler invokes it when its trigger fires.

Without a custom setting, APScheduler uses a cron trigger at the configured hour and minute (default: 6:00 AM UTC). The dashboard can save a recurring interval of 1 minute, 5 minutes, 1 hour, or 1 day. It stores the chosen interval in MongoDB's `app_settings` collection and reschedules the job. The browser refreshes its view from the API at the same interval.

## 3. What If the Server Is Stopped at the Scheduled Time?

The scheduler runs inside the Python application. If the application is stopped at the scheduled time, the job cannot run. On restart, the application creates a new scheduler using the saved interval. This project does not catch up a missed run: with the default cron schedule, it waits for the next scheduled time; with a saved interval, the next run is based on the new scheduler's start time. `coalesce=True` also prevents a backlog of missed runs from being replayed.

To run collection immediately after restarting, use the dashboard's **Collect latest** button or send `POST /collect`.

## 4. How Are Duplicate Articles Prevented?

There are two checks:

- Before saving, `scheduler.py` removes repeated article URLs from the current GNews response.
- MongoDB has a unique index on `news.url`. When `save_news()` tries to insert an already-stored URL, MongoDB rejects that insert and the function counts it as a duplicate.

This prevents exact URL duplicates. URLs that point to the same story but differ in tracking parameters may still be treated as separate articles.

## 5. How Does News Travel from the External API to Postman?

**GNews -> Python:** `news_service.py` sends an HTTP request to GNews. The GNews API key is used by the backend and must be kept in `.env`; it is not sent by Postman. Python reads the JSON response and converts each usable article into the project's standard dictionary format.

**Python -> MongoDB:** The scheduler categorizes and saves articles to the `tech_news.news` collection. MongoDB assigns each document an `_id`; its unique URL index prevents exact duplicates. The scheduler then creates and saves the briefing in `tech_news.daily_briefings`.

**MongoDB -> REST API:** A FastAPI route queries MongoDB. For example, `GET /news/search?keyword=python` searches article title, description, and category. The API converts MongoDB ObjectIds to strings and returns matching documents as JSON.

**REST API -> Postman:** Postman sends the HTTP request to the local FastAPI application and displays its JSON response. Postman calls this project's API; it does not call GNews directly.

## Key Safety

Keep `GNEWS_API_KEY` in `.env`. Do not paste it into chat, commit it, or include it in screenshots. Revoke and replace any key that has been exposed.
