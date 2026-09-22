"""Tests for `manage.py seed_demo_data`."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.meetings.demo_data import DEMO_PREFIX, MEETINGS
from apps.meetings.models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


class _Capture(StringIO):
    """Django's OutputWrapper flushes its stream after the test has finished,
    which on a plain StringIO raises 'I/O operation on closed file' into the
    test output. Ignoring close() keeps the buffer usable until it is
    collected."""

    def close(self):
        pass


def seed(*args):
    out = _Capture()
    call_command("seed_demo_data", *args, stdout=out)
    return out.getvalue()


def past_meetings():
    """Seeded meetings that have actually happened - the scheduled ones carry
    no transcript, summary or follow-ups."""
    return Meeting.objects.filter(status=Meeting.Status.READY)


def counts():
    return {
        "meetings": Meeting.objects.count(),
        "participants": Participant.objects.count(),
        "segments": TranscriptSegment.objects.count(),
        "summaries": MeetingSummary.objects.count(),
        "action_items": ActionItem.objects.count(),
        "highlights": Highlight.objects.count(),
    }


class TestSeeding:
    def test_creates_every_meeting_in_the_dataset(self):
        seed()
        assert Meeting.objects.count() == len(MEETINGS)
        assert past_meetings().count() == 6
        assert Meeting.objects.filter(status=Meeting.Status.SCHEDULED).count() == 3

    def test_every_meeting_matches_its_spec(self):
        seed()
        for spec in MEETINGS:
            meeting = Meeting.objects.get(external_id=DEMO_PREFIX + spec["key"])
            assert meeting.title == spec["title"]
            assert meeting.participants.count() == len(spec["people"])
            assert meeting.action_items.count() == len(spec.get("action_items", []))
            assert meeting.highlights.count() == len(spec.get("highlights", []))
            assert meeting.summaries.count() == (1 if spec.get("summary") else 0)
            if spec.get("status", "ready") == "ready":
                assert meeting.duration_seconds == spec["duration_minutes"] * 60
            else:
                # Not yet happened: scheduled, with no start or end.
                assert meeting.duration_seconds is None
                assert meeting.scheduled_start > timezone.now()

    def test_the_required_meetings_are_present_with_the_required_shape(self):
        seed()
        expected = {
            "Customer Discovery — Acme": (4, 45),
            "Product Roadmap Sync": (5, 58),
            "Enterprise Sales Call — Northwind": (4, 38),
            "Engineering Standup": (6, 23),
            "One-on-One — Sofia & Meera": (2, 30),
            "Company Planning — Q1": (8, 60),
        }
        for title, (people, minutes) in expected.items():
            meeting = Meeting.objects.get(title=title)
            assert meeting.participants.count() == people
            assert meeting.duration_seconds == minutes * 60

    def test_upcoming_meetings_are_scheduled_with_no_transcript(self):
        seed()
        upcoming = Meeting.objects.filter(status=Meeting.Status.SCHEDULED)
        assert upcoming.count() == 3
        for meeting in upcoming:
            assert meeting.scheduled_start > timezone.now()
            assert meeting.started_at is None and meeting.ended_at is None
            assert meeting.segments.count() == 0
            assert meeting.summaries.count() == 0
            assert meeting.action_items.count() == 0
            # They still have an invite list.
            assert meeting.participants.count() >= 3
            assert not meeting.participants.filter(joined_at__isnull=False).exists()

    def test_company_planning_meets_its_minimums(self):
        seed()
        meeting = Meeting.objects.get(title="Company Planning — Q1")
        assert meeting.action_items.count() >= 6
        assert meeting.highlights.count() >= 3
        assert len(meeting.summaries.first().decisions) >= 3

    def test_every_meeting_that_happened_has_a_ready_summary(self):
        seed()
        assert MeetingSummary.objects.count() == past_meetings().count()
        for summary in MeetingSummary.objects.all():
            assert summary.status == MeetingSummary.Status.READY
            assert summary.generated_at is not None
            assert summary.topics and summary.decisions
            assert len(summary.summary) > 200

    def test_internal_people_get_accounts_and_guests_do_not(self):
        seed()
        internal = Participant.objects.filter(email__endswith="@fathom.test")
        external = Participant.objects.exclude(email__endswith="@fathom.test")
        assert internal.exists() and external.exists()
        assert not internal.filter(user__isnull=True).exists()
        assert not external.filter(user__isnull=False).exists()

    def test_every_meeting_is_owned_by_its_host(self):
        seed()
        for meeting in Meeting.objects.all():
            host = meeting.participants.get(role=Participant.Role.HOST)
            assert meeting.owner == host.user


class TestTranscript:
    def test_every_meeting_has_a_substantial_transcript(self):
        seed()
        for meeting in past_meetings():
            assert meeting.segments.count() >= 25

    def test_segments_are_chronological_and_never_overlap(self):
        seed()
        for meeting in past_meetings():
            segments = list(meeting.segments.order_by("start_ms", "id"))
            for earlier, later in zip(segments, segments[1:]):
                assert earlier.end_ms <= later.start_ms
                assert earlier.start_ms <= earlier.end_ms

    def test_transcripts_fit_inside_the_meeting(self):
        seed()
        for meeting in past_meetings():
            last = meeting.segments.order_by("-end_ms").first()
            assert last.end_ms <= meeting.duration_seconds * 1000

    def test_transcripts_span_most_of_the_meeting(self):
        """Turns are spread across the call, not bunched at the start.

        The excerpt does not have to run to the final second - the last quoted
        section starts around three-quarters in - but it must reach the closing
        stretch of every meeting.
        """
        seed()
        for meeting in past_meetings():
            last = meeting.segments.order_by("-end_ms").first()
            assert last.end_ms > meeting.duration_seconds * 1000 * 0.75

    def test_transcripts_start_at_the_beginning(self):
        seed()
        for meeting in past_meetings():
            first = meeting.segments.order_by("start_ms").first()
            assert first.start_ms == 0

    def test_every_segment_is_attributed_to_someone_in_the_meeting(self):
        seed()
        for segment in TranscriptSegment.objects.select_related("speaker"):
            assert segment.speaker is not None
            assert segment.speaker.meeting_id == segment.meeting_id

    def test_the_dialogue_is_not_placeholder_text(self):
        seed()
        texts = list(TranscriptSegment.objects.values_list("text", flat=True))
        # No lorem ipsum, and no line repeated verbatim anywhere in the corpus.
        assert not any("lorem" in t.lower() or "ipsum" in t.lower() for t in texts)
        assert len(set(texts)) == len(texts)
        assert sum(len(t.split()) for t in texts) > 2_000

    def test_talk_time_is_derived_from_the_transcript(self):
        seed()
        for participant in Participant.objects.all():
            spoken = sum(s.duration_ms for s in participant.segments.all())
            assert participant.talk_time_seconds == round(spoken / 1000)


class TestActionItemsAndHighlights:
    def test_action_item_owners_are_in_their_own_meeting(self):
        seed()
        for item in ActionItem.objects.select_related("owner"):
            assert item.owner is not None
            assert item.owner.meeting_id == item.meeting_id

    def test_completed_items_carry_a_timestamp(self):
        seed()
        assert ActionItem.objects.filter(completed=True).exists()
        for item in ActionItem.objects.filter(completed=True):
            assert item.completed_at is not None
        for item in ActionItem.objects.filter(completed=False):
            assert item.completed_at is None

    def test_highlights_line_up_with_real_transcript_spans(self):
        seed()
        for highlight in Highlight.objects.all():
            assert highlight.end_ms >= highlight.start_ms
            # The bounds were taken from segments, so the span must contain some.
            assert highlight.segments.exists()
            assert highlight.text.strip()


class TestIdempotency:
    def test_running_twice_does_not_duplicate_anything(self):
        seed()
        first = counts()
        seed()
        assert counts() == first

    def test_running_five_times_is_still_stable(self):
        seed()
        first = counts()
        for _ in range(4):
            seed()
        assert counts() == first

    def test_reseeding_produces_identical_transcripts(self):
        """Timings are seeded per meeting, so a reseed is byte-identical."""
        seed()
        before = list(
            TranscriptSegment.objects.order_by("meeting__external_id", "start_ms")
            .values_list("meeting__external_id", "start_ms", "end_ms", "text")
        )
        seed()
        after = list(
            TranscriptSegment.objects.order_by("meeting__external_id", "start_ms")
            .values_list("meeting__external_id", "start_ms", "end_ms", "text")
        )
        assert before == after

    def test_reseeding_reuses_demo_accounts(self):
        seed()
        users = set(User.objects.values_list("email", flat=True))
        seed()
        assert set(User.objects.values_list("email", flat=True)) == users

    def test_it_leaves_non_demo_data_alone(self):
        keeper = Meeting.objects.create(
            title="Real meeting",
            owner=User.objects.create_user(email="real@example.test", password="x"),
        )
        seed()
        seed()
        keeper.refresh_from_db()
        assert keeper.title == "Real meeting"
        assert Meeting.objects.count() == len(MEETINGS) + 1

    def test_clear_removes_only_the_demo_dataset(self):
        keeper = Meeting.objects.create(
            title="Real meeting",
            owner=User.objects.create_user(email="real@example.test", password="x"),
        )
        seed()
        output = seed("--clear")
        assert "Removed 9 demo meeting(s)" in output
        assert list(Meeting.objects.all()) == [keeper]
        assert TranscriptSegment.objects.count() == 0
        assert Highlight.objects.count() == 0


class TestOutput:
    def test_it_reports_what_it_created(self):
        output = seed()
        assert "9 meetings" in output
        assert "transcript segments" in output
        for spec in MEETINGS:
            assert spec["title"][:34] in output

    def test_a_reseed_says_it_is_replacing(self):
        seed()
        assert "Replacing 9 existing demo meeting(s)" in seed()


class TestShareWith:
    """`--share-with` exists because the API scopes meetings to the people in
    them, so demo data is invisible to an account registered by hand."""

    def test_an_outside_account_sees_nothing_without_it(self):
        outsider = User.objects.create_user(email="outsider@example.test", password="x")
        seed()
        from apps.meetings.views import visible_meetings

        assert visible_meetings(outsider).count() == 0

    def test_share_with_adds_them_to_every_meeting(self):
        outsider = User.objects.create_user(
            email="outsider@example.test", password="x", full_name="Outside Person"
        )
        seed()
        output = seed("--share-with", "outsider@example.test")

        from apps.meetings.views import visible_meetings

        assert visible_meetings(outsider).count() == Meeting.objects.count()
        assert "Added outsider@example.test to 9 demo meeting(s)" in output

    def test_it_does_not_fake_attendance(self):
        outsider = User.objects.create_user(email="outsider@example.test", password="x")
        seed("--share-with", "outsider@example.test")
        added = Participant.objects.filter(user=outsider)
        assert added.exists()
        for participant in added:
            # Granted access, not present in the room - anything else would
            # corrupt the talk-time figures derived from the transcript.
            assert participant.joined_at is None
            assert participant.talk_time_seconds == 0

    def test_the_seeded_cast_is_left_intact(self):
        outsider = User.objects.create_user(email="outsider@example.test", password="x")
        seed()
        before = Participant.objects.exclude(user=outsider).count()
        seed("--share-with", "outsider@example.test")
        assert Participant.objects.exclude(user=outsider).count() == before

    def test_it_is_idempotent(self):
        User.objects.create_user(email="outsider@example.test", password="x")
        seed("--share-with", "outsider@example.test")
        first = counts()
        seed("--share-with", "outsider@example.test")
        assert counts() == first

    def test_an_unknown_email_fails_loudly(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError, match="No account with the email"):
            seed("--share-with", "nobody@example.test")

    def test_the_plain_run_explains_why_the_dashboard_looks_empty(self):
        output = seed()
        assert "only returns meetings you own or attended" in output
        assert "--share-with" in output
