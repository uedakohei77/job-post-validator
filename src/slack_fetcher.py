import time

import requests
from config import settings

def fetch_slack_history(channel_id, auth_token, limit=10):
    """
    Fetches the history of messages from a Slack channel.
    Uses the official conversations.history endpoint.
    
    Args:
        channel_id (str): The Slack channel ID.
        auth_token (str): The User OAuth access token (xoxp-...).
        limit (int): Maximum number of messages to fetch (default: 10).
        
    Returns:
        list[dict]: A list of message objects, or an empty list if an error occurs.
    """
    if not channel_id:
        print("Error: Channel ID is not configured.")
        return []
    if not auth_token:
        print("Error: Slack authorization token is missing.")
        return []

    url = "https://slack.com/api/conversations.history"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    params = {
        "channel": channel_id,
        "limit": limit
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        response_json = response.json()
        
        if not response_json.get("ok"):
            error_msg = response_json.get("error", "Unknown Slack API error")
            # If the token is invalid/revoked, let the user know
            if error_msg in ["invalid_auth", "token_revoked"]:
                print(f"Slack API Error: {error_msg}. You might need to re-authenticate.")
            else:
                print(f"Slack API Error: {error_msg}")
            return []
            
        messages = response_json.get("messages", [])
        return messages
        
    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed while fetching Slack history: {e}")
        return []


def fetch_slack_history_since(channel_id, auth_token, oldest_ts, page_size=200, max_retries=5):
    """
    Fetches ALL messages in a channel newer than `oldest_ts`, following Slack's
    cursor pagination and honoring HTTP 429 rate limits.

    Unlike fetch_slack_history (a single page of `limit` messages), this is meant
    for backfills such as "the last 365 days of postings".

    Args:
        channel_id (str): The Slack channel ID.
        auth_token (str): The User OAuth access token (xoxp-...).
        oldest_ts (float): Unix timestamp; only messages after this are returned.
        page_size (int): Messages per API call (Slack recommends <= 200).
        max_retries (int): Max consecutive 429 retries before giving up.

    Returns:
        list[dict]: Message objects, newest first. Empty list on error.
    """
    if not channel_id:
        print("Error: Channel ID is not configured.")
        return []
    if not auth_token:
        print("Error: Slack authorization token is missing.")
        return []

    url = "https://slack.com/api/conversations.history"
    headers = {"Authorization": f"Bearer {auth_token}"}
    messages = []
    cursor = None
    retries = 0

    while True:
        params = {"channel": channel_id, "limit": page_size, "oldest": f"{oldest_ts:.6f}"}
        if cursor:
            params["cursor"] = cursor

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 429:
                retries += 1
                if retries > max_retries:
                    print("Slack API Error: rate limited too many times, giving up.")
                    return messages
                wait = int(response.headers.get("Retry-After", "5"))
                print(f"Rate limited by Slack; retrying in {wait}s...")
                time.sleep(wait)
                continue
            retries = 0
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"HTTP Request failed while fetching Slack history: {e}")
            return messages

        if not data.get("ok"):
            print(f"Slack API Error: {data.get('error', 'Unknown Slack API error')}")
            return messages

        messages.extend(data.get("messages", []))
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not data.get("has_more") or not cursor:
            return messages


def extract_message_texts(messages):
    """
    Extracts the text contents of messages.
    Ignores system messages (e.g., joins, channel name changes) and empty messages.
    
    Args:
        messages (list[dict]): List of message objects.
        
    Returns:
        list[str]: List of message text strings.
    """
    texts = []
    for msg in messages:
        # Ignore subtyped system messages like "channel_join"
        if "subtype" in msg:
            continue
        
        text = msg.get("text", "").strip()
        if text:
            texts.append(text)
            
    return texts
