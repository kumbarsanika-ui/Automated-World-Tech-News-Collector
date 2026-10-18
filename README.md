# Daily Global Tech News Scheduler

A beginner-friendly Python project that will collect technology news, save it in MongoDB, and generate a daily briefing.

## Stage 1: Project Setup and Configuration

This stage defines the packages and settings used by later stages. The application code reads settings from environment variables, so API keys and database credentials do not need to be written into Python files.

### Technologies

- Python for application logic
- FastAPI and Uvicorn for the REST API
- Requests for news API calls
- PyMongo for MongoDB access
- APScheduler for the daily job
- python-dotenv for loading local `.env` settings

### Setup

Install Python 3.10 or newer, then open a terminal in the project folder and run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your MongoDB URI and a GNews API key (`GNEWS_API_KEY`). Get a key from the [GNews dashboard](https://gnews.io/dashboard). Keep `.env` private; it is excluded by `.gitignore`. `.env.example` contains only placeholder values and can be shared. Do not reuse or share an API key that has appeared in a screenshot.

The scheduler defaults to 6:00 AM UTC. Change `NEWS_SCHEDULE_HOUR`, `NEWS_SCHEDULE_MINUTE`, or `NEWS_TIMEZONE` in `.env` to configure it. The GNews URL and key are used in the news-collection stage.

## Stage 2: MongoDB Connection

`database.py` connects to MongoDB using `MONGODB_URI`, checks the connection with `ping`, and prepares the `tech_news` database with its `news` and `daily_briefings` collections. MongoDB creates databases and collections when they are first written to; creating indexes makes these collections available now.

The `news.url` unique index prevents saving the same article URL more than once. The briefing date index helps MongoDB find briefings by date. If an existing `news` collection has repeated or missing URLs, MongoDB may reject creation of the unique index; remove or correct those documents before retrying.

Install the listed packages and make sure MongoDB is running. To check the connection from PowerShell, run:

```powershell
py -m pip install -r requirements.txt
py -c "from database import connect_to_mongodb; client, database, news, briefings = connect_to_mongodb(); print(database.name, news.name, briefings.name); client.close()"
```

The command should print `tech_news news daily_briefings`. In MongoDB Compass, connect using the same MongoDB URI and inspect the `tech_news` database and its collections. The collections may remain empty until articles and briefings are inserted.

## Stage 3: Collect and Categorize News

`news_service.py` requests English technology articles from GNews's `/api/v4/search` endpoint. Set `GNEWS_API_URL=https://gnews.io/api/v4/search` and `GNEWS_API_KEY` in your private `.env` file. GNews requires the key as an `apikey` request parameter; the application does not print it. The free plan currently limits a request to 10 articles and delays new articles, so results may not include breaking news. Check GNews's current plan, quota, and [article availability](https://docs.gnews.io/article-availability).

The service reads GNews's JSON `articles` list and converts each usable item into a dictionary with a consistent set of fields for MongoDB. GNews provides `source.name` and `publishedAt`; articles without a title or URL are skipped. Publication timestamps are converted to Python `datetime` values; missing or invalid timestamps become `None`. The editable `CATEGORY_KEYWORDS` dictionary assigns one category based on the first whole-word keyword match in the title or description.

Requests use a 15-second timeout. Network problems, timeout, invalid JSON, missing configuration, rejected keys, rate limits, and unexpected response shapes produce a `NewsServiceError`. A valid but empty article list returns an empty list.

To fetch a GNews batch after adding a valid GNews key to `.env`, run:

```powershell
py -c "from news_service import fetch_news; articles = fetch_news(); print('Articles:', len(articles)); print(articles[0] if articles else 'No articles returned')"
```

## Stage 4: Save News and Skip Duplicates

`save_news(articles, news_collection)` inserts articles one at a time. MongoDB's unique index on `url` rejects repeated article URLs, including duplicates in the same input list. The function counts inserted and duplicate articles separately and raises a simple `NewsStorageError` if another MongoDB operation fails.

The storage function only catches duplicate-key errors as expected duplicates. Other database errors are not silently ignored. A duplicate keeps the already-stored document unchanged.

After saving, inspect `tech_news.news` in MongoDB Compass. Each document has MongoDB's automatic `_id` plus the article fields, including its category and collected timestamp. The complete application will call this function after fetching the news; its scheduler and REST API are later stages.

## Stage 5: Rank News and Generate a Briefing

`briefing_service.py` gives each article a simple relevance score:

- Priority categories (AI, Agentic AI, Quantum Computing, and Cybersecurity) add 3 points.
- Each matching impact keyword (such as `vulnerability`, `outage`, or `acquisition`) adds 2 points, up to 6 points.
- Articles published within 24 hours add 3 points, within 72 hours add 2, and within seven days add 1.

Articles are sorted by score, then publication time. Selection is limited to 15 articles total and three per briefing section, allowing a fuller briefing while keeping coverage balanced. The briefing uses the source description for its summary and a short category-specific explanation for why the topic matters. It also includes a practical learning suggestion and career-related skills based on selected categories.

`build_briefing()` returns a dictionary containing the date, generation time, total article count, category counts, and selected news. `format_briefing()` turns it into readable terminal text. `save_briefing()` upserts by date: rerunning a briefing updates that date's record while preserving its original `created_at`. The briefing date has a unique index. If an older database already contains duplicate briefing dates, clean those duplicates before starting the updated application.

To preview an empty briefing without calling the news API, run:

```powershell
py -c "from briefing_service import build_briefing, format_briefing; print(format_briefing(build_briefing([])))"
```

The scheduler connects collection, saving, briefing generation, and printing in Stage 6.

## Stage 6: Daily Scheduler

`scheduler.py` connects the earlier stages into one job. It fetches articles, removes repeated URLs within the response, saves new articles, reads articles collected during the last seven days, generates and saves today's briefing, then prints it. A repeat run updates the briefing for that date.

With no dashboard override, the job runs daily using `NEWS_SCHEDULE_HOUR`, `NEWS_SCHEDULE_MINUTE`, and `NEWS_TIMEZONE` from `.env` (default: 6:00 AM UTC). The dashboard can instead save a recurring interval of 1 minute, 5 minutes, 1 hour, or 1 day. The selected value is stored in the `app_settings` collection and restored when the app restarts. The browser refreshes its MongoDB-backed view at the same selected interval. `main.py` starts the background scheduler and keeps the process alive. Run one application process; multiple processes would each start a scheduler.

Frequent collection uses provider quota. GNews's free plan currently returns up to 10 articles per request and has a daily request allowance, so a 1-minute or 5-minute interval can exhaust it quickly. Use 1 day for regular demos unless your GNews plan supports more frequent polling.

To start the scheduled application:

```powershell
py main.py
```

To test the whole job immediately instead of waiting for its scheduled time, run:

```powershell
py -c "from scheduler import run_daily_job; print(run_daily_job())"
```

The immediate command makes a real provider request and may consume API quota. Set valid provider settings before running it. Use `Ctrl+C` to stop `main.py` gracefully.

## Stage 7: REST API

`main.py` serves the REST API and starts the scheduler with the application. Start it with `py main.py`, then use `http://127.0.0.1:8000` as the Postman base URL. FastAPI's interactive API page is available at `http://127.0.0.1:8000/docs`.

The same server also provides a browser dashboard at `http://127.0.0.1:8000/`. It shows connection health, saved articles, category/search filters, article details, and previous briefings. Use **Collect latest** to call GNews, store new articles, regenerate today's briefing, and refresh the view. This action spends provider quota; **Refresh** only reloads MongoDB data and makes no GNews request. **Auto-collect every** saves a recurring server schedule and refreshes the open page at the same interval. The dashboard never displays the provider key.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/collect` | Fetch GNews articles, save new stories, and generate today's briefing. |
| GET | `/scheduler` | Get the active interval and next run time. |
| PUT | `/scheduler` | Set `interval_minutes` to `1`, `5`, `60`, or `1440`. |
| GET | `/health` | Check application and MongoDB connectivity. |
| GET | `/news?limit=20` | List latest collected articles; `limit` is 1-100. |
| GET | `/news/{id}` | Get an article by its MongoDB ObjectId. |
| GET | `/news/category/{category}` | Filter by a supported category. |
| GET | `/news/search?keyword=python` | Search title, description, and category. |
| GET | `/briefings?limit=20` | List previous briefings; `limit` is 1-100. |
| GET | `/briefings/{date}` | Get a briefing using `YYYY-MM-DD`. |

Examples to enter in Postman:

```text
POST http://127.0.0.1:8000/collect
GET http://127.0.0.1:8000/scheduler
PUT http://127.0.0.1:8000/scheduler
Content-Type: application/json
{"interval_minutes": 1440}
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/news?limit=10
GET http://127.0.0.1:8000/news/REPLACE_WITH_MONGODB_OBJECT_ID
GET http://127.0.0.1:8000/news/category/Quantum%20Computing
GET http://127.0.0.1:8000/news/search?keyword=python
GET http://127.0.0.1:8000/briefings?limit=10
GET http://127.0.0.1:8000/briefings/2026-10-18
```

For a ready-to-import collection, import `postman_collection.json` in Postman. `Collect Latest from GNews` makes a real API request and may use quota; `Set Scheduler to 1 Day` changes the persistent server schedule. Before running `News by ID` or `Briefing by Date`, edit the collection variables to use an article ObjectId and briefing date that exist in your database. Each request includes basic response assertions.

Article and briefing responses are JSON. MongoDB ObjectIds are returned as strings:

```json
{
	"_id": "671234567890abcdef123456",
	"title": "Example technology headline",
	"description": "A short source description.",
	"source": "Example News",
	"author": null,
	"url": "https://example.com/story",
	"category": "AI",
	"published_at": "2026-10-18T05:00:00Z",
	"collected_at": "2026-10-18T06:00:00Z"
}
```

The API returns `400` for invalid categories, article IDs, search keywords, or dates; `404` when an article or briefing is not found; and `503` when MongoDB is unavailable. Database error details and credentials are not sent to clients. FastAPI uses `422` for invalid query parameter formats such as a non-numeric limit. Use one application process because each process starts its own scheduler.

## MongoDB Structure and Compass

The database is named `tech_news`. MongoDB stores BSON documents; dates are stored as BSON dates and returned as ISO-formatted strings by the REST API.

Example `news` document:

```json
{
	"title": "Example technology headline",
	"description": "A short source description.",
	"source": "Example News",
	"author": null,
	"url": "https://example.com/story",
	"category": "AI",
	"published_at": "2026-10-18T05:00:00Z",
	"collected_at": "2026-10-18T06:00:00Z"
}
```

Example `daily_briefings` document:

```json
{
	"briefing_date": "2026-10-18",
	"generated_at": "2026-10-18T06:00:00Z",
	"total_news": 24,
	"categories": {"AI": 5, "Cybersecurity": 3},
	"top_news": [],
	"learning_of_the_day": "Study tool calling and task boundaries in AI agents.",
	"career_opportunity": ["Python and API integration; AI application developer."],
	"created_at": "2026-10-18T06:00:00Z"
}
```

To inspect data in MongoDB Compass:

1. Connect with the same URI as `MONGODB_URI` in `.env`.
2. Open the `tech_news` database and select `news` or `daily_briefings`.
3. Use the Documents tab to inspect records. Example filter: `{ "category": "AI" }`.
4. Use the Indexes tab to inspect the unique `news.url` and `daily_briefings.briefing_date` indexes.

MongoDB terms used here: a database groups collections; a collection groups documents; `_id` is each document's ObjectId; queries filter with conditions such as `$gte`; sorting orders results; indexes speed up lookups and can enforce uniqueness. The application demonstrates insert, find, and update/upsert. Compass can also update or delete a selected test document; avoid deleting real news unless intended.

## Learning Map

| Python concept | Where to see it |
| --- | --- |
| Variables and data types | Configuration constants and article fields. |
| Lists and dictionaries | API responses, article batches, MongoDB documents. |
| Tuples and sets | Category keyword groups and priority categories. |
| Functions, parameters, and return values | Collection, storage, scoring, and API functions. |
| Loops and conditionals | Article normalization, category matching, and scoring. |
| Exception handling | Provider, MongoDB, and API error handling. |
| Modules | Each project `.py` file has one main responsibility. |
| JSON | News provider responses and REST request/response bodies. |
| File handling and environment variables | `python-dotenv` reads local `.env` settings. |
| API requests | `requests.get()` in `news_service.py`. |
| Date and time | Publication dates, collection dates, and briefing dates. |
| Scheduling | APScheduler runs the daily job at the configured time. |

| MongoDB concept | Where to see it |
| --- | --- |
| Database, collection, and document | `tech_news`, its two collections, and Compass Documents. |
| ObjectId | The `_id` field and `GET /news/{id}`. |
| Insert and find | `save_news()` and the REST read endpoints. |
| Update | `save_briefing()` uses an upsert to create or update by date. |
| Delete | Remove a selected test document in Compass. |
| Query, filtering, and sorting | Category/search endpoints and recent-news selection. |
| Index and unique index | Article URL and briefing-date indexes. |

## Final Demonstration Checklist

1. Start MongoDB and connect with MongoDB Compass.
2. Start the application with `py main.py` and show the health endpoint in Postman.
3. Run the daily job manually once with valid provider credentials; explain that this makes a real API request.
4. Show inserted documents and indexes in Compass.
5. In Postman, try latest news, one article by ID, category filtering, keyword search, briefing history, and one briefing by date.
6. Show the generated briefing in the terminal and its stored document in Compass.
7. Show the configured schedule and explain the complete provider → normalization/category → MongoDB → scoring/briefing → API data flow.

## Project Files

- `main.py`: FastAPI app and application entry point.
- `dashboard.html`: local browser UI for testing the API.
- `config.py` and `.env.example`: environment-based settings.
- `models.py`: TypedDict descriptions of article and briefing data.
- `database.py`: MongoDB connection, indexes, and storage helpers.
- `news_service.py`: provider requests and article categorization.
- `briefing_service.py`: relevance scoring and briefing formatting.
- `scheduler.py`: daily orchestration.
- `requirements.txt`: project dependencies.
- `postman_collection.json`: Postman requests for all API endpoints.