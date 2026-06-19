# Job Post Validator

An automated validation tool that fetches volunteer job postings from Slack and uses Gemini's structured output capability to verify that their contents (working hours, task description, and reward points) are logically consistent, complete, and correct.

## Core Features

- **Pydantic Validation Schema**: Guarantees clean, typed validation reports (e.g., validation status, duration calculation, points/hour rate, corrections needed).
- **Dynamic Few-Shot In-Context Learning**: Uses Gemini's embeddings (`text-embedding-004`) to find the top-3 most similar historical posts from [config/historical_posts.json](file:///Users/koheiueda/antigravity/JobPostValidator/config/historical_posts.json). It only feeds those top-3 relevant examples to Gemini on each validation check, optimizing cost, speed, and validation accuracy.
- **Auto-Caching Vector Embeddings**: The tool automatically checks for and populates missing embedding vectors in the reference JSON file on run, making ingestion completely automated.
- **Slack OAuth Integration**: Implements a clean OAuth 2.0 flow with a local redirection callback server to authenticate and retrieve Slack User Tokens (`xoxp-...`) safely.
- **Dry-Run & Interactive Modes**: Fully testable CLI options without requiring active Slack setup.

## Project Structure

```
JobPostValidator/
├── config/
│   ├── settings.py           # Configuration loading, environment variables
│   └── historical_posts.json # Historical posts used as few-shot reference examples
├── src/
│   ├── auth.py               # Slack OAuth redirect receiver and token manager
│   ├── slack_fetcher.py      # Slack history fetching logic
│   ├── models.py             # Pydantic schemas (VolunteerPostValidation)
│   ├── validator.py          # Gemini API validation orchestrator
│   └── main.py               # CLI entrypoint
├── .env.example              # Template for credentials
├── requirements.txt          # Python dependencies
└── README.md                 # User documentation
```

## Setup & Installation

### 1. Initialize Virtual Environment and Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

1. Copy the template:
   ```bash
   cp .env.example .env
   ```
2. Fill in the keys in `.env`:
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `SLACK_CLIENT_ID`: Your Slack App's Client ID.
   - `SLACK_CLIENT_SECRET`: Your Slack App's Client Secret.
   - `SLACK_CHANNEL_ID`: Channel ID of the channel to read posts from.
   - `SLACK_PORT`: Port for the local OAuth redirect server (default: `8080`).

### 3. Configure Slack App redirect URI

Ensure your Slack App has `http://localhost:8080/` (or the custom port you set in `SLACK_PORT`) configured under **OAuth & Permissions > Redirect URLs**. Also, ensure you request the `channels:history` user scope.

## How to Run

You can run the script in three different modes:

### 1. Dry Run Mode (No Slack Connection Required)
Validates local mock volunteer posts to demonstrate Gemini's reasoning and Pydantic validation:
```bash
python3 src/main.py --dry-run
```

### 2. Interactive Mode
Allows typing or pasting a volunteer post manually to run immediate validation:
```bash
python3 src/main.py --interactive
```

### 3. Slack Fetcher Mode (Production Pipeline)
Fetches recent posts from your Slack channel and validates them:
```bash
python3 src/main.py
```
*Note: If no cached token file `slack_token.json` exists, the tool will automatically launch a browser to initiate the OAuth consent flow, capture the authorization code on `http://localhost:8080/`, and exchange it for a user access token.*

To force re-authentication (e.g. if the token expires or scope changes):
```bash
python3 src/main.py --force-reauth
```
