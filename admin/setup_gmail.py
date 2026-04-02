"""
Run this ONCE to authorize the app with the group Gmail account.
It will open a browser window — log in with dominustecum@gmail.com.
The resulting token.json contents go into your .env as GMAIL_TOKEN.

Usage:
    python3 setup_gmail.py
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets',
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES
    )
    creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as f:
        f.write(creds.to_json())

    print('\n✓ token.json created!')
    print('\nCopy the contents below into your .env as GMAIL_TOKEN=')
    print('(or paste it as an environment variable on Render)\n')
    print(creds.to_json())

if __name__ == '__main__':
    main()
