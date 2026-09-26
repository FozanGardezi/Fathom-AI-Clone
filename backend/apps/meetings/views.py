"""Meeting API endpoints.

Follows the same pattern as apps.accounts: DRF generic views wired to explicit
url paths, with permissions coming from the project-wide IsAuthenticated
default.
"""

from datetime import timedelta

import django_filters
from django.db.models import Count, DurationField, ExpressionWrapper, F, Max, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)
from .serializers import (
    ActionItemSerializer,
    ActionItemWithMeetingSerializer,
    ActionItemWriteSerializer,
    GenerateSummarySerializer,
    HighlightSerializer,
    HighlightWithMeetingSerializer,
    HighlightWriteSerializer,
    MeetingDetailSerializer,
    MeetingSummarySerializer,
    MeetingListSerializer,
    MeetingStatsSerializer,
    MeetingWriteSerializer,
    ParticipantWriteSerializer,
    StartLiveMeetingSerializer,
    TranscriptSegmentSerializer,
    TranscriptSegmentWriteSerializer,
)
from . import extraction


class MeetingFilter(django_filters.FilterSet):
    """Basic filtering: by processing state and by meeting type.

    `type` is offered as an alias for `platform`, which is what the column is
    called - callers think in terms of "what kind of meeting was this".
    """

    type = django_filters.ChoiceFilter(
        field_name="platform", choices=Meeting.Platform.choices
    )

    # A calendar asks "what is in this month", which has to cover meetings that
    # have happened and meetings that have only been scheduled. `occurs_at` is
    # annotated by the view as started_at falling back to scheduled_start, so
    # both kinds land on the right day from one filter.
    occurs_after = django_filters.IsoDateTimeFilter(field_name="occurs_at", lookup_expr="gte")
    occurs_before = django_filters.IsoDateTimeFilter(field_name="occurs_at", lookup_expr="lte")

    class Meta:
        model = Meeting
        fields = ["status", "platform", "type"]


def visible_meetings(user):
    """Meetings `user` may see: the ones they own, and the ones they attended.

    Attendance is matched with a subquery rather than `participants__user=user`
    on purpose. That join both duplicates rows - hence the `.distinct()` this
    used to need - and, worse, silently poisons any `Count("participants")`
    annotated on top of it: the join is already filtered to the caller's own
    participant row, so a meeting they attended but do not own would report one
    participant instead of all of them. A subquery filters without joining, so
    counts stay correct.
    """
    attended = Participant.objects.filter(user=user).values("meeting_id")
    return Meeting.objects.filter(
        Q(owner=user) | Q(pk__in=attended)
    ).select_related("owner")


class MeetingQuerysetMixin:
    """Scopes every endpoint to meetings the caller can actually see."""

    def get_queryset(self):
        return visible_meetings(self.request.user)


