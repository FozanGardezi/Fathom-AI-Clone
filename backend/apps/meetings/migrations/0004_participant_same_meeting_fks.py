"""Make it impossible, at the database level, to attribute a child row to a
participant from a different meeting.

Both transcript_segments and meeting_action_items carry their own meeting_id
alongside a participant reference. Nothing so far stopped those two from
disagreeing: a segment in meeting A could name a speaker who only ever
attended meeting B, and only application code would have noticed.

The fix is a composite foreign key - (speaker_id, meeting_id) must exist as a
(id, meeting_id) pair on meeting_participants - which Django has no field for,
hence raw SQL. Two properties make this safe:

* MATCH SIMPLE (the default) skips the check when any referencing column is
  NULL, so an unattributed segment or an unassigned action item still inserts
  freely. That is the common case and must stay cheap.
* DEFERRABLE INITIALLY DEFERRED defers the check to commit, matching how
  Django writes its own foreign keys, so ORM cascades that touch parent and
  child in one transaction are not tripped by statement ordering.

Deletes stay NO ACTION: Django's collector handles SET_NULL and CASCADE itself
rather than delegating to the database.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0003_highlight"),
    ]

    operations = [
        # The unique key the composite foreign keys below reference.
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("id", "meeting"), name="participant_id_and_meeting_uniq"
            ),
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE transcript_segments
                    ADD CONSTRAINT segment_speaker_in_same_meeting
                    FOREIGN KEY (speaker_id, meeting_id)
                    REFERENCES meeting_participants (id, meeting_id)
                    DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE transcript_segments
                    DROP CONSTRAINT segment_speaker_in_same_meeting;
            """,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE meeting_action_items
                    ADD CONSTRAINT action_item_owner_in_same_meeting
                    FOREIGN KEY (owner_id, meeting_id)
                    REFERENCES meeting_participants (id, meeting_id)
                    DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE meeting_action_items
                    DROP CONSTRAINT action_item_owner_in_same_meeting;
            """,
        ),
    ]
