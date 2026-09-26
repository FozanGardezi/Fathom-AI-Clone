"""Google Calendar: OAuth 2.0 and the events API.

The flow below is the standard authorization-code exchange, 
and `list_events` calls the Calendarv3 API. 
What it needs to work is a Google Cloud OAuth client; until
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set, `is_configured()` is
false and the API says so rather than failing at the redirect.

Uses `urllib` from the standard library rather than adding an HTTP client to
the dependency list. Three small requests do not justify a new package in a
deployment.
"""

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar}/events"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Read-only: this app displays a calendar, it has no business writing to one.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "openid",
    "email",
]

TIMEOUT = 15


def _ssl_context():
    """An SSL context that can actually verify Google's certificate.

    Several Python builds ship without a usable CA bundle - the python.org
    macOS installer is the common one, which is why "Install
    Certificates.command" exists. On those, every HTTPS call fails with
    CERTIFICATE_VERIFY_FAILED and the cause looks nothing like a certificate
    problem by the time it reaches a user. Pinning certifi's bundle makes the
    behaviour the same on every machine, with no manual step after install.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        # Falls back to whatever the interpreter trusts. Verification stays
        # on either way - this never disables it.
        return ssl.create_default_context()


_SSL_CONTEXT = _ssl_context()


class GoogleCalendarError(Exception):
    """Anything Google refused, with a message fit to show a user."""


def is_configured():
    return bool(getattr(settings, "GOOGLE_CLIENT_ID", "") and
                getattr(settings, "GOOGLE_CLIENT_SECRET", ""))


def _require_configured():
    if not is_configured():
        raise GoogleCalendarError(
            "Google Calendar is not configured on this server. Set "
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )


def _request(url, *, data=None, headers=None, method=None):
    """One HTTP call, with Google's error body surfaced rather than swallowed."""
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=_SSL_CONTEXT) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            payload = json.loads(error.read().decode())
            # Google uses both shapes depending on the endpoint.
            detail = (
                payload.get("error_description")
                or payload.get("error", {}).get("message")
                or (payload.get("error") if isinstance(payload.get("error"), str) else "")
            )
        except Exception:
            pass
        raise GoogleCalendarError(detail or "Google returned %s." % error.code) from error
    except urllib.error.URLError as error:
        raise GoogleCalendarError("Could not reach Google: %s" % error.reason) from error


def authorization_url(state, redirect_uri):
    """Where to send someone to grant access."""
    _require_configured()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        # Required to get a refresh token at all, and `consent` forces one to
        # be reissued even if the user has approved this app before.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return "%s?%s" % (AUTH_URL, urllib.parse.urlencode(params))


def exchange_code(code, redirect_uri):
    """Trade the one-time code for tokens."""
    _require_configured()
    return _request(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )


def refresh_access_token(refresh_token):
    """Get a fresh access token. Google does not return a new refresh token
    here, so the caller keeps the one it has."""
    _require_configured()
    if not refresh_token:
        raise GoogleCalendarError(
            "This calendar has no refresh token. Disconnect and reconnect it."
        )
    return _request(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
    )


def revoke(token):
    """Best effort. A token Google has already forgotten is not an error worth
    blocking a disconnect over."""
    try:
        _request(REVOKE_URL, data={"token": token})
    except GoogleCalendarError:
        pass


def fetch_account_email(access_token):
    try:
        return _request(
            USERINFO_URL, headers={"Authorization": "Bearer %s" % access_token}
        ).get("email", "")
    except GoogleCalendarError:
        return ""


def list_events(access_token, *, time_min, time_max, calendar="primary", max_results=250):
    """Events in a window, single occurrences, in time order.

    `singleEvents` expands a recurring series into its instances, which is
    what a calendar view needs - otherwise a weekly standup arrives as one
    event with a recurrence rule to interpret.
    """
    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    url = "%s?%s" % (
        EVENTS_URL.format(calendar=urllib.parse.quote(calendar)),
        urllib.parse.urlencode(params),
    )
    payload = _request(url, headers={"Authorization": "Bearer %s" % access_token})
    return payload.get("items", [])


# ------------------------------------------------------------------ parsing


def parse_event_time(node):
    """A Google start/end node into a datetime, or None.

    All-day events carry `date` instead of `dateTime`; they are treated as
    starting at midnight in the event's own timezone, which is the best
    available answer without pulling in the calendar's timezone separately.
    """
    if not node:
        return None
    if node.get("dateTime"):
        return datetime.fromisoformat(node["dateTime"])
    if node.get("date"):
        naive = datetime.fromisoformat(node["date"])
        return timezone.make_aware(naive) if timezone.is_naive(naive) else naive
    return None


def detect_platform(event):
    """Work out which conferencing tool the event points at."""
    solution = (
        event.get("conferenceData", {}).get("conferenceSolution", {}).get("key", {}).get("type", "")
    )
    if solution == "hangoutsMeet" or event.get("hangoutLink"):
        return "google_meet"

    haystack = " ".join(
        filter(
            None,
            [
                event.get("location", ""),
                event.get("description", ""),
                *[
                    point.get("uri", "")
                    for point in event.get("conferenceData", {}).get("entryPoints", [])
                ],
            ],
        )
    ).lower()

    if "zoom.us" in haystack:
        return "zoom"
    if "teams.microsoft.com" in haystack or "teams.live.com" in haystack:
        return "microsoft_teams"
    if "meet.google.com" in haystack:
        return "google_meet"
    return "other"


def meeting_url(event):
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for point in event.get("conferenceData", {}).get("entryPoints", []):
        if point.get("entryPointType") == "video" and point.get("uri"):
            return point["uri"]
    location = event.get("location", "")
    return location if location.startswith("http") else ""


def attendees(event):
    """The invite list, as (name, email, is_organizer) triples.

    Rooms and resources are dropped - a conference room is not a participant -
    and anyone who declined is left out, because they were not there.
    """
    people = []
    for attendee in event.get("attendees", []) or []:
        if attendee.get("resource"):
            continue
        if attendee.get("responseStatus") == "declined":
            continue
        email = attendee.get("email", "")
        name = attendee.get("displayName") or (email.split("@")[0] if email else "Guest")
        people.append((name, email, bool(attendee.get("organizer"))))

    organizer = event.get("organizer") or {}
    if organizer.get("email") and not any(
        e.lower() == organizer["email"].lower() for _n, e, _o in people
    ):
        people.append(
            (
                organizer.get("displayName") or organizer["email"].split("@")[0],
                organizer["email"],
                True,
            )
        )
    return people