class MeetingListCreateView(MeetingQuerysetMixin, generics.ListCreateAPIView):
    """GET /api/v1/meetings/ and POST /api/v1/meetings/"""

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_class = MeetingFilter
    ordering_fields = [
        "started_at",
        "scheduled_start",
        "occurs_at",
        "created_at",
        "updated_at",
        "title",
    ]
    ordering = ["-started_at", "-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MeetingWriteSerializer
        return MeetingListSerializer

    def get_queryset(self):
        # Counts are annotated rather than serialized per row: without this,
        # every meeting on the page costs two extra queries.
        return (
            super()
            .get_queryset()
            .annotate(
                participant_count=Count("participants", distinct=True),
                action_item_count=Count("action_items", distinct=True),
                # When a meeting actually happened, or when it is due to.
                occurs_at=Coalesce("started_at", "scheduled_start"),
            )
            # One query for the whole page's summaries, so `summary_excerpt`
            # does not reintroduce an N+1.
            .prefetch_related(
                Prefetch(
                    "summaries",
                    queryset=MeetingSummary.objects.filter(
                        status=MeetingSummary.Status.READY
                    ).order_by("-generated_at"),
                    to_attr="ready_summaries",
                )
            )
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


def _detail_queryset(user):
    """A meeting with everything the detail response needs, in five queries."""
    return visible_meetings(user).prefetch_related(
        "participants",
        Prefetch("action_items", queryset=ActionItem.objects.select_related("owner")),
        Prefetch("highlights", queryset=Highlight.objects.select_related("created_by")),
        Prefetch(
            "summaries",
            queryset=MeetingSummary.objects.filter(
                status=MeetingSummary.Status.READY
            ).order_by("-generated_at"),
            to_attr="ready_summaries",
        ),
    )


class MeetingDetailView(MeetingQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET /api/v1/meetings/{id}/ and PATCH /api/v1/meetings/{id}/"""

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return MeetingWriteSerializer
        return MeetingDetailSerializer

    def get_queryset(self):
        # One query per related collection for the whole response, rather than
        # one per row of each collection.
        return super().get_queryset().prefetch_related(
            "participants",
            Prefetch(
                "action_items",
                queryset=ActionItem.objects.select_related("owner"),
            ),
            Prefetch(
                "highlights",
                queryset=Highlight.objects.select_related("created_by"),
            ),
            Prefetch(
                "summaries",
                queryset=MeetingSummary.objects.filter(
                    status=MeetingSummary.Status.READY
                ).order_by("-generated_at"),
                to_attr="ready_summaries",
            ),
        )

    def update(self, request, *args, **kwargs):
        """PATCH responds with the full detail shape.

        The client changes a title and gets the whole meeting back, related
        objects included, instead of having to re-fetch it.
        """
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()
        response.data = MeetingDetailSerializer(
            instance, context=self.get_serializer_context()
        ).data
        return response


class MeetingScopedMixin:
    """Base for endpoints nested under a meeting.

    Resolves `meeting_id` from the url against the meetings the caller can see,
    so a meeting that does not exist and one they are not party to are
    indistinguishable from the outside.
    """

    def get_meeting(self):
        if not hasattr(self, "_meeting"):
            try:
                self._meeting = visible_meetings(self.request.user).get(
                    pk=self.kwargs["meeting_id"]
                )
            except Meeting.DoesNotExist:
                raise NotFound("Meeting not found.")
        return self._meeting

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["meeting"] = self.get_meeting()
        return context


class MeetingTranscriptView(MeetingScopedMixin, generics.ListCreateAPIView):
    """GET and POST /api/v1/meetings/{id}/transcript/

    GET returns segments in chronological order, paginated by the project
    default - an hour of conversation is thousands of rows and no client wants
    them in one response.

    POST appends a segment, which is how a live call records itself: the
    browser transcribes speech and posts each finished utterance as it lands.
    """

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TranscriptSegmentWriteSerializer
        return TranscriptSegmentSerializer

    def perform_create(self, serializer):
        serializer.save(meeting=self.get_meeting())

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Answer with the read shape so the live transcript can render the new
        # line without a second request.
        segment = TranscriptSegment.objects.select_related("speaker").get(
            pk=response.data["id"]
        )
        response.data = TranscriptSegmentSerializer(segment).data
        return response

    def get_queryset(self):
        return (
            TranscriptSegment.objects.filter(meeting=self.get_meeting())
            # One join instead of a query per segment for the speaker.
            .select_related("speaker")
            # Explicit rather than relying on Meta.ordering: chronological
            # order is the contract of this endpoint. `id` breaks ties so
            # pagination cannot repeat or drop a row.
            .order_by("start_ms", "id")
        )


class MeetingActionItemListCreateView(MeetingScopedMixin, generics.ListCreateAPIView):
    """GET and POST /api/v1/meetings/{id}/action-items/"""

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ActionItemWriteSerializer
        return ActionItemSerializer

    def get_queryset(self):
        return ActionItem.objects.filter(meeting=self.get_meeting()).select_related("owner")

    def perform_create(self, serializer):
        serializer.save(meeting=self.get_meeting())

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Answer with the read shape so the client gets the owner expanded and
        # the derived fields filled in.
        item = ActionItem.objects.select_related("owner").get(pk=response.data["id"])
        response.data = ActionItemSerializer(item).data
        return response


class ActionItemDetailView(generics.RetrieveUpdateAPIView):
    """GET and PATCH /api/v1/action-items/{id}/

    Covers completing and reopening an item as well as editing its title,
    description, owner and due date.
    """

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ActionItemWriteSerializer
        return ActionItemSerializer

    def get_queryset(self):
        return ActionItem.objects.filter(
            meeting__in=visible_meetings(self.request.user)
        ).select_related("owner", "meeting")

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        item = self.get_queryset().get(pk=self.kwargs["pk"])
        return Response(ActionItemSerializer(item).data)


class MeetingHighlightListCreateView(MeetingScopedMixin, generics.ListCreateAPIView):
    """GET and POST /api/v1/meetings/{id}/highlights/"""

    def get_serializer_class(self):
        if self.request.method == "POST":
            return HighlightWriteSerializer
        return HighlightSerializer

    def get_queryset(self):
        return (
            Highlight.objects.filter(meeting=self.get_meeting())
            .select_related("created_by")
            .order_by("start_ms", "id")
        )

    def perform_create(self, serializer):
        serializer.save(meeting=self.get_meeting(), created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        highlight = Highlight.objects.select_related("created_by").get(pk=response.data["id"])
        response.data = HighlightSerializer(highlight).data
        return response


class HighlightDetailView(generics.RetrieveUpdateAPIView):
    """GET and PATCH /api/v1/highlights/{id}/"""

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return HighlightWriteSerializer
        return HighlightSerializer

    def get_queryset(self):
        return Highlight.objects.filter(
            meeting__in=visible_meetings(self.request.user)
        ).select_related("created_by", "meeting")

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        highlight = self.get_queryset().get(pk=self.kwargs["pk"])
        return Response(HighlightSerializer(highlight).data)


class MeetingStatsView(generics.GenericAPIView):
    """GET /api/v1/meetings/stats/

    Totals across every meeting the caller can see. Aggregated in SQL rather
    than by walking a page of results: the numbers must describe the whole
    workspace, and a paginated list can only ever describe one page of it.
    """

    serializer_class = MeetingStatsSerializer

    def get(self, request):
        meetings = visible_meetings(request.user)

        # `duration_seconds` is a Python property, so the sum has to be
        # expressed against the columns it derives from. Meetings that have
        # not finished contribute nothing rather than breaking the sum.
        duration = meetings.filter(
            started_at__isnull=False, ended_at__isnull=False
        ).aggregate(
            total=Sum(
                ExpressionWrapper(F("ended_at") - F("started_at"), output_field=DurationField())
            )
        )["total"]

        stats = {
            "total_meetings": meetings.count(),
            "total_duration_seconds": int(duration.total_seconds()) if duration else 0,
            "open_action_items": ActionItem.objects.filter(
                meeting__in=meetings, completed=False
            ).count(),
            "highlights": Highlight.objects.filter(meeting__in=meetings).count(),
        }
        return Response(self.get_serializer(stats).data)


class HighlightListView(generics.ListAPIView):
    """GET /api/v1/highlights/ - every highlight the caller can see.

    The per-meeting endpoint answers "what is clipped in this call"; this one
    answers "what have we clipped", which is the question the Highlights
    section of the app exists for.
    """

    serializer_class = HighlightWithMeetingSerializer

    def get_queryset(self):
        return (
            Highlight.objects.filter(meeting__in=visible_meetings(self.request.user))
            .select_related("created_by", "meeting")
            .order_by("-created_at")
        )


class ActionItemListView(generics.ListAPIView):
    """GET /api/v1/action-items/ - every follow-up the caller can see."""

    serializer_class = ActionItemWithMeetingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["completed"]

    def get_queryset(self):
        return (
            ActionItem.objects.filter(meeting__in=visible_meetings(self.request.user))
            .select_related("owner", "meeting")
            # Open work first, soonest deadline first, undated behind dated -
            # the same order as within a meeting, applied across all of them.
            .order_by("completed", F("due_date").asc(nulls_last=True), "created_at")
        )


# ---------------------------------------------------------------- live calls


class StartLiveMeetingView(generics.GenericAPIView):
    """POST /api/v1/meetings/live/

    Opens a recording. Creates the meeting already in `recording` state with
    `started_at` set, adds the cast, and hands back the full detail shape so
    the live page has everything it needs from one call.

    The host is added as a participant automatically - whoever starts a
    recording is in the room, and without it the meeting would not appear in
    its own creator's list.
    """

    serializer_class = StartLiveMeetingSerializer

    @transaction.atomic
    def post(self, request):
        form = self.get_serializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        started_at = timezone.now()
        meeting = Meeting.objects.create(
            owner=request.user,
            title=data["title"],
            platform=data.get("platform", Meeting.Platform.OTHER),
            language=data.get("language", "en"),
            status=Meeting.Status.RECORDING,
            scheduled_start=started_at,
            started_at=started_at,
        )

        host_email = (request.user.email or "").lower()
        Participant.objects.create(
            meeting=meeting,
            user=request.user,
            display_name=request.user.full_name or request.user.email,
            email=request.user.email,
            role=Participant.Role.HOST,
            joined_at=started_at,
        )

        for entry in data.get("participants", []):
            # Skip a duplicate of the host rather than tripping the unique
            # email-per-meeting constraint on their behalf.
            if (entry.get("email") or "").lower() == host_email:
                continue
            Participant.objects.create(
                meeting=meeting,
                display_name=entry["display_name"],
                email=entry.get("email", ""),
                role=entry.get("role", Participant.Role.ATTENDEE),
                joined_at=started_at,
            )

        meeting = _detail_queryset(request.user).get(pk=meeting.pk)
        return Response(
            MeetingDetailSerializer(meeting, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def _ensure_host_participant(meeting, user, when):
    """Add the caller to the room as host, unless they are already in it.

    A calendar-synced meeting may already carry the caller as an attendee (they
    were on the invite), so match on the account first and their email second
    before adding a row - the unique-email-per-meeting constraint would reject a
    duplicate anyway.
    """
    email = (user.email or "").lower()
    existing = meeting.participants.all()
    if any(p.user_id == user.pk for p in existing):
        return
    if email and any((p.email or "").lower() == email for p in existing):
        return
    Participant.objects.create(
        meeting=meeting,
        user=user,
        display_name=user.full_name or user.email,
        email=user.email,
        role=Participant.Role.HOST,
        joined_at=when,
    )


class StartMeetingRecordingView(MeetingScopedMixin, generics.GenericAPIView):
    """POST /api/v1/meetings/{id}/start/

    Connects the notetaker to a meeting that already exists - typically one
    synced from the calendar - by moving it into `recording`. This is what
    "join and take notes" calls: the meeting keeps its title, its Meet link and
    the people already on the invite, and the live page takes it from there.

    Idempotent: a meeting that is already recording is returned unchanged rather
    than restarted, so pressing join twice never resets the clock.
    """

    serializer_class = MeetingDetailSerializer

    @transaction.atomic
    def post(self, request, meeting_id):
        meeting = self.get_meeting()

        if meeting.status != Meeting.Status.RECORDING:
            meeting.status = Meeting.Status.RECORDING
        # Only stamp a start time the first time round; a meeting the sync
        # already marked as happening keeps the start it had.
        if meeting.started_at is None:
            meeting.started_at = timezone.now()
        # Reopening a finished meeting to record more clears the old end, which
        # would otherwise sit before the new recording and trip the constraint.
        meeting.ended_at = None
        meeting.save(update_fields=["status", "started_at", "ended_at", "updated_at"])

        _ensure_host_participant(meeting, request.user, meeting.started_at)

        meeting = _detail_queryset(request.user).get(pk=meeting.pk)
        return Response(
            MeetingDetailSerializer(meeting, context={"request": request}).data
        )


class MeetingSummaryGenerateView(MeetingScopedMixin, generics.GenericAPIView):
    """POST /api/v1/meetings/{id}/summaries/

    Generate (or regenerate) the summary under one template. The templates read
    the same extracted facts and frame them differently - see extraction.py -
    so switching template is cheap and never invents anything the transcript
    did not contain. One row per template, replaced in place on a re-run.
    """

    serializer_class = GenerateSummarySerializer

    @transaction.atomic
    def post(self, request, meeting_id):
        meeting = self.get_meeting()
        form = self.get_serializer(data=request.data)
        form.is_valid(raise_exception=True)
        template = form.validated_data["template"]

        segments = list(
            meeting.segments.select_related("speaker").order_by("start_ms", "id")
        )
        if not segments:
            return Response(
                {"detail": "This meeting has no transcript to summarise yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        participants = list(meeting.participants.all())

        topics = extraction.extract_topics(segments)
        decisions = extraction.extract_decisions(segments)
        actions = extraction.extract_action_items(segments, participants)
        summary_text = extraction.build_summary_for(
            template, meeting, segments, topics, decisions, actions
        )

        summary, _ = MeetingSummary.objects.update_or_create(
            meeting=meeting,
            template=template,
            defaults={
                "status": MeetingSummary.Status.READY,
                "summary": summary_text,
                "topics": topics,
                "decisions": decisions,
                "generated_at": timezone.now(),
            },
        )
        return Response(
            MeetingSummarySerializer(summary).data, status=status.HTTP_201_CREATED
        )


class MeetingParticipantsView(MeetingScopedMixin, generics.ListCreateAPIView):
    """GET and POST /api/v1/meetings/{id}/participants/

    People turn up late to calls, so the cast is editable while one is running.
    """

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ParticipantWriteSerializer
        return ParticipantSerializer

    def get_queryset(self):
        return Participant.objects.filter(meeting=self.get_meeting())

    def perform_create(self, serializer):
        meeting = self.get_meeting()
        serializer.save(
            meeting=meeting,
            joined_at=timezone.now() if meeting.is_live else None,
        )


class FinishLiveMeetingView(MeetingScopedMixin, generics.GenericAPIView):
    """POST /api/v1/meetings/{id}/finish/

    Closes the recording and derives everything downstream of the transcript:
    a summary, its topics and decisions, the action items people took on, and
    highlights over the moments a decision was reached.

    All of it comes from `extraction.py`, which reads the words that were
    actually said. Nothing here is generated or guessed - see that module for
    what that costs and why it is the honest option without a language model.

    Idempotent: finishing an already-finished meeting re-derives from the
    current transcript rather than stacking a second set of everything.
    """

    serializer_class = MeetingDetailSerializer

    @transaction.atomic
    def post(self, request, meeting_id):
        meeting = self.get_meeting()

        segments = list(
            meeting.segments.select_related("speaker").order_by("start_ms", "id")
        )
        participants = list(meeting.participants.all())

        topics = extraction.extract_topics(segments)
        decisions = extraction.extract_decisions(segments)
        actions = extraction.extract_action_items(segments, participants)
        highlights = extraction.extract_highlights(segments)
        summary_text = extraction.build_summary(meeting, segments, topics, decisions)

        now = timezone.now()
        # End the meeting at its last spoken word when there is one: the wall
        # clock includes however long the tab sat open afterwards.
        last_word_ms = segments[-1].end_ms if segments else None
        ended_at = (
            meeting.started_at + timedelta(milliseconds=last_word_ms)
            if meeting.started_at and last_word_ms
            else now
        )
        meeting.ended_at = max(ended_at, meeting.started_at or ended_at)
        meeting.status = Meeting.Status.READY
        meeting.save(update_fields=["ended_at", "status", "updated_at"])

        for participant in participants:
            spoken = sum(s.duration_ms for s in segments if s.speaker_id == participant.pk)
            participant.talk_time_seconds = round(spoken / 1000)
            participant.left_at = meeting.ended_at
        Participant.objects.bulk_update(participants, ["talk_time_seconds", "left_at"])

        MeetingSummary.objects.update_or_create(
            meeting=meeting,
            template=MeetingSummary.Template.GENERAL,
            defaults={
                "status": MeetingSummary.Status.READY,
                "summary": summary_text,
                "topics": topics,
                "decisions": decisions,
                "generated_at": now,
            },
        )

        # Replace rather than append, so finishing twice does not duplicate.
        meeting.action_items.filter(completed=False).delete()
        ActionItem.objects.bulk_create(
            [
                ActionItem(
                    meeting=meeting,
                    owner=item["owner"],
                    title=item["title"],
                    description="Picked up from the transcript at %s."
                    % item["source_segment"].timestamp,
                    due_date=item["due_date"],
                )
                for item in actions
            ]
        )

        # Replace only what the extractor made last time. A moment someone
        # flagged by hand mid-call is theirs to keep, not ours to regenerate.
        meeting.highlights.filter(auto_generated=True).delete()
        Highlight.objects.bulk_create(
            [
                Highlight(
                    meeting=meeting,
                    created_by=request.user,
                    title=item["title"],
                    description=item["description"],
                    start_ms=item["start_ms"],
                    end_ms=item["end_ms"],
                    auto_generated=True,
                )
                for item in highlights
            ]
        )

        meeting = _detail_queryset(request.user).get(pk=meeting.pk)
        return Response(MeetingDetailSerializer(meeting, context={"request": request}).data)
