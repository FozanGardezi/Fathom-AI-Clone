"""Serializers for the meetings API.

Two shapes for a Meeting: a light one for lists, and a full one for detail
that carries the meeting's related objects. They are kept apart deliberately -
the list endpoint must not pull participants, summaries, action items and
highlights for every row on the page.
"""

from django.utils import timezone
from rest_framework import serializers

# Long enough to carry the gist of a summary, short enough for a card without
# the layout depending on how verbose the model was that day.
EXCERPT_LENGTH = 180


def truncate_summary(text):
    """Cut to EXCERPT_LENGTH on a word boundary, with an ellipsis."""
    text = (text or "").strip()
    if len(text) <= EXCERPT_LENGTH:
        return text
    clipped = text[:EXCERPT_LENGTH].rsplit(" ", 1)[0].rstrip(".,;:")
    return clipped + "…"

from apps.accounts.serializers import UserSerializer

from .models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)


class ParticipantSerializer(serializers.ModelSerializer):
    is_host = serializers.BooleanField(read_only=True)

    class Meta:
        model = Participant
        fields = [
            "id",
            "display_name",
            "email",
            "role",
            "is_host",
            "joined_at",
            "left_at",
            "talk_time_seconds",
        ]


class MeetingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingSummary
        fields = ["id", "template", "status", "summary", "topics", "decisions", "generated_at"]


class ActionItemSerializer(serializers.ModelSerializer):
    # Nested rather than a bare id: the UI renders the assignee's name next to
    # every item, and the owning participant is already prefetched.
    owner = ParticipantSerializer(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = ActionItem
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "due_date",
            "completed",
            "completed_at",
            "is_overdue",
            "created_at",
        ]


class HighlightSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    timestamp = serializers.CharField(read_only=True)
    duration_ms = serializers.IntegerField(read_only=True)

    class Meta:
        model = Highlight
        # `text` and `segments` are deliberately absent: each would run its own
        # transcript query per highlight. A highlight's text belongs on the
        # highlight detail endpoint, not in a list of them.
        fields = [
            "id",
            "title",
            "description",
            "start_ms",
            "end_ms",
            "timestamp",
            "duration_ms",
            "auto_generated",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["auto_generated"]


class MeetingListSerializer(serializers.ModelSerializer):
    """Row shape for GET /meetings/ - metadata and counts only."""

    owner = UserSerializer(read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)
    is_live = serializers.BooleanField(read_only=True)
    # Annotated by the view; counting here would be a query per row.
    participant_count = serializers.IntegerField(read_only=True)
    action_item_count = serializers.IntegerField(read_only=True)
    summary_excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "platform",
            "status",
            "language",
            "meeting_url",
            "owner",
            "scheduled_start",
            "started_at",
            "ended_at",
            "duration_seconds",
            "is_live",
            "participant_count",
            "action_item_count",
            "summary_excerpt",
            "created_at",
            "updated_at",
        ]

    def get_summary_excerpt(self, meeting):
        """First couple of sentences of the ready summary, for a card.

        Reads the view's `ready_summaries` prefetch, so a page of rows costs
        one extra query rather than one per row. A meeting with no ready
        summary - anything still scheduled or processing - returns "".
        """
        summaries = getattr(meeting, "ready_summaries", None)
        if not summaries:
            return ""
        return truncate_summary(summaries[0].summary)


