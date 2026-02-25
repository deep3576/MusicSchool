import datetime
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import uuid

# If modifying these scopes, delete token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def create_google_meet():
    creds = None

    # Token file stores user access after first login
    if os.path.exists('../instance/API/token.json'):
        creds = Credentials.from_authorized_user_file('../instance/API/token.json', SCOPES)

    # If no valid credentials, login flow starts
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '../instance/API/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('../instance/API/token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    # ⏰ Meeting time (example: tomorrow 5 PM, 45 mins)
    start_time = datetime.datetime.now() + datetime.timedelta(days=1)
    start_time = start_time.replace(hour=17, minute=0, second=0)
    end_time = start_time + datetime.timedelta(minutes=45)

    event = {
        'summary': 'Music Class - The Rhythm School',
        'description': 'Online music class session.',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Toronto',
        },
        'attendees': [
            {'email': 'deep3576@gmail.com'},
            {'email': 'uber.inderdeep@gmail.com'}
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        },
    }

    event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates='all'
    ).execute()

    print("Meeting created!")
    print("Google Meet link:", event['hangoutLink'])


if __name__ == '__main__':
    create_google_meet()
