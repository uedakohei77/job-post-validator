import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# Historical examples configuration
HISTORICAL_POSTS_PATH = os.getenv(
    "HISTORICAL_POSTS_PATH", str(BASE_DIR / "config" / "historical_posts.json")
)
