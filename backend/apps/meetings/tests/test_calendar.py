"""Tests for the Google Calendar connection and sync.

Google itself is stubbed at the HTTP boundary - `google_calendar.list_events`
and the token calls - because the point is our mapping and reconciliation, not
whether Google returns JSON. The event fixtures below are the real shape the
Calendar v3 API returns.
"""

from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.meetings import calendar_sync, google_calendar
from apps.meetings.models import CalendarConnection, Meeting, Participant

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="host@fathom.test", password="Str0ngPass!2026", full_name="Dana Host"
    )


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def connection(user):
    return CalendarConnection.objects.create(
        user=user,
        provider=CalendarConnection.Provider.GOOGLE,
        account_email="dana@gmail.test",
        access_token="access-token",
        refresh_token="refresh-token",
        token_expires_at=timezone.now() + timedelta(hours=1),
    )


def event(**overrides):
    """A Calendar v3 event, in the shape Google actually sends."""
    start = overrides.pop("start_at", timezone.now() + timedelta(days=1))
    end = overrides.pop("end_at", start + timedelta(minutes=30))
    payload = {
        "id": overrides.pop("id", "evt-1"),
        "status": "confirmed",
        "summary": "Quarterly review",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "organizer": {"email": "dana@gmail.test", "displayName": "Dana Host"},
        "attendees": [
            {"email": "dana@gmail.test", "displayName": "Dana Host", "organizer": True},
            {"email": "ada@partner.test", "displayName": "Ada Lovelace"},
        ],
    }
    payload.update(overrides)
    return payload


class TestConfiguration:
    def test_it_reports_itself_unconfigured_without_credentials(self, client, settings):
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        body = client.get(reverse("calendar-connection")).data
        assert body["is_configured"] is False
        assert body["is_connected"] is False

    def test_connecting_without_credentials_is_refused_clearly(self, client, settings):
        settings.GOOGLE_CLIENT_ID = ""
        settings.GOOGLE_CLIENT_SECRET = ""
        response = client.post(reverse("calendar-connect"))
        assert response.status_code == 501
        assert "not configured" in response.data["detail"]

    def test_with_credentials_it_hands_back_a_google_consent_url(self, client, settings):
        settings.GOOGLE_CLIENT_ID = "client-id.apps.googleusercontent.com"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        url = client.post(reverse("calendar-connect")).data["authorization_url"]
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client-id.apps.googleusercontent.com" in url
        # Without these Google never issues a refresh token.
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "calendar.readonly" in url

    def test_anonymous_callers_are_rejected(self):
        assert APIClient().get(reverse("calendar-connection")).status_code == 401


class TestCallback:
    def test_a_denied_consent_returns_the_user_to_the_app(self, client):
        response = APIClient().get(reverse("calendar-callback"), {"error": "access_denied"})
        assert response.status_code == 302
        assert "calendar=denied" in response.url

    def test_a_tampered_state_is_rejected(self, client):
        response = APIClient().get(
            reverse("calendar-callback"), {"code": "abc", "state": "not-a-signed-state"}
        )
        assert response.status_code == 302
        assert "calendar=failed" in response.url
        assert CalendarConnection.objects.count() == 0

    def test_a_valid_exchange_stores_the_tokens(self, client, user, settings, monkeypatch):
        settings.GOOGLE_CLIENT_ID = "id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        monkeypatch.setattr(
            google_calendar, "exchange_code",
            lambda code, uri: {
                "access_token": "new-access", "refresh_token": "new-refresh",
                "expires_in": 3600, "scope": "calendar.readonly",
            },
        )
        monkeypatch.setattr(google_calendar, "fetch_account_email", lambda t: "dana@gmail.test")

        url = client.post(reverse("calendar-connect")).data["authorization_url"]
        # The state is percent-encoded in the URL; a browser decodes it before
        # handing it back, so the test has to as well.
        signed = parse_qs(urlparse(url).query)["state"][0]

        response = APIClient().get(reverse("calendar-callback"), {"code": "abc", "state": signed})
        assert "calendar=connected" in response.url

        connection = CalendarConnection.objects.get(user=user)
        assert connection.access_token == "new-access"
        assert connection.refresh_token == "new-refresh"
        assert connection.account_email == "dana@gmail.test"
        assert connection.token_expires_at > timezone.now()

    def test_reconnecting_keeps_an_existing_refresh_token(self, client, connection, settings, monkeypatch):
        """Google only issues a refresh token on first consent. Overwriting it
        with nothing would silently break every later refresh."""
        settings.GOOGLE_CLIENT_ID = "id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        monkeypatch.setattr(
            google_calendar, "exchange_code",
            lambda code, uri: {"access_token": "second-access", "expires_in": 3600},
        )
        monkeypatch.setattr(google_calendar, "fetch_account_email", lambda t: "dana@gmail.test")

        url = client.post(reverse("calendar-connect")).data["authorization_url"]
        signed = parse_qs(urlparse(url).query)["state"][0]
        APIClient().get(reverse("calendar-callback"), {"code": "abc", "state": signed})

        connection.refresh_from_db()
        assert connection.access_token == "second-access"
        assert connection.refresh_token == "refresh-token"


