"""Tests for the live-call flow: start, record, finish, extract."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.meetings import extraction
from apps.meetings.models import ActionItem, Highlight, Meeting, MeetingSummary, Participant

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


def start(client, **overrides):
    payload = {"title": "Live call", "platform": "zoom"}
    payload.update(overrides)
    return client.post(reverse("meeting-live-start"), payload, format="json")


def say(client, meeting_id, speaker_id, start_ms, end_ms, text):
    return client.post(
        reverse("meeting-transcript", args=[meeting_id]),
        {"speaker": speaker_id, "start_ms": start_ms, "end_ms": end_ms, "text": text},
        format="json",
    )


class TestStarting:
    def test_it_opens_a_recording(self, client, user):
        response = start(client)
        assert response.status_code == 201
        meeting = Meeting.objects.get(pk=response.data["id"])
        assert meeting.status == Meeting.Status.RECORDING
        assert meeting.started_at is not None
        assert meeting.ended_at is None
        assert meeting.is_live is True
        assert meeting.owner == user

    def test_the_host_is_in_the_room(self, client, user):
        response = start(client)
        host = Meeting.objects.get(pk=response.data["id"]).participants.get(role="host")
        assert host.user == user
        assert host.display_name == "Dana Host"
        assert host.joined_at is not None

    def test_it_takes_a_cast(self, client):
        response = start(client, participants=[
            {"display_name": "Ada Lovelace", "email": "ada@fathom.test"},
            {"display_name": "Bob Chen", "email": "bob@fathom.test", "role": "cohost"},
        ])
        names = {p["display_name"] for p in response.data["participants"]}
        assert names == {"Dana Host", "Ada Lovelace", "Bob Chen"}

    def test_the_host_is_not_added_twice(self, client):
        response = start(client, participants=[
            {"display_name": "Dana Again", "email": "HOST@fathom.test"},
        ])
        assert len(response.data["participants"]) == 1

    def test_duplicate_emails_are_rejected(self, client):
        response = start(client, participants=[
            {"display_name": "One", "email": "same@fathom.test"},
            {"display_name": "Two", "email": "same@fathom.test"},
        ])
        assert response.status_code == 400

    def test_a_title_is_required(self, client):
        assert client.post(reverse("meeting-live-start"), {}, format="json").status_code == 400

    def test_live_is_not_read_as_a_meeting_id(self, client):
        assert reverse("meeting-live-start") == "/api/v1/meetings/live/"

    def test_anonymous_callers_are_rejected(self):
        assert APIClient().post(reverse("meeting-live-start"), {"title": "x"},
                                format="json").status_code == 401


class TestRecording:
    def test_segments_can_be_appended_while_live(self, client):
        meeting = start(client).data
        speaker = meeting["participants"][0]["id"]
        response = say(client, meeting["id"], speaker, 0, 2_500, "Morning everyone.")
        assert response.status_code == 201
        # Answers with the read shape so the live view can render it directly.
        assert response.data["speaker"]["display_name"] == "Dana Host"
        assert response.data["timestamp"] == "00:00"
        assert response.data["start_seconds"] == 0.0

    def test_an_unattributed_segment_is_allowed(self, client):
        meeting = start(client).data
        response = say(client, meeting["id"], None, 0, 1_000, "Someone unidentified.")
        assert response.status_code == 201
        assert response.data["speaker"] is None

    def test_a_backwards_segment_is_a_400(self, client):
        meeting = start(client).data
        response = say(client, meeting["id"], None, 5_000, 4_000, "Time travel.")
        assert response.status_code == 400
        assert "end_ms" in response.data

    def test_a_speaker_from_another_meeting_is_a_400(self, client):
        first = start(client).data
        second = start(client, title="Other").data
        stranger = second["participants"][0]["id"]
        response = say(client, first["id"], stranger, 0, 1_000, "Wrong room.")
        assert response.status_code == 400
        assert "speaker" in response.data

    def test_participants_can_join_mid_call(self, client):
        meeting = start(client).data
        response = client.post(
            reverse("meeting-participants", args=[meeting["id"]]),
            {"display_name": "Late Arrival", "email": "late@fathom.test"},
            format="json",
        )
        assert response.status_code == 201
        assert Participant.objects.filter(display_name="Late Arrival").exists()
        # Joined now, because the call is running.
        assert Participant.objects.get(display_name="Late Arrival").joined_at is not None


class TestFinishing:
    @pytest.fixture
    def recorded(self, client):
        """A short call with a decision, a commitment and a delegation in it."""
        meeting = start(client, participants=[
            {"display_name": "Ada Lovelace", "email": "ada@fathom.test"},
        ]).data
        host, ada = meeting["participants"][0]["id"], meeting["participants"][1]["id"]
        if meeting["participants"][0]["display_name"] != "Dana Host":
            host, ada = ada, host

        lines = [
            (host, 0, 6_000, "Thanks for joining. We need to settle the pricing model today."),
            (ada, 6_500, 14_000, "The pricing feedback is consistent. Customers want per-department pricing."),
            (host, 14_500, 21_000, "Then let's price by department rather than per seat."),
            (ada, 21_500, 27_000, "I'll draft the pricing page copy by Friday."),
            (host, 27_500, 34_000, "Ada, can you also send the pricing model to finance?"),
        ]
        for speaker, s_ms, e_ms, text in lines:
            assert say(client, meeting["id"], speaker, s_ms, e_ms, text).status_code == 201
        return meeting

    def test_it_closes_the_recording(self, client, recorded):
        response = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json")
        assert response.status_code == 200
        meeting = Meeting.objects.get(pk=recorded["id"])
        assert meeting.status == Meeting.Status.READY
        assert meeting.ended_at is not None
        assert meeting.is_live is False
        # Length comes from the last spoken word, not from how long the tab
        # sat open afterwards.
        assert meeting.duration_seconds == 34

    def test_it_writes_a_summary_with_topics_and_decisions(self, client, recorded):
        body = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        assert body["summary"]["status"] == "ready"
        assert "Dana Host and Ada Lovelace" in body["summary"]["summary"]
        assert "pricing" in [t.lower() for t in body["topics"]]
        assert any("price by department" in d.lower() for d in body["decisions"])

    def test_a_self_commitment_becomes_the_speakers_action_item(self, client, recorded):
        body = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        drafted = next(i for i in body["action_items"] if "draft the pricing page" in i["title"].lower())
        assert drafted["owner"]["display_name"] == "Ada Lovelace"
        assert drafted["due_date"] is not None

    def test_a_delegation_is_assigned_to_the_person_named(self, client, recorded):
        body = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        asked = next(i for i in body["action_items"] if "send the pricing model" in i["title"].lower())
        assert asked["owner"]["display_name"] == "Ada Lovelace"

    def test_decisions_become_highlights_over_real_spans(self, client, recorded):
        body = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        assert body["highlights"]
        for highlight in body["highlights"]:
            assert highlight["end_ms"] > highlight["start_ms"]
            assert highlight["end_ms"] <= 34_000

    def test_talk_time_is_derived_from_the_transcript(self, client, recorded):
        client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json")
        for participant in Participant.objects.filter(meeting_id=recorded["id"]):
            spoken = sum(s.duration_ms for s in participant.segments.all())
            assert participant.talk_time_seconds == round(spoken / 1000)
            assert participant.left_at is not None

    def test_finishing_twice_does_not_duplicate_anything(self, client, recorded):
        first = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        second = client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json").data
        assert len(second["action_items"]) == len(first["action_items"])
        assert len(second["highlights"]) == len(first["highlights"])
        assert MeetingSummary.objects.filter(meeting_id=recorded["id"]).count() == 1

    def test_completed_items_survive_a_refinish(self, client, recorded):
        client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json")
        item = ActionItem.objects.filter(meeting_id=recorded["id"]).first()
        item.mark_completed()
        client.post(reverse("meeting-finish", args=[recorded["id"]]), format="json")
        item.refresh_from_db()
        assert item.completed is True

    def test_a_silent_call_finishes_without_inventing_anything(self, client):
        meeting = start(client).data
        body = client.post(reverse("meeting-finish", args=[meeting["id"]]), format="json").data
        assert body["summary"]["summary"] == "No speech was captured for this meeting."
        assert body["topics"] == []
        assert body["decisions"] == []
        assert body["action_items"] == []
        assert body["highlights"] == []

    def test_someone_elses_meeting_cannot_be_finished(self, client):
        other = User.objects.create_user(email="other@fathom.test", password="x")
        theirs = Meeting.objects.create(title="Not yours", owner=other)
        assert client.post(reverse("meeting-finish", args=[theirs.pk]),
                           format="json").status_code == 404


class TestConnectingToAnExistingMeeting:
    """POST /meetings/{id}/start/ - joining a meeting the calendar already made."""

    def scheduled_meeting(self, owner, **overrides):
        defaults = {
            "title": "Northwind sync",
            "owner": owner,
            "platform": Meeting.Platform.GOOGLE_MEET,
            "status": Meeting.Status.SCHEDULED,
            "scheduled_start": timezone.now() + timedelta(minutes=2),
            "meeting_url": "https://meet.google.com/abc-defg-hij",
        }
        defaults.update(overrides)
        return Meeting.objects.create(**defaults)

    def test_it_moves_a_scheduled_meeting_into_recording(self, client, user):
        meeting = self.scheduled_meeting(user)
        response = client.post(reverse("meeting-start", args=[meeting.pk]), format="json")
        assert response.status_code == 200
        meeting.refresh_from_db()
        assert meeting.status == Meeting.Status.RECORDING
        assert meeting.started_at is not None
        assert meeting.ended_at is None

    def test_it_adds_the_caller_as_host(self, client, user):
        meeting = self.scheduled_meeting(user)
        response = client.post(reverse("meeting-start", args=[meeting.pk]), format="json")
        host = [p for p in response.data["participants"] if p["role"] == "host"]
        assert len(host) == 1
        assert host[0]["display_name"] == "Dana Host"

    def test_it_does_not_add_the_caller_twice(self, client, user):
        meeting = self.scheduled_meeting(user)
        # Already on the invite under the same address the account uses.
        Participant.objects.create(
            meeting=meeting, display_name="Dana Host", email=user.email,
            role=Participant.Role.ATTENDEE,
        )
        client.post(reverse("meeting-start", args=[meeting.pk]), format="json")
        assert meeting.participants.count() == 1

    def test_starting_twice_keeps_the_original_clock(self, client, user):
        meeting = self.scheduled_meeting(user)
        first = client.post(reverse("meeting-start", args=[meeting.pk]), format="json").data
        second = client.post(reverse("meeting-start", args=[meeting.pk]), format="json").data
        assert first["started_at"] == second["started_at"]

    def test_someone_elses_meeting_cannot_be_started(self, client):
        other = User.objects.create_user(email="stranger@fathom.test", password="x")
        theirs = self.scheduled_meeting(other)
        assert client.post(reverse("meeting-start", args=[theirs.pk]),
                           format="json").status_code == 404


class TestSummaryTemplates:
    """POST /meetings/{id}/summaries/ - the same call under a different lens."""

    @pytest.fixture
    def recorded_and_finished(self, client):
        meeting = start(client, participants=[
            {"display_name": "Ada Lovelace", "email": "ada@fathom.test"},
        ]).data
        host = meeting["participants"][0]["id"]
        ada = meeting["participants"][1]["id"]
        if meeting["participants"][0]["display_name"] != "Dana Host":
            host, ada = ada, host
        for speaker, s, e, text in [
            (host, 0, 6_000, "Let's settle the pricing model today. What do you think?"),
            (ada, 6_500, 14_000, "Customers want per-department pricing across the board."),
            (host, 14_500, 21_000, "Then we'll price by department rather than per seat."),
            (ada, 21_500, 27_000, "I'll draft the pricing page copy by Friday."),
        ]:
            say(client, meeting["id"], speaker, s, e, text)
        client.post(reverse("meeting-finish", args=[meeting["id"]]), format="json")
        return meeting

    def test_it_generates_a_summary_under_a_template(self, client, recorded_and_finished):
        response = client.post(
            reverse("meeting-summaries", args=[recorded_and_finished["id"]]),
            {"template": "action_items"}, format="json",
        )
        assert response.status_code == 201
        assert response.data["template"] == "action_items"
        assert response.data["status"] == "ready"
        assert "draft the pricing page" in response.data["summary"].lower()

    def test_templates_read_the_same_facts_differently(self, client, recorded_and_finished):
        mid = recorded_and_finished["id"]
        general = MeetingSummary.objects.get(meeting_id=mid, template="general").summary
        sales = client.post(reverse("meeting-summaries", args=[mid]),
                            {"template": "sales_call"}, format="json").data["summary"]
        assert general != sales
        assert "next steps" in sales.lower()

    def test_regenerating_replaces_rather_than_stacks(self, client, recorded_and_finished):
        mid = recorded_and_finished["id"]
        client.post(reverse("meeting-summaries", args=[mid]),
                    {"template": "standup"}, format="json")
        client.post(reverse("meeting-summaries", args=[mid]),
                    {"template": "standup"}, format="json")
        assert MeetingSummary.objects.filter(meeting_id=mid, template="standup").count() == 1

    def test_every_ready_summary_is_exposed_on_the_detail(self, client, recorded_and_finished):
        mid = recorded_and_finished["id"]
        client.post(reverse("meeting-summaries", args=[mid]),
                    {"template": "sales_call"}, format="json")
        detail = client.get(reverse("meeting-detail", args=[mid])).data
        templates = {s["template"] for s in detail["summaries"]}
        assert {"general", "sales_call"} <= templates

    def test_a_meeting_with_no_transcript_cannot_be_summarised(self, client, user):
        meeting = Meeting.objects.create(title="Empty", owner=user)
        response = client.post(reverse("meeting-summaries", args=[meeting.pk]),
                               {"template": "general"}, format="json")
        assert response.status_code == 400

    def test_an_unknown_template_is_rejected(self, client, recorded_and_finished):
        response = client.post(
            reverse("meeting-summaries", args=[recorded_and_finished["id"]]),
            {"template": "nonsense"}, format="json",
        )
        assert response.status_code == 400


class TestManualHighlights:
    """A moment flagged mid-call must survive the finish that regenerates the
    automatic ones."""

    def test_a_manual_highlight_survives_finishing(self, client):
        meeting = start(client).data
        host = meeting["participants"][0]["id"]
        say(client, meeting["id"], host, 0, 6_000, "Then let's price by department.")
        # Flagged by hand while the call was running.
        marked = client.post(
            reverse("meeting-highlights", args=[meeting["id"]]),
            {"title": "Flag this", "start_ms": 1_000, "end_ms": 4_000},
            format="json",
        )
        assert marked.status_code == 201
        assert marked.data["auto_generated"] is False

        client.post(reverse("meeting-finish", args=[meeting["id"]]), format="json")

        kept = Highlight.objects.filter(meeting_id=meeting["id"], auto_generated=False)
        assert kept.count() == 1
        assert kept.first().title == "Flag this"

    def test_automatic_highlights_are_still_regenerated(self, client):
        meeting = start(client).data
        host = meeting["participants"][0]["id"]
        say(client, meeting["id"], host, 0, 6_000, "Then let's price by department instead.")
        client.post(reverse("meeting-highlights", args=[meeting["id"]]),
                    {"title": "Manual", "start_ms": 0, "end_ms": 2_000}, format="json")
        # Finishing twice must not stack the automatic highlights, and must not
        # touch the manual one either.
        client.post(reverse("meeting-finish", args=[meeting["id"]]), format="json")
        client.post(reverse("meeting-finish", args=[meeting["id"]]), format="json")
        assert Highlight.objects.filter(meeting_id=meeting["id"], auto_generated=False).count() == 1
        auto = Highlight.objects.filter(meeting_id=meeting["id"], auto_generated=True).count()
        assert auto == 1


class TestExtraction:
    """The rules, tested directly - they are the part that has to be honest."""

    def test_due_dates_read_weekdays_forwards(self):
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        found = extraction.find_due_date("I'll have it by Wednesday", today=monday)
        assert found == monday + timedelta(days=2)

    def test_a_weekday_already_past_this_week_means_next_week(self):
        friday = timezone.localdate() - timedelta(days=timezone.localdate().weekday()) + timedelta(days=4)
        found = extraction.find_due_date("by Monday", today=friday)
        assert found == friday + timedelta(days=3)

    def test_relative_dates(self):
        today = timezone.localdate()
        assert extraction.find_due_date("by tomorrow", today=today) == today + timedelta(days=1)
        assert extraction.find_due_date("next week", today=today) == today + timedelta(days=7)

    def test_no_date_means_no_date(self):
        assert extraction.find_due_date("I'll get to it at some point") is None

    def test_topics_ignore_filler_words(self):
        class FakeSegment:
            def __init__(self, text):
                self.text = text

        segments = [FakeSegment("We think the pricing is really the thing, you know."),
                    FakeSegment("Pricing, pricing and more pricing. Budget matters too."),
                    FakeSegment("The budget question is a pricing question.")]
        topics = extraction.extract_topics(segments)
        assert "Pricing" in topics
        assert not {"Think", "Thing", "Really", "Know"} & set(topics)

    def test_a_word_said_once_is_not_a_topic(self):
        class FakeSegment:
            def __init__(self, text):
                self.text = text

        topics = extraction.extract_topics([FakeSegment("Pricing pricing. Serendipity.")])
        assert "Serendipity" not in topics
