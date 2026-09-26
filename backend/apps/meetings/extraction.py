"""Turn a finished transcript into a summary, decisions, action items and highlights.

This is rule-based extraction over the words people actually said, not a
language model. That is a deliberate limit and worth being plain about: there
is no LLM configured in this project, and a fabricated summary would be worse
than an honest extractive one. Everything below is derived from the transcript
and can be traced back to the line it came from.

The rules encode how people actually talk in meetings:

* A decision sounds like a commitment the group made - "we'll", "let's",
  "agreed", "the call is".
* An action item sounds like a person taking something on - "I'll", "I can" -
  or being handed it - "can you", "<Name>, could you".
* A due date is usually a weekday or a relative word, not a calendar date.

When the transcript does not contain those shapes, the extractor returns less
rather than inventing something. A short call with no decisions in it should
produce a summary with no decisions in it.
"""

import re
from datetime import timedelta

from django.utils import timezone

# Phrases that mark the group settling something.
DECISION_MARKERS = (
    "we'll ",
    "we will ",
    "let's ",
    "lets ",
    "we're going to ",
    "we are going to ",
    "we agreed",
    "agreed,",
    "we decided",
    "decision is",
    "the call is",
    "we should ",
    "going with ",
    "we'll go with",
)

# Phrases where the speaker takes something on themselves.
SELF_COMMITMENT = ("i'll ", "i will ", "i can ", "i'm going to ", "let me ")

# Phrases where work is handed to someone else.
DELEGATION = ("can you ", "could you ", "would you ", "please ")

# Weekday and relative-date words, mapped to days from today.
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
RELATIVE_DATES = {
    "today": 0,
    "tonight": 0,
    "tomorrow": 1,
    "this week": 3,
    "next week": 7,
    "end of the week": 5,
    "end of week": 5,
    "next month": 30,
    "this month": 14,
}

# Words too common to say anything about what a meeting was about.
STOPWORDS = frozenset("""
a about after all also am an and any are as at be because been before being but by can could
did do does doing done down each even every for from get gets go going got had has have he her
here hers him his how i if in into is it its just like make me more most much my no not now of
off on once one only or other our out over own re said same she should so some such than that
the their them then there these they this those through to too up us very was we well were what
when where which while who why will with would you your yeah yes okay ok right think thing
things going really actually maybe probably sure let lets us there's that's it's we'll i'll
""".split())

MIN_TOPIC_LENGTH = 4
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text):
    """Split a turn into sentences, dropping fragments too short to mean anything."""
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if len(s.strip()) > 12]


def _contains(haystack, needles):
    lowered = " " + haystack.lower().strip()
    return any(needle in lowered for needle in needles)


def _tidy(sentence):
    """Trim a quoted sentence down to something that reads as a bullet."""
    sentence = sentence.strip().rstrip(".").strip()
    # Drop conversational throat-clearing so the bullet starts on the substance.
    for opener in ("okay, ", "ok, ", "right, ", "so ", "well, ", "yeah, ", "i think "):
        if sentence.lower().startswith(opener):
            sentence = sentence[len(opener):]
    return sentence[:1].upper() + sentence[1:] if sentence else sentence


def find_due_date(text, today=None):
    """Read a due date out of a sentence, or return None.

    Weekdays resolve forwards - "by Friday" said on a Thursday means tomorrow,
    not six days ago.
    """
    today = today or timezone.localdate()
    lowered = text.lower()

    for phrase, days in RELATIVE_DATES.items():
        if phrase in lowered:
            return today + timedelta(days=days)

    for index, day in enumerate(WEEKDAYS):
        if day in lowered:
            ahead = (index - today.weekday()) % 7
            return today + timedelta(days=ahead or 7)

    return None


def _match_participant(text, participants):
    """Find a participant addressed by name in a sentence.

    Matches on first name because that is how people are addressed out loud -
    "Ada, can you take that" rather than "Ada Lovelace, can you take that".
    """
    lowered = text.lower()
    for participant in participants:
        first = (participant.display_name or "").strip().split(" ")[0].lower()
        if len(first) > 2 and re.search(r"\b%s\b" % re.escape(first), lowered):
            return participant
    return None