class TestSync:
    def _sync(self, monkeypatch, connection, events, now=None):
        monkeypatch.setattr(google_calendar, "list_events", lambda *a, **k: events)
        return calendar_sync.sync_events(connection, access_token="token", now=now)

    def test_an_upcoming_event_becomes_a_scheduled_meeting(self, monkeypatch, connection, user):
        start = timezone.now() + timedelta(days=2)
        counts = self._sync(monkeypatch, connection, [event(start_at=start)])
        assert counts["created"] == 1

        meeting = Meeting.objects.get(owner=user)
        assert meeting.title == "Quarterly review"
        assert meeting.status == Meeting.Status.SCHEDULED
        assert meeting.scheduled_start is not None
        # Not yet happened, so no real start or end.
        assert meeting.started_at is None
        assert meeting.ended_at is None
        assert meeting.external_id.startswith("gcal-")

    def test_a_past_event_becomes_a_finished_meeting_with_no_transcript(
        self, monkeypatch, connection, user
    ):
        start = timezone.now() - timedelta(days=2)
        self._sync(monkeypatch, connection, [event(start_at=start)])

        meeting = Meeting.objects.get(owner=user)
        assert meeting.status == Meeting.Status.READY
        assert meeting.started_at is not None and meeting.ended_at is not None
        assert meeting.duration_seconds == 30 * 60
        # A calendar cannot supply any of this, and nothing is invented.
        assert meeting.segments.count() == 0
        assert meeting.summaries.count() == 0
        assert meeting.action_items.count() == 0
        assert meeting.highlights.count() == 0

    def test_attendees_become_participants_with_the_organiser_as_host(
        self, monkeypatch, connection
    ):
        self._sync(monkeypatch, connection, [event()])
        meeting = Meeting.objects.first()
        assert meeting.participants.count() == 2
        assert meeting.participants.get(role="host").email == "dana@gmail.test"
        assert meeting.participants.filter(display_name="Ada Lovelace").exists()

    def test_rooms_and_decliners_are_not_participants(self, monkeypatch, connection):
        self._sync(monkeypatch, connection, [event(attendees=[
            {"email": "dana@gmail.test", "displayName": "Dana Host", "organizer": True},
            {"email": "room@resource.test", "displayName": "Boardroom", "resource": True},
            {"email": "no@partner.test", "displayName": "Declined Person",
             "responseStatus": "declined"},
        ])])
        names = set(Meeting.objects.first().participants.values_list("display_name", flat=True))
        assert names == {"Dana Host"}

    @pytest.mark.parametrize("payload,expected", [
        ({"hangoutLink": "https://meet.google.com/abc-defg-hij"}, "google_meet"),
        ({"location": "https://acme.zoom.us/j/123"}, "zoom"),
        ({"location": "https://teams.microsoft.com/l/meetup-join/x"}, "microsoft_teams"),
        ({"location": "Meeting room 3"}, "other"),
    ])
    def test_the_platform_is_read_from_the_event(self, monkeypatch, connection, payload, expected):
        self._sync(monkeypatch, connection, [event(**payload)])
        assert Meeting.objects.first().platform == expected

    def test_cancelled_events_are_skipped(self, monkeypatch, connection):
        counts = self._sync(monkeypatch, connection, [event(status="cancelled")])
        assert counts["created"] == 0 and counts["skipped"] == 1
        assert Meeting.objects.count() == 0

    def test_syncing_twice_updates_rather_than_duplicates(self, monkeypatch, connection):
        self._sync(monkeypatch, connection, [event()])
        counts = self._sync(monkeypatch, connection, [event(summary="Renamed review")])
        assert counts["created"] == 0 and counts["updated"] == 1
        assert Meeting.objects.count() == 1
        assert Meeting.objects.first().title == "Renamed review"

    def test_a_resync_does_not_duplicate_participants(self, monkeypatch, connection):
        self._sync(monkeypatch, connection, [event()])
        self._sync(monkeypatch, connection, [event()])
        assert Meeting.objects.first().participants.count() == 2

    def test_a_recorded_meeting_survives_a_resync(self, monkeypatch, connection, user):
        """The calendar does not know this call was recorded here, and must
        not overwrite what the recording produced."""
        from apps.meetings.models import TranscriptSegment

        start = timezone.now() - timedelta(days=1)
        self._sync(monkeypatch, connection, [event(start_at=start)])
        meeting = Meeting.objects.first()
        speaker = meeting.participants.first()
        TranscriptSegment.objects.create(
            meeting=meeting, speaker=speaker, start_ms=0, end_ms=4_000, text="We agreed to ship."
        )
        original_end = meeting.ended_at

        self._sync(monkeypatch, connection, [event(start_at=start)])
        meeting.refresh_from_db()
        assert meeting.segments.count() == 1
        assert meeting.ended_at == original_end

    def test_it_records_when_it_last_synced(self, monkeypatch, connection):
        self._sync(monkeypatch, connection, [event()])
        connection.refresh_from_db()
        assert connection.last_synced_at is not None
        assert connection.last_sync_error == ""

    def test_all_day_events_are_handled(self, monkeypatch, connection):
        today = timezone.localdate()
        self._sync(monkeypatch, connection, [event(
            start={"date": today.isoformat()},
            end={"date": (today + timedelta(days=1)).isoformat()},
        )])
        assert Meeting.objects.count() == 1


