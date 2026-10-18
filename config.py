import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
GNEWS_API_URL = os.getenv("GNEWS_API_URL", "https://gnews.io/api/v4/search")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
NEWS_SCHEDULE_HOUR = int(os.getenv("NEWS_SCHEDULE_HOUR", "6"))
NEWS_SCHEDULE_MINUTE = int(os.getenv("NEWS_SCHEDULE_MINUTE", "0"))
NEWS_TIMEZONE = os.getenv("NEWS_TIMEZONE", "UTC")

if not 0 <= NEWS_SCHEDULE_HOUR <= 23:
    raise ValueError("NEWS_SCHEDULE_HOUR must be between 0 and 23")

if not 0 <= NEWS_SCHEDULE_MINUTE <= 59:
    raise ValueError("NEWS_SCHEDULE_MINUTE must be between 0 and 59")