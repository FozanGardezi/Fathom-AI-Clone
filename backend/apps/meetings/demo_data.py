"""The dataset behind `manage.py seed_demo_data`.

Kept apart from the command itself so the command stays about *how* the data is
written and this file about *what* it is.

Each meeting is a dict:

  key            stable slug; becomes the meeting's external_id and is what
                 makes reseeding idempotent
  people         (display_name, email, role) - a role of host/cohost marks
                 someone internal, and the host's account owns the meeting
  sections       (anchor, [(speaker, text), ...]) where `anchor` is how far
                 into the meeting the section starts, as a fraction. Turns
                 inside a section run back to back with natural pauses; the
                 jump between sections stands in for the parts of the call the
                 excerpt skips, which is why timestamps span the full duration.
  highlights     bounds given as transcript turn numbers, so a highlight always
                 lines up with something actually said.
  status         defaults to "ready". A meeting that has not happened yet is
                 "scheduled", and then `days_ago` is negative - it is a date in
                 the future - and `sections`, `summary`, `action_items` and
                 `highlights` are all omitted, because a call nobody has had
                 produces no transcript and nothing to follow up.

Addresses use RFC-reserved domains (.test, .example) - none of this is a real
person or company.
"""

# Every demo meeting's external_id starts with this, which is how a reseed
# finds and replaces the previous run without touching anyone's real data.
DEMO_PREFIX = "demo-"


