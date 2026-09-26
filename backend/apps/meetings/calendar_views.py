"""Endpoints for connecting and syncing an external calendar."""

import logging

from django.conf import settings
from django.core import signing
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from . import calendar_sync, google_calendar
from .models import CalendarConnection
from .serializers import CalendarConnectionSerializer

# The state parameter is signed rather than stored: the callback arrives as a
# plain browser redirect with no Authorization header, so it has to carry
# proof of who started the flow. Signing means no server-side session to keep.
logger = logging.getLogger(__name__)

STATE_SALT = "meetings.calendar.oauth"
STATE_MAX_AGE = 600  # ten minutes is longer than any consent screen takes


def _connection_state(user):
    """The payload every calendar endpoint answers with."""
    connection = CalendarConnection.objects.filter(
        user=user, provider=CalendarConnection.Provider.GOOGLE
    ).first()
    return {
        "provider": CalendarConnection.Provider.GOOGLE,
        "provider_label": CalendarConnection.Provider.GOOGLE.label,
        # False means the server has no OAuth client, which is a different
        # problem from the user not having connected yet - the UI shows a
        # different thing for each.
        "is_configured": google_calendar.is_configured(),
        "is_connected": connection is not None,
        "account_email": connection.account_email if connection else "",
        "last_synced_at": connection.last_synced_at if connection else None,
        "last_sync_error": connection.last_sync_error if connection else "",
    }


def _fresh_access_token(connection):
    """A usable access token, refreshing it first if it has aged out."""
    if not connection.is_expired:
        return connection.access_token

    payload = google_calendar.refresh_access_token(connection.refresh_token)
    connection.access_token = payload["access_token"]
    if payload.get("expires_in"):
        connection.token_expires_at = timezone.now() + timedelta(
            seconds=int(payload["expires_in"])
        )
    connection.save(update_fields=["access_token", "token_expires_at", "updated_at"])
    return connection.access_token


class CalendarConnectionView(generics.GenericAPIView):
    """GET and DELETE /api/v1/calendar/connection/"""

    serializer_class = CalendarConnectionSerializer

    def get(self, request):
        return Response(self.get_serializer(_connection_state(request.user)).data)

    def delete(self, request):
        connection = CalendarConnection.objects.filter(
            user=request.user, provider=CalendarConnection.Provider.GOOGLE
        ).first()
        if connection:
            # Tell Google too, so access actually ends rather than merely
            # being forgotten on our side.
            google_calendar.revoke(connection.refresh_token or connection.access_token)
            connection.delete()
        return Response(self.get_serializer(_connection_state(request.user)).data)


class CalendarConnectView(APIView):
    """POST /api/v1/calendar/connect/

    Hands back the Google consent URL for the browser to visit. The exchange
    happens on the callback below, server side, so the client secret is never
    anywhere near a browser.
    """

    def post(self, request):
        if not google_calendar.is_configured():
            return Response(
                {
                    "detail": "Google Calendar is not configured on this server. "
                    "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        state = signing.dumps({"user_id": str(request.user.pk)}, salt=STATE_SALT)
        return Response(
            {
                "authorization_url": google_calendar.authorization_url(
                    state, settings.GOOGLE_REDIRECT_URI
                )
            }
        )


class CalendarCallbackView(APIView):
    """GET /api/v1/calendar/callback/

    Where Google sends the browser back. Unauthenticated by necessity - a
    top-level redirect carries no bearer token - so the signed `state` is what
    establishes who this is. It always ends in a redirect to the frontend,
    because a user should never be left looking at raw JSON.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _failed(self, reason, detail=""):
        """Send the browser back, and leave the real reason somewhere findable.

        The user gets a short code in the URL; the operator gets the full
        message in the log. An earlier version of this discarded the exception
        entirely, which turned an SSL trust failure into a blank "that didn't
        complete" with nothing anywhere to diagnose it from.
        """
        logger.warning("Calendar OAuth callback failed (%s): %s", reason, detail or "-")
        return redirect(
            "%s/calendar?calendar=failed&reason=%s"
            % (settings.FRONTEND_URL.rstrip("/"), reason)
        )

    def get(self, request):
        frontend = settings.FRONTEND_URL.rstrip("/")

        if request.GET.get("error"):
            return redirect("%s/calendar?calendar=denied" % frontend)

        code = request.GET.get("code")
        raw_state = request.GET.get("state", "")
        if not code or not raw_state:
            return self._failed("missing_code")

        try:
            state = signing.loads(raw_state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
            user = User.objects.get(pk=state["user_id"])
        except signing.SignatureExpired:
            return self._failed("expired")
        except (signing.BadSignature, User.DoesNotExist, KeyError) as error:
            return self._failed("bad_state", str(error))

        try:
            payload = google_calendar.exchange_code(code, settings.GOOGLE_REDIRECT_URI)
        except google_calendar.GoogleCalendarError as error:
            # Whatever Google actually said - a redirect mismatch, a bad
            # secret, a TLS problem reaching them at all.
            return self._failed("exchange", str(error))

        connection = CalendarConnection.objects.filter(
            user=user, provider=CalendarConnection.Provider.GOOGLE
        ).first() or CalendarConnection(
            user=user, provider=CalendarConnection.Provider.GOOGLE
        )

        connection.access_token = payload.get("access_token", "")
        # Google issues a refresh token on first consent only. Keeping the
        # existing one matters - overwriting it with "" on a re-auth would
        # silently break every future refresh.
        if payload.get("refresh_token"):
            connection.refresh_token = payload["refresh_token"]
        if payload.get("expires_in"):
            connection.token_expires_at = timezone.now() + timedelta(
                seconds=int(payload["expires_in"])
            )
        connection.scope = payload.get("scope", "")
        connection.account_email = google_calendar.fetch_account_email(
            connection.access_token
        )
        connection.save()

        return redirect("%s/calendar?calendar=connected" % frontend)


class CalendarSyncView(APIView):
    """POST /api/v1/calendar/sync/

    Pulls a window of events and reconciles them into meetings. Safe to press
    repeatedly - matching on the Google event id makes a second run an update.
    """

    def post(self, request):
        connection = CalendarConnection.objects.filter(
            user=request.user, provider=CalendarConnection.Provider.GOOGLE
        ).first()
        if not connection:
            return Response(
                {"detail": "No calendar is connected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = _fresh_access_token(connection)
            counts = calendar_sync.sync_events(connection, access_token=token)
        except google_calendar.GoogleCalendarError as error:
            connection.last_sync_error = str(error)
            connection.save(update_fields=["last_sync_error", "updated_at"])
            return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                **counts,
                "connection": CalendarConnectionSerializer(
                    _connection_state(request.user)
                ).data,
            }
        )
