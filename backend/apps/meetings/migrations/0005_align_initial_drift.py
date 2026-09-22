"""Bring the database back in line with models.py.

0001_initial was written against an earlier shape of Meeting and Participant
and never caught up: the table still has `name`/`is_host` where the model has
`display_name`/`role`, carries two Meeting columns the model dropped, spells
the Teams platform `ms_teams`, and is missing a transcript index and the
confidence check constraint. Any database built from these migrations rejects
ordinary ORM writes as a result.

models.py is the source of truth here - admin.py has always referenced
`display_name` and `role` - so this repairs forward rather than reverting the
model. Existing rows are carried over: hosts keep host status through the new
`role` field, and `ms_teams` meetings are respelled.
"""

from django.db import migrations, models


def is_host_to_role(apps, schema_editor):
    Participant = apps.get_model("meetings", "Participant")
    Participant.objects.filter(is_host=True).update(role="host")


def role_to_is_host(apps, schema_editor):
    Participant = apps.get_model("meetings", "Participant")
    Participant.objects.filter(role__in=["host", "cohost"]).update(is_host=True)


def rename_teams_platform(apps, schema_editor):
    Meeting = apps.get_model("meetings", "Meeting")
    Meeting.objects.filter(platform="ms_teams").update(platform="microsoft_teams")


def unrename_teams_platform(apps, schema_editor):
    Meeting = apps.get_model("meetings", "Meeting")
    Meeting.objects.filter(platform="microsoft_teams").update(platform="ms_teams")


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0004_participant_same_meeting_fks"),
    ]

    operations = [
        # -- Participant: name -> display_name, is_host -> role ---------------
        migrations.RenameField(
            model_name="participant", old_name="name", new_name="display_name"
        ),
        migrations.AddField(
            model_name="participant",
            name="role",
            field=models.CharField(
                choices=[("host", "Host"), ("cohost", "Co-host"), ("attendee", "Attendee")],
                default="attendee",
                max_length=16,
            ),
        ),
        migrations.RunPython(is_host_to_role, role_to_is_host),
        # The old index names is_host, so it has to go before the column does.
        migrations.RemoveIndex(
            model_name="participant", name="participant_meeting_host_idx"
        ),
        migrations.RemoveField(model_name="participant", name="is_host"),
        migrations.RemoveField(model_name="participant", name="is_internal"),
        migrations.AddIndex(
            model_name="participant",
            index=models.Index(fields=["meeting", "role"], name="participant_meeting_role_idx"),
        ),
        migrations.AlterModelOptions(
            name="participant", options={"ordering": ["display_name"]}
        ),
        # -- Meeting: drop unused columns, respell the Teams platform ---------
        migrations.RunPython(rename_teams_platform, unrename_teams_platform),
        migrations.AlterField(
            model_name="meeting",
            name="platform",
            field=models.CharField(
                choices=[
                    ("zoom", "Zoom"),
                    ("google_meet", "Google Meet"),
                    ("microsoft_teams", "Microsoft Teams"),
                    ("upload", "Uploaded recording"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=32,
            ),
        ),
        migrations.RemoveField(model_name="meeting", name="recording_url"),
        migrations.RemoveField(model_name="meeting", name="duration_seconds"),
        migrations.RenameIndex(
            model_name="meeting",
            new_name="meeting_owner_recent_idx",
            old_name="meeting_owner_started_idx",
        ),
        migrations.RemoveConstraint(
            model_name="meeting", name="meeting_unique_external_id_per_platform"
        ),
        migrations.AddConstraint(
            model_name="meeting",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_id", ""), _negated=True),
                fields=("platform", "external_id"),
                name="meeting_unique_platform_external_id",
            ),
        ),
        # -- TranscriptSegment: the index and check that never got migrated ---
        migrations.AddIndex(
            model_name="transcriptsegment",
            index=models.Index(fields=["speaker"], name="segment_speaker_idx"),
        ),
        migrations.AddConstraint(
            model_name="transcriptsegment",
            constraint=models.CheckConstraint(
                condition=models.Q(("confidence__isnull", True))
                | models.Q(("confidence__gte", 0.0), ("confidence__lte", 1.0)),
                name="segment_confidence_between_zero_and_one",
            ),
        ),
    ]
