import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Slack configuration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")
SLACK_PORT = int(os.getenv("SLACK_PORT", "8080"))
SLACK_TOKEN_FILE = os.getenv("SLACK_TOKEN_FILE", str(BASE_DIR / "slack_token.json"))

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")

# Category suggestion module
CATEGORY_INDEX_PATH = os.getenv(
    "CATEGORY_INDEX_PATH", str(BASE_DIR / "data" / "category_index.json")
)
# Postings are fetched from this date (YYYY-MM-DD, UTC) up to the time of the run.
# Kept as a string and validated by the CLI, so a typo can never break the validator.
CATEGORY_START_DATE = os.getenv("CATEGORY_START_DATE", "2025-01-01")
# Channels to scan for past postings (comma-separated), e.g. the current school
# year's channel plus last year's. Defaults to SLACK_CHANNEL_ID. The validator
# keeps using SLACK_CHANNEL_ID only.
CATEGORY_CHANNEL_IDS = [
    c.strip() for c in os.getenv("CATEGORY_CHANNEL_IDS", "").split(",") if c.strip()
] or ([SLACK_CHANNEL_ID] if SLACK_CHANNEL_ID else [])

# Historical examples configuration
HISTORICAL_POSTS_PATH = os.getenv(
    "HISTORICAL_POSTS_PATH", str(BASE_DIR / "config" / "historical_posts.json")
)
