"""Model-level tests for the meetings app.

These exercise the database contract - defaults, constraints, cascades and the
derived properties - rather than the API, which has its own suite in
test_api.py.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.meetings.models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
    format_offset,
)

from .factories import (
    make_action_item,
    make_highlight,
    make_meeting,
    make_participant,
    make_segment,
    make_summary,
    make_user,
)

pytestmark = pytest.mark.django_db


def check_deferred_constraints():
    """Force the database to check DEFERRABLE constraints right now.

    The cross-meeting foreign keys are DEFERRABLE INITIALLY DEFERRED - the same
    way Django writes its own - so they are normally verified at COMMIT. A test
    runs inside a transaction that never commits, so without this the violation
    would surface during teardown instead of at the statement that caused it.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class TestFormatOffset:
    @pytest.mark.parametrize(
        "ms,expected",
        [
            (0, "00:00"),
            (5_000, "00:05"),
            (65_000, "01:05"),
            (599_000, "09:59"),
            (3_600_000, "1:00:00"),
            (3_723_000, "1:02:03"),
        ],
    )
    def test_offsets_render_for_the_ui(self, ms, expected):
        assert format_offset(ms) == expected


class TestMeeting:
    def test_defaults(self):
        meeting = Meeting.objects.create(title="Kickoff", owner=make_user())
        assert meeting.status == Meeting.Status.SCHEDULED
        assert meeting.platform == Meeting.Platform.OTHER
        assert meeting.language == "en"
        assert meeting.external_id == ""
        assert str(meeting) == "Kickoff"

    def test_duration_is_none_until_the_call_ends(self):
        meeting = make_meeting(ended_at=None, status=Meeting.Status.RECORDING)
        assert meeting.duration is None
        assert meeting.duration_seconds is None
        assert meeting.is_live is True

    def test_duration_once_both_ends_are_known(self):
        start = timezone.now() - timedelta(minutes=45)
        meeting = make_meeting(started_at=start, ended_at=start + timedelta(minutes=45))
        assert meeting.duration == timedelta(minutes=45)
        assert meeting.duration_seconds == 45 * 60
        assert meeting.is_live is False

    def test_cannot_end_before_it_starts(self):
        now = timezone.now()
        with pytest.raises(IntegrityError):
            Meeting.objects.create(
                title="Time travel", owner=make_user(),
                started_at=now, ended_at=now - timedelta(minutes=5),
            )

    def test_an_open_meeting_is_allowed(self):
        meeting = make_meeting(started_at=timezone.now(), ended_at=None)
        assert meeting.ended_at is None

    def test_external_id_is_unique_per_platform(self):
        owner = make_user()
        make_meeting(owner=owner, platform=Meeting.Platform.ZOOM, external_id="abc-123")

        # The same id on another platform is a different call.
        make_meeting(owner=owner, platform=Meeting.Platform.MICROSOFT_TEAMS,
                     external_id="abc-123")

        with pytest.raises(IntegrityError):
            make_meeting(owner=owner, platform=Meeting.Platform.ZOOM, external_id="abc-123")

    def test_blank_external_ids_do_not_collide(self):
        owner = make_user()
        make_meeting(owner=owner, platform=Meeting.Platform.ZOOM, external_id="")
        make_meeting(owner=owner, platform=Meeting.Platform.ZOOM, external_id="")
        assert Meeting.objects.filter(external_id="").count() == 2

    def test_ordering_is_newest_first(self):
        owner = make_user()
        now = timezone.now()
        older = make_meeting(owner=owner, title="Older", started_at=now - timedelta(days=2))
        newer = make_meeting(owner=owner, title="Newer", started_at=now - timedelta(hours=2))
        assert list(Meeting.objects.all()) == [newer, older]

    def test_deleting_the_owner_removes_their_meetings(self):
        owner = make_user()
        make_meeting(owner=owner)
        owner.delete()
        assert Meeting.objects.count() == 0


