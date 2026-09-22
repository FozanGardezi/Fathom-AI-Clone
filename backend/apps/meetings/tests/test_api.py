"""Tests for the meetings API.

Fixtures are defined here rather than pulled from tests/factories.py: that
module still targets the pre-0005 model shape and does not import.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

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

LIST_URL = reverse("meeting-list")


def detail_url(meeting_id):
    return reverse("meeting-detail", args=[meeting_id])


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
        title="Weekly sync",
        owner=user,
        platform=Meeting.Platform.ZOOM,
        status=Meeting.Status.READY,
        started_at=started,
        ended_at=started + timedelta(minutes=30),
    )


@pytest.fixture
def full_meeting(meeting, user):
    """A meeting with one of everything hanging off it."""
    ada = Participant.objects.create(
        meeting=meeting, display_name="Ada", email="ada@fathom.test",
        role=Participant.Role.HOST, talk_time_seconds=600,
    )
    Participant.objects.create(
        meeting=meeting, display_name="Bob", email="bob@fathom.test",
    )
    TranscriptSegment.objects.create(
        meeting=meeting, speaker=ada, start_ms=0, end_ms=4_000,
        text="Let's talk about the budget.",
    )
    MeetingSummary.objects.create(
        meeting=meeting,
        template=MeetingSummary.Template.GENERAL,
        status=MeetingSummary.Status.READY,
        summary="The team agreed to cut scope to hit the deadline.",
        topics=["Budget", "Timeline"],
        decisions=["Cut the reporting module from v1"],
        generated_at=timezone.now(),
    )
    # A second, still-generating summary must not be the one returned.
    MeetingSummary.objects.create(
        meeting=meeting,
        template=MeetingSummary.Template.SALES_CALL,
        status=MeetingSummary.Status.GENERATING,
    )
    ActionItem.objects.create(
        meeting=meeting, owner=ada, title="Draft the revised timeline",
        description="Share before Friday.", due_date=timezone.localdate() + timedelta(days=3),
    )
    Highlight.objects.create(
        meeting=meeting, created_by=user, title="The budget decision",
        description="Where scope got cut.", start_ms=1_000, end_ms=3_500,
    )
    return meeting


class TestAuth:
    def test_anonymous_callers_are_rejected(self):
        assert APIClient().get(LIST_URL).status_code == 401


class TestList:
    def test_returns_the_callers_meetings(self, client, meeting):
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert [m["title"] for m in response.data["results"]] == ["Weekly sync"]

    def test_row_shape_carries_metadata_and_counts(self, client, full_meeting):
        row = client.get(LIST_URL).data["results"][0]
        assert row["participant_count"] == 2
        assert row["action_item_count"] == 1
        assert row["duration_seconds"] == 30 * 60
        assert row["owner"]["email"] == "owner@fathom.test"
        # The list shape stays light - no related collections.
        assert "participants" not in row
        assert "highlights" not in row

    def test_other_peoples_meetings_are_hidden(self, client, other_user):
        Meeting.objects.create(title="Not yours", owner=other_user)
        assert client.get(LIST_URL).data["count"] == 0

    def test_meetings_you_attended_are_visible(self, client, user, other_user):
        theirs = Meeting.objects.create(title="Invited", owner=other_user)
        Participant.objects.create(meeting=theirs, user=user, display_name="Me",
                                   email="owner@fathom.test")
        assert [m["title"] for m in client.get(LIST_URL).data["results"]] == ["Invited"]

    def test_attending_and_owning_does_not_duplicate_a_row(self, client, user, meeting):
        Participant.objects.create(meeting=meeting, user=user, display_name="Me",
                                   email="owner@fathom.test")
        assert client.get(LIST_URL).data["count"] == 1

    def test_counts_are_right_on_a_meeting_you_attended_but_do_not_own(
        self, client, user, other_user
    ):
        """Regression: filtering attendance with a join made Count() see only
        the caller's own participant row, reporting 1 instead of 3."""
        theirs = Meeting.objects.create(title="Invited", owner=other_user)
        Participant.objects.create(meeting=theirs, user=user, display_name="Me",
                                   email="owner@fathom.test")
        Participant.objects.create(meeting=theirs, display_name="Ada", email="ada@fathom.test")
        Participant.objects.create(meeting=theirs, display_name="Bob", email="bob@fathom.test")
        ActionItem.objects.create(meeting=theirs, title="One")
        ActionItem.objects.create(meeting=theirs, title="Two")

        row = client.get(LIST_URL).data["results"][0]
        assert row["participant_count"] == 3
        assert row["action_item_count"] == 2

    def test_default_ordering_is_newest_first(self, client, user):
        now = timezone.now()
        Meeting.objects.create(title="Older", owner=user, started_at=now - timedelta(days=2))
        Meeting.objects.create(title="Newer", owner=user, started_at=now - timedelta(hours=1))
        assert [m["title"] for m in client.get(LIST_URL).data["results"]] == ["Newer", "Older"]

    def test_ordering_can_be_overridden(self, client, user):
        for title in ("Banana", "Apple", "Cherry"):
            Meeting.objects.create(title=title, owner=user)
        titles = [m["title"] for m in client.get(LIST_URL, {"ordering": "title"}).data["results"]]
        assert titles == ["Apple", "Banana", "Cherry"]
        titles = [m["title"] for m in client.get(LIST_URL, {"ordering": "-title"}).data["results"]]
        assert titles == ["Cherry", "Banana", "Apple"]

    def test_unknown_ordering_field_is_ignored_not_fatal(self, client, meeting):
        assert client.get(LIST_URL, {"ordering": "nonsense"}).status_code == 200


