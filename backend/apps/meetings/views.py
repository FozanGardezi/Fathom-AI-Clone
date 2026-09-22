"""Meeting API endpoints.

Follows the same pattern as apps.accounts: DRF generic views wired to explicit
url paths, with permissions coming from the project-wide IsAuthenticated
default.
"""

import django_filters
from django.db.models import Count, DurationField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
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
    HighlightSerializer,
    HighlightWithMeetingSerializer,
    HighlightWriteSerializer,
    MeetingDetailSerializer,
    MeetingListSerializer,
    MeetingStatsSerializer,
    MeetingWriteSerializer,
    TranscriptSegmentSerializer,
)


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


class MeetingTranscriptView(MeetingScopedMixin, generics.ListAPIView):
    """GET /api/v1/meetings/{id}/transcript/

    Segments in chronological order. Paginated by the project default, because
    an hour of conversation is thousands of rows and no client wants them in
    one response.
    """

    serializer_class = TranscriptSegmentSerializer

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