class TestSyncEndpoint:
    def test_syncing_without_a_connection_is_a_400(self, client):
        response = client.post(reverse("calendar-sync"))
        assert response.status_code == 400
        assert "No calendar is connected" in response.data["detail"]

    def test_it_reports_what_it_did(self, client, connection, monkeypatch):
        monkeypatch.setattr(google_calendar, "list_events", lambda *a, **k: [event()])
        body = client.post(reverse("calendar-sync")).data
        assert body["created"] == 1
        assert body["connection"]["is_connected"] is True
        assert body["connection"]["last_synced_at"] is not None

    def test_a_google_failure_is_reported_not_swallowed(self, client, connection, monkeypatch):
        def explode(*args, **kwargs):
            raise google_calendar.GoogleCalendarError("Rate limit exceeded")

        monkeypatch.setattr(google_calendar, "list_events", explode)
        response = client.post(reverse("calendar-sync"))
        assert response.status_code == 502
        assert response.data["detail"] == "Rate limit exceeded"
        connection.refresh_from_db()
        assert connection.last_sync_error == "Rate limit exceeded"

    def test_an_expired_token_is_refreshed_first(self, client, connection, monkeypatch):
        connection.token_expires_at = timezone.now() - timedelta(minutes=5)
        connection.save()
        refreshed = {}

        def fake_refresh(token):
            refreshed["called_with"] = token
            return {"access_token": "refreshed-token", "expires_in": 3600}

        monkeypatch.setattr(google_calendar, "refresh_access_token", fake_refresh)
        monkeypatch.setattr(google_calendar, "list_events", lambda *a, **k: [])

        assert client.post(reverse("calendar-sync")).status_code == 200
        assert refreshed["called_with"] == "refresh-token"
        connection.refresh_from_db()
        assert connection.access_token == "refreshed-token"


class TestDisconnect:
    def test_it_forgets_the_connection_and_tells_google(self, client, connection, monkeypatch):
        revoked = []
        monkeypatch.setattr(google_calendar, "revoke", lambda token: revoked.append(token))
        body = client.delete(reverse("calendar-connection")).data
        assert body["is_connected"] is False
        assert CalendarConnection.objects.count() == 0
        assert revoked == ["refresh-token"]