class TestPagination:
    def test_page_size_and_links(self, client, user, settings):
        for i in range(30):
            Meeting.objects.create(title="Meeting %02d" % i, owner=user,
                                   started_at=timezone.now() - timedelta(minutes=i))
        first = client.get(LIST_URL).data
        assert first["count"] == 30
        assert len(first["results"]) == settings.REST_FRAMEWORK["PAGE_SIZE"] == 25
        assert first["next"] is not None and first["previous"] is None

        second = client.get(LIST_URL, {"page": 2}).data
        assert len(second["results"]) == 5
        assert second["next"] is None and second["previous"] is not None

        # No row appears on both pages.
        ids = {m["id"] for m in first["results"]} | {m["id"] for m in second["results"]}
        assert len(ids) == 30

    def test_page_beyond_the_end_is_404(self, client, meeting):
        assert client.get(LIST_URL, {"page": 99}).status_code == 404


class TestFiltering:
    @pytest.fixture
    def mixed(self, user):
        Meeting.objects.create(title="Zoom ready", owner=user,
                               platform=Meeting.Platform.ZOOM, status=Meeting.Status.READY)
        Meeting.objects.create(title="Zoom processing", owner=user,
                               platform=Meeting.Platform.ZOOM, status=Meeting.Status.PROCESSING)
        Meeting.objects.create(title="Teams ready", owner=user,
                               platform=Meeting.Platform.MICROSOFT_TEAMS,
                               status=Meeting.Status.READY)

    def test_filter_by_status(self, client, mixed):
        titles = {m["title"] for m in client.get(LIST_URL, {"status": "ready"}).data["results"]}
        assert titles == {"Zoom ready", "Teams ready"}

    def test_filter_by_platform(self, client, mixed):
        titles = {m["title"] for m in client.get(LIST_URL, {"platform": "zoom"}).data["results"]}
        assert titles == {"Zoom ready", "Zoom processing"}

    def test_type_is_an_alias_for_platform(self, client, mixed):
        titles = {m["title"] for m in client.get(LIST_URL, {"type": "microsoft_teams"}).data["results"]}
        assert titles == {"Teams ready"}

    def test_filters_combine(self, client, mixed):
        titles = {m["title"]
                  for m in client.get(LIST_URL, {"type": "zoom", "status": "ready"}).data["results"]}
        assert titles == {"Zoom ready"}

    def test_invalid_filter_value_is_a_400(self, client, mixed):
        assert client.get(LIST_URL, {"status": "not-a-status"}).status_code == 400


