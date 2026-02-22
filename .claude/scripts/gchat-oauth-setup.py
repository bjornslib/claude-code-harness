#!/usr/bin/env python3
"""One-time OAuth2 setup for Google Chat API access.

Run this ONCE to authorize and store refresh tokens:
    python3 .claude/scripts/gchat-oauth-setup.py

This opens a browser window for Google authorization.
After approval, tokens are stored at .claude/credentials/google-chat-token.json
and will auto-refresh on subsequent uses.
"""
import json
import sys
from pathlib import Path

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CREDENTIALS_DIR = PROJECT_ROOT / ".claude" / "credentials"
CLIENT_SECRET = CREDENTIALS_DIR / "google-chat-oauth-client.json"
TOKEN_FILE = CREDENTIALS_DIR / "google-chat-token.json"

SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.messages.create",
]

def main():
    if not CLIENT_SECRET.exists():
        print(f"ERROR: Client secret not found at {CLIENT_SECRET}")
        print("Copy your OAuth2 client secret JSON to this location first.")
        sys.exit(1)

    if TOKEN_FILE.exists():
        print(f"Token file already exists at {TOKEN_FILE}")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != "y":
            print("Aborted.")
            sys.exit(0)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib")
        sys.exit(1)

    print(f"Using client secret: {CLIENT_SECRET}")
    print("Opening browser for authorization...")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json())

    print()
    print(f"Token saved to: {TOKEN_FILE}")
    print("OAuth2 setup complete. The token will auto-refresh on subsequent uses.")

    # Quick test
    try:
        from googleapiclient.discovery import build
        service = build("chat", "v1", credentials=creds)
        # Try to list spaces to verify
        result = service.spaces().list(pageSize=5).execute()
        spaces = result.get("spaces", [])
        print(f"\nVerification: Found {len(spaces)} accessible spaces.")
        for s in spaces[:3]:
            print(f"  - {s.get('displayName', s.get('name', 'unnamed'))}")
    except Exception as e:
        print(f"\nWarning: Verification failed ({e}), but token was saved successfully.")
        print("The token may still work for the specific space you have access to.")

if __name__ == "__main__":
    main()
