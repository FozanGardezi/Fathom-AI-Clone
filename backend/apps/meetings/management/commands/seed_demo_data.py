"""Populate the database with a realistic demo dataset.

Idempotent by construction: every meeting it writes carries an external_id
prefixed with `demo-`, and each run deletes those meetings before rebuilding
them. Deleting a meeting cascades to its participants, transcript, summary,
action items and highlights, so a second run replaces the dataset rather than
duplicating it. Nothing without that prefix is ever touched.

Rebuilding rather than skipping means the data always matches demo_data.py -
edit the dialogue, reseed, and the database follows.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.meetings.demo_data import DEMO_PREFIX, MEETINGS
from apps.meetings.models import (
    ActionItem,
    Highlight,
    Meeting,
    MeetingSummary,
    Participant,
    TranscriptSegment,
)

# Speaking pace used to turn a line of dialogue into a duration. 2.6 words a
# second is an unhurried conversational rate.
WORDS_PER_SECOND = 2.6
MIN_TURN_MS = 1_500
# Pause between consecutive turns in the same stretch of conversation.
MIN_GAP_MS, MAX_GAP_MS = 250, 1_100

# Anyone on this domain is one of ours and gets a real account; everyone else
# is an external guest, recorded by name and email only.
INTERNAL_DOMAIN = "fathom.test"
DEMO_PASSWORD = "DemoPass!2026"


class Command(BaseCommand):
    help = "Create a realistic demo dataset (meetings, transcripts, summaries, action items, highlights)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the demo dataset and exit without reseeding.",
        )
        parser.add_argument(
            "--share-with",
            metavar="EMAIL",
            help=(
                "Also add this existing account to every demo meeting, so the "
                "data shows up in their dashboard. The API only returns "
                "meetings you own or attended, so without this the demo data "
                "is invisible to an account you registered yourself."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        removed = self._clear()
        if options["clear"]:
            self.stdout.write(self.style.SUCCESS("Removed %d demo meeting(s)." % removed))
            return

        if removed:
            self.stdout.write("Replacing %d existing demo meeting(s)." % removed)

        totals = {
            "meetings": 0, "participants": 0, "segments": 0,
            "summaries": 0, "action_items": 0, "highlights": 0,
        }
        rows = []
        for spec in MEETINGS:
            counts = self._seed_meeting(spec)
            rows.append((spec["title"], spec["duration_minutes"], counts))
            for key, value in counts.items():
                totals[key] = totals.get(key, 0) + value
            totals["meetings"] += 1

        guest = self._share_with(options.get("share_with"))
        self._report(rows, totals, guest)

    # ------------------------------------------------------------------ steps

    def _clear(self):
        """Remove previously seeded demo meetings. Cascades to everything under
        them; demo user accounts are left in place and reused."""
        demo = Meeting.objects.filter(external_id__startswith=DEMO_PREFIX)
        count = demo.count()
        demo.delete()
        return count

    def _share_with(self, email):
        """Give an existing account sight of the whole demo workspace.

        Meetings are visible to their owner and to anyone who attended, so an
        account registered by hand sees none of this data. Adding the account
        as a participant on every demo meeting is the smallest change that
        makes the dataset usable from a real login, and it leaves the seeded
        cast intact - they are added alongside, not in place of anyone.
        """
        if not email:
            return None

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise CommandError(
                "No account with the email %r. Register it in the app first, "
                "or pick one of the seeded demo logins." % email
            )

        added = 0
        for meeting in Meeting.objects.filter(external_id__startswith=DEMO_PREFIX):
            # The email is unique per meeting, and they may already be in the
            # cast under their own name.
            if meeting.participants.filter(email__iexact=user.email).exists():
                continue
            Participant.objects.create(
                meeting=meeting,
                user=user,
                display_name=user.full_name or user.email,
                email=user.email,
                role=Participant.Role.ATTENDEE,
                # Left null: they were granted access, they did not sit in the
                # call, and pretending otherwise would corrupt the talk-time
                # figures the transcript produces.
                joined_at=None,
                left_at=None,
            )
            added += 1

        return {"email": user.email, "added": added}

    def _seed_meeting(self, spec):
        people = spec["people"]
        users = {
            name: self._demo_user(name, email)
            for name, email, _ in people
            if email.endswith("@" + INTERNAL_DOMAIN)
        }

        host_name = next(name for name, _, role in people if role == "host")
        if host_name not in users:
            raise CommandError(
                "%s: the host must be internal, but %s is external."
                % (spec["title"], host_name)
            )

        duration = timedelta(minutes=spec["duration_minutes"])
        status = spec.get("status", Meeting.Status.READY)
        has_happened = status == Meeting.Status.READY
        # Negative `days_ago` puts the meeting in the future.
        slot = (
            timezone.now().replace(minute=0, second=0, microsecond=0)
            - timedelta(days=spec["days_ago"])
        )

        meeting = Meeting.objects.create(
            title=spec["title"],
            owner=users[host_name],
            platform=spec["platform"],
            language=spec["language"],
            status=status,
            external_id=DEMO_PREFIX + spec["key"],
            meeting_url="",
            scheduled_start=slot,
            # A meeting nobody has had has no start or end, which is what makes
            # `duration_seconds` null and keeps it out of the recent list.
            started_at=slot if has_happened else None,
            ended_at=slot + duration if has_happened else None,
        )

        participants = {
            name: Participant.objects.create(
                meeting=meeting,
                user=users.get(name),
                display_name=name,
                email=email,
                role=role,
                joined_at=slot if has_happened else None,
                left_at=slot + duration if has_happened else None,
            )
            for name, email, role in people
        }

        segments = self._seed_transcript(meeting, spec, participants)
        self._seed_talk_time(participants, segments)
        summaries = self._seed_summary(meeting, spec)
        action_items = self._seed_action_items(meeting, spec, participants)
        highlights = self._seed_highlights(meeting, spec, users[host_name], segments)

        return {
            "participants": len(participants),
            "segments": len(segments),
            "summaries": summaries,
            "action_items": action_items,
            "highlights": highlights,
        }

    def _seed_transcript(self, meeting, spec, participants):
        """Lay the dialogue out across the meeting's running time.

        Turns inside a section follow each other with short pauses. Each
        section starts at its own anchor point, so the gap between sections
        stands in for the stretches of the call the excerpt does not quote and
        timestamps end up spread across the full duration.
        """
        # Seeded per meeting so reseeding produces byte-identical timings.
        if not spec.get("sections"):
            return []

        rng = random.Random(spec["key"])
        duration_ms = spec["duration_minutes"] * 60 * 1000

        rows, cursor = [], 0
        for anchor, turns in spec["sections"]:
            cursor = max(cursor, int(anchor * duration_ms))
            for speaker_name, text in turns:
                length = max(MIN_TURN_MS, int(len(text.split()) / WORDS_PER_SECOND * 1000))
                start, end = cursor, cursor + length
                if end > duration_ms:
                    raise CommandError(
                        "%s: transcript runs past the meeting's %d minutes."
                        % (spec["title"], spec["duration_minutes"])
                    )
                rows.append(
                    TranscriptSegment(
                        meeting=meeting,
                        speaker=participants[speaker_name],
                        speaker_label="",
                        start_ms=start,
                        end_ms=end,
                        text=text,
                        # Long, clearly-spoken turns transcribe better than
                        # short interjections.
                        confidence=round(rng.uniform(0.88, 0.99), 2)
                        if len(text.split()) > 8
                        else round(rng.uniform(0.71, 0.93), 2),
                    )
                )
                cursor = end + rng.randint(MIN_GAP_MS, MAX_GAP_MS)

        return TranscriptSegment.objects.bulk_create(rows)

    def _seed_talk_time(self, participants, segments):
        """Denormalise talk time from the transcript we just wrote, the same
        way the real pipeline would."""
        totals = {}
        for segment in segments:
            totals[segment.speaker_id] = (
                totals.get(segment.speaker_id, 0) + segment.duration_ms
            )
        for participant in participants.values():
            participant.talk_time_seconds = round(totals.get(participant.pk, 0) / 1000)
        Participant.objects.bulk_update(
            participants.values(), ["talk_time_seconds"]
        )

    def _seed_summary(self, meeting, spec):
        summary = spec.get("summary")
        if not summary:
            return 0
        MeetingSummary.objects.create(
            meeting=meeting,
            template=summary["template"],
            status=MeetingSummary.Status.READY,
            summary=summary["text"],
            topics=summary["topics"],
            decisions=summary["decisions"],
            # Generated a few minutes after the call ended, as it would be.
            generated_at=meeting.ended_at + timedelta(minutes=4),
        )
        return 1

    def _seed_action_items(self, meeting, spec, participants):
        today = timezone.localdate()
        rows = []
        for owner_name, title, description, due_in_days, completed in spec.get("action_items", []):
            if owner_name not in participants:
                raise CommandError(
                    "%s: action item owner %r is not in the meeting."
                    % (spec["title"], owner_name)
                )
            rows.append(
                ActionItem(
                    meeting=meeting,
                    owner=participants[owner_name],
                    title=title,
                    description=description,
                    due_date=today + timedelta(days=due_in_days),
                    completed=completed,
                    # The flag and the timestamp are one fact - the database
                    # rejects them disagreeing.
                    completed_at=meeting.ended_at + timedelta(hours=3) if completed else None,
                )
            )
        ActionItem.objects.bulk_create(rows)
        return len(rows)

    def _seed_highlights(self, meeting, spec, author, segments):
        rows = []
        for title, description, first_turn, last_turn in spec.get("highlights", []):
            if not 0 <= first_turn <= last_turn < len(segments):
                raise CommandError(
                    "%s: highlight %r points at turns %d-%d, but the transcript "
                    "has %d." % (spec["title"], title, first_turn, last_turn, len(segments))
                )
            rows.append(
                Highlight(
                    meeting=meeting,
                    created_by=author,
                    title=title,
                    description=description,
                    # Bounds come from real segments, so every highlight lines
                    # up with something actually said.
                    start_ms=segments[first_turn].start_ms,
                    end_ms=segments[last_turn].end_ms,
                )
            )
        Highlight.objects.bulk_create(rows)
        return len(rows)

    def _demo_user(self, name, email):
        user, created = User.objects.get_or_create(
            email=email, defaults={"full_name": name}
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
        return user

    # ----------------------------------------------------------------- output

    def _report(self, rows, totals, guest=None):
        self.stdout.write("")
        self.stdout.write(
            "%-34s %7s %6s %9s %6s %6s" % ("MEETING", "MINS", "PEOPLE", "SEGMENTS",
                                           "ITEMS", "HIGHL")
        )
        self.stdout.write("-" * 72)
        for title, minutes, counts in rows:
            self.stdout.write(
                "%-34s %7d %6d %9d %6d %6d"
                % (title[:34], minutes, counts["participants"], counts["segments"],
                   counts["action_items"], counts["highlights"])
            )
        self.stdout.write("-" * 72)
        self.stdout.write(
            "%-34s %7s %6d %9d %6d %6d"
            % ("%d meetings" % totals["meetings"], "", totals["participants"],
               totals["segments"], totals["action_items"], totals["highlights"])
        )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Seeded %d meetings, %d participants, %d transcript segments, "
            "%d summaries, %d action items, %d highlights."
            % (totals["meetings"], totals["participants"], totals["segments"],
               totals["summaries"], totals["action_items"], totals["highlights"])
        ))
        self.stdout.write(
            "Demo accounts use the password %r. Re-running replaces this data "
            "rather than adding to it." % DEMO_PASSWORD
        )

        if guest:
            self.stdout.write(
                self.style.SUCCESS(
                    "Added %s to %d demo meeting(s) — sign in as them to see this data."
                    % (guest["email"], guest["added"])
                )
            )
        else:
            # The single most common reason the dashboard looks empty.
            hosts = sorted({spec["people"][0][1] for spec in MEETINGS})
            self.stdout.write(
                "\nThe API only returns meetings you own or attended, so this data is "
                "invisible to an account you registered yourself.\n"
                "Sign in as a demo host (e.g. %s), or re-run with\n"
                "  --share-with you@example.com  to add your own account to every meeting."
                % hosts[0]
            )
