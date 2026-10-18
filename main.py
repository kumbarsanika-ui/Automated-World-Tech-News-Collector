from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from re import escape
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from bson import ObjectId
from pydantic import BaseModel
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from database import ScheduleStorageError, connect_to_mongodb
from news_service import CATEGORY_KEYWORDS
from scheduler import get_schedule_status, run_daily_job, start_scheduler, update_schedule


@asynccontextmanager
async def lifespan(app):
    scheduler = start_scheduler()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Daily Global Tech News Scheduler", lifespan=lifespan)


class ScheduleUpdate(BaseModel):
    interval_minutes: Literal[1, 5, 60, 1440]


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).resolve().with_name("dashboard.html"))


def get_collections():
    try:
        client, database, news_collection, briefing_collection = connect_to_mongodb()
    except ConnectionError:
        raise HTTPException(status_code=503, detail="Database is unavailable.") from None

    try:
        yield news_collection, briefing_collection
    finally:
        client.close()


@app.exception_handler(PyMongoError)
async def handle_database_error(request: Request, error: PyMongoError):
    return JSONResponse(
        status_code=503,
        content={"detail": "The database request could not be completed."},
    )


def serialize_document(document):
    if isinstance(document, ObjectId):
        return str(document)
    if isinstance(document, dict):
        return {key: serialize_document(value) for key, value in document.items()}
    if isinstance(document, list):
        return [serialize_document(value) for value in document]
    return document


@app.get("/health")
def health_check(collections: tuple = Depends(get_collections)):
    return {"status": "ok", "database": "connected"}


@app.post("/collect")
def collect_latest_news():
    result = run_daily_job()
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@app.get("/scheduler")
def read_scheduler(request: Request):
    return get_schedule_status(request.app.state.scheduler)


@app.put("/scheduler")
def change_scheduler(settings: ScheduleUpdate, request: Request):
    try:
        return update_schedule(request.app.state.scheduler, settings.interval_minutes)
    except (ConnectionError, ScheduleStorageError):
        raise HTTPException(status_code=503, detail="Could not save scheduler settings.") from None
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


@app.get("/news")
def get_latest_news(
    limit: int = Query(default=20, ge=1, le=100),
    collections: tuple = Depends(get_collections),
):
    news_collection, _ = collections
    documents = news_collection.find().sort("collected_at", DESCENDING).limit(limit)
    return [serialize_document(document) for document in documents]


@app.get("/news/category/{category}")
def get_news_by_category(
    category: str,
    limit: int = Query(default=20, ge=1, le=100),
    collections: tuple = Depends(get_collections),
):
    valid_categories = [*CATEGORY_KEYWORDS, "Other Technology"]
    matched_category = next(
        (item for item in valid_categories if item.casefold() == category.casefold()),
        None,
    )
    if matched_category is None:
        raise HTTPException(status_code=400, detail="Invalid news category.")

    news_collection, _ = collections
    documents = (
        news_collection.find({"category": matched_category})
        .sort("collected_at", DESCENDING)
        .limit(limit)
    )
    return [serialize_document(document) for document in documents]


@app.get("/news/search")
def search_news(
    keyword: str,
    limit: int = Query(default=20, ge=1, le=100),
    collections: tuple = Depends(get_collections),
):
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Search keyword cannot be empty.")

    pattern = {"$regex": escape(keyword), "$options": "i"}
    news_collection, _ = collections
    documents = (
        news_collection.find(
            {"$or": [{"title": pattern}, {"description": pattern}, {"category": pattern}]}
        )
        .sort("collected_at", DESCENDING)
        .limit(limit)
    )
    return [serialize_document(document) for document in documents]


@app.get("/news/{article_id}")
def get_news_article(
    article_id: str,
    collections: tuple = Depends(get_collections),
):
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=400, detail="Article ID must be a valid MongoDB ID.")

    news_collection, _ = collections
    document = news_collection.find_one({"_id": ObjectId(article_id)})
    if document is None:
        raise HTTPException(status_code=404, detail="News article not found.")
    return serialize_document(document)


@app.get("/briefings")
def get_briefings(
    limit: int = Query(default=20, ge=1, le=100),
    collections: tuple = Depends(get_collections),
):
    _, briefing_collection = collections
    documents = (
        briefing_collection.find().sort("briefing_date", DESCENDING).limit(limit)
    )
    return [serialize_document(document) for document in documents]


@app.get("/briefings/{briefing_date}")
def get_briefing(
    briefing_date: str,
    collections: tuple = Depends(get_collections),
):
    try:
        parsed_date = datetime.strptime(briefing_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Briefing date must use YYYY-MM-DD format."
        ) from None

    if parsed_date.isoformat() != briefing_date:
        raise HTTPException(
            status_code=400, detail="Briefing date must use YYYY-MM-DD format."
        )

    _, briefing_collection = collections
    document = briefing_collection.find_one({"briefing_date": briefing_date})
    if document is None:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    return serialize_document(document)


def main():
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()