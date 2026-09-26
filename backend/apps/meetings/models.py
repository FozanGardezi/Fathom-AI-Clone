"""Core meeting domain: a Meeting, the people in it, what was said, and what
came out of it.

Transcript text is deliberately kept in its own table rather than as a blob on
Meeting: the product needs to seek to a timestamp, attribute a line to a
speaker, and search across segments, none of which a single text column does
well. The generated artefacts - MeetingSummary and ActionItem - sit in their
own tables for the same reason: they are produced asynchronously, re-runnable,
and queried independently of the call itself.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


def format_offset(ms):
    """Milliseconds from the start of a recording as mm:ss, or h:mm:ss past an hour."""
    hours, remainder = divmod(ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    return "%02d:%02d" % (minutes, seconds)


class Meeting(models.Model):
    """A single recorded conversation and its processing state.

    Everything the product shows for a call hangs off this row: its
    ``participants``, the transcript ``segments``, the generated ``summaries``
    and ``action_items``, and the ``highlights`` people clipped from it.
    """

    class Platform(models.TextChoices):
        ZOOM = "zoom", "Zoom"
        GOOGLE_MEET = "google_meet", "Google Meet"
        MICROSOFT_TEAMS = "microsoft_teams", "Microsoft Teams"
        UPLOAD = "upload", "Uploaded recording"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        RECORDING = "recording", "Recording"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    # UUID rather than a sequential id: meeting ids end up in URLs and share
    # links, and sequential ids leak how many meetings exist.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meetings",
    )

    title = models.CharField(max_length=255)
    platform = models.CharField(max_length=32, choices=Platform.choices, default=Platform.OTHER)
    # The conferencing provider's own id, used to reconcile webhook callbacks.
    external_id = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    language = models.CharField(max_length=16, default="en")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)

    scheduled_start = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meetings"
        ordering = ["-started_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "-started_at"], name="meeting_owner_recent_idx"),
            models.Index(fields=["status"], name="meeting_status_idx"),
        ]
        constraints = [
            # A meeting cannot finish before it starts.
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True)
                | Q(started_at__isnull=True)
                | Q(ended_at__gte=F("started_at")),
                name="meeting_ends_after_it_starts",
            ),
            # One row per provider-side meeting, but plenty of rows may have no
            # external id at all - hence the partial index.
            models.UniqueConstraint(
                fields=["platform", "external_id"],
                condition=~Q(external_id=""),
                name="meeting_unique_platform_external_id",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def duration(self):
        """Wall-clock length, or None while the meeting is still open."""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None

    @property
    def duration_seconds(self):
        duration = self.duration
        return int(duration.total_seconds()) if duration else None

    @property
    def is_live(self):
        return self.status == self.Status.RECORDING


class Participant(models.Model):
    """Someone who attended a meeting.

    `user` is set only for people who have an account here; external guests are
    recorded by name and email alone.
    """

    class Role(models.TextChoices):
        HOST = "host", "Host"
        COHOST = "cohost", "Co-host"
        ATTENDEE = "attendee", "Attendee"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meeting_participations",
    )

    display_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ATTENDEE)

    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    # Denormalised from the transcript so the participant list can be rendered
    # without summing every segment.
    talk_time_seconds = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "meeting_participants"
        ordering = ["display_name"]
        indexes = [
            models.Index(fields=["meeting", "role"], name="participant_meeting_role_idx"),
        ]
        constraints = [
            # The same address cannot appear twice in one meeting, but blank
            # emails are common (dial-ins, unidentified speakers) and must not
            # collide with each other.
            models.UniqueConstraint(
                fields=["meeting", "email"],
                condition=~Q(email=""),
                name="participant_unique_email_per_meeting",
            ),
            models.CheckConstraint(
                condition=Q(left_at__isnull=True)
                | Q(joined_at__isnull=True)
                | Q(left_at__gte=F("joined_at")),
                name="participant_leaves_after_joining",
            ),
            # Redundant on its own - `id` is already the primary key - but a
            # composite foreign key needs a unique key of matching shape to
            # reference. Rows that point at a participant *and* carry their own
            # meeting_id use this to prove both agree. See migration 0004.
            models.UniqueConstraint(
                fields=["id", "meeting"],
                name="participant_id_and_meeting_uniq",
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def is_host(self):
        return self.role in {self.Role.HOST, self.Role.COHOST}


class TranscriptSegment(models.Model):
    """One utterance: a span of audio, a speaker, and the text of it.

    Unlike the other two models this keeps an ordinary auto id. A busy account
    generates millions of these rows, and a 16-byte random UUID primary key
    would bloat every index and scatter inserts across the B-tree.
    """

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="segments")
    # Diarisation often identifies a voice before it can be matched to a
    # person, so the raw label is kept even when `speaker` is null.
    speaker = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="segments",
    )
    speaker_label = models.CharField(max_length=64, blank=True)

    # Milliseconds from the start of the recording - integers, because floating
    # point offsets do not survive repeated seeking and re-alignment cleanly.
    start_ms = models.PositiveIntegerField()
    end_ms = models.PositiveIntegerField()

    text = models.TextField()
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transcript_segments"
        ordering = ["meeting_id", "start_ms", "id"]
        indexes = [
            models.Index(fields=["meeting", "start_ms"], name="segment_meeting_start_idx"),
            models.Index(fields=["speaker"], name="segment_speaker_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_ms__gte=F("start_ms")),
                name="segment_ends_after_it_starts",
            ),
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0.0, confidence__lte=1.0),
                name="segment_confidence_between_zero_and_one",
            ),
            # NOTE: a further constraint lives in migration 0004 and cannot be
            # expressed here - a composite foreign key on
            # (speaker_id, meeting_id) -> meeting_participants (id, meeting_id),
            # which makes it impossible to attribute a segment to a participant
            # from a different meeting. Django has no composite-FK field, so it
            # is raw SQL; see `segment_speaker_in_same_meeting`.
        ]

    def clean(self):
        """Reject a speaker from another meeting with a readable error.

        The database enforces this too (migration 0004); this only gets there
        first, so forms and the admin show a message instead of an
        IntegrityError.
        """
        super().clean()
        if self.speaker_id and self.speaker.meeting_id != self.meeting_id:
            raise ValidationError(
                {"speaker": "Speaker must be a participant in this meeting."}
            )

    def __str__(self):
        preview = self.text if len(self.text) <= 40 else self.text[:37] + "…"
        return "[%s] %s" % (self.timestamp, preview)

    @property
    def duration_ms(self):
        return self.end_ms - self.start_ms

    @property
    def timestamp(self):
        """Start offset as mm:ss (or h:mm:ss past an hour), for the UI."""
        return format_offset(self.start_ms)


class MeetingSummary(models.Model):
    """An AI-generated write-up of one meeting, under one template.

    Kept apart from Meeting because generation is asynchronous and re-runnable:
    a summary has its own lifecycle (queued, generating, ready, failed) that has
    nothing to do with whether the recording itself is ready, and the same call
    can be summarised more than once under different templates.
    """

    class Template(models.TextChoices):
        GENERAL = "general", "General summary"
        ACTION_ITEMS = "action_items", "Action items"
        SALES_CALL = "sales_call", "Sales call"
        ONE_ON_ONE = "one_on_one", "One-on-one"
        STANDUP = "standup", "Standup"
        INTERVIEW = "interview", "Interview"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATING = "generating", "Generating"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Summaries are shared by the same links as the meeting, so a summary row
    # belongs to exactly one meeting and dies with it.
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="summaries")

    template = models.CharField(max_length=32, choices=Template.choices, default=Template.GENERAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    summary = models.TextField(blank=True)
    # Free-form lists the model returns - ordered, variable-length, and only
    # ever read back whole, so JSON beats a pair of child tables here.
    topics = models.JSONField(default=list, blank=True)
    decisions = models.JSONField(default=list, blank=True)

    # When the text was produced, which is not when the row was created: the row
    # exists from the moment generation is queued.
    generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_summaries"
        verbose_name_plural = "meeting summaries"
        ordering = ["-generated_at", "-created_at"]
        indexes = [
            models.Index(fields=["meeting", "status"], name="summary_meeting_status_idx"),
            models.Index(fields=["status"], name="summary_status_idx"),
        ]
        constraints = [
            # Re-running a template replaces its summary rather than stacking a
            # second one beside it.
            models.UniqueConstraint(
                fields=["meeting", "template"],
                name="summary_unique_template_per_meeting",
            ),
            # A summary cannot be readable without a generation time. Status
            # values are written out because a nested TextChoices class is not
            # in scope inside Meta.
            models.CheckConstraint(
                condition=~Q(status="ready") | Q(generated_at__isnull=False),
                name="summary_ready_has_generated_at",
            ),
        ]

    def __str__(self):
        return "%s summary of %s" % (self.get_template_display(), self.meeting_id)

    @property
    def is_ready(self):
        return self.status == self.Status.READY

    def mark_ready(self, when=None):
        """Publish the generated text, stamping the time the constraint needs."""
        self.status = self.Status.READY
        self.generated_at = when or timezone.now()
        self.save(update_fields=["status", "generated_at", "updated_at"])


class ActionItem(models.Model):
    """A follow-up task the meeting produced.

    Owned by a Participant rather than a User: plenty of action items land on
    external guests who have no account here, and the participant row is the
    only handle the product has on those people.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="action_items")
    # Unassigned items are normal - the model extracts "we should ship this"
    # with no owner attached - and an item outlives the participant record.
    owner = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_items",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # A date, not a datetime: "by Friday" carries no time of day.
    due_date = models.DateField(null=True, blank=True)

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_action_items"
        # Open work first, soonest deadline first; undated items sort behind
        # dated ones instead of ahead of them.
        ordering = ["completed", F("due_date").asc(nulls_last=True), "created_at"]
        indexes = [
            models.Index(fields=["meeting", "completed"], name="action_item_meeting_open_idx"),
            models.Index(fields=["owner", "completed"], name="action_item_owner_open_idx"),
            models.Index(fields=["due_date"], name="action_item_due_date_idx"),
        ]
        constraints = [
            # The flag and the timestamp are one fact; letting them disagree
            # makes "what did we close last week" unanswerable.
            models.CheckConstraint(
                condition=Q(completed=True, completed_at__isnull=False)
                | Q(completed=False, completed_at__isnull=True),
                name="action_item_completed_at_matches_completed",
            ),
            # As on TranscriptSegment, a composite foreign key in migration
            # 0004 (`action_item_owner_in_same_meeting`) stops an item being
            # assigned to a participant from another meeting.
        ]

    def clean(self):
        """Same cross-meeting guard as TranscriptSegment.speaker."""
        super().clean()
        if self.owner_id and self.owner.meeting_id != self.meeting_id:
            raise ValidationError(
                {"owner": "Owner must be a participant in this meeting."}
            )

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        """Past its deadline and still open. Undated items are never overdue."""
        if self.completed or self.due_date is None:
            return False
        return self.due_date < timezone.localdate()

    def mark_completed(self, when=None):
        self.completed = True
        self.completed_at = when or timezone.now()
        self.save(update_fields=["completed", "completed_at", "updated_at"])

    def reopen(self):
        self.completed = False
        self.completed_at = None
        self.save(update_fields=["completed", "completed_at", "updated_at"])