def extract_topics(segments, limit=5):
    """The words the meeting kept coming back to.

    Frequency over the whole transcript, minus stopwords. Crude, but it
    surfaces the actual subject matter - a call about pricing says "pricing" a
    lot - and it never invents a topic that was not discussed.
    """
    counts = {}
    for segment in segments:
        for word in re.findall(r"[a-zA-Z][a-zA-Z'-]+", segment.text.lower()):
            if len(word) < MIN_TOPIC_LENGTH or word in STOPWORDS:
                continue
            counts[word] = counts.get(word, 0) + 1

    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    # A word said once is not a topic.
    return [word.capitalize() for word, count in ranked[:limit] if count > 1]


def extract_decisions(segments, limit=6):
    """Sentences where the group settled something."""
    decisions = []
    seen = set()
    for segment in segments:
        for sentence in _sentences(segment.text):
            if not _contains(sentence, DECISION_MARKERS):
                continue
            tidied = _tidy(sentence)
            key = tidied.lower()
            if key in seen:
                continue
            seen.add(key)
            decisions.append(tidied)
            if len(decisions) >= limit:
                return decisions
    return decisions


def extract_action_items(segments, participants, limit=8):
    """Work someone took on, or was handed.

    Returns dicts rather than model instances so the caller decides what to do
    with them - the live-call flow writes them, and tests can inspect them
    without touching the database.
    """
    items = []
    seen = set()

    for segment in segments:
        for sentence in _sentences(segment.text):
            owner = None
            if _contains(sentence, SELF_COMMITMENT):
                # "I'll send the deck" - the speaker owns it.
                owner = segment.speaker
            elif _contains(sentence, DELEGATION):
                # "Ada, can you send the deck" - the person named owns it, and
                # falling back to nobody is better than guessing wrong.
                owner = _match_participant(sentence, participants)
            else:
                continue

            title = _tidy(sentence)
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)

            items.append(
                {
                    "title": title[:255],
                    "owner": owner,
                    "due_date": find_due_date(sentence),
                    "source_segment": segment,
                }
            )
            if len(items) >= limit:
                return items
    return items


def extract_highlights(segments, limit=3, padding=1):
    """Spans worth replaying: the moments a decision was made.

    Each highlight covers the deciding line plus a little either side, because
    a decision rarely makes sense without the sentence before it.
    """
    highlights = []
    for index, segment in enumerate(segments):
        if not _contains(segment.text, DECISION_MARKERS):
            continue
        first = segments[max(0, index - padding)]
        last = segments[min(len(segments) - 1, index + padding)]
        title = _tidy(_sentences(segment.text)[0] if _sentences(segment.text) else segment.text)
        highlights.append(
            {
                "title": title[:255],
                "description": "Captured automatically where the call reached a decision.",
                "start_ms": first.start_ms,
                "end_ms": last.end_ms,
            }
        )
        if len(highlights) >= limit:
            break
    return highlights


def build_summary(meeting, segments, topics, decisions):
    """A few sentences describing what happened, assembled from what was said.

    Extractive on purpose: it reports the shape of the call - who was in it,
    how long it ran, what it kept returning to - and quotes the decisions
    verbatim rather than paraphrasing them into something nobody said.
    """
    if not segments:
        return "No speech was captured for this meeting."

    speakers = _speaker_names(segments)
    minutes = max(1, round((segments[-1].end_ms - segments[0].start_ms) / 60000))
    parts = [
        "%s spoke across %d minute%s and %d turn%s."
        % (
            _join_names(speakers) if speakers else "Participants",
            minutes,
            "" if minutes == 1 else "s",
            len(segments),
            "" if len(segments) == 1 else "s",
        )
    ]

    if topics:
        parts.append("The conversation kept returning to %s." % _join_names(topics).lower())

    if decisions:
        parts.append(
            "%d decision%s came out of it, starting with: %s."
            % (len(decisions), "" if len(decisions) == 1 else "s", decisions[0].rstrip("."))
        )
    else:
        parts.append("No decisions were recorded.")

    return " ".join(parts)


