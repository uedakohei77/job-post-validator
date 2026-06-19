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
