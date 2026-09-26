"""Bring Google Calendar events into the meetings table.

What a calendar can and cannot give you is worth stating plainly, because it
sets the shape of everything below.

It gives you: a title, a start and end, a conferencing link, and an invite
list. That is enough to make a real Meeting with real Participants, so an
upcoming call shows up in Upcoming and a past one shows up in Recent.

It does not give you a recording. There is no transcript in a calendar event,
and so no summary, no decisions, no action items and no highlights either -
those are all derived from speech, and a calendar never heard any. Past events
therefore import as meetings with nothing attached, and the UI already says
"No transcript yet" for exactly that case. The way to get a transcript for one
of them is to record it with the live feature.

Syncing is idempotent: events are matched on their Google id, so running it
twice updates in place. Anything recorded against a synced meeting survives a
re-sync - the sync only ever touches the fields the calendar owns.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import google_calendar
from .models import Meeting, Participant

# Prefix on external_id, which is what makes a re-sync an update rather than a
# duplicate. Seeded demo meetings use "demo-", so the two never collide.
SOURCE_PREFIX = "gcal-"

DEFAULT_PAST_DAYS = 30
DEFAULT_FUTURE_DAYS = 60


def _external_id(event):
    return SOURCE_PREFIX + event["id"]


def _status_for(start, end, now):
    """A calendar event that has already finished is a meeting that happened.

    It gets `ready` rather than `scheduled` so it appears in Recent - with no
    transcript, which is the truth about it.
    """
    if end and end <= now:
        return Meeting.Status.READY
    if start and start <= now <= (end or now):
        return Meeting.Status.RECORDING
    return Meeting.Status.SCHEDULED


@transaction.atomic
def sync_events(connection, *, access_token, past_days=DEFAULT_PAST_DAYS,
                future_days=DEFAULT_FUTURE_DAYS, now=None):
    """Pull a window of events and reconcile them into meetings.

    Returns counts rather than objects: the caller reports what changed, and
    the client refetches through the ordinary endpoints.
    """
    now = now or timezone.now()
    events = google_calendar.list_events(
        access_token,
        time_min=now - timedelta(days=past_days),
        time_max=now + timedelta(days=future_days),
    )

    created = updated = skipped = 0

    for event in events:
        # Cancelled events come back in the feed so clients can remove them.
        if event.get("status") == "cancelled":
            skipped += 1
            continue

        start = google_calendar.parse_event_time(event.get("start"))
        end = google_calendar.parse_event_time(event.get("end"))
        if not start:
            skipped += 1
            continue

        status = _status_for(start, end, now)
        has_happened = status == Meeting.Status.READY

        defaults = {
            "owner": connection.user,
            "title": (event.get("summary") or "Untitled meeting")[:255],
            "platform": google_calendar.detect_platform(event),
            "meeting_url": google_calendar.meeting_url(event)[:200],
            "scheduled_start": start,
            # Only a meeting that has already finished gets real start and end
            # times; a future one has a slot, not a duration.
            "started_at": start if has_happened else None,
            "ended_at": end if has_happened else None,
        }

        meeting = Meeting.objects.filter(
            owner=connection.user, external_id=_external_id(event)
        ).first()

        if meeting is None:
            meeting = Meeting.objects.create(
                external_id=_external_id(event), status=status, **defaults
            )
            created += 1
        else:
            for field, value in defaults.items():
                setattr(meeting, field, value)
            # A meeting that was recorded through this app keeps its own
            # status and timings - the calendar does not know it happened here
            # and must not overwrite that.
            if not meeting.segments.exists():
                meeting.status = status
            else:
                meeting.started_at = meeting.started_at or start
                meeting.ended_at = meeting.ended_at or end
            meeting.save()
            updated += 1

        _sync_participants(meeting, event, joined_at=start if has_happened else None)

    connection.last_synced_at = now
    connection.last_sync_error = ""
    connection.save(update_fields=["last_synced_at", "last_sync_error", "updated_at"])

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": created + updated,
    }


def _sync_participants(meeting, event, joined_at):
    """Add anyone on the invite who is not already in the meeting.

    Additive only. Someone who spoke in a recording of this meeting must not
    be removed because they are missing from the calendar invite, and their
    talk time must survive a re-sync.
    """
    existing = {
        (p.email or "").lower(): p for p in meeting.participants.all() if p.email
    }

    for name, email, is_organizer in google_calendar.attendees(event):
        key = (email or "").lower()
        if key and key in existing:
            continue
        Participant.objects.create(
            meeting=meeting,
            display_name=name[:150],
            email=email,
            role=Participant.Role.HOST if is_organizer else Participant.Role.ATTENDEE,
            joined_at=joined_at,
        )
        if key:
            existing[key] = True