MEETINGS = [
    {
        "key": "customer-discovery-acme",
        "title": "Customer Discovery — Acme",
        "platform": "zoom",
        "language": "en",
        "duration_minutes": 45,
        "days_ago": 9,
        "people": [
            ("Priya Raman", "priya@fathom.test", "host"),
            ("Daniel Okafor", "daniel@fathom.test", "cohost"),
            ("Marcus Feld", "marcus.feld@acme.example", "attendee"),
            ("Lena Vogt", "lena.vogt@acme.example", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Priya Raman", "Thanks for making the time, both of you. I want to keep this mostly on your side — I'd rather understand how dispatch actually works today than talk at you about us."),
                ("Marcus Feld", "That's a relief, honestly. We've sat through four of these and three of them were demos in disguise."),
                ("Priya Raman", "Noted. Daniel's here as our solutions engineer, so if we hit anything technical he can go deeper than I can."),
                ("Daniel Okafor", "Happy to just listen for most of it."),
                ("Lena Vogt", "Should I share my screen? I've got the dispatch board open."),
                ("Priya Raman", "Let's start with words, then look at it. Marcus, who owns dispatch day to day?"),
                ("Marcus Feld", "Lena owns the process. I own the outcome when it goes wrong, which is most Mondays."),
            ]),
            (0.14, [
                ("Lena Vogt", "So a load comes in through the portal or by email. If it's email, someone on my team retypes it into the TMS. That's about forty a day."),
                ("Priya Raman", "Retypes. Meaning there's no parsing on the email side at all?"),
                ("Lena Vogt", "None. We tried a rules engine two years ago and it broke every time a customer changed their template."),
                ("Marcus Feld", "Which they do constantly. One of our biggest shippers changed their PO format in March and nobody told us for six weeks."),
                ("Daniel Okafor", "What happened during those six weeks?"),
                ("Marcus Feld", "We ate it. Two people manually reconciling, about fifteen hours a week between them."),
                ("Priya Raman", "And that's the part that doesn't show up in any system of record."),
                ("Marcus Feld", "Right. It shows up in my overtime budget and nowhere else."),
            ]),
            (0.36, [
                ("Priya Raman", "Walk me through the worst version of a Monday."),
                ("Lena Vogt", "Weekend loads pile up. We come in to maybe ninety in the queue, half of them emailed. By ten we're triaging instead of dispatching."),
                ("Lena Vogt", "And every one we're late on, the customer calls. So now two people are on the phone instead of clearing the queue."),
                ("Daniel Okafor", "Is the calling reactive, or do you have an SLA you're notifying against?"),
                ("Lena Vogt", "Reactive. Entirely. We find out we're late when they tell us."),
                ("Marcus Feld", "That's the thing I actually want to fix. Not the typing — the not knowing."),
                ("Priya Raman", "That's a useful distinction. If the retyping stayed but you knew about every exception within ten minutes, is that a win?"),
                ("Marcus Feld", "That's most of the win, yes. The typing is annoying. The blind spot is expensive."),
            ]),
            (0.60, [
                ("Daniel Okafor", "What's the TMS? And is there an API, or are we talking flat-file exports?"),
                ("Lena Vogt", "MercuryTMS. There's an API but our contract tier doesn't include it, apparently."),
                ("Daniel Okafor", "That's usually a line item rather than a hard no. Worth asking them."),
                ("Marcus Feld", "Lena, can you get that in writing from our rep? If it's an upsell I'd rather know the number now."),
                ("Lena Vogt", "I'll ask this week."),
                ("Daniel Okafor", "Even without it there's a nightly export we could work from. It'd mean exceptions surface in hours rather than minutes, which is worse but not useless."),
                ("Priya Raman", "Let's scope both and let you pick."),
            ]),
            (0.81, [
                ("Priya Raman", "Timeline — is there anything forcing a date?"),
                ("Marcus Feld", "Peak starts mid-October. If we're not running by the first week of October we won't touch it until January."),
                ("Priya Raman", "Then let's work backwards from that. Daniel, what does a pilot need?"),
                ("Daniel Okafor", "Two weeks if the API's open, four if we're on exports. I'd want one lane, not the whole board."),
                ("Marcus Feld", "Start with the Midwest lane. It's the noisiest and Lena knows it cold."),
                ("Priya Raman", "I'll send a one-page scope by Thursday and we'll book the technical session for next week."),
                ("Lena Vogt", "Send it to both of us. Marcus doesn't read anything that isn't in a calendar invite."),
                ("Marcus Feld", "That is unfortunately accurate."),
            ]),
        ],
        "summary": {
            "template": "sales_call",
            "text": (
                "Acme's dispatch team manually rekeys roughly 40 emailed loads a day into "
                "MercuryTMS, with no parsing layer after a rules engine failed two years ago. "
                "Marcus Feld was clear that the manual entry is an irritation but the real cost "
                "is the exception blind spot — they learn they are late when the customer calls. "
                "He confirmed that surfacing exceptions within ten minutes would capture most of "
                "the value even if rekeying continued. API access to MercuryTMS is gated behind "
                "their contract tier; Lena Vogt is confirming whether it is a paid add-on, with a "
                "nightly-export fallback if not. Peak season starting mid-October is a hard "
                "deadline: not live by the first week of October means no project until January."
            ),
            "topics": [
                "Current dispatch workflow and manual rekeying",
                "Exception visibility and customer-reported delays",
                "MercuryTMS API access and contract tier",
                "Pilot scope and peak-season timeline",
            ],
            "decisions": [
                "Pilot will cover the Midwest lane only, not the full dispatch board",
                "Scope both an API integration and a nightly-export fallback, and let Acme choose",
                "Target go-live is the first week of October, before peak season",
            ],
        },
        "action_items": [
            ("Priya Raman", "Send one-page pilot scope to Marcus and Lena", "Cover both the API and nightly-export paths with separate timelines. Copy both of them — Marcus only reads what arrives as a calendar invite.", 2, False),
            ("Lena Vogt", "Confirm MercuryTMS API access with the account rep", "Get it in writing whether API access is a paid add-on and what the number is.", 5, False),
            ("Daniel Okafor", "Draft technical requirements for the Midwest lane pilot", "Two-week estimate assuming API access, four weeks on nightly exports.", 4, False),
            ("Priya Raman", "Book the technical deep-dive session", "Needs Daniel, Lena, and whoever owns MercuryTMS on Acme's side.", 3, True),
            ("Marcus Feld", "Share March PO format change details", "The reconciliation effort during those six weeks is the clearest cost example we have.", 7, False),
        ],
        "highlights": [
            ("The real problem isn't the typing", "Marcus reframes the pain from data entry to exception blind spots — the line to quote in the proposal.", 20, 23),
            ("Hard October deadline", "Peak season forces a date. Miss it and the deal slips to January.", 30, 31),
        ],
    },
    {
        "key": "product-roadmap-sync",
        "title": "Product Roadmap Sync",
        "platform": "google_meet",
        "language": "en",
        "duration_minutes": 58,
        "days_ago": 6,
        "people": [
            ("Sofia Marchetti", "sofia@fathom.test", "host"),
            ("Tom Whitfield", "tom@fathom.test", "cohost"),
            ("Aisha Nwosu", "aisha@fathom.test", "attendee"),
            ("Ravi Chandra", "ravi@fathom.test", "attendee"),
            ("Grace Lin", "grace@fathom.test", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Sofia Marchetti", "Three things today: search, the mobile decision, and how much of Q1 we're giving to debt. I want to leave with a number on that last one."),
                ("Tom Whitfield", "I'd like to start with debt, actually, because it changes what's possible in the other two."),
                ("Sofia Marchetti", "Go ahead."),
                ("Tom Whitfield", "The transcript pipeline is the problem. It was written for ten thousand segments a day and we're doing two hundred thousand."),
                ("Ravi Chandra", "Two hundred and forty as of last week."),
                ("Tom Whitfield", "Right. It hasn't fallen over, but the retry logic is doing a lot of quiet work."),
            ]),
            (0.13, [
                ("Sofia Marchetti", "What does 'quiet work' cost us?"),
                ("Ravi Chandra", "About four percent of segments land more than a minute late. Customers don't see it because the summary waits for them."),
                ("Grace Lin", "They do see it, though. We get tickets that say 'transcript stopped updating' and it's almost always this."),
                ("Sofia Marchetti", "How many tickets?"),
                ("Grace Lin", "Eleven last month. Small, but they're the ones that take forty minutes each because we can't reproduce them."),
                ("Tom Whitfield", "That's the tell. Unreproducible support load is a debt symptom."),
                ("Aisha Nwosu", "It also means the live view is unreliable, and the live view is the thing people demo."),
            ]),
            (0.31, [
                ("Sofia Marchetti", "Okay. Search. Aisha, where did the research land?"),
                ("Aisha Nwosu", "People don't search the way we built it. We assumed keyword-in-transcript. What they actually do is search for a decision they half-remember."),
                ("Aisha Nwosu", "Eight of twelve participants typed a phrase that wasn't in the transcript at all. It was in the summary."),
                ("Sofia Marchetti", "So search over summaries and decisions, not just segments."),
                ("Aisha Nwosu", "Or both, weighted. But if I had to pick one, summaries."),
                ("Ravi Chandra", "That's cheaper too. Summaries are a fraction of the volume."),
                ("Tom Whitfield", "It's cheaper until someone asks for it to be real-time. Let's say up front that search is eventually consistent."),
                ("Sofia Marchetti", "Agreed, and let's put that in the spec rather than discovering it in a bug report."),
            ]),
            (0.55, [
                ("Sofia Marchetti", "Mobile. We keep deferring this."),
                ("Grace Lin", "I'll make the case. Roughly a third of our support conversations start with someone saying they were trying to check something on their phone."),
                ("Tom Whitfield", "A responsive web view is two sprints. A native app is a quarter and a hiring plan."),
                ("Aisha Nwosu", "The read-only case covers most of it. Nobody's editing a summary on a phone."),
                ("Sofia Marchetti", "So responsive read-only, and we revisit native when there's a reason beyond convenience."),
                ("Grace Lin", "That would close most of those tickets."),
                ("Tom Whitfield", "I can live with that."),
            ]),
            (0.78, [
                ("Sofia Marchetti", "Back to the number. How much of Q1 goes to the pipeline?"),
                ("Tom Whitfield", "Thirty percent gets it stable. Twenty gets it less bad."),
                ("Sofia Marchetti", "Take thirty. I'd rather ship two things well than four things that page you."),
                ("Ravi Chandra", "That's the right call. I'll size the rewrite properly this week rather than guessing."),
                ("Sofia Marchetti", "Then search and mobile split the rest, search leading. Aisha, spec by the end of next week?"),
                ("Aisha Nwosu", "End of next week works."),
                ("Sofia Marchetti", "Good. I'll write this up so nobody remembers it differently in three weeks."),
            ]),
        ],
        "summary": {
            "template": "general",
            "text": (
                "The team allocated 30% of Q1 engineering capacity to rewriting the transcript "
                "pipeline, which was built for 10,000 segments a day and is now handling 240,000. "
                "Roughly 4% of segments land over a minute late, surfacing as unreproducible "
                "support tickets — eleven last month, each costing about forty minutes. User "
                "research reframed search: eight of twelve participants searched for phrases that "
                "appeared in summaries rather than transcripts, so search will index summaries and "
                "decisions first and be explicitly eventually consistent. Mobile was settled as "
                "responsive read-only web rather than native, on the grounds that nobody edits a "
                "summary on a phone."
            ),
            "topics": [
                "Transcript pipeline scale and retry behaviour",
                "Support ticket load from late segments",
                "Search research findings",
                "Mobile: responsive web vs native",
                "Q1 capacity allocation",
            ],
            "decisions": [
                "Allocate 30% of Q1 engineering capacity to the transcript pipeline rewrite",
                "Search will index summaries and decisions first, weighted above raw segments",
                "Search is explicitly eventually consistent, stated in the spec up front",
                "Mobile ships as responsive read-only web; native is deferred until there is a reason beyond convenience",
            ],
        },
        "action_items": [
            ("Ravi Chandra", "Size the transcript pipeline rewrite", "Proper estimate rather than the current guess. Needed before Q1 planning locks.", 5, False),
            ("Aisha Nwosu", "Write the search specification", "Summaries and decisions weighted above segments. State eventual consistency explicitly.", 10, False),
            ("Tom Whitfield", "Scope responsive read-only mobile view", "Two-sprint estimate to confirm.", 7, False),
            ("Grace Lin", "Pull the eleven late-segment tickets into one doc", "So the rewrite has real reproduction cases to work from.", 4, False),
            ("Sofia Marchetti", "Write up the Q1 allocation decision", "Circulate so the 30% number doesn't get relitigated in three weeks.", 2, True),
        ],
        "highlights": [
            ("Unreproducible tickets are a debt symptom", "Tom's framing for why support load justifies the rewrite.", 11, 13),
            ("People search summaries, not transcripts", "The research finding that redirected the whole search project.", 15, 17),
        ],
    },
    {
        "key": "enterprise-sales-northwind",
        "title": "Enterprise Sales Call — Northwind",
        "platform": "microsoft_teams",
        "language": "en",
        "duration_minutes": 38,
        "days_ago": 4,
        "people": [
            ("Priya Raman", "priya@fathom.test", "host"),
            ("Jordan Blake", "jordan@fathom.test", "cohost"),
            ("Karen Stoll", "karen.stoll@northwind.example", "attendee"),
            ("Victor Hale", "victor.hale@northwind.example", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Karen Stoll", "Before we go anywhere — Victor runs security review and he has a hard stop at the half hour. Can we do his questions first?"),
                ("Priya Raman", "Absolutely, let's flip the agenda."),
                ("Victor Hale", "Appreciated. Three things: SOC 2, where the data physically sits, and what happens to recordings when we delete an account."),
                ("Jordan Blake", "SOC 2 Type II, renewed in June. I'll send the report under NDA today."),
                ("Victor Hale", "Type II is what I needed to hear. Type I would have ended this."),
            ]),
            (0.16, [
                ("Victor Hale", "Data residency. We have German subsidiaries and works council agreements that don't bend."),
                ("Priya Raman", "EU region is available. Recordings, transcripts and derived summaries all stay in-region."),
                ("Victor Hale", "Derived data too? That's usually where the answer gets vague."),
                ("Priya Raman", "Derived data too. I'd rather you hear the caveat from me though — our vector index for search currently runs in a single region."),
                ("Victor Hale", "So search would be out of scope for the German entities."),
                ("Priya Raman", "For now, yes. I won't pretend otherwise."),
                ("Victor Hale", "I'd rather hear that than find it in an audit. That's workable if it's documented."),
                ("Jordan Blake", "We'll put it in writing as a known limitation with a roadmap date."),
            ]),
            (0.38, [
                ("Victor Hale", "Deletion. If we terminate, what's the actual sequence?"),
                ("Priya Raman", "Thirty-day soft delete, then hard deletion across primaries and backups within ninety. Certificate on request."),
                ("Victor Hale", "Ninety days on backups is longer than our standard but I've approved it before. That's all from me — thank you both, this was less painful than I expected."),
                ("Karen Stoll", "High praise. Victor, go."),
            ]),
            (0.52, [
                ("Karen Stoll", "Right. Money. Your per-seat number is roughly double what we're paying now."),
                ("Jordan Blake", "What are you comparing against?"),
                ("Karen Stoll", "The recording tool we already have bundled. It's not as good, but it's effectively free at this point."),
                ("Jordan Blake", "Free is hard to argue with on price. Can I argue on scope instead? How many of your two hundred seats actually need summaries?"),
                ("Karen Stoll", "Honestly? Maybe sixty. Sales and customer success."),
                ("Jordan Blake", "Then let's not price two hundred. Sixty seats at the enterprise tier lands close to your current spend."),
                ("Karen Stoll", "That's a more interesting conversation. Could we expand later without a renegotiation?"),
                ("Jordan Blake", "Mid-term expansion at the same rate, written into the order form."),
                ("Karen Stoll", "Do that and I can take it to procurement."),
            ]),
            (0.76, [
                ("Karen Stoll", "What does rollout look like? I don't have people to spare for a six-week implementation."),
                ("Priya Raman", "SSO and the calendar integration are the only real setup. Half a day with your IT, then it's self-serve per user."),
                ("Karen Stoll", "Half a day I can find. What about our existing recordings — do we lose them?"),
                ("Priya Raman", "They stay where they are. We don't migrate history by default; most customers run parallel for a quarter."),
                ("Karen Stoll", "Parallel is fine. Our fiscal year starts in November, so budget would come from next year's allocation."),
                ("Jordan Blake", "Then a November start with paper signed in October?"),
                ("Karen Stoll", "If procurement moves. Send me the sixty-seat number and the security package and I'll open the request this week."),
                ("Priya Raman", "You'll have both tomorrow."),
            ]),
        ],
        "summary": {
            "template": "sales_call",
            "text": (
                "Northwind's security lead Victor Hale cleared the call on SOC 2 Type II, EU data "
                "residency, and deletion timelines, with one disclosed limitation: the search vector "
                "index is single-region, so search is out of scope for their German entities until "
                "that changes. He explicitly valued hearing the caveat directly rather than "
                "discovering it in an audit. The pricing objection — roughly double their current "
                "bundled tool — was reframed from 200 seats to the 60 that actually need summaries, "
                "which lands near current spend, with mid-term expansion at the same rate written "
                "into the order form. Karen Stoll's fiscal year starts in November, pointing at "
                "October paper for a November start."
            ),
            "topics": [
                "SOC 2 Type II certification",
                "EU data residency and the single-region search index",
                "Data deletion and backup retention",
                "Per-seat pricing versus bundled incumbent",
                "Rollout effort and parallel running",
            ],
            "decisions": [
                "Price 60 seats at the enterprise tier rather than all 200",
                "Write mid-term expansion at the same rate into the order form",
                "Document the single-region search index as a known limitation with a roadmap date",
                "Target October signature for a November start, aligned to Northwind's fiscal year",
            ],
        },
        "action_items": [
            ("Jordan Blake", "Send SOC 2 Type II report under NDA", "Victor confirmed Type II was the bar. Same-day commitment.", 1, True),
            ("Jordan Blake", "Produce the 60-seat enterprise quote", "Include mid-term expansion at the same rate in the order form language.", 1, False),
            ("Priya Raman", "Send the security package", "Bundle the residency answer and the single-region search limitation with a roadmap date.", 1, False),
            ("Priya Raman", "Document search index residency limitation", "In writing, as a known limitation — Victor will accept it documented, not discovered.", 3, False),
            ("Karen Stoll", "Open the procurement request", "Blocked on the quote and security package.", 5, False),
        ],
        "highlights": [
            ("Honesty on the residency gap", "Priya volunteers the single-region search limitation unprompted and it builds trust rather than costing the deal.", 9, 13),
            ("Reframing 200 seats to 60", "Jordan moves the pricing objection from price to scope — the turn that unblocked procurement.", 20, 25),
        ],
    },
    {
        "key": "engineering-standup",
        "title": "Engineering Standup",
        "platform": "google_meet",
        "language": "en",
        "duration_minutes": 23,
        "days_ago": 1,
        "people": [
            ("Tom Whitfield", "tom@fathom.test", "host"),
            ("Meera Iyer", "meera@fathom.test", "attendee"),
            ("Chris Dawson", "chris@fathom.test", "attendee"),
            ("Yuki Tanaka", "yuki@fathom.test", "attendee"),
            ("Ben Alvarez", "ben@fathom.test", "attendee"),
            ("Nadia Haddad", "nadia@fathom.test", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Tom Whitfield", "Quick one today. Blockers first, updates second, and if your update has no blocker keep it to a sentence."),
                ("Meera Iyer", "Blocked. The participant migration needs an exclusive lock and staging has a connection that won't die."),
                ("Tom Whitfield", "Which connection?"),
                ("Meera Iyer", "An idle transaction from the analytics reader. It's been open since Thursday."),
                ("Ben Alvarez", "That's mine. I left a session open debugging the export job. I'll kill it right now."),
                ("Meera Iyer", "Then I'm unblocked in about five minutes."),
            ]),
            (0.18, [
                ("Chris Dawson", "Also blocked, differently. The summarisation provider is rate limiting us on the backfill."),
                ("Tom Whitfield", "At what rate?"),
                ("Chris Dawson", "Sixty a minute sustained. We're asking for four hundred because the backfill doesn't back off."),
                ("Yuki Tanaka", "It doesn't back off at all? That's going to bite us in production too."),
                ("Chris Dawson", "Right now it retries immediately and logs a warning nobody reads."),
                ("Tom Whitfield", "Then that's the actual bug. Add exponential backoff with jitter and the backfill becomes a scheduling problem instead of an incident."),
                ("Chris Dawson", "I'll do it today. The backfill can wait a day."),
            ]),
            (0.42, [
                ("Yuki Tanaka", "Not blocked. The flaky highlight test — I found it. It assumed segment ordering without a tiebreak, so equal start offsets shuffled."),
                ("Tom Whitfield", "That's the third flake from missing tiebreaks this month."),
                ("Yuki Tanaka", "I added an ordering assertion to the shared fixture so the next one fails loudly instead of intermittently."),
                ("Nadia Haddad", "Can you write that up? I keep hitting the same thing in the API tests."),
                ("Yuki Tanaka", "I'll put it in the testing notes."),
            ]),
            (0.63, [
                ("Nadia Haddad", "Mine's short. Action item endpoints are done and reviewed, highlights are in review."),
                ("Ben Alvarez", "Export job is back to normal after I stop leaving transactions open, apparently."),
                ("Tom Whitfield", "We'll let that one go."),
                ("Meera Iyer", "One thing — once the migration lands, staging needs reseeding. It's been drifting for weeks."),
                ("Tom Whitfield", "Good call. Nadia, can you own that once Meera's migration is through?"),
                ("Nadia Haddad", "Sure."),
            ]),
            (0.85, [
                ("Tom Whitfield", "Anything that needs me?"),
                ("Chris Dawson", "Only if the provider won't raise the limit. Then it's a procurement conversation."),
                ("Tom Whitfield", "Ping me if they say no. That's it — go."),
            ]),
        ],
        "summary": {
            "template": "standup",
            "text": (
                "Two blockers, both resolved in the call. Meera Iyer's participant migration was "
                "waiting on an exclusive lock held by an idle analytics transaction Ben Alvarez had "
                "left open since Thursday; he closed it on the call. Chris Dawson hit provider rate "
                "limiting on the summarisation backfill — 60/min sustained against 400 requested — "
                "which Tom Whitfield reframed as a missing-backoff bug rather than a quota problem, "
                "since the same behaviour would cause production incidents. Yuki Tanaka root-caused "
                "the flaky highlight test to missing ordering tiebreaks, the third such flake this "
                "month, and added a shared fixture assertion."
            ),
            "topics": [
                "Participant migration blocked on a staging lock",
                "Summarisation provider rate limiting",
                "Flaky highlight test and ordering tiebreaks",
                "Staging data drift",
            ],
            "decisions": [
                "Treat the missing backoff as the bug; the backfill waits a day",
                "Add exponential backoff with jitter before retrying the backfill",
                "Reseed staging once the participant migration lands",
            ],
        },
        "action_items": [
            ("Ben Alvarez", "Kill the idle analytics transaction on staging", "Open since Thursday, holding the lock Meera's migration needs.", 0, True),
            ("Chris Dawson", "Add exponential backoff with jitter to the summarisation client", "The retry-immediately behaviour is a production risk, not just a backfill problem.", 1, False),
            ("Yuki Tanaka", "Write up the ordering-tiebreak flake pattern", "Third occurrence this month. Add to the testing notes so the API tests stop hitting it.", 3, False),
            ("Nadia Haddad", "Reseed staging after the migration lands", "Blocked on Meera's participant migration.", 4, False),
            ("Chris Dawson", "Escalate the provider rate limit if they decline", "Becomes a procurement conversation — loop in Tom.", 6, False),
        ],
        "highlights": [
            ("The rate limit is a backoff bug", "Tom reframes a quota complaint as a production-risk bug. Worth reusing in the incident review.", 10, 12),
        ],
    },
    {
        "key": "one-on-one-sofia-meera",
        "title": "One-on-One — Sofia & Meera",
        "platform": "zoom",
        "language": "en",
        "duration_minutes": 30,
        "days_ago": 2,
        "people": [
            ("Sofia Marchetti", "sofia@fathom.test", "host"),
            ("Meera Iyer", "meera@fathom.test", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Sofia Marchetti", "How are you actually doing? Not the status version."),
                ("Meera Iyer", "Tired, if I'm honest. Not unhappy. The migration work has been heads-down for three weeks and I've lost the thread on everything else."),
                ("Sofia Marchetti", "That tracks with what I've seen. You've been the only name on those PRs."),
                ("Meera Iyer", "That's part of it. It's not hard work, it's just lonely work."),
            ]),
            (0.17, [
                ("Sofia Marchetti", "Is that a staffing problem or a scoping problem?"),
                ("Meera Iyer", "Scoping, I think. I took the whole migration because it was easier than explaining it. That was a mistake."),
                ("Sofia Marchetti", "It's a common one. What would splitting it have looked like?"),
                ("Meera Iyer", "Chris could have taken the backfill half. There's a clean seam there and I ignored it."),
                ("Sofia Marchetti", "Next time, I'd rather you spend the day writing the handoff than the three weeks alone."),
                ("Meera Iyer", "Noted. Genuinely."),
            ]),
            (0.38, [
                ("Sofia Marchetti", "Let's talk about where you want to be in a year, because I don't think I actually know."),
                ("Meera Iyer", "I want to be leading something. Not managing — I've watched Tom's calendar and I don't want that yet. Technical leadership on a whole area."),
                ("Sofia Marchetti", "Which area?"),
                ("Meera Iyer", "Data model and the pipeline. It's the part I understand better than anyone and it's also the part that keeps breaking."),
                ("Sofia Marchetti", "That's a real gap and you'd be the obvious person. What's missing?"),
                ("Meera Iyer", "Visibility, probably. I fix things quietly and nobody knows there was a problem."),
                ("Sofia Marchetti", "Then let's fix the visibility rather than asking you to fix things louder."),
            ]),
            (0.62, [
                ("Sofia Marchetti", "Concretely: the pipeline rewrite is thirty percent of Q1. I'd like you to own the design, not just the implementation."),
                ("Meera Iyer", "Own it how far? Do I get to say no to things?"),
                ("Sofia Marchetti", "You get to say no to things. You'd present the design to the team and defend it, and I'd back you in the room."),
                ("Meera Iyer", "That's what I want. Yes."),
                ("Sofia Marchetti", "Then that's the growth plan for the half, and we'll review it properly at the end of Q1."),
            ]),
            (0.84, [
                ("Meera Iyer", "One piece of feedback going the other way, if that's alright."),
                ("Sofia Marchetti", "Please."),
                ("Meera Iyer", "Roadmap decisions land in writing after the fact. By then it feels settled. I'd rather see the draft while it's still a question."),
                ("Sofia Marchetti", "That's fair and it's easy to fix. I'll share the Q1 draft before the next sync instead of after."),
                ("Meera Iyer", "That's all I wanted."),
            ]),
        ],
        "summary": {
            "template": "one_on_one",
            "text": (
                "Meera Iyer named the three weeks of solo migration work as lonely rather than "
                "difficult, and diagnosed it as a scoping mistake — she absorbed the whole migration "
                "because it was easier than explaining a handoff, ignoring a clean seam where Chris "
                "could have taken the backfill. On direction, she wants technical leadership over "
                "the data model and pipeline rather than people management, and identified "
                "visibility as the gap: she fixes things quietly. Sofia offered ownership of the Q1 "
                "pipeline rewrite design, including authority to decline scope, with Sofia backing "
                "her in the room. Meera gave upward feedback that roadmap decisions arrive in "
                "writing already settled; Sofia agreed to circulate the Q1 draft before the next "
                "sync rather than after."
            ),
            "topics": [
                "Workload and solo work on the migration",
                "Scoping and handoff habits",
                "Career direction: technical leadership over management",
                "Visibility of quiet fixes",
                "Upward feedback on roadmap communication",
            ],
            "decisions": [
                "Meera owns the design of the Q1 pipeline rewrite, with authority to decline scope",
                "Sofia will circulate roadmap drafts before syncs rather than decisions after them",
                "Growth plan reviewed formally at the end of Q1",
            ],
        },
        "action_items": [
            ("Sofia Marchetti", "Share the Q1 roadmap draft before the next sync", "Meera's feedback: decisions currently arrive already settled.", 3, False),
            ("Meera Iyer", "Draft the pipeline rewrite design for team review", "Present and defend it; Sofia backs it in the room.", 12, False),
            ("Sofia Marchetti", "Schedule the end-of-Q1 growth plan review", "Formal checkpoint on the technical leadership track.", 20, False),
        ],
        "highlights": [
            ("It's not hard work, it's lonely work", "The line that reframed the workload conversation from capacity to scoping.", 3, 3),
            ("Fix the visibility, not the volume", "Sofia's response to Meera fixing things quietly — worth reusing in other one-on-ones.", 15, 16),
        ],
    },
    {
        "key": "company-planning-q1",
        "title": "Company Planning — Q1",
        "platform": "zoom",
        "language": "en",
        "duration_minutes": 60,
        "days_ago": 13,
        "people": [
            ("Elena Vargas", "elena@fathom.test", "host"),
            ("Jordan Blake", "jordan@fathom.test", "cohost"),
            ("Sofia Marchetti", "sofia@fathom.test", "attendee"),
            ("Tom Whitfield", "tom@fathom.test", "attendee"),
            ("Hannah Cole", "hannah@fathom.test", "attendee"),
            ("Omar Faruqi", "omar@fathom.test", "attendee"),
            ("Grace Lin", "grace@fathom.test", "attendee"),
            ("Ravi Chandra", "ravi@fathom.test", "attendee"),
        ],
        "sections": [
            (0.00, [
                ("Elena Vargas", "Four topics: the number we're committing to, hiring, the enterprise tier, and support coverage. I want decisions on all four, not discussion."),
                ("Hannah Cole", "Then let me put the number up first. Current run rate gives us nineteen months of runway. Every plan today spends some of that."),
                ("Elena Vargas", "And the board's expectation?"),
                ("Hannah Cole", "They'd like eighteen months maintained at the end of Q1. So we can spend, but not faster than we grow."),
                ("Jordan Blake", "That's tighter than last quarter."),
                ("Hannah Cole", "It is. Last quarter we hadn't closed two enterprise deals that then slipped."),
            ]),
            (0.11, [
                ("Elena Vargas", "Jordan, where does enterprise actually stand?"),
                ("Jordan Blake", "Three in late stage. Northwind is the closest — sixty seats, November start if procurement moves."),
                ("Jordan Blake", "The pattern across all three is the same: security review is no longer the blocker, pricing structure is."),
                ("Elena Vargas", "Meaning our per-seat model doesn't fit them."),
                ("Jordan Blake", "It fits badly. They all want to buy for the team that needs it, not the company that has it."),
                ("Omar Faruqi", "That matches what I see inbound. People self-describe as a department, not a company."),
                ("Elena Vargas", "Then the enterprise tier isn't a discount, it's a different unit of sale. Let's design it that way."),
            ]),
            (0.26, [
                ("Hannah Cole", "If we price by department we need to model it carefully. Sixty seats at enterprise versus two hundred at standard isn't obviously better revenue."),
                ("Jordan Blake", "It's better closed revenue than two hundred seats we don't win."),
                ("Hannah Cole", "Agreed, I just want the model before the pricing page."),
                ("Elena Vargas", "Fair. Hannah and Jordan, bring a model to next week's exec sync, then we commit."),
                ("Jordan Blake", "We can do that."),
            ]),
            (0.38, [
                ("Elena Vargas", "Hiring. Tom, you've been asking for two engineers since October."),
                ("Tom Whitfield", "Still asking. But I'd change the shape of the ask — one senior backend and one infrastructure, not two generalists."),
                ("Ravi Chandra", "The infrastructure gap is the one that hurts. We're all part-time on it and nobody owns it."),
                ("Hannah Cole", "Two hires in Q1 is roughly a month of runway across the year."),
                ("Elena Vargas", "One in Q1, one in Q2, infrastructure first. If enterprise closes the way Jordan thinks, we accelerate the second."),
                ("Tom Whitfield", "I'll take that. Infrastructure first is the right order anyway."),
                ("Sofia Marchetti", "Can we write down the trigger for accelerating? Otherwise it quietly never happens."),
                ("Elena Vargas", "Two enterprise deals signed. Hannah, hold us to it."),
            ]),
            (0.56, [
                ("Elena Vargas", "Support. Grace, you've been covering alone for a quarter."),
                ("Grace Lin", "A quarter and a half. Volume is up about forty percent since the summer and I'm triaging rather than resolving."),
                ("Grace Lin", "The part that worries me is that I'm the only person who knows why certain things break. That's not a staffing risk, it's a knowledge risk."),
                ("Elena Vargas", "That's the more serious problem of the two."),
                ("Sofia Marchetti", "Some of this is product. Eleven of last month's tickets were the pipeline issue we're already fixing."),
                ("Grace Lin", "True, but even at half the volume I can't be the only one who can answer."),
                ("Elena Vargas", "Then two things: a support hire in Q2, and a rotation so engineering takes support duty one week in six starting in January."),
                ("Tom Whitfield", "The team won't love it. It's still right."),
                ("Grace Lin", "The rotation matters more than the hire, honestly."),
            ]),
            (0.76, [
                ("Omar Faruqi", "Marketing — if we're changing the unit of sale, the site has to change with it. Right now every page says per user."),
                ("Elena Vargas", "How long?"),
                ("Omar Faruqi", "Three weeks once pricing is settled. I can't start before that or I'll build it twice."),
                ("Elena Vargas", "Then you're gated on Hannah and Jordan's model. That's fine, it's next week."),
                ("Omar Faruqi", "Then three weeks from next week."),
            ]),
            (0.88, [
                ("Elena Vargas", "Let me read the four decisions back. Enterprise tier priced by department, model first, commit next week."),
                ("Elena Vargas", "Infrastructure hire in Q1, second engineer in Q2, accelerated if two enterprise deals sign."),
                ("Elena Vargas", "Support hire in Q2 plus an engineering rotation one week in six from January."),
                ("Elena Vargas", "And site messaging follows pricing, three weeks after it's settled. Anyone disagree with any of that?"),
                ("Tom Whitfield", "No."),
                ("Hannah Cole", "No, and I'll have the runway impact of all four in writing tomorrow."),
                ("Elena Vargas", "Good. That's the quarter."),
            ]),
        ],
        "summary": {
            "template": "general",
            "text": (
                "Four decisions committed against a runway constraint: the board expects eighteen "
                "months maintained at the end of Q1, so spend cannot outpace growth. Jordan Blake "
                "reported that security review is no longer the enterprise blocker — pricing "
                "structure is, with all three late-stage deals wanting to buy per department rather "
                "than per company. The enterprise tier will therefore be designed as a different "
                "unit of sale rather than a discount, with Hannah Cole and Jordan modelling it "
                "before the pricing page is written. Hiring was reshaped from two generalists to "
                "infrastructure-first, one in Q1 and one in Q2, with an explicit written trigger — "
                "two signed enterprise deals — for acceleration. Grace Lin reframed support from a "
                "staffing risk to a knowledge risk, being the only person who understands certain "
                "failures; this produced both a Q2 hire and an engineering support rotation."
            ),
            "topics": [
                "Runway and board expectations",
                "Enterprise pricing as a unit-of-sale problem",
                "Hiring shape and sequencing",
                "Support coverage and knowledge concentration",
                "Website messaging dependencies",
            ],
            "decisions": [
                "Enterprise tier is priced per department, not as a per-seat discount",
                "Hannah and Jordan model enterprise pricing before the pricing page is written",
                "Infrastructure hire in Q1, second engineer in Q2",
                "Accelerate the second hire only when two enterprise deals are signed",
                "Support hire in Q2, plus engineering support rotation one week in six from January",
                "Site messaging follows settled pricing by three weeks",
            ],
        },
        "action_items": [
            ("Hannah Cole", "Model department-based enterprise pricing", "Sixty seats at enterprise versus two hundred at standard. Needed before the pricing page.", 6, False),
            ("Jordan Blake", "Define the enterprise tier packaging", "Unit of sale is the department. Pair with Hannah's model for next week's exec sync.", 6, False),
            ("Hannah Cole", "Put runway impact of all four decisions in writing", "Committed same-week during the call.", 1, True),
            ("Tom Whitfield", "Open the infrastructure engineer role", "Q1 hire, infrastructure before generalist.", 8, False),
            ("Hannah Cole", "Track the two-signed-deals acceleration trigger", "Sofia's point: written down or it quietly never happens.", 10, False),
            ("Grace Lin", "Draft the engineering support rotation", "One week in six starting January. The rotation matters more than the hire.", 14, False),
            ("Omar Faruqi", "Rewrite site messaging for department pricing", "Three weeks, gated on pricing being settled.", 26, False),
            ("Sofia Marchetti", "Fold the support-driven product fixes into Q1 scope", "Eleven of last month's tickets were the pipeline issue already scheduled.", 9, False),
        ],
        "highlights": [
            ("Pricing, not security, is the enterprise blocker", "Jordan's pattern across all three late-stage deals — the insight that reshaped the tier.", 8, 12),
            ("A knowledge risk, not a staffing risk", "Grace reframes support coverage. This is what produced the rotation decision.", 27, 29),
            ("The four decisions, read back", "Elena restating all four commitments at the close — the cleanest summary of the quarter.", 40, 43),
        ],
    },
    # -- Not yet happened -----------------------------------------------------
    {
        "key": "upcoming-acme-technical-review",
        "title": "Acme — Technical Deep Dive",
        "platform": "zoom",
        "language": "en",
        "status": "scheduled",
        # Negative: this many days in the future.
        "days_ago": -2,
        "duration_minutes": 60,
        "people": [
            ("Daniel Okafor", "daniel@fathom.test", "host"),
            ("Priya Raman", "priya@fathom.test", "cohost"),
            ("Lena Vogt", "lena.vogt@acme.example", "attendee"),
            ("Marcus Feld", "marcus.feld@acme.example", "attendee"),
        ],
    },
    {
        "key": "upcoming-northwind-procurement",
        "title": "Northwind — Procurement Review",
        "platform": "microsoft_teams",
        "language": "en",
        "status": "scheduled",
        "days_ago": -5,
        "duration_minutes": 30,
        "people": [
            ("Jordan Blake", "jordan@fathom.test", "host"),
            ("Priya Raman", "priya@fathom.test", "cohost"),
            ("Karen Stoll", "karen.stoll@northwind.example", "attendee"),
        ],
    },
    {
        "key": "upcoming-q1-kickoff",
        "title": "Q1 Kickoff — All Hands",
        "platform": "google_meet",
        "language": "en",
        "status": "scheduled",
        "days_ago": -9,
        "duration_minutes": 45,
        "people": [
            ("Elena Vargas", "elena@fathom.test", "host"),
            ("Sofia Marchetti", "sofia@fathom.test", "attendee"),
            ("Tom Whitfield", "tom@fathom.test", "attendee"),
            ("Jordan Blake", "jordan@fathom.test", "attendee"),
            ("Grace Lin", "grace@fathom.test", "attendee"),
            ("Omar Faruqi", "omar@fathom.test", "attendee"),
        ],
    },
]