class MeetingDetailSerializer(serializers.ModelSerializer):
    """Full shape for GET/PATCH /meetings/{id}/.

    Every nested list reads from a prefetch the view set up, so rendering a
    detail response costs a fixed number of queries no matter how many
    participants or highlights the meeting has.
    """

    owner = UserSerializer(read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    participants = ParticipantSerializer(many=True, read_only=True)
    action_items = ActionItemSerializer(many=True, read_only=True)
    highlights = HighlightSerializer(many=True, read_only=True)

    summary = serializers.SerializerMethodField()
    summaries = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()
    decisions = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "platform",
            "status",
            "language",
            "external_id",
            "meeting_url",
            "owner",
            "scheduled_start",
            "started_at",
            "ended_at",
            "duration_seconds",
            "is_live",
            "participants",
            "summary",
            "summaries",
            "topics",
            "decisions",
            "action_items",
            "highlights",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def _primary_summary(self, meeting):
        """The newest ready summary, or None.

        `ready_summaries` is populated by the view's Prefetch, so this never
        hits the database. Falling back to the related manager would, which is
        why a meeting serialized without that prefetch reports no summary
        rather than quietly running a query per row.
        """
        summaries = getattr(meeting, "ready_summaries", None)
        return summaries[0] if summaries else None

    def get_summary(self, meeting):
        summary = self._primary_summary(meeting)
        return MeetingSummarySerializer(summary).data if summary else None

    def get_summaries(self, meeting):
        """Every ready summary, one per template, newest first.

        Reads the view's `ready_summaries` prefetch so the template switcher
        can move between already-generated write-ups without a query per row.
        """
        summaries = getattr(meeting, "ready_summaries", None) or []
        return MeetingSummarySerializer(summaries, many=True).data

    def get_topics(self, meeting):
        summary = self._primary_summary(meeting)
        return summary.topics if summary else []

    def get_decisions(self, meeting):
        summary = self._primary_summary(meeting)
        return summary.decisions if summary else []


class MeetingWriteSerializer(serializers.ModelSerializer):
    """Input shape for POST and PATCH.

    `owner` is never accepted from the client - it comes from the authenticated
    user - and the generated artefacts are not writable through this endpoint.
    """

    # Meeting's partial unique constraint on (platform, external_id) makes DRF
    # build a UniqueTogetherValidator, and that validator marks every field it
    # covers as required. Giving external_id an explicit default keeps it
    # optional on create without dropping the uniqueness check.
    external_id = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "platform",
            "status",
            "language",
            "external_id",
            "meeting_url",
            "scheduled_start",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        # Mirrors the database's check constraint so a bad range comes back as
        # a 400 with a field error rather than a 500 from the IntegrityError.
        started = attrs.get("started_at", getattr(self.instance, "started_at", None))
        ended = attrs.get("ended_at", getattr(self.instance, "ended_at", None))
        if started and ended and ended < started:
            raise serializers.ValidationError(
                {"ended_at": "A meeting cannot end before it starts."}
            )
        return attrs


class TranscriptSegmentSerializer(serializers.ModelSerializer):
    """One line of transcript.

    Offsets are exposed in seconds because that is what a media player seeks
    with; the millisecond integers stay on the model, where the arithmetic is
    exact.
    """

    speaker = ParticipantSerializer(read_only=True)
    start_seconds = serializers.SerializerMethodField()
    end_seconds = serializers.SerializerMethodField()
    timestamp = serializers.CharField(read_only=True)

    class Meta:
        model = TranscriptSegment
        fields = [
            "id",
            "speaker",
            "speaker_label",
            "start_seconds",
            "end_seconds",
            "timestamp",
            "text",
            "confidence",
        ]

    def get_start_seconds(self, segment):
        return round(segment.start_ms / 1000, 3)

    def get_end_seconds(self, segment):
        return round(segment.end_ms / 1000, 3)


class ActionItemWriteSerializer(serializers.ModelSerializer):
    """Input shape for creating and updating an action item.

    `completed_at` is not writable: it is derived from `completed` so the pair
    can never disagree, which the database would reject anyway.
    """

    owner = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = ActionItem
        fields = ["id", "owner", "title", "description", "due_date", "completed"]
        read_only_fields = ["id"]

    def _meeting(self):
        """The meeting this item belongs to - from the URL on create, from the
        instance on update."""
        if self.instance is not None:
            return self.instance.meeting
        return self.context.get("meeting")

    def validate_owner(self, owner):
        # The cross-meeting foreign key is deferred, so without this check the
        # violation would not surface until commit - as a 500 rather than a 400.
        meeting = self._meeting()
        if owner is not None and meeting is not None and owner.meeting_id != meeting.pk:
            raise serializers.ValidationError(
                "Owner must be a participant in this meeting."
            )
        return owner

    def create(self, validated_data):
        if validated_data.get("completed"):
            validated_data["completed_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Pulled out before the ordinary field update so the completion
        # timestamp is written through the model's own helpers.
        completed = validated_data.pop("completed", None)
        instance = super().update(instance, validated_data)
        if completed is not None and completed != instance.completed:
            if completed:
                instance.mark_completed()
            else:
                instance.reopen()
        return instance


class HighlightWriteSerializer(serializers.ModelSerializer):
    """Input shape for creating and updating a highlight."""

    class Meta:
        model = Highlight
        fields = ["id", "title", "description", "start_ms", "end_ms"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        # Mirrors the database check constraint, as a field error rather than
        # an IntegrityError.
        start = attrs.get("start_ms", getattr(self.instance, "start_ms", None))
        end = attrs.get("end_ms", getattr(self.instance, "end_ms", None))
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError(
                {"end_ms": "A highlight cannot end before it starts."}
            )
        return attrs


class MeetingStatsSerializer(serializers.Serializer):
    """Aggregates for the dashboard header.

    A serializer rather than a hand-built dict so the numbers appear in the
    OpenAPI schema alongside everything else.
    """

    total_meetings = serializers.IntegerField()
    total_duration_seconds = serializers.IntegerField()
    open_action_items = serializers.IntegerField()
    highlights = serializers.IntegerField()


class MeetingRefSerializer(serializers.ModelSerializer):
    """Just enough of a meeting to label and link to it.

    The workspace-wide lists below are read across meetings, so every row has
    to say which call it came from - but nesting the full meeting shape would
    make those responses enormous for no gain.
    """

    class Meta:
        model = Meeting
        fields = ["id", "title", "platform", "status", "started_at", "scheduled_start"]


class HighlightWithMeetingSerializer(HighlightSerializer):
    """A highlight, told where it came from."""

    meeting = MeetingRefSerializer(read_only=True)

    class Meta(HighlightSerializer.Meta):
        fields = [*HighlightSerializer.Meta.fields, "meeting"]


class ActionItemWithMeetingSerializer(ActionItemSerializer):
    """An action item, told where it came from."""

    meeting = MeetingRefSerializer(read_only=True)

    class Meta(ActionItemSerializer.Meta):
        fields = [*ActionItemSerializer.Meta.fields, "meeting"]

# ---------------------------------------------------------------- live calls

class ParticipantWriteSerializer(serializers.ModelSerializer):
    """Adding someone to a call that is being recorded."""

    class Meta:
        model = Participant
        fields = ["id", "display_name", "email", "role"]
        read_only_fields = ["id"]


class TranscriptSegmentWriteSerializer(serializers.ModelSerializer):
    """One utterance, appended while the call is running.

    `speaker` is a participant of this meeting; the view supplies the meeting,
    so the cross-meeting foreign key cannot be violated from here.
    """

    speaker = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = TranscriptSegment
        fields = ["id", "speaker", "speaker_label", "start_ms", "end_ms", "text", "confidence"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("end_ms", 0) < attrs.get("start_ms", 0):
            raise serializers.ValidationError(
                {"end_ms": "A segment cannot end before it starts."}
            )
        meeting = self.context.get("meeting")
        speaker = attrs.get("speaker")
        # Mirrors the database's composite foreign key, which is deferred and
        # would otherwise surface as a 500 at commit rather than a 400 here.
        if speaker and meeting and speaker.meeting_id != meeting.pk:
            raise serializers.ValidationError(
                {"speaker": "Speaker must be a participant in this meeting."}
            )
        return attrs


class StartLiveMeetingSerializer(serializers.Serializer):
    """What it takes to begin recording: a title, and who is in the room."""

    title = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=Meeting.Platform.choices, default=Meeting.Platform.OTHER
    )
    language = serializers.CharField(max_length=16, default="en")
    participants = ParticipantWriteSerializer(many=True, required=False)

    def validate_participants(self, participants):
        emails = [p["email"].lower() for p in participants if p.get("email")]
        if len(emails) != len(set(emails)):
            raise serializers.ValidationError("Two participants share an email address.")
        return participants


class GenerateSummarySerializer(serializers.Serializer):
    """Which template to (re)generate a summary under.

    `custom` is not offered here: it has no extraction rules of its own and
    would only ever mirror the general write-up, so asking for it is a mistake
    worth rejecting rather than silently answering with something else.
    """

    template = serializers.ChoiceField(
        choices=[
            (value, label)
            for value, label in MeetingSummary.Template.choices
            if value != MeetingSummary.Template.CUSTOM
        ]
    )


class CalendarConnectionSerializer(serializers.Serializer):
    """The calendar's state, as the UI needs to render it.

    `is_configured` and `is_connected` are separate on purpose: a server with
    no OAuth client and a user who has not connected yet look the same from
    the outside but need different words.
    """

    provider = serializers.CharField()
    provider_label = serializers.CharField()
    is_configured = serializers.BooleanField()
    is_connected = serializers.BooleanField()
    account_email = serializers.EmailField(allow_blank=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
    last_sync_error = serializers.CharField(allow_blank=True)
