import datetime
import os
import uuid
from pathlib import Path

from flask import current_app, has_app_context

# If modifying these scopes, delete token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _api_base_path() -> Path:
    if has_app_context():
        return Path(current_app.instance_path) / "API"
    return Path(__file__).resolve().parent.parent / "instance" / "API"


def _load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    api_path = _api_base_path()
    token_path = api_path / "token.json"
    creds_path = api_path / "credentials.json"

    creds = None

    # Token file stores user access after first login
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If no valid credentials, login flow starts
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with token_path.open("w") as token:
            token.write(creds.to_json())

    return creds


def create_google_meet(start_time, end_time, student_email, teacher_email=None, summary=None, description=None):
    try:
        from googleapiclient.discovery import build
    except Exception:
        return {"meet_link": None, "event_id": None}

    creds = _load_credentials()
    service = build('calendar', 'v3', credentials=creds)

    tz_name = os.getenv("BOOKING_TIMEZONE", "America/Toronto")
    school_email = os.getenv("SCHOOL_NOTIFY_EMAIL", "therythmschool@gmail.com")
    attendees = [{"email": student_email}, {"email": school_email}]
    if teacher_email:
        attendees.append({"email": teacher_email})

    event = {
        'summary': summary or 'Music Class - The Rhythm School',
        'description': description or 'Online music class session.',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': tz_name,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': tz_name,
        },
        'attendees': attendees,
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

    return {
        "meet_link": event.get("hangoutLink"),
        "event_id": event.get("id"),
    }


if __name__ == '__main__':
    start = datetime.datetime.now() + datetime.timedelta(days=1)
    end = start + datetime.timedelta(minutes=45)
    print(create_google_meet(start, end, "student@example.com"))