class TestDetail:
    def test_includes_every_related_object(self, client, full_meeting):
        response = client.get(detail_url(full_meeting.pk))
        assert response.status_code == 200
        body = response.data

        assert body["title"] == "Weekly sync"
        assert body["platform"] == "zoom"
        assert body["duration_seconds"] == 30 * 60
        assert body["owner"]["email"] == "owner@fathom.test"

        assert [p["display_name"] for p in body["participants"]] == ["Ada", "Bob"]
        assert body["participants"][0]["is_host"] is True

        assert body["summary"]["summary"].startswith("The team agreed")
        assert body["summary"]["template"] == "general"
        assert body["topics"] == ["Budget", "Timeline"]
        assert body["decisions"] == ["Cut the reporting module from v1"]

        assert [a["title"] for a in body["action_items"]] == ["Draft the revised timeline"]
        assert body["action_items"][0]["owner"]["display_name"] == "Ada"
        assert body["action_items"][0]["is_overdue"] is False

        assert [h["title"] for h in body["highlights"]] == ["The budget decision"]
        assert body["highlights"][0]["timestamp"] == "00:01"
        assert body["highlights"][0]["duration_ms"] == 2_500
        assert body["highlights"][0]["created_by"]["email"] == "owner@fathom.test"

    def test_a_meeting_with_nothing_attached_still_renders(self, client, meeting):
        body = client.get(detail_url(meeting.pk)).data
        assert body["participants"] == []
        assert body["summary"] is None
        assert body["topics"] == []
        assert body["decisions"] == []
        assert body["action_items"] == []
        assert body["highlights"] == []

    def test_unready_summaries_are_not_returned(self, client, meeting):
        MeetingSummary.objects.create(
            meeting=meeting, template=MeetingSummary.Template.GENERAL,
            status=MeetingSummary.Status.GENERATING, topics=["ignored"],
        )
        body = client.get(detail_url(meeting.pk)).data
        assert body["summary"] is None
        assert body["topics"] == []

    def test_someone_elses_meeting_is_404_not_403(self, client, other_user):
        theirs = Meeting.objects.create(title="Not yours", owner=other_user)
        assert client.get(detail_url(theirs.pk)).status_code == 404

    def test_unknown_but_valid_uuid_is_404(self, client):
        assert client.get(detail_url("3f2504e0-4f89-11d3-9a0c-0305e82c3301")).status_code == 404


class TestInvalidUuid:
    @pytest.mark.parametrize(
        "bad", ["not-a-uuid", "123", "3f2504e0-4f89-11d3-9a0c", "' OR 1=1--"]
    )
    def test_malformed_ids_are_404_not_500(self, client, bad):
        response = client.get("/api/v1/meetings/%s/" % bad)
        assert response.status_code == 404

    def test_malformed_id_on_patch_is_also_404(self, client):
        assert client.patch("/api/v1/meetings/not-a-uuid/", {"title": "x"},
                            format="json").status_code == 404


class TestCreate:
    def test_creates_a_meeting_owned_by_the_caller(self, client, user):
        response = client.post(LIST_URL, {
            "title": "Kickoff",
            "platform": "google_meet",
            "meeting_url": "https://meet.google.com/abc-defg-hij",
        }, format="json")
        assert response.status_code == 201

        meeting = Meeting.objects.get(pk=response.data["id"])
        assert meeting.owner == user
        assert meeting.title == "Kickoff"
        # Defaults the client did not send.
        assert meeting.status == Meeting.Status.SCHEDULED
        assert meeting.language == "en"

    def test_owner_cannot_be_set_by_the_client(self, client, user, other_user):
        response = client.post(LIST_URL, {"title": "Mine", "owner": str(other_user.pk)},
                               format="json")
        assert response.status_code == 201
        assert Meeting.objects.get(pk=response.data["id"]).owner == user

    def test_title_is_required(self, client):
        response = client.post(LIST_URL, {"platform": "zoom"}, format="json")
        assert response.status_code == 400
        assert "title" in response.data

    def test_unknown_platform_is_rejected(self, client):
        response = client.post(LIST_URL, {"title": "X", "platform": "carrier-pigeon"},
                               format="json")
        assert response.status_code == 400
        assert "platform" in response.data

    def test_ending_before_starting_is_a_400_not_a_500(self, client):
        now = timezone.now()
        response = client.post(LIST_URL, {
            "title": "Time travel",
            "started_at": now.isoformat(),
            "ended_at": (now - timedelta(minutes=5)).isoformat(),
        }, format="json")
        assert response.status_code == 400
        assert "ended_at" in response.data