class TestParticipant:
    def test_defaults_and_str(self):
        participant = make_participant(display_name="Ada Lovelace")
        assert participant.role == Participant.Role.ATTENDEE
        assert participant.talk_time_seconds == 0
        assert str(participant) == "Ada Lovelace"

    @pytest.mark.parametrize(
        "role,expected",
        [
            (Participant.Role.HOST, True),
            (Participant.Role.COHOST, True),
            (Participant.Role.ATTENDEE, False),
        ],
    )
    def test_is_host_covers_cohosts(self, role, expected):
        assert make_participant(role=role).is_host is expected

    def test_same_email_twice_in_one_meeting_is_rejected(self):
        meeting = make_meeting()
        make_participant(meeting=meeting, email="ada@fathom.test")
        with pytest.raises(IntegrityError):
            make_participant(meeting=meeting, display_name="Ada again",
                             email="ada@fathom.test")

    def test_same_email_in_different_meetings_is_fine(self):
        owner = make_user()
        first, second = make_meeting(owner=owner), make_meeting(owner=owner)
        make_participant(meeting=first, email="ada@fathom.test")
        make_participant(meeting=second, email="ada@fathom.test")
        assert Participant.objects.filter(email="ada@fathom.test").count() == 2

    def test_anonymous_participants_can_share_a_blank_email(self):
        meeting = make_meeting()
        make_participant(meeting=meeting, display_name="Dial-in 1", email="")
        make_participant(meeting=meeting, display_name="Dial-in 2", email="")
        assert meeting.participants.filter(email="").count() == 2

    def test_cannot_leave_before_joining(self):
        now = timezone.now()
        with pytest.raises(IntegrityError):
            make_participant(joined_at=now, left_at=now - timedelta(minutes=1))

    def test_ordering_is_by_name(self):
        meeting = make_meeting()
        make_participant(meeting=meeting, display_name="Zoe")
        make_participant(meeting=meeting, display_name="Ada")
        assert [p.display_name for p in meeting.participants.all()] == ["Ada", "Zoe"]

    def test_deleting_the_user_keeps_the_participant_row(self):
        user = make_user(email="attendee@fathom.test")
        participant = make_participant(user=user, email="attendee@fathom.test")
        user.delete()
        participant.refresh_from_db()  # SET_NULL keeps the attendance record
        assert participant.user is None
        assert participant.email == "attendee@fathom.test"

    def test_deleting_the_meeting_removes_participants(self):
        meeting = make_meeting()
        make_participant(meeting=meeting)
        meeting.delete()
        assert Participant.objects.count() == 0


class TestTranscriptSegment:
    def test_duration_and_timestamp(self):
        segment = make_segment(start_ms=65_000, end_ms=68_500)
        assert segment.duration_ms == 3_500
        assert segment.timestamp == "01:05"

    def test_str_truncates_long_text(self):
        segment = make_segment(text="word " * 40)
        assert str(segment).endswith("…")
        assert len(str(segment)) < 60

    def test_zero_length_segment_is_allowed(self):
        assert make_segment(start_ms=1_000, end_ms=1_000).duration_ms == 0

    def test_cannot_end_before_it_starts(self):
        with pytest.raises(IntegrityError):
            make_segment(start_ms=5_000, end_ms=4_999)

    def test_segments_read_back_in_timestamp_order(self):
        meeting = make_meeting()
        make_segment(meeting=meeting, start_ms=10_000, text="third")
        make_segment(meeting=meeting, start_ms=0, text="first")
        make_segment(meeting=meeting, start_ms=5_000, text="second")
        assert [s.text for s in meeting.segments.all()] == ["first", "second", "third"]

    def test_speaker_label_survives_speaker_deletion(self):
        meeting = make_meeting()
        speaker = make_participant(meeting=meeting)
        segment = make_segment(meeting=meeting, speaker=speaker, speaker_label="Speaker 1")
        speaker.delete()
        segment.refresh_from_db()
        assert segment.speaker is None
        assert segment.speaker_label == "Speaker 1"  # transcript stays readable

    def test_deleting_the_meeting_removes_the_transcript(self):
        meeting = make_meeting()
        make_segment(meeting=meeting)
        meeting.delete()
        assert TranscriptSegment.objects.count() == 0

    def test_confidence_bounds_are_validated(self):
        # Unsaved: saving would trip the database constraint first, which is a
        # different code path (covered by the test below).
        segment = TranscriptSegment(meeting=make_meeting(), start_ms=0, end_ms=1_000,
                                    text="x", confidence=1.5)
        with pytest.raises(ValidationError):
            segment.full_clean()

    def test_confidence_bounds_are_enforced_by_the_database(self):
        with pytest.raises(IntegrityError):
            make_segment(confidence=1.5)

    def test_a_confidence_in_range_is_accepted(self):
        assert make_segment(confidence=0.92).confidence == 0.92

    def test_transcript_round_trip(self):
        """The shape the UI actually reads: speaker + timestamp + text."""
        meeting = make_meeting()
        ada = make_participant(meeting=meeting, display_name="Ada")
        bob = make_participant(meeting=meeting, display_name="Bob")
        make_segment(meeting=meeting, speaker=ada, start_ms=0, end_ms=2_000, text="Morning.")
        make_segment(meeting=meeting, speaker=bob, start_ms=2_100, end_ms=6_000,
                     text="Shall we start?")

        lines = [
            (s.speaker.display_name, s.timestamp, s.text)
            for s in meeting.segments.select_related("speaker")
        ]
        assert lines == [("Ada", "00:00", "Morning."), ("Bob", "00:02", "Shall we start?")]


