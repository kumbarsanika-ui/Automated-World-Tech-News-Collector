from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import MONGODB_URI
from datetime import datetime, timezone


class NewsStorageError(Exception):
    """Raised when an article cannot be saved to MongoDB."""


class BriefingStorageError(Exception):
    """Raised when a daily briefing cannot be saved to MongoDB."""


class ScheduleStorageError(Exception):
    """Raised when scheduler settings cannot be read or saved."""


def connect_to_mongodb():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000, tz_aware=True)

    try:
        client.admin.command("ping")

        database = client["tech_news"]
        news_collection = database["news"]
        briefing_collection = database["daily_briefings"]

        news_collection.create_index("url", unique=True)
        briefing_indexes = briefing_collection.index_information()
        date_index = briefing_indexes.get("briefing_date_1")
        if date_index and not date_index.get("unique", False):
            briefing_collection.drop_index("briefing_date_1")
        briefing_collection.create_index("briefing_date", unique=True)
    except PyMongoError:
        client.close()
        raise ConnectionError(
            "MongoDB connection or collection setup failed. Check the service, "
            "URI, permissions, and duplicate article URLs or briefing dates."
        ) from None

    return client, database, news_collection, briefing_collection


def save_news(articles, news_collection):
    inserted_count = 0
    duplicate_count = 0

    try:
        for article in articles:
            try:
                news_collection.insert_one(article)
                inserted_count += 1
            except DuplicateKeyError:
                duplicate_count += 1
    except PyMongoError as error:
        raise NewsStorageError("Could not save news to MongoDB.") from error

    return {"inserted": inserted_count, "duplicates": duplicate_count}


def find_recent_news(news_collection, since):
    try:
        return list(
            news_collection.find({"collected_at": {"$gte": since}}).sort(
                "published_at", -1
            )
        )
    except PyMongoError as error:
        raise NewsStorageError("Could not read recent news from MongoDB.") from error


def save_briefing(briefing, briefing_collection):
    briefing_date = briefing["briefing_date"]
    created_at = briefing.get("created_at", datetime.now(timezone.utc))
    fields_to_update = {
        key: value for key, value in briefing.items() if key != "created_at"
    }

    try:
        briefing_collection.update_one(
            {"briefing_date": briefing_date},
            {
                "$set": fields_to_update,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
    except PyMongoError as error:
        raise BriefingStorageError("Could not save the daily briefing to MongoDB.") from error


def load_scheduler_settings():
    client, database, _, _ = connect_to_mongodb()
    try:
        return database["app_settings"].find_one({"_id": "scheduler"})
    except PyMongoError as error:
        raise ScheduleStorageError("Could not read scheduler settings.") from error
    finally:
        client.close()


def save_scheduler_settings(interval_minutes):
    client, database, _, _ = connect_to_mongodb()
    try:
        database["app_settings"].update_one(
            {"_id": "scheduler"},
            {
                "$set": {
                    "interval_minutes": interval_minutes,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except PyMongoError as error:
        raise ScheduleStorageError("Could not save scheduler settings.") from error
    finally:
        client.close()