class TestUpdate:
    def test_patch_changes_only_what_was_sent(self, client, meeting):
        response = client.patch(detail_url(meeting.pk), {"title": "Renamed"}, format="json")
        assert response.status_code == 200
        meeting.refresh_from_db()
        assert meeting.title == "Renamed"
        assert meeting.platform == Meeting.Platform.ZOOM  # untouched

    def test_patch_responds_with_the_full_detail_shape(self, client, full_meeting):
        body = client.patch(detail_url(full_meeting.pk), {"status": "processing"},
                            format="json").data
        assert body["status"] == "processing"
        assert [p["display_name"] for p in body["participants"]] == ["Ada", "Bob"]
        assert body["topics"] == ["Budget", "Timeline"]

    def test_patch_validates_choices(self, client, meeting):
        response = client.patch(detail_url(meeting.pk), {"status": "nonsense"}, format="json")
        assert response.status_code == 400
        assert "status" in response.data

    def test_patch_rejects_an_end_before_the_start(self, client, meeting):
        response = client.patch(
            detail_url(meeting.pk),
            {"ended_at": (meeting.started_at - timedelta(minutes=1)).isoformat()},
            format="json",
        )
        assert response.status_code == 400

    def test_cannot_patch_someone_elses_meeting(self, client, other_user):
        theirs = Meeting.objects.create(title="Not yours", owner=other_user)
        assert client.patch(detail_url(theirs.pk), {"title": "Hijacked"},
                            format="json").status_code == 404
        theirs.refresh_from_db()
        assert theirs.title == "Not yours"


