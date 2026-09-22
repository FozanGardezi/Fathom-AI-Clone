"""Tests for the endpoints nested under a meeting: transcript, action items
and highlights."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.meetings.models import ActionItem, Highlight, Meeting, Participant, TranscriptSegment

pytestmark = pytest.mark.django_db
User = get_user_model()

UNKNOWN_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


def transcript_url(meeting_id):
    return reverse("meeting-transcript", args=[meeting_id])


def action_items_url(meeting_id):
    return reverse("meeting-action-items", args=[meeting_id])


def action_item_url(item_id):
    return reverse("action-item-detail", args=[item_id])


def highlights_url(meeting_id):
    return reverse("meeting-highlights", args=[meeting_id])


def highlight_url(highlight_id):
    return reverse("highlight-detail", args=[highlight_id])


@pytest.fixture
def user():
    return User.objects.create_user(email="owner@fathom.test", password="Str0ngPass!2026")


@pytest.fixture
def other_user():
    return User.objects.create_user(email="other@fathom.test", password="Str0ngPass!2026")


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def meeting(user):
    started = timezone.now() - timedelta(hours=1)
    return Meeting.objects.create(
        title="Weekly sync", owner=user, platform=Meeting.Platform.ZOOM,
        status=Meeting.Status.READY, started_at=started,
        ended_at=started + timedelta(minutes=30),
    )


@pytest.fixture
def ada(meeting):
    return Participant.objects.create(
        meeting=meeting, display_name="Ada Lovelace", email="ada@fathom.test",
        role=Participant.Role.HOST,
    )


@pytest.fixture
def bob(meeting):
    return Participant.objects.create(
        meeting=meeting, display_name="Bob Chen", email="bob@fathom.test"
    )


@pytest.fixture
def other_meeting(other_user):
    return Meeting.objects.create(title="Not yours", owner=other_user)


# --------------------------------------------------------------- transcript


class TestTranscriptRetrieval:
    def test_returns_segments_with_speaker_and_times(self, client, meeting, ada):
        TranscriptSegment.objects.create(
            meeting=meeting, speaker=ada, speaker_label="Speaker 1",
            start_ms=65_000, end_ms=68_500, text="Let's talk about the budget.",
            confidence=0.94,
        )
        response = client.get(transcript_url(meeting.pk))
        assert response.status_code == 200

        segment = response.data["results"][0]
        assert segment["text"] == "Let's talk about the budget."
        assert segment["start_seconds"] == 65.0
        assert segment["end_seconds"] == 68.5
        assert segment["timestamp"] == "01:05"
        assert segment["speaker_label"] == "Speaker 1"
        assert segment["confidence"] == 0.94
        assert segment["speaker"]["display_name"] == "Ada Lovelace"
        assert segment["speaker"]["role"] == "host"
        assert segment["speaker"]["is_host"] is True

    def test_unattributed_segments_have_a_null_speaker(self, client, meeting):
        TranscriptSegment.objects.create(meeting=meeting, start_ms=0, end_ms=1_000,
                                         text="Unknown voice.")
        segment = client.get(transcript_url(meeting.pk)).data["results"][0]
        assert segment["speaker"] is None
        assert segment["text"] == "Unknown voice."

    def test_sub_second_offsets_survive_the_conversion(self, client, meeting):
        TranscriptSegment.objects.create(meeting=meeting, start_ms=1_234, end_ms=5_678,
                                         text="x")
        segment = client.get(transcript_url(meeting.pk)).data["results"][0]
        assert segment["start_seconds"] == 1.234
        assert segment["end_seconds"] == 5.678

    def test_only_this_meetings_segments_are_returned(self, client, meeting, other_meeting):
        TranscriptSegment.objects.create(meeting=meeting, start_ms=0, end_ms=1, text="Mine")
        TranscriptSegment.objects.create(meeting=other_meeting, start_ms=0, end_ms=1,
                                         text="Theirs")
        texts = [s["text"] for s in client.get(transcript_url(meeting.pk)).data["results"]]
        assert texts == ["Mine"]


class TestTranscriptOrdering:
    def test_segments_come_back_chronologically(self, client, meeting):
        for start, text in [(10_000, "third"), (0, "first"), (5_000, "second")]:
            TranscriptSegment.objects.create(meeting=meeting, start_ms=start,
                                             end_ms=start + 1_000, text=text)
        texts = [s["text"] for s in client.get(transcript_url(meeting.pk)).data["results"]]
        assert texts == ["first", "second", "third"]

    def test_creation_order_does_not_affect_it(self, client, meeting):
        for start in (9_000, 1_000, 5_000, 3_000, 7_000):
            TranscriptSegment.objects.create(meeting=meeting, start_ms=start,
                                             end_ms=start + 500, text=str(start))
        seconds = [s["start_seconds"]
                   for s in client.get(transcript_url(meeting.pk)).data["results"]]
        assert seconds == sorted(seconds)

    def test_pagination_does_not_repeat_or_drop_a_segment(self, client, meeting):
        # Identical start offsets - ties must break deterministically.
        for i in range(30):
            TranscriptSegment.objects.create(meeting=meeting, start_ms=0, end_ms=1,
                                             text="line %02d" % i)
        first = client.get(transcript_url(meeting.pk)).data
        second = client.get(transcript_url(meeting.pk), {"page": 2}).data
        assert first["count"] == 30
        ids = [s["id"] for s in first["results"]] + [s["id"] for s in second["results"]]
        assert len(set(ids)) == 30


class TestTranscriptEmpty:
    def test_a_meeting_with_no_transcript_returns_an_empty_page(self, client, meeting):
        response = client.get(transcript_url(meeting.pk))
        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["results"] == []
        assert response.data["next"] is None


class TestTranscriptMeetingLookup:
    def test_unknown_meeting_is_a_useful_404(self, client):
        response = client.get(transcript_url(UNKNOWN_ID))
        assert response.status_code == 404
        assert response.data["detail"] == "Meeting not found."

    @pytest.mark.parametrize("bad", ["not-a-uuid", "123", "3f2504e0-4f89"])
    def test_malformed_meeting_id_is_404(self, client, bad):
        assert client.get("/api/v1/meetings/%s/transcript/" % bad).status_code == 404

    def test_someone_elses_meeting_is_404_not_403(self, client, other_meeting):
        response = client.get(transcript_url(other_meeting.pk))
        assert response.status_code == 404
        assert response.data["detail"] == "Meeting not found."

    def test_anonymous_callers_are_rejected(self, meeting):
        assert APIClient().get(transcript_url(meeting.pk)).status_code == 401


class TestTranscriptQueryCount:
    def test_speakers_do_not_cost_a_query_each(self, client, meeting):
        def build(n, offset=0):
            for i in range(offset, offset + n):
                speaker = Participant.objects.create(
                    meeting=meeting, display_name="P%d" % i, email="p%d@t.test" % i)
                TranscriptSegment.objects.create(meeting=meeting, speaker=speaker,
                                                 start_ms=i * 100, end_ms=i * 100 + 50,
                                                 text="line %d" % i)

        def measure():
            with CaptureQueriesContext(connection) as ctx:
                assert client.get(transcript_url(meeting.pk)).status_code == 200
            return len(ctx)

        build(3)
        baseline = measure()
        build(20, offset=3)
        assert measure() == baseline


# ------------------------------------------------------------- action items


class TestActionItemList:
    def test_lists_this_meetings_items_with_owners_expanded(self, client, meeting, ada):
        ActionItem.objects.create(meeting=meeting, owner=ada, title="Draft the roadmap")
        item = client.get(action_items_url(meeting.pk)).data["results"][0]
        assert item["title"] == "Draft the roadmap"
        assert item["owner"]["display_name"] == "Ada Lovelace"
        assert item["completed"] is False
        assert item["is_overdue"] is False

    def test_empty_meeting_returns_an_empty_page(self, client, meeting):
        assert client.get(action_items_url(meeting.pk)).data["results"] == []

    def test_open_work_comes_first_and_undated_last(self, client, meeting):
        today = timezone.localdate()
        ActionItem.objects.create(meeting=meeting, title="Undated")
        ActionItem.objects.create(meeting=meeting, title="Soon", due_date=today)
        ActionItem.objects.create(meeting=meeting, title="Later",
                                  due_date=today + timedelta(days=5))
        done = ActionItem.objects.create(meeting=meeting, title="Done", due_date=today)
        done.mark_completed()
        titles = [i["title"] for i in client.get(action_items_url(meeting.pk)).data["results"]]
        assert titles == ["Soon", "Later", "Undated", "Done"]

    def test_unknown_meeting_is_a_useful_404(self, client):
        response = client.get(action_items_url(UNKNOWN_ID))
        assert response.status_code == 404
        assert response.data["detail"] == "Meeting not found."

    def test_owners_do_not_cost_a_query_each(self, client, meeting):
        def build(n, offset=0):
            for i in range(offset, offset + n):
                p = Participant.objects.create(meeting=meeting, display_name="P%d" % i,
                                               email="p%d@t.test" % i)
                ActionItem.objects.create(meeting=meeting, owner=p, title="T%d" % i)

        def measure():
            with CaptureQueriesContext(connection) as ctx:
                client.get(action_items_url(meeting.pk))
            return len(ctx)

        build(3)
        baseline = measure()
        build(20, offset=3)
        assert measure() == baseline


class TestActionItemCreate:
    def test_creates_an_item_against_the_meeting_in_the_url(self, client, meeting, ada):
        response = client.post(action_items_url(meeting.pk), {
            "title": "Draft the revised timeline",
            "description": "Share before Friday.",
            "owner": str(ada.pk),
            "due_date": "2026-10-01",
        }, format="json")
        assert response.status_code == 201
        assert response.data["owner"]["display_name"] == "Ada Lovelace"
        assert response.data["due_date"] == "2026-10-01"

        item = ActionItem.objects.get(pk=response.data["id"])
        assert item.meeting == meeting
        assert item.completed is False

    def test_owner_is_optional(self, client, meeting):
        response = client.post(action_items_url(meeting.pk), {"title": "Unassigned"},
                               format="json")
        assert response.status_code == 201
        assert response.data["owner"] is None

    def test_title_is_required(self, client, meeting):
        response = client.post(action_items_url(meeting.pk), {"description": "no title"},
                               format="json")
        assert response.status_code == 400
        assert "title" in response.data

    def test_owner_from_another_meeting_is_a_400(self, client, meeting, other_meeting):
        stranger = Participant.objects.create(meeting=other_meeting, display_name="Eve",
                                              email="eve@fathom.test")
        response = client.post(action_items_url(meeting.pk),
                               {"title": "T", "owner": str(stranger.pk)}, format="json")
        assert response.status_code == 400
        assert "owner" in response.data

    def test_creating_as_already_completed_stamps_the_time(self, client, meeting):
        response = client.post(action_items_url(meeting.pk),
                               {"title": "Already done", "completed": True}, format="json")
        assert response.status_code == 201
        assert response.data["completed"] is True
        assert response.data["completed_at"] is not None

    def test_cannot_post_to_someone_elses_meeting(self, client, other_meeting):
        response = client.post(action_items_url(other_meeting.pk), {"title": "T"},
                               format="json")
        assert response.status_code == 404
        assert ActionItem.objects.count() == 0


class TestActionItemUpdate:
    @pytest.fixture
    def item(self, meeting, ada):
        return ActionItem.objects.create(meeting=meeting, owner=ada, title="Draft the roadmap")

    def test_complete_an_item(self, client, item):
        response = client.patch(action_item_url(item.pk), {"completed": True}, format="json")
        assert response.status_code == 200
        assert response.data["completed"] is True
        assert response.data["completed_at"] is not None

        item.refresh_from_db()
        assert item.completed is True and item.completed_at is not None

    def test_reopen_an_item(self, client, item):
        item.mark_completed()
        response = client.patch(action_item_url(item.pk), {"completed": False}, format="json")
        assert response.status_code == 200
        assert response.data["completed"] is False
        assert response.data["completed_at"] is None

        item.refresh_from_db()
        assert item.completed is False and item.completed_at is None

    def test_completing_twice_keeps_the_first_timestamp(self, client, item):
        first = client.patch(action_item_url(item.pk), {"completed": True},
                             format="json").data["completed_at"]
        again = client.patch(action_item_url(item.pk), {"completed": True},
                             format="json").data["completed_at"]
        assert first == again

    def test_update_the_title(self, client, item):
        response = client.patch(action_item_url(item.pk), {"title": "Renamed"}, format="json")
        assert response.status_code == 200
        assert response.data["title"] == "Renamed"
        item.refresh_from_db()
        assert item.title == "Renamed"
        assert item.owner is not None  # untouched

    def test_update_the_owner(self, client, item, bob):
        response = client.patch(action_item_url(item.pk), {"owner": str(bob.pk)},
                                format="json")
        assert response.status_code == 200
        assert response.data["owner"]["display_name"] == "Bob Chen"

    def test_unassign_the_owner(self, client, item):
        response = client.patch(action_item_url(item.pk), {"owner": None}, format="json")
        assert response.status_code == 200
        assert response.data["owner"] is None

    def test_update_the_due_date(self, client, item):
        response = client.patch(action_item_url(item.pk), {"due_date": "2026-12-24"},
                                format="json")
        assert response.status_code == 200
        assert response.data["due_date"] == "2026-12-24"

    def test_clear_the_due_date(self, client, item):
        item.due_date = timezone.localdate()
        item.save(update_fields=["due_date"])
        response = client.patch(action_item_url(item.pk), {"due_date": None}, format="json")
        assert response.status_code == 200
        assert response.data["due_date"] is None

    def test_overdue_is_reported(self, client, item):
        response = client.patch(
            action_item_url(item.pk),
            {"due_date": (timezone.localdate() - timedelta(days=1)).isoformat()},
            format="json",
        )
        assert response.data["is_overdue"] is True

    def test_several_fields_at_once(self, client, item, bob):
        response = client.patch(action_item_url(item.pk), {
            "title": "Everything", "owner": str(bob.pk),
            "due_date": "2026-11-05", "completed": True,
        }, format="json")
        assert response.status_code == 200
        assert response.data["title"] == "Everything"
        assert response.data["owner"]["display_name"] == "Bob Chen"
        assert response.data["due_date"] == "2026-11-05"
        assert response.data["completed"] is True

    def test_owner_from_another_meeting_is_a_400(self, client, item, other_meeting):
        stranger = Participant.objects.create(meeting=other_meeting, display_name="Eve",
                                              email="eve@fathom.test")
        response = client.patch(action_item_url(item.pk), {"owner": str(stranger.pk)},
                                format="json")
        assert response.status_code == 400
        assert "owner" in response.data
        item.refresh_from_db()
        assert item.owner.display_name == "Ada Lovelace"

    def test_completed_at_is_not_client_writable(self, client, item):
        forged = (timezone.now() - timedelta(days=400)).isoformat()
        client.patch(action_item_url(item.pk), {"completed": True, "completed_at": forged},
                     format="json")
        item.refresh_from_db()
        assert item.completed_at.year == timezone.now().year

    def test_cannot_patch_an_item_from_someone_elses_meeting(self, client, other_meeting):
        theirs = ActionItem.objects.create(meeting=other_meeting, title="Not yours")
        assert client.patch(action_item_url(theirs.pk), {"title": "Hijacked"},
                            format="json").status_code == 404
        theirs.refresh_from_db()
        assert theirs.title == "Not yours"

    def test_unknown_item_is_404(self, client):
        assert client.patch(action_item_url(UNKNOWN_ID), {"title": "x"},
                            format="json").status_code == 404

    def test_malformed_item_id_is_404(self, client):
        assert client.patch("/api/v1/action-items/not-a-uuid/", {"title": "x"},
                            format="json").status_code == 404


# ---------------------------------------------------------------- highlights


class TestHighlightList:
    def test_lists_this_meetings_highlights_in_time_order(self, client, meeting, user):
        for start, title in [(9_000, "Third"), (1_000, "First"), (5_000, "Second")]:
            Highlight.objects.create(meeting=meeting, created_by=user, title=title,
                                     start_ms=start, end_ms=start + 500)
        titles = [h["title"] for h in client.get(highlights_url(meeting.pk)).data["results"]]
        assert titles == ["First", "Second", "Third"]

    def test_shape_includes_derived_values_and_author(self, client, meeting, user):
        Highlight.objects.create(meeting=meeting, created_by=user, title="The decision",
                                 description="Where scope got cut.",
                                 start_ms=65_000, end_ms=68_500)
        highlight = client.get(highlights_url(meeting.pk)).data["results"][0]
        assert highlight["title"] == "The decision"
        assert highlight["description"] == "Where scope got cut."
        assert highlight["start_ms"] == 65_000
        assert highlight["end_ms"] == 68_500
        assert highlight["timestamp"] == "01:05"
        assert highlight["duration_ms"] == 3_500
        assert highlight["created_by"]["email"] == "owner@fathom.test"

    def test_empty_meeting_returns_an_empty_page(self, client, meeting):
        assert client.get(highlights_url(meeting.pk)).data["results"] == []

    def test_unknown_meeting_is_a_useful_404(self, client):
        response = client.get(highlights_url(UNKNOWN_ID))
        assert response.status_code == 404
        assert response.data["detail"] == "Meeting not found."

    def test_authors_do_not_cost_a_query_each(self, client, meeting, user):
        def build(n, offset=0):
            for i in range(offset, offset + n):
                Highlight.objects.create(meeting=meeting, created_by=user, title="H%d" % i,
                                         start_ms=i * 100, end_ms=i * 100 + 50)

        def measure():
            with CaptureQueriesContext(connection) as ctx:
                client.get(highlights_url(meeting.pk))
            return len(ctx)

        build(3)
        baseline = measure()
        build(20, offset=3)
        assert measure() == baseline


class TestHighlightCreate:
    def test_creates_a_highlight_authored_by_the_caller(self, client, meeting, user):
        response = client.post(highlights_url(meeting.pk), {
            "title": "The budget decision",
            "description": "Where scope got cut.",
            "start_ms": 744_000,
            "end_ms": 812_000,
        }, format="json")
        assert response.status_code == 201
        assert response.data["timestamp"] == "12:24"
        assert response.data["duration_ms"] == 68_000
        assert response.data["created_by"]["email"] == "owner@fathom.test"

        highlight = Highlight.objects.get(pk=response.data["id"])
        assert highlight.meeting == meeting
        assert highlight.created_by == user

    def test_description_is_optional(self, client, meeting):
        response = client.post(highlights_url(meeting.pk),
                               {"title": "Pin", "start_ms": 0, "end_ms": 1_000},
                               format="json")
        assert response.status_code == 201
        assert response.data["description"] == ""

    def test_title_and_bounds_are_required(self, client, meeting):
        response = client.post(highlights_url(meeting.pk), {}, format="json")
        assert response.status_code == 400
        assert {"title", "start_ms", "end_ms"} <= set(response.data)

    def test_ending_before_starting_is_a_400_not_a_500(self, client, meeting):
        response = client.post(highlights_url(meeting.pk),
                               {"title": "Backwards", "start_ms": 5_000, "end_ms": 4_999},
                               format="json")
        assert response.status_code == 400
        assert "end_ms" in response.data

    def test_a_zero_length_pin_is_allowed(self, client, meeting):
        response = client.post(highlights_url(meeting.pk),
                               {"title": "Pin", "start_ms": 100, "end_ms": 100},
                               format="json")
        assert response.status_code == 201
        assert response.data["duration_ms"] == 0

    def test_negative_offsets_are_rejected(self, client, meeting):
        response = client.post(highlights_url(meeting.pk),
                               {"title": "Negative", "start_ms": -1, "end_ms": 100},
                               format="json")
        assert response.status_code == 400

    def test_cannot_post_to_someone_elses_meeting(self, client, other_meeting):
        response = client.post(highlights_url(other_meeting.pk),
                               {"title": "T", "start_ms": 0, "end_ms": 1}, format="json")
        assert response.status_code == 404
        assert Highlight.objects.count() == 0


class TestHighlightUpdate:
    @pytest.fixture
    def highlight(self, meeting, user):
        return Highlight.objects.create(meeting=meeting, created_by=user,
                                        title="The decision", description="Original.",
                                        start_ms=1_000, end_ms=5_000)

    def test_update_the_title_and_description(self, client, highlight):
        response = client.patch(highlight_url(highlight.pk),
                                {"title": "Renamed", "description": "Rewritten."},
                                format="json")
        assert response.status_code == 200
        assert response.data["title"] == "Renamed"
        assert response.data["description"] == "Rewritten."
        assert response.data["start_ms"] == 1_000  # untouched

    def test_move_the_bounds(self, client, highlight):
        response = client.patch(highlight_url(highlight.pk),
                                {"start_ms": 65_000, "end_ms": 68_500}, format="json")
        assert response.status_code == 200
        assert response.data["timestamp"] == "01:05"
        assert response.data["duration_ms"] == 3_500

    def test_moving_only_the_start_past_the_end_is_a_400(self, client, highlight):
        response = client.patch(highlight_url(highlight.pk), {"start_ms": 9_000},
                                format="json")
        assert response.status_code == 400
        assert "end_ms" in response.data
        highlight.refresh_from_db()
        assert highlight.start_ms == 1_000

    def test_cannot_patch_a_highlight_from_someone_elses_meeting(self, client,
                                                                 other_meeting, other_user):
        theirs = Highlight.objects.create(meeting=other_meeting, created_by=other_user,
                                          title="Not yours", start_ms=0, end_ms=1)
        assert client.patch(highlight_url(theirs.pk), {"title": "Hijacked"},
                            format="json").status_code == 404
        theirs.refresh_from_db()
        assert theirs.title == "Not yours"

    def test_unknown_highlight_is_404(self, client):
        assert client.patch(highlight_url(UNKNOWN_ID), {"title": "x"},
                            format="json").status_code == 404

    def test_malformed_highlight_id_is_404(self, client):
        assert client.patch("/api/v1/highlights/not-a-uuid/", {"title": "x"},
                            format="json").status_code == 404


# ------------------------------------------------- workspace-wide listings


class TestWorkspaceHighlights:
    @pytest.fixture
    def url(self):
        return reverse("highlight-list")

    def test_collects_highlights_from_every_meeting(self, client, user, url, meeting):
        second = Meeting.objects.create(title="Another", owner=user)
        Highlight.objects.create(meeting=meeting, created_by=user, title="From one",
                                 start_ms=0, end_ms=1_000)
        Highlight.objects.create(meeting=second, created_by=user, title="From two",
                                 start_ms=0, end_ms=1_000)
        body = client.get(url).data
        assert body["count"] == 2
        assert {h["title"] for h in body["results"]} == {"From one", "From two"}

    def test_each_row_says_which_meeting_it_came_from(self, client, user, url, meeting):
        Highlight.objects.create(meeting=meeting, created_by=user, title="H",
                                 start_ms=65_000, end_ms=68_500)
        row = client.get(url).data["results"][0]
        assert row["meeting"]["title"] == "Weekly sync"
        assert row["meeting"]["id"] == str(meeting.pk)
        assert row["timestamp"] == "01:05"

    def test_other_peoples_highlights_are_excluded(self, client, url, other_meeting, other_user):
        Highlight.objects.create(meeting=other_meeting, created_by=other_user,
                                 title="Not yours", start_ms=0, end_ms=1)
        assert client.get(url).data["count"] == 0

    def test_empty_workspace(self, client, url):
        assert client.get(url).data["results"] == []

    def test_authors_and_meetings_do_not_cost_a_query_each(self, client, user, url, meeting):
        def add(n, offset=0):
            for i in range(offset, offset + n):
                Highlight.objects.create(meeting=meeting, created_by=user, title="H%d" % i,
                                         start_ms=i * 100, end_ms=i * 100 + 50)

        def measure():
            with CaptureQueriesContext(connection) as ctx:
                client.get(url)
            return len(ctx)

        add(3)
        baseline = measure()
        add(20, offset=3)
        assert measure() == baseline


class TestWorkspaceActionItems:
    @pytest.fixture
    def url(self):
        return reverse("action-item-list")

    def test_collects_items_from_every_meeting(self, client, user, url, meeting):
        second = Meeting.objects.create(title="Another", owner=user)
        ActionItem.objects.create(meeting=meeting, title="From one")
        ActionItem.objects.create(meeting=second, title="From two")
        assert client.get(url).data["count"] == 2

    def test_open_work_comes_first_across_meetings(self, client, user, url, meeting):
        today = timezone.localdate()
        second = Meeting.objects.create(title="Another", owner=user)
        ActionItem.objects.create(meeting=second, title="Undated")
        ActionItem.objects.create(meeting=meeting, title="Soon", due_date=today)
        ActionItem.objects.create(meeting=second, title="Later",
                                  due_date=today + timedelta(days=5))
        done = ActionItem.objects.create(meeting=meeting, title="Done", due_date=today)
        done.mark_completed()

        titles = [i["title"] for i in client.get(url).data["results"]]
        assert titles == ["Soon", "Later", "Undated", "Done"]

    def test_can_filter_to_open_items(self, client, url, meeting):
        ActionItem.objects.create(meeting=meeting, title="Open")
        ActionItem.objects.create(meeting=meeting, title="Closed").mark_completed()
        body = client.get(url, {"completed": "false"}).data
        assert [i["title"] for i in body["results"]] == ["Open"]

    def test_each_row_carries_its_meeting_and_owner(self, client, url, meeting, ada):
        ActionItem.objects.create(meeting=meeting, owner=ada, title="T")
        row = client.get(url).data["results"][0]
        assert row["meeting"]["title"] == "Weekly sync"
        assert row["owner"]["display_name"] == "Ada Lovelace"

    def test_other_peoples_items_are_excluded(self, client, url, other_meeting):
        ActionItem.objects.create(meeting=other_meeting, title="Not yours")
        assert client.get(url).data["count"] == 0

    def test_owners_and_meetings_do_not_cost_a_query_each(self, client, url, meeting):
        def add(n, offset=0):
            for i in range(offset, offset + n):
                p = Participant.objects.create(meeting=meeting, display_name="P%d" % i,
                                               email="p%d@t.test" % i)
                ActionItem.objects.create(meeting=meeting, owner=p, title="T%d" % i)

        def measure():
            with CaptureQueriesContext(connection) as ctx:
                client.get(url)
            return len(ctx)

        add(3)
        baseline = measure()
        add(20, offset=3)
        assert measure() == baseline


class TestCalendarRangeFilter:
    def test_covers_past_and_scheduled_meetings_in_one_range(self, client, user):
        base = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        past = Meeting.objects.create(
            title="Happened", owner=user, status=Meeting.Status.READY,
            started_at=base - timedelta(days=3), ended_at=base - timedelta(days=3) + timedelta(hours=1),
        )
        future = Meeting.objects.create(
            title="Scheduled", owner=user, status=Meeting.Status.SCHEDULED,
            scheduled_start=base + timedelta(days=3),
        )
        Meeting.objects.create(
            title="Far past", owner=user, started_at=base - timedelta(days=90),
            ended_at=base - timedelta(days=90) + timedelta(hours=1),
        )

        body = client.get(reverse("meeting-list"), {
            "occurs_after": (base - timedelta(days=7)).isoformat(),
            "occurs_before": (base + timedelta(days=7)).isoformat(),
            "ordering": "occurs_at",
        }).data

        assert [m["title"] for m in body["results"]] == ["Happened", "Scheduled"]
        assert {m["id"] for m in body["results"]} == {str(past.pk), str(future.pk)}

    def test_ordering_by_occurrence_mixes_both_kinds(self, client, user):
        base = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        Meeting.objects.create(title="B scheduled", owner=user,
                               scheduled_start=base + timedelta(days=1))
        Meeting.objects.create(title="A happened", owner=user,
                               started_at=base - timedelta(days=1),
                               ended_at=base - timedelta(days=1) + timedelta(hours=1))
        titles = [m["title"] for m in
                  client.get(reverse("meeting-list"), {"ordering": "occurs_at"}).data["results"]]
        assert titles == ["A happened", "B scheduled"]
