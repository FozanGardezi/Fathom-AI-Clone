from django.urls import path

from .views import (
    ActionItemDetailView,
    ActionItemListView,
    HighlightDetailView,
    HighlightListView,
    MeetingActionItemListCreateView,
    MeetingDetailView,
    MeetingHighlightListCreateView,
    MeetingListCreateView,
    MeetingStatsView,
    MeetingTranscriptView,
)

urlpatterns = [
    path("meetings/", MeetingListCreateView.as_view(), name="meeting-list"),
    # Before the <uuid:pk> route so "stats" is never read as an id.
    path("meetings/stats/", MeetingStatsView.as_view(), name="meeting-stats"),
    # <uuid:pk> rather than a loose slug: a malformed id fails to match here
    # and returns 404 instead of reaching the database.
    path("meetings/<uuid:pk>/", MeetingDetailView.as_view(), name="meeting-detail"),
    path(
        "meetings/<uuid:meeting_id>/transcript/",
        MeetingTranscriptView.as_view(),
        name="meeting-transcript",
    ),
    path(
        "meetings/<uuid:meeting_id>/action-items/",
        MeetingActionItemListCreateView.as_view(),
        name="meeting-action-items",
    ),
    path(
        "meetings/<uuid:meeting_id>/highlights/",
        MeetingHighlightListCreateView.as_view(),
        name="meeting-highlights",
    ),
    # Editing an existing item does not need the meeting in the path - the row
    # already knows which meeting it belongs to.
    # Workspace-wide lists, for the Highlights and Action Items sections.
    path("highlights/", HighlightListView.as_view(), name="highlight-list"),
    path("action-items/", ActionItemListView.as_view(), name="action-item-list"),
    path("action-items/<uuid:pk>/", ActionItemDetailView.as_view(), name="action-item-detail"),
    path("highlights/<uuid:pk>/", HighlightDetailView.as_view(), name="highlight-detail"),
]
