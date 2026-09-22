# Hand-written for the same reason as 0002: models.py and 0001_initial have
# pre-existing drift, so the autodetector cannot produce a clean migration.
# This one touches only the new meeting_highlights table.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("meetings", "0002_meetingsummary_actionitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="Highlight",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("start_ms", models.PositiveIntegerField()),
                ("end_ms", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="highlights",
                        to="meetings.meeting",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="highlights",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "meeting_highlights",
                "ordering": ["meeting_id", "start_ms", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="highlight",
            index=models.Index(
                fields=["meeting", "start_ms"], name="highlight_meeting_start_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="highlight",
            index=models.Index(fields=["created_by"], name="highlight_created_by_idx"),
        ),
        migrations.AddConstraint(
            model_name="highlight",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_ms__gte", models.F("start_ms"))),
                name="highlight_ends_after_it_starts",
            ),
        ),
    ]