def build_summary_for(template, meeting, segments, topics, decisions, actions):
    """A template-flavoured write-up, still assembled from what was said.

    Every template reads the same extracted facts - the shape of the call, the
    topics, the decisions, and the action items - and frames them differently.
    Nothing here paraphrases or invents: an action-items summary that finds no
    commitments says so, rather than inflating an aside into a task. Unknown or
    custom templates fall back to the general write-up.
    """
    if not segments:
        return "No speech was captured for this meeting."

    builder = _TEMPLATE_BUILDERS.get(template)
    if builder is None:
        return build_summary(meeting, segments, topics, decisions)
    return builder(meeting, segments, topics, decisions, actions)


def _summary_actions(actions):
    """Action items rendered as sentences, owner-attributed where known."""
    lines = []
    for item in actions:
        owner = item.get("owner")
        who = owner.display_name if owner else "Unassigned"
        lines.append("%s: %s" % (who, item["title"].rstrip(".")))
    return lines


def _action_items_summary(meeting, segments, topics, decisions, actions):
    if not actions:
        return (
            "No action items were picked up from this call - nobody was heard "
            "taking something on or being handed it."
        )
    rendered = _summary_actions(actions)
    parts = [
        "%d action item%s came out of this call."
        % (len(actions), "" if len(actions) == 1 else "s")
    ]
    parts.extend("• %s." % line for line in rendered)
    return "\n".join(parts)


def _sales_call_summary(meeting, segments, topics, decisions, actions):
    parts = [
        "Sales call notes.",
        build_summary(meeting, segments, topics, decisions),
    ]
    if decisions:
        parts.append(
            "What was agreed: %s." % _join_names([d.rstrip(".") for d in decisions]).rstrip(".")
        )
    next_steps = _summary_actions(actions)
    parts.append(
        "Next steps: %s."
        % (_join_names(next_steps).rstrip(".") if next_steps else "none captured")
    )
    return " ".join(parts)


def _one_on_one_summary(meeting, segments, topics, decisions, actions):
    speakers = _speaker_names(segments)
    who = _join_names(speakers) if speakers else "The two participants"
    parts = ["One-on-one between %s." % who]
    if topics:
        parts.append("They talked mostly about %s." % _join_names(topics).lower())
    follow_ups = _summary_actions(actions)
    parts.append(
        "Follow-ups: %s."
        % (_join_names(follow_ups).rstrip(".") if follow_ups else "none recorded")
    )
    return " ".join(parts)


def _standup_summary(meeting, segments, topics, decisions, actions):
    """One line per speaker, quoting each person's longest turn.

    A standup is really a round of updates, so the useful shape is per-person
    rather than one narrative - each line is the substance of what that person
    said, taken verbatim from their longest turn.
    """
    longest = {}
    for segment in segments:
        name = segment.speaker.display_name if segment.speaker else "Unattributed"
        current = longest.get(name)
        if current is None or segment.duration_ms > current.duration_ms:
            longest[name] = segment
    lines = ["Standup updates:"]
    for name, segment in longest.items():
        sentence = _sentences(segment.text)
        gist = _tidy(sentence[0]) if sentence else _tidy(segment.text)
        lines.append("• %s: %s." % (name, gist.rstrip(".")))
    return "\n".join(lines)


def _interview_summary(meeting, segments, topics, decisions, actions):
    questions = [
        _tidy(sentence)
        for segment in segments
        for sentence in _sentences(segment.text)
        if sentence.rstrip().endswith("?")
    ]
    parts = [build_summary(meeting, segments, topics, decisions)]
    if questions:
        parts.append(
            "%d question%s were put during the interview, starting with: %s?"
            % (
                len(questions),
                "" if len(questions) == 1 else "s",
                questions[0].rstrip("?"),
            )
        )
    else:
        parts.append("No questions were detected in the transcript.")
    return " ".join(parts)


_TEMPLATE_BUILDERS = {
    "action_items": _action_items_summary,
    "sales_call": _sales_call_summary,
    "one_on_one": _one_on_one_summary,
    "standup": _standup_summary,
    "interview": _interview_summary,
}


def _speaker_names(segments):
    """Distinct speaker names in the order they first spoke."""
    names = []
    for segment in segments:
        name = segment.speaker.display_name if segment.speaker else None
        if name and name not in names:
            names.append(name)
    return names


def _join_names(names):
    """['a', 'b', 'c'] -> 'a, b and c'."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return "%s and %s" % (", ".join(names[:-1]), names[-1])