class TestSpeakerCannotCrossMeetings:
    """A participant from meeting A must never speak in meeting B."""

    def test_database_rejects_a_speaker_from_another_meeting(self):
        owner = make_user()
        a, b = make_meeting(owner=owner), make_meeting(owner=owner)
        stranger = make_participant(meeting=b)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_segment(meeting=a, speaker=stranger)
                check_deferred_constraints()

    def test_full_clean_reports_it_as_a_field_error(self):
        owner = make_user()
        a, b = make_meeting(owner=owner), make_meeting(owner=owner)
        stranger = make_participant(meeting=b)
        segment = TranscriptSegment(meeting=a, speaker=stranger, start_ms=0,
                                    end_ms=1_000, text="x")
        with pytest.raises(ValidationError) as excinfo:
            segment.full_clean()
        assert "speaker" in excinfo.value.message_dict

    def test_an_unattributed_segment_is_still_fine(self):
        assert make_segment(speaker=None).speaker is None


class TestMeetingSummary:
    def test_defaults(self):
        summary = make_summary()
        assert summary.status == MeetingSummary.Status.PENDING
        assert summary.template == MeetingSummary.Template.GENERAL
        assert summary.generated_at is None
        assert summary.is_ready is False

    def test_topics_and_decisions_round_trip_as_lists(self):
        summary = make_summary(topics=["A", "B"], decisions=["Ship it"])
        summary.refresh_from_db()
        assert summary.topics == ["A", "B"]
        assert summary.decisions == ["Ship it"]

    def test_they_default_to_empty_lists(self):
        summary = MeetingSummary.objects.create(meeting=make_meeting())
        summary.refresh_from_db()
        assert summary.topics == [] and summary.decisions == []

    def test_mark_ready_stamps_the_generation_time(self):
        summary = make_summary()
        summary.mark_ready()
        summary.refresh_from_db()
        assert summary.is_ready is True
        assert summary.generated_at is not None

    def test_ready_without_a_generation_time_is_rejected(self):
        with pytest.raises(IntegrityError):
            make_summary(status=MeetingSummary.Status.READY, generated_at=None)

    def test_a_pending_summary_needs_no_generation_time(self):
        assert make_summary(generated_at=None).generated_at is None

    def test_one_summary_per_template_per_meeting(self):
        meeting = make_meeting()
        make_summary(meeting=meeting, template=MeetingSummary.Template.GENERAL)
        with pytest.raises(IntegrityError):
            make_summary(meeting=meeting, template=MeetingSummary.Template.GENERAL)

    def test_different_templates_coexist_on_one_meeting(self):
        meeting = make_meeting()
        make_summary(meeting=meeting, template=MeetingSummary.Template.GENERAL)
        make_summary(meeting=meeting, template=MeetingSummary.Template.STANDUP)
        assert meeting.summaries.count() == 2

    def test_str_names_the_template(self):
        assert "General summary" in str(make_summary())

    def test_deleting_the_meeting_removes_its_summaries(self):
        meeting = make_meeting()
        make_summary(meeting=meeting)
        meeting.delete()
        assert MeetingSummary.objects.count() == 0