def count_queries(fn):
    """How many queries `fn` runs."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx)


class TestQueryCounts:
    """The endpoints must not scale their query count with the row count.

    Each test measures a baseline, multiplies the data, and asserts the count
    did not move - which is what "no N+1" actually means, and does not break
    when an unrelated query is added elsewhere.
    """

    def test_list_does_not_grow_with_the_number_of_meetings(self, client, user):
        def add_meetings(start, count):
            for i in range(start, start + count):
                m = Meeting.objects.create(title="M%d" % i, owner=user)
                for n in range(3):
                    Participant.objects.create(meeting=m, display_name="P%d" % n,
                                               email="p%d-%d@t.test" % (i, n))
                    ActionItem.objects.create(meeting=m, title="A%d" % n)

        add_meetings(0, 3)
        baseline = count_queries(lambda: client.get(LIST_URL))
        add_meetings(3, 6)
        assert count_queries(lambda: client.get(LIST_URL)) == baseline
        assert client.get(LIST_URL).data["count"] == 9

    def test_detail_does_not_grow_with_related_rows(self, client, full_meeting, user):
        fetch = lambda: client.get(detail_url(full_meeting.pk))
        baseline = count_queries(fetch)

        for n in range(10):
            p = Participant.objects.create(meeting=full_meeting, display_name="Extra%d" % n,
                                           email="x%d@t.test" % n)
            ActionItem.objects.create(meeting=full_meeting, owner=p, title="Task %d" % n)
            Highlight.objects.create(meeting=full_meeting, created_by=user,
                                     title="H%d" % n, start_ms=n * 100, end_ms=n * 100 + 50)

        assert count_queries(fetch) == baseline
        assert len(fetch().data["participants"]) == 12


class TestSummaryExcerpt:
    def test_rows_carry_an_excerpt_of_the_ready_summary(self, client, full_meeting):
        row = client.get(LIST_URL).data["results"][0]
        assert row["summary_excerpt"].startswith("The team agreed to cut scope")

    def test_a_long_summary_is_truncated_on_a_word_boundary(self, client, meeting):
        MeetingSummary.objects.create(
            meeting=meeting, status=MeetingSummary.Status.READY,
            summary=("The team reviewed the quarterly numbers in detail and agreed that the "
                     "reporting module should be cut from the first release in order to "
                     "protect the January launch date that sales has already committed to."),
            generated_at=timezone.now(),
        )
        excerpt = client.get(LIST_URL).data["results"][0]["summary_excerpt"]
        assert len(excerpt) <= 181
        assert excerpt.endswith("…")
        assert "  " not in excerpt and not excerpt[:-1].endswith(" ")

    def test_a_meeting_with_no_ready_summary_has_an_empty_excerpt(self, client, meeting):
        MeetingSummary.objects.create(
            meeting=meeting, status=MeetingSummary.Status.GENERATING, summary="not ready",
        )
        assert client.get(LIST_URL).data["results"][0]["summary_excerpt"] == ""

    def test_excerpts_do_not_reintroduce_an_n_plus_one(self, client, user):
        def add(start, count):
            for i in range(start, start + count):
                m = Meeting.objects.create(title="M%d" % i, owner=user)
                MeetingSummary.objects.create(
                    meeting=m, status=MeetingSummary.Status.READY,
                    summary="Summary %d" % i, generated_at=timezone.now(),
                )

        add(0, 3)
        baseline = count_queries(lambda: client.get(LIST_URL))
        add(3, 6)
        assert count_queries(lambda: client.get(LIST_URL)) == baseline


class TestMeetingStats:
    @pytest.fixture
    def stats_url(self):
        return reverse("meeting-stats")

    def test_totals_across_the_whole_workspace(self, client, stats_url, full_meeting, user):
        # A second meeting so the numbers are sums, not a single row.
        started = timezone.now() - timedelta(hours=3)
        second = Meeting.objects.create(
            title="Another", owner=user, started_at=started,
            ended_at=started + timedelta(minutes=15),
        )
        ActionItem.objects.create(meeting=second, title="Open one")
        done = ActionItem.objects.create(meeting=second, title="Closed one")
        done.mark_completed()
        Highlight.objects.create(meeting=second, title="H", start_ms=0, end_ms=1)

        body = client.get(stats_url).data
        assert body["total_meetings"] == 2
        assert body["total_duration_seconds"] == (30 + 15) * 60
        # The completed one is excluded; full_meeting contributes one open item.
        assert body["open_action_items"] == 2
        assert body["highlights"] == 2

    def test_an_empty_workspace_reports_zeroes(self, client, stats_url):
        assert client.get(stats_url).data == {
            "total_meetings": 0,
            "total_duration_seconds": 0,
            "open_action_items": 0,
            "highlights": 0,
        }

    def test_unfinished_meetings_do_not_break_the_duration_sum(self, client, stats_url, user):
        Meeting.objects.create(title="Scheduled", owner=user, scheduled_start=timezone.now())
        Meeting.objects.create(title="Live", owner=user, started_at=timezone.now(),
                               status=Meeting.Status.RECORDING)
        body = client.get(stats_url).data
        assert body["total_meetings"] == 2
        assert body["total_duration_seconds"] == 0

    def test_other_peoples_meetings_are_not_counted(self, client, stats_url, other_user):
        started = timezone.now() - timedelta(hours=1)
        theirs = Meeting.objects.create(title="Not yours", owner=other_user,
                                        started_at=started, ended_at=started + timedelta(hours=1))
        ActionItem.objects.create(meeting=theirs, title="Theirs")
        body = client.get(stats_url).data
        assert body["total_meetings"] == 0
        assert body["open_action_items"] == 0

    def test_stats_is_not_mistaken_for_a_meeting_id(self, client, stats_url):
        assert stats_url == "/api/v1/meetings/stats/"
        assert client.get(stats_url).status_code == 200

    def test_anonymous_callers_are_rejected(self, stats_url):
        assert APIClient().get(stats_url).status_code == 401
