from django.contrib import admin

from .models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)


class HighlightInline(admin.TabularInline):
    model = Highlight
    extra = 0
    fields = ["title", "start_ms", "end_ms", "created_by"]


class ActionItemInline(admin.TabularInline):
    model = ActionItem
    extra = 0
    fields = ["title", "owner", "due_date", "completed", "completed_at"]


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ["display_name", "email", "role", "talk_time_seconds"]


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "platform", "status", "started_at", "duration"]
    list_filter = ["status", "platform"]
    search_fields = ["title", "owner__email", "external_id"]
    date_hierarchy = "created_at"
    inlines = [ParticipantInline, ActionItemInline, HighlightInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ["display_name", "email", "meeting", "role", "talk_time_seconds"]
    list_filter = ["role"]
    search_fields = ["display_name", "email"]
    raw_id_fields = ["meeting", "user"]


@admin.register(TranscriptSegment)
class TranscriptSegmentAdmin(admin.ModelAdmin):
    list_display = ["meeting", "timestamp", "speaker_label", "text"]
    search_fields = ["text", "speaker_label"]
    raw_id_fields = ["meeting", "speaker"]


@admin.register(MeetingSummary)
class MeetingSummaryAdmin(admin.ModelAdmin):
    list_display = ["meeting", "template", "status", "generated_at"]
    list_filter = ["template", "status"]
    search_fields = ["summary", "meeting__title"]
    date_hierarchy = "generated_at"
    raw_id_fields = ["meeting"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = ["title", "meeting", "owner", "due_date", "completed", "is_overdue"]
    list_filter = ["completed", "due_date"]
    search_fields = ["title", "description", "meeting__title"]
    raw_id_fields = ["meeting", "owner"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Highlight)
class HighlightAdmin(admin.ModelAdmin):
    list_display = ["title", "meeting", "timestamp", "duration_ms", "created_by"]
    search_fields = ["title", "description", "meeting__title"]
    date_hierarchy = "created_at"
    raw_id_fields = ["meeting", "created_by"]
    readonly_fields = ["created_at"]