class Highlight(models.Model):
    """A clipped span of a meeting someone wanted to keep.

    A highlight stores only its boundaries, never a copy of the transcript
    text: the segments it covers are whatever currently falls inside the span,
    so re-running diarisation or correcting a transcript fixes every highlight
    over it at once.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="highlights")
    # Highlights are made by hand, so the author matters - but the clip stays
    # useful to the rest of the team after that account is gone.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="highlights",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Same units and reference point as TranscriptSegment - milliseconds from
    # the start of the recording - so the two can be compared directly.
    start_ms = models.PositiveIntegerField()
    end_ms = models.PositiveIntegerField()

    # Whether the extractor made this on finish, as opposed to a person marking
    # it by hand. Finishing re-derives the automatic ones from the current
    # transcript, but must never wipe a moment someone flagged mid-call.
    auto_generated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "meeting_highlights"
        ordering = ["meeting_id", "start_ms", "id"]
        indexes = [
            models.Index(fields=["meeting", "start_ms"], name="highlight_meeting_start_idx"),
            models.Index(fields=["created_by"], name="highlight_created_by_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_ms__gte=F("start_ms")),
                name="highlight_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def duration_ms(self):
        return self.end_ms - self.start_ms

    @property
    def timestamp(self):
        """Start offset as mm:ss (or h:mm:ss past an hour), for the UI."""
        return format_offset(self.start_ms)

    @property
    def segments(self):
        """The transcript segments this span covers.

        Overlap rather than containment: a highlight dropped mid-sentence
        should still carry the sentence it started in.
        """
        return (
            TranscriptSegment.objects.filter(meeting_id=self.meeting_id)
            .filter(start_ms__lt=self.end_ms, end_ms__gt=self.start_ms)
            .select_related("speaker")
        )

    @property
    def text(self):
        """The highlighted span as readable text, one line per speaker turn."""
        return "\n".join(
            "%s: %s" % (s.speaker.display_name, s.text) if s.speaker else s.text
            for s in self.segments
        )


class CalendarConnection(models.Model):
    """A user's link to an external calendar.

    Holds the OAuth tokens rather than putting them on the user, because a
    person may eventually connect more than one calendar and because tokens
    have their own lifecycle - they expire, refresh, and get revoked
    independently of the account.
    """

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google Calendar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_connections",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.GOOGLE)

    # The account that was actually authorised, which is not necessarily the
    # address they signed up with.
    account_email = models.EmailField(blank=True)

    access_token = models.TextField()
    # Google only returns a refresh token on first consent, so an existing one
    # has to be preserved across re-authorisations rather than overwritten
    # with the empty string.
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_connections"
        ordering = ["-created_at"]
        constraints = [
            # One connection per provider per person. Reconnecting updates the
            # tokens in place instead of leaving a trail of dead ones.
            models.UniqueConstraint(
                fields=["user", "provider"], name="calendar_one_connection_per_provider"
            ),
        ]

    def __str__(self):
        return "%s for %s" % (self.get_provider_display(), self.user_id)

    @property
    def is_expired(self):
        """Whether the access token needs refreshing before the next call."""
        if not self.token_expires_at:
            return False
        # A minute of slack, so a token does not expire mid-request.
        return timezone.now() >= self.token_expires_at - timedelta(seconds=60)
