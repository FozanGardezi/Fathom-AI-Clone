"""Test fixtures for the meetings app.

Every factory takes the parent it hangs off and fills the rest with something
plausible, so a test names only the fields it actually cares about. Parents
default to being created on demand, which keeps single-model tests to one line.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.meetings.models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)

User = get_user_model()

# Counter for factories that need a unique value per call. Participant emails
# are unique per meeting, so tests that make several must not collide.
_sequence = iter(range(1, 10_000))


def _next(prefix):
    return "%s%d" % (prefix, next(_sequence))


def make_user(email=None, **extra):
    return User.objects.create_user(
        email=email or _next("user") + "@fathom.test",
        password="Str0ngPass!2026",
        **extra,
    )


def make_meeting(owner=None, **extra):
    """A finished, 30-minute meeting unless told otherwise."""
    owner = owner or make_user()
    started = extra.pop("started_at", timezone.now() - timedelta(hours=1))
    defaults = {
        "title": "Weekly sync",
        "owner": owner,
        "started_at": started,
        "ended_at": started + timedelta(minutes=30) if started else None,
        "status": Meeting.Status.READY,
    }
    defaults.update(extra)
    return Meeting.objects.create(**defaults)


def make_participant(meeting=None, **extra):
    meeting = meeting or make_meeting()
    defaults = {
        "meeting": meeting,
        "display_name": "Ada Lovelace",
        "email": _next("person") + "@fathom.test",
    }
    defaults.update(extra)
    return Participant.objects.create(**defaults)


def make_segment(meeting=None, **extra):
    """A two-second utterance. `end_ms` follows `start_ms` unless given, so a
    test can move a segment along the timeline without restating both ends."""
    meeting = meeting or make_meeting()
    start = extra.pop("start_ms", 0)
    defaults = {
        "meeting": meeting,
        "start_ms": start,
        "end_ms": start + 2_000,
        "text": "Hello everyone.",
    }
    defaults.update(extra)
    return TranscriptSegment.objects.create(**defaults)


def make_summary(meeting=None, **extra):
    """A pending summary - call `mark_ready()` or pass status/generated_at."""
    meeting = meeting or make_meeting()
    defaults = {
        "meeting": meeting,
        "template": MeetingSummary.Template.GENERAL,
        "summary": "The team agreed to cut scope.",
        "topics": ["Budget", "Timeline"],
        "decisions": ["Cut the reporting module"],
    }
    defaults.update(extra)
    return MeetingSummary.objects.create(**defaults)


def make_action_item(meeting=None, **extra):
    meeting = meeting or make_meeting()
    defaults = {"meeting": meeting, "title": "Draft the revised timeline"}
    defaults.update(extra)
    return ActionItem.objects.create(**defaults)


def make_highlight(meeting=None, **extra):
    meeting = meeting or make_meeting()
    defaults = {
        "meeting": meeting,
        "title": "The budget decision",
        "start_ms": 1_000,
        "end_ms": 5_000,
    }
    defaults.update(extra)
    return Highlight.objects.create(**defaults)
