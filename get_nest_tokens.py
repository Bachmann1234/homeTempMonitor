#!/usr/bin/env python3

import urllib.parse
import urllib.request
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/?code="):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)

            if "code" in params:
                self.server.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"""
                <html>
                <body>
                    <h1>Authorization successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """
                )
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Error: No authorization code received</h1>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress log messages


def get_auth_code(client_id, project_id, redirect_uri="http://localhost:8080"):
    # OAuth parameters
    scope = "https://www.googleapis.com/auth/sdm.service"

    # Build authorization URL
    auth_url = "https://nestservices.google.com/partnerconnections/{}/auth".format(
        project_id
    )
    params = {
        "redirect_uri": redirect_uri,
        "access_type": "offline",
        "prompt": "consent",
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
    }

    full_auth_url = auth_url + "?" + urllib.parse.urlencode(params)

    print("Opening browser for authorization...")
    print(f"If the browser doesn't open, visit this URL manually:")
    print(full_auth_url)
    print()

    # Parse redirect URI to get port
    parsed_uri = urllib.parse.urlparse(redirect_uri)
    port = parsed_uri.port or 8080

    # Start local server to receive callback
    server = HTTPServer(("localhost", port), OAuthHandler)
    server.auth_code = None

    # Start server in background
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Open browser
    webbrowser.open(full_auth_url)

    # Wait for authorization
    print("Waiting for authorization...")
    timeout = 300  # 5 minutes
    start_time = time.time()

    while server.auth_code is None and (time.time() - start_time) < timeout:
        time.sleep(1)

    server.shutdown()

    if server.auth_code is None:
        raise Exception("Authorization timed out or failed")

    return server.auth_code


def exchange_code_for_tokens(
    client_id, client_secret, auth_code, redirect_uri="http://localhost:8080"
):
    token_url = "https://www.googleapis.com/oauth2/v4/token"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    # Encode data
    post_data = urllib.parse.urlencode(data).encode("utf-8")

    # Make request
    req = urllib.request.Request(token_url, data=post_data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"Token exchange failed: {e.code} {e.reason}\n{error_body}")


def main():
    print("=== Nest API Token Generator ===")
    print()

    # Get client credentials
    client_id = input("Enter your Google OAuth Client ID: ").strip()
    if not client_id:
        print("Error: Client ID is required")
        return

    client_secret = input("Enter your Google OAuth Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required")
        return

    project_id = input("Enter your Device Access Project ID: ").strip()
    if not project_id:
        print("Error: Project ID is required")
        return

    # Ask about ngrok
    use_ngrok = input("Are you using ngrok? (y/n): ").strip().lower()
    if use_ngrok == "y":
        ngrok_url = input(
            "Enter your ngrok URL (e.g., https://abc123.ngrok.io): "
        ).strip()
        if not ngrok_url:
            print("Error: ngrok URL is required")
            return
        redirect_uri = ngrok_url
        print(f"Using ngrok redirect URI: {redirect_uri}")
        print("Make sure to add this redirect URI to your Google OAuth config!")
    else:
        redirect_uri = "http://localhost:8080"
        print(f"Using localhost redirect URI: {redirect_uri}")

    print()
    print("Starting OAuth flow...")

    try:
        # Step 1: Get authorization code
        auth_code = get_auth_code(client_id, project_id, redirect_uri)
        print(f"✓ Authorization code received")

        # Step 2: Exchange code for tokens
        tokens = exchange_code_for_tokens(
            client_id, client_secret, auth_code, redirect_uri
        )

        if "access_token" in tokens and "refresh_token" in tokens:
            print()
            print("✓ Success! Here are your tokens:")
            print()
            print("=== Add these to your .env file ===")
            print(f"NEST_CLIENT_ID={client_id}")
            print(f"NEST_CLIENT_SECRET={client_secret}")
            print(f"NEST_REFRESH_TOKEN={tokens['refresh_token']}")
            print(f"NEST_PROJECT_ID={project_id}")
            print()
            print("Access Token (expires in 1 hour):")
            print(f"NEST_ACCESS_TOKEN={tokens['access_token']}")
            print()
            print("The refresh token is what you need for long-term access.")
            print("The access token will be automatically refreshed by your app.")

        else:
            print("Error: Did not receive expected tokens")
            print("Response:", tokens)

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