class TestActionItem:
    def test_defaults(self):
        item = make_action_item()
        assert item.completed is False
        assert item.completed_at is None
        assert item.due_date is None
        assert item.owner is None  # unassigned items are normal
        assert str(item) == "Draft the revised timeline"

    def test_mark_completed_then_reopen(self):
        item = make_action_item()
        item.mark_completed()
        item.refresh_from_db()
        assert item.completed is True and item.completed_at is not None

        item.reopen()
        item.refresh_from_db()
        assert item.completed is False and item.completed_at is None

    def test_completed_without_a_timestamp_is_rejected(self):
        with pytest.raises(IntegrityError):
            make_action_item(completed=True, completed_at=None)

    def test_open_with_a_timestamp_is_rejected(self):
        with pytest.raises(IntegrityError):
            make_action_item(completed=False, completed_at=timezone.now())

    def test_overdue_only_applies_to_open_dated_items(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        assert make_action_item(due_date=yesterday).is_overdue is True
        assert make_action_item(due_date=timezone.localdate() + timedelta(days=1)).is_overdue is False
        assert make_action_item(due_date=None).is_overdue is False

        done = make_action_item(due_date=yesterday)
        done.mark_completed()
        assert done.is_overdue is False

    def test_ordering_puts_open_work_first_and_undated_last(self):
        meeting = make_meeting()
        today = timezone.localdate()
        undated = make_action_item(meeting=meeting, title="Undated")
        soon = make_action_item(meeting=meeting, title="Soon", due_date=today)
        later = make_action_item(meeting=meeting, title="Later",
                                 due_date=today + timedelta(days=5))
        done = make_action_item(meeting=meeting, title="Done", due_date=today)
        done.mark_completed()

        assert [i.title for i in meeting.action_items.all()] == [
            "Soon", "Later", "Undated", "Done",
        ]

    def test_owner_must_be_in_the_same_meeting(self):
        owner = make_user()
        a, b = make_meeting(owner=owner), make_meeting(owner=owner)
        stranger = make_participant(meeting=b)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_action_item(meeting=a, owner=stranger)
                check_deferred_constraints()

    def test_full_clean_reports_a_foreign_owner_as_a_field_error(self):
        owner = make_user()
        a, b = make_meeting(owner=owner), make_meeting(owner=owner)
        item = ActionItem(meeting=a, owner=make_participant(meeting=b), title="T")
        with pytest.raises(ValidationError) as excinfo:
            item.full_clean()
        assert "owner" in excinfo.value.message_dict

    def test_deleting_the_owner_keeps_the_item(self):
        meeting = make_meeting()
        participant = make_participant(meeting=meeting)
        item = make_action_item(meeting=meeting, owner=participant)
        participant.delete()
        item.refresh_from_db()
        assert item.owner is None

    def test_deleting_the_meeting_removes_its_action_items(self):
        meeting = make_meeting()
        make_action_item(meeting=meeting)
        meeting.delete()
        assert ActionItem.objects.count() == 0


class TestHighlight:
    def test_defaults_and_derived_values(self):
        highlight = make_highlight(start_ms=65_000, end_ms=68_500)
        assert highlight.duration_ms == 3_500
        assert highlight.timestamp == "01:05"
        assert highlight.description == ""
        assert highlight.created_by is None
        assert str(highlight) == "The budget decision"

    def test_cannot_end_before_it_starts(self):
        with pytest.raises(IntegrityError):
            make_highlight(start_ms=5_000, end_ms=4_999)

    def test_a_zero_length_pin_is_allowed(self):
        assert make_highlight(start_ms=100, end_ms=100).duration_ms == 0

    def test_ordering_is_by_start_time(self):
        meeting = make_meeting()
        make_highlight(meeting=meeting, title="Third", start_ms=9_000, end_ms=9_500)
        make_highlight(meeting=meeting, title="First", start_ms=100, end_ms=200)
        make_highlight(meeting=meeting, title="Second", start_ms=4_000, end_ms=4_500)
        assert [h.title for h in meeting.highlights.all()] == ["First", "Second", "Third"]

    def test_segments_are_matched_by_overlap_not_containment(self):
        meeting = make_meeting()
        make_segment(meeting=meeting, start_ms=0, end_ms=2_000, text="Morning.")
        make_segment(meeting=meeting, start_ms=2_000, end_ms=5_000, text="Budget is the issue.")
        make_segment(meeting=meeting, start_ms=5_000, end_ms=9_000, text="Agreed, we cut scope.")
        make_segment(meeting=meeting, start_ms=9_000, end_ms=12_000, text="Anything else?")

        # Starts mid-sentence and ends mid-sentence; both are carried.
        highlight = make_highlight(meeting=meeting, start_ms=3_000, end_ms=8_000)
        assert [s.text for s in highlight.segments] == [
            "Budget is the issue.", "Agreed, we cut scope.",
        ]

    def test_segments_from_other_meetings_are_never_pulled_in(self):
        owner = make_user()
        a, b = make_meeting(owner=owner), make_meeting(owner=owner)
        make_segment(meeting=b, start_ms=0, end_ms=10_000, text="Other meeting.")
        assert list(make_highlight(meeting=a, start_ms=0, end_ms=10_000).segments) == []

    def test_text_attributes_each_line_to_its_speaker(self):
        meeting = make_meeting()
        ada = make_participant(meeting=meeting, display_name="Ada")
        bob = make_participant(meeting=meeting, display_name="Bob")
        make_segment(meeting=meeting, speaker=ada, start_ms=0, end_ms=2_000, text="Morning.")
        make_segment(meeting=meeting, speaker=bob, start_ms=2_000, end_ms=4_000, text="Hello.")

        assert make_highlight(meeting=meeting, start_ms=0, end_ms=4_000).text == (
            "Ada: Morning.\nBob: Hello."
        )

    def test_text_falls_back_to_bare_lines_when_nobody_is_attributed(self):
        meeting = make_meeting()
        make_segment(meeting=meeting, start_ms=0, end_ms=2_000, text="Unattributed.")
        assert make_highlight(meeting=meeting, start_ms=0, end_ms=2_000).text == "Unattributed."

    def test_editing_the_transcript_updates_the_highlight(self):
        """Highlights store boundaries, not copies - so corrections propagate."""
        meeting = make_meeting()
        segment = make_segment(meeting=meeting, start_ms=0, end_ms=2_000, text="Typo here.")
        highlight = make_highlight(meeting=meeting, start_ms=0, end_ms=2_000)
        assert highlight.text == "Typo here."

        segment.text = "Corrected."
        segment.save(update_fields=["text"])
        assert highlight.text == "Corrected."

    def test_deleting_the_author_keeps_the_highlight(self):
        """SET_NULL on created_by: the clip stays useful to the rest of the team.

        The meeting is owned by someone else on purpose - deleting its owner
        would cascade the meeting and take the highlight with it, which is a
        different rule.
        """
        author = make_user()
        highlight = make_highlight(meeting=make_meeting(owner=make_user()),
                                   created_by=author)
        author.delete()
        highlight.refresh_from_db()
        assert highlight.created_by is None

    def test_deleting_the_meeting_owner_does_remove_the_highlight(self):
        owner = make_user()
        highlight = make_highlight(meeting=make_meeting(owner=owner), created_by=owner)
        owner.delete()
        assert Highlight.objects.filter(pk=highlight.pk).exists() is False

    def test_deleting_the_meeting_removes_its_highlights(self):
        meeting = make_meeting()
        make_highlight(meeting=meeting)
        meeting.delete()
        assert Highlight.objects.count() == 0


class TestMeetingRelations:
    def test_a_meeting_exposes_all_five_collections(self):
        meeting = make_meeting()
        participant = make_participant(meeting=meeting)
        make_segment(meeting=meeting, speaker=participant)
        make_summary(meeting=meeting)
        make_action_item(meeting=meeting, owner=participant)
        make_highlight(meeting=meeting)

        assert meeting.participants.count() == 1
        assert meeting.segments.count() == 1
        assert meeting.summaries.count() == 1
        assert meeting.action_items.count() == 1
        assert meeting.highlights.count() == 1

    def test_deleting_a_meeting_takes_everything_with_it(self):
        meeting = make_meeting()
        participant = make_participant(meeting=meeting)
        make_segment(meeting=meeting, speaker=participant)
        make_summary(meeting=meeting)
        make_action_item(meeting=meeting, owner=participant)
        make_highlight(meeting=meeting)

        meeting.delete()

        assert Participant.objects.count() == 0
        assert TranscriptSegment.objects.count() == 0
        assert MeetingSummary.objects.count() == 0
        assert ActionItem.objects.count() == 0
        assert Highlight.objects.count() == 0
