"""
authorize_youtube.py — (re)generate token.json for YouTube uploads.

Use this when uploads fail with "deleted_client" / "invalid_grant" / 401,
i.e. the OAuth client or refresh token is no longer valid.

Prerequisites (Google Cloud Console, one-time):
  1. Create/restore a project, enable "YouTube Data API v3".
  2. Create an OAuth consent screen (External). While in "Testing", add your
     Google account as a Test user.
  3. Credentials -> Create credentials -> OAuth client ID -> "Desktop app".
  4. Download the JSON and save it as credentials.json next to this script.

Then run:
    python authorize_youtube.py
Sign in with the CHANNEL's Google account and approve. This writes token.json.

Finally, update the GitHub repo secrets (so CI uses the new credentials):
    gh secret set CREDENTIALS_JSON -R gabgaamana00a-a11y/math-quiz-channel < credentials.json
    gh secret set TOKEN_JSON       -R gabgaamana00a-a11y/math-quiz-channel < token.json
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "credentials.json")
TOKEN = os.path.join(HERE, "token.json")


def main():
    if not os.path.exists(CREDS):
        raise SystemExit(
            f"Missing {CREDS}.\n"
            "Download your OAuth client (Desktop app) JSON from Google Cloud "
            "Console and save it as credentials.json, then re-run."
        )
    # access_type=offline + prompt=consent guarantees a refresh_token is issued.
    flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"\nSaved new token.json -> {TOKEN}")
    print("Now update the GitHub secrets CREDENTIALS_JSON and TOKEN_JSON.")


if __name__ == "__main__":
    main()
