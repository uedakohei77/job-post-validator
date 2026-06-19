import json
from pathlib import Path
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import requests
from config import settings

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the OAuth redirect callback."""
    
    code = None
    error = None

    def do_GET(self):
        # Parse the path and query parameters
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if "code" in query_params:
            OAuthCallbackHandler.code = query_params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # Return a friendly confirmation message in HTML
            html_response = """
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background-color: #f5f6fa; color: #2f3640; }
                        .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center; max-width: 400px; }
                        h1 { color: #2ecc71; margin-bottom: 10px; }
                        p { color: #718093; line-height: 1.5; }
                        .success-icon { font-size: 48px; margin-bottom: 20px; color: #2ecc71; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="success-icon">✓</div>
                        <h1>Authentication Successful!</h1>
                        <p>Slack OAuth authentication was successful. You can safely close this browser window and return to your terminal.</p>
                    </div>
                </body>
            </html>
            """
            self.wfile.write(html_response.encode("utf-8"))
        else:
            error_msg = query_params.get("error", ["unknown_error"])[0]
            OAuthCallbackHandler.error = error_msg
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html_response = f"""
            <html>
                <head>
                    <title>Authentication Failed</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background-color: #f5f6fa; color: #2f3640; }}
                        .card {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center; max-width: 400px; }}
                        h1 {{ color: #e74c3c; margin-bottom: 10px; }}
                        p {{ color: #718093; line-height: 1.5; }}
                        .error-icon {{ font-size: 48px; margin-bottom: 20px; color: #e74c3c; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="error-icon">✗</div>
                        <h1>Authentication Failed</h1>
                        <p>Slack OAuth authentication failed with error: <strong>{error_msg}</strong>. Please check your Slack App configuration.</p>
                    </div>
                </body>
            </html>
            """
            self.wfile.write(html_response.encode("utf-8"))

    def log_message(self, format, *args):
        # Silence default request logging to keep terminal output clean
        pass


def run_callback_server(port):
    """Starts a temporary web server to receive the Slack auth callback code."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    
    print(f"Waiting for authorization callback on http://localhost:{port}/...")
    try:
        # Handle a single request, which will block until the redirect occurs
        httpd.handle_request()
    finally:
        httpd.server_close()
    
    return OAuthCallbackHandler.code, OAuthCallbackHandler.error


def get_slack_token(force_reauth=False):
    """
    Retrieves the Slack user token. Looks for a cached local file 'slack_token.json'.
    If missing or invalid (or force_reauth=True), initiates OAuth 2.0 flow.
    """
    token_path = Path(settings.SLACK_TOKEN_FILE)
    
    # 1. Attempt to load cached token
    if not force_reauth and token_path.exists():
        try:
            with open(token_path, "r") as f:
                data = json.load(f)
                token = data.get("access_token")
                if token:
                    return token
        except Exception as e:
            print(f"Warning: Failed to load cached token from {token_path}: {e}")

    # 2. Check credentials for OAuth
    client_id = settings.SLACK_CLIENT_ID
    client_secret = settings.SLACK_CLIENT_SECRET
    
    if not client_id or not client_secret:
        print("\n" + "="*80)
        print("SLACK AUTHENTICATION ERROR")
        print("="*80)
        print("Missing SLACK_CLIENT_ID and/or SLACK_CLIENT_SECRET in environment variables.")
        print("Please check your .env file.")
        print("\nAlternatively, you can manually place a User Token starting with 'xoxp-'")
        print(f"in a file at: {token_path} with the following JSON structure:")
        print('{\n  "access_token": "xoxp-your-token-here"\n}')
        print("="*80 + "\n")
        sys.exit(1)

    # 3. Perform OAuth 2.0 Flow
    port = settings.SLACK_PORT
    redirect_uri = f"http://localhost:{port}/"
    
    # Define scopes needed to fetch channel history
    # 'channels:history' allows reading public channel history
    # 'groups:history' allows reading private channel history
    # We request channels:history under user scopes (user_scope) to obtain a User Token (xoxp-)
    scopes = "channels:history"
    
    auth_params = {
        "client_id": client_id,
        "user_scope": scopes,
        "redirect_uri": redirect_uri
    }
    
    auth_url = "https://slack.com/oauth/v2/authorize?" + urllib.parse.urlencode(auth_params)
    
    print("\n" + "="*80)
    print("SLACK OAUTH AUTHORIZATION REQUIRED")
    print("="*80)
    print("Please open the following URL in your web browser to authorize this tool:")
    print(f"\n{auth_url}\n")
    print("="*80 + "\n")
    
    # Try to open the browser automatically
    try:
        import webbrowser
        webbrowser.open(auth_url)
    except Exception:
        pass
        
    # Start local callback server to receive authorization code
    code, error = run_callback_server(port)
    
    if error:
        print(f"Error during OAuth flow: {error}")
        sys.exit(1)
        
    if not code:
        print("Failed to receive authorization code from the Slack callback.")
        sys.exit(1)
        
    print("Exchanging authorization code for access token...")
    
    # Exchange code for access token
    exchange_url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    response = requests.post(exchange_url, data=data)
    response_json = response.json()
    
    if not response_json.get("ok"):
        print(f"Token exchange failed: {response_json.get('error')}")
        print(f"Details: {response_json}")
        sys.exit(1)
        
    # Extract user token (xoxp-...)
    # In Slack OAuth v2, user tokens are returned under the 'authed_user' key
    authed_user = response_json.get("authed_user", {})
    access_token = authed_user.get("access_token")
    
    # Fallback to top-level access_token if bot scopes were granted instead
    if not access_token:
        access_token = response_json.get("access_token")
        
    if not access_token:
        print("Could not find access_token in the Slack OAuth response.")
        print(f"Response: {response_json}")
        sys.exit(1)
        
    # Save the token locally
    token_data = {
        "access_token": access_token,
        "app_id": response_json.get("app_id"),
        "team_id": response_json.get("team", {}).get("id"),
        "authed_user_id": authed_user.get("id")
    }
    
    try:
        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        print(f"Successfully authenticated! Token cached at {token_path}")
    except Exception as e:
        print(f"Warning: Could not save token file: {e}")
        
    return access_token
