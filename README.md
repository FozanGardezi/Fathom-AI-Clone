# Fathom

A meeting intelligence application: records are ingested as transcripts, summarised into
topics and decisions, and turned into follow-ups and clipped highlights that a team can
work from after the call.

Django REST API + React frontend, with a seeded demo dataset you can run against locally.

---

## Contents

- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Data model](#data-model)
- [API](#api)
- [Frontend](#frontend)
- [Demo data](#demo-data)
- [Configuration](#configuration)
- [Tests](#tests)
- [Deployment](#deployment)
- [Known gaps](#known-gaps)

---

## Quick start

### With Docker (everything at once)

```bash
cp .env.example .env
docker compose up --build
```

Frontend on <http://localhost:3000>, API on <http://localhost:8000>, Postgres on `5433`,
Redis on `6380`.

### Without Docker

You need Postgres running and reachable. The default expects it on `localhost:5433`.

```bash
# API
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo_data
.venv/bin/python manage.py runserver 8000
```

```bash
# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `localhost:8000`, so the frontend needs no API URL configured in
development.

### Signing in

`seed_demo_data` creates sixteen demo accounts. On a local database they all share the
password `DemoPass!2026`:

```
priya@fathom.test     sales
sofia@fathom.test     product
tom@fathom.test       engineering
elena@fathom.test     leadership
```

> **Meetings are scoped to the people in them.** The API only returns meetings you own or
> attended, so an account you register yourself will see an empty workspace even with the
> demo data loaded. Either sign in as one of the accounts above, or attach your own:
>
> ```bash
> python manage.py seed_demo_data --share-with you@example.com
> ```

---

## Architecture

```
┌──────────────┐     /api/*      ┌──────────────┐
│   React SPA  │ ──────────────► │  Django REST │
│  Vite + TS   │  JWT bearer     │   Framework  │
└──────────────┘                 └──────┬───────┘
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                        ┌─────▼─────┐      ┌──────▼─────┐
                        │ Postgres  │      │   Redis    │
                        └───────────┘      │  + Celery  │
                                           └────────────┘
```

| | |
|---|---|
| **API** | Django 5.1, Django REST Framework, SimpleJWT, drf-spectacular, django-filter |
| **Database** | PostgreSQL (psycopg 3) |
| **Async** | Celery + Redis (wired up; no tasks defined yet) |
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind v4, React Router 7, TanStack Query, axios |
| **Serving** | Gunicorn + WhiteNoise; nginx for the built frontend |

### Layout

```
backend/
  config/            settings, urls, database config, celery, wsgi/asgi
  apps/accounts/     custom User (email login), JWT auth, /me
  apps/meetings/     the domain: models, serializers, views, demo dataset
    management/commands/seed_demo_data.py
    demo_data.py     the demo dataset itself, kept apart from the command
    tests/
frontend/src/
  components/
    layout/          app shell, sidebar, top bar
    ui/              buttons, cards, tabs, skeletons, error and empty states
    meetings/        dashboard cards, stats
    meetings/detail/ player, transcript, highlights, action items
    calendar/        month grid, connect-calendar
  hooks/             data hooks (one per concern)
  lib/api/           the only place axios is imported
  pages/             one per route
```

---

## Data model

A `Meeting` is the root. Everything else hangs off it and dies with it.

```
Meeting ─┬─ Participant ──── (optional) User
         ├─ TranscriptSegment ── speaker → Participant
         ├─ MeetingSummary   (summary text, topics[], decisions[])
         ├─ ActionItem       owner → Participant
         └─ Highlight        created_by → User
```

Decisions worth knowing about:

- **UUID primary keys everywhere except `TranscriptSegment`,** which keeps a sequential
  id. Meeting ids end up in URLs and share links; transcript segments run to millions of
  rows, where a random 16-byte key bloats every index and scatters inserts.
- **Transcripts are their own table,** not a blob on `Meeting`. The product seeks to a
  timestamp, attributes a line to a speaker, and searches across segments.
- **Highlights store boundaries, not text.** Correcting a transcript fixes every highlight
  over it at once.
- **Integrity is enforced in the database,** not only in application code. A meeting cannot
  end before it starts; an action item's `completed` flag and `completed_at` timestamp
  cannot disagree; a summary cannot be `ready` without a generation time; one summary per
  template per meeting.
- **A participant from one meeting cannot be attached to another meeting's rows.** Django
  has no composite foreign key, so this is raw SQL in `0004_participant_same_meeting_fks`:
  `(speaker_id, meeting_id)` must exist as an `(id, meeting_id)` pair on participants. It
  is `DEFERRABLE INITIALLY DEFERRED`, so violations surface at commit — worth knowing when
  reading a stack trace.

---

## API

All endpoints require a bearer token except register, login and health. Everything is
scoped to meetings you own or attended.

### Auth

| Method | Path | |
|---|---|---|
| `POST` | `/api/auth/register/` | create an account |
| `POST` | `/api/auth/login/` | returns `access` + `refresh` |
| `POST` | `/api/auth/refresh/` | rotate the access token |
| `GET` | `/api/me/` | the signed-in user |
| `GET` | `/api/health/` | API and database status |

### Meetings

| Method | Path | |
|---|---|---|
| `GET` | `/api/v1/meetings/` | paginated list, 25/page |
| `POST` | `/api/v1/meetings/` | owner comes from the token |
| `GET` | `/api/v1/meetings/stats/` | workspace totals, aggregated in SQL |
| `GET` | `/api/v1/meetings/{id}/` | full detail: participants, summary, topics, decisions, action items, highlights |
| `PATCH` | `/api/v1/meetings/{id}/` | responds with the full detail shape |
| `GET` | `/api/v1/meetings/{id}/transcript/` | segments in chronological order |

List supports `?status=`, `?platform=`, `?type=` (alias for platform), `?occurs_after=`,
`?occurs_before=`, `?ordering=` (`started_at`, `scheduled_start`, `occurs_at`,
`created_at`, `updated_at`, `title`; prefix `-` to reverse) and `?page=`.

`occurs_at` is `COALESCE(started_at, scheduled_start)` — it lets one date filter cover
both meetings that happened and meetings only scheduled, which is what the calendar needs.

### Action items and highlights

| Method | Path | |
|---|---|---|
| `GET` `POST` | `/api/v1/meetings/{id}/action-items/` | per meeting |
| `GET` `PATCH` | `/api/v1/action-items/{id}/` | complete, reopen, retitle, reassign, re-date |
| `GET` | `/api/v1/action-items/` | across the workspace, `?completed=` |
| `GET` `POST` | `/api/v1/meetings/{id}/highlights/` | per meeting |
| `GET` `PATCH` | `/api/v1/highlights/{id}/` | |
| `GET` | `/api/v1/highlights/` | across the workspace |

`completed_at` is not client-writable — it is derived from `completed`, because the
database rejects the two disagreeing.

### Schema

Browsable at `/api/docs/`, raw OpenAPI at `/api/schema/`.

### Query behaviour

Endpoints are flat in query count regardless of row count, and there are tests that assert
it by multiplying the data and comparing:

| | |
|---|---|
| meetings list | 2 queries |
| meeting detail | 5 queries |
| transcript, action items, highlights | flat |

---

## Frontend

| Route | |
|---|---|
| `/` | overview |
| `/meetings` | dashboard: greeting, stats, upcoming, recent |
| `/meetings/:id` | the meeting workspace |
| `/calendar` | month grid + upcoming + connect-calendar |
| `/highlights` | every clip across the workspace |
| `/action-items` | every follow-up, filterable |
| `/search` `/settings` | placeholders |

**The meeting workspace** is the centre of the app: a player, and tabs for Summary,
Transcript, Highlights and Action Items (deep-linkable via `?tab=`).

The player has no media behind it — the backend stores transcripts and timings, not
recordings. It is a clock: a `requestAnimationFrame` loop advancing a millisecond counter
at the current rate, driving a seek bar, playback speed, and a waveform whose bars are
computed from real transcript segment density and confidence. Everything downstream reads
that counter exactly as it would an `<audio>` element, so swapping in real media means
replacing one provider, not its consumers.

The transcript highlights the active line, follows playback while playing, and stops
following the moment you scroll — offering a "Jump to current" pill rather than yanking
the page. Clicking any line seeks. Marking lines opens an in-place bar to save them as a
highlight.

Two conventions worth keeping:

- **axios is imported in exactly one place**, `lib/api/`. Components use hooks.
- **Every failure becomes an `ApiError`** with a `kind` and a message fit to render.
  Retry policy is decided once, in `lib/queryClient.ts`: network, timeout and 5xx retry;
  404s and validation errors surface immediately.

---

## Demo data

```bash
python manage.py seed_demo_data
```

Nine meetings — six that happened, three scheduled — with **208 transcript segments** of
hand-written dialogue across 2,842 words, no line repeated. Summaries carry real topics
and decisions; action items have owners and due dates; highlights point at real transcript
spans.

| Meeting | People | Length | Items | Highlights |
|---|---|---|---|---|
| Customer Discovery — Acme | 4 | 45m | 5 | 2 |
| Product Roadmap Sync | 5 | 58m | 5 | 2 |
| Enterprise Sales Call — Northwind | 4 | 38m | 5 | 2 |
| Engineering Standup | 6 | 23m | 5 | 1 |
| One-on-One — Sofia & Meera | 2 | 30m | 3 | 2 |
| Company Planning — Q1 | 8 | 60m | 8 | 3 |
| *3 upcoming* | 3–6 | — | — | — |

Timings are computed, not typed: each turn's duration comes from its word count at ~2.6
words/second, with pauses between turns, grouped into topical sections anchored across the
meeting. A per-meeting RNG seed makes reseeding produce byte-identical timings. Talk time
is summed from the transcript, and highlight bounds are taken from real segment offsets.

**Idempotent.** Every demo meeting carries an `external_id` prefixed `demo-`, which is both
the key and the safety boundary. A run deletes exactly those and rebuilds them; nothing
else is touched. Running it three times leaves the same counts.

```bash
python manage.py seed_demo_data --share-with you@example.com   # make it visible to your account
python manage.py seed_demo_data --password 'Chosen!Password'   # required for a remote database
python manage.py seed_demo_data --clear                        # remove it
```

> Re-running **replaces** the meetings, which removes previously shared accounts from them.
> Pass `--share-with` again afterwards.

---

## Configuration

Copy `.env.example` to `.env`. Nothing needs setting to run locally.

| | |
|---|---|
| `SECRET_KEY` `JWT_SECRET` | change both before deploying |
| `DEBUG` | default off |
| `ALLOWED_HOSTS` `CORS_ALLOWED_ORIGINS` | comma-separated |
| `DATABASE_URL` | wins over the `POSTGRES_*` group |
| `REDIS_URL` | Celery broker and result backend |
| `VITE_API_URL` | defaults to `/api`; inlined at build time |
| `DEMO_PASSWORD` | demo account password; required when seeding a remote database |
| `GOOGLE_CLIENT_ID` `GOOGLE_CLIENT_SECRET` | enable Google Calendar sync; blank means "not set up" |
| `GOOGLE_REDIRECT_URI` `FRONTEND_URL` | OAuth callback and where to return the browser |

### Database

`config/database.py` assembles the connection and derives the rest from where the database
actually is, so neither environment needs tuning:

| | Local / compose | Remote |
|---|---|---|
| `sslmode` | `prefer` | `require` |
| `CONN_MAX_AGE` | `0` | `60` |
| `CONN_HEALTH_CHECKS` | off | on |

`CONN_HEALTH_CHECKS` is the one that bites: with persistent connections, a database restart
or a pooler dropping idle connections otherwise leaves Django handing a dead socket to the
next request.

Overridable with `DB_SSLMODE`, `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`, `DB_CONNECT_TIMEOUT`,
`DB_APP_NAME`, `DB_ENGINE`, `POSTGRES_HOST`.

**On serverless, set `CONN_MAX_AGE=0`** — each invocation is its own process, so a
"persistent" connection is one that never gets closed, and the connection limit goes first.

If `DEBUG` is off and nothing is configured, startup fails by name rather than quietly
pointing production at localhost.

---

## Tests

```bash
cd backend && .venv/bin/pytest          # whole suite
.venv/bin/pytest apps/meetings/tests/test_api.py -q
```

```bash
cd frontend && npx tsc -b && npm run lint && npm run build
```

Roughly 230 backend tests across four files: models and database constraints, the API,
the nested and workspace endpoints, and the seed command. They cover the constraint
behaviour directly (a completed item must carry a timestamp; a participant cannot cross
meetings), query counts, pagination, filtering, and idempotency.

Note: the cross-meeting foreign keys are deferred, so a test that expects one to fire must
force the check — see `check_deferred_constraints()` in `test_models.py`.

---

## Deployment

`vercel.json` routes `/api/*` to the Django service and everything else to the built
frontend. `compose.yaml` runs the same stack locally, plus a Celery worker.

Deploying needs:

1. `SECRET_KEY` and `JWT_SECRET` set to real values
2. `DATABASE_URL` pointing at the managed database
3. `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` covering the deployed domains
4. `python manage.py migrate`
5. `CONN_MAX_AGE=0` if the backend runs serverless

---

## Known gaps

Honest list of what is not finished.

- **Search is not implemented.** The page is a placeholder, and `searchMeetings()` in the
  API client filters the page it fetched client-side — it cannot see matches beyond the
  first page. It is a stopgap with the final signature; switching it over is deleting one
  marked block once the backend supports `?search=`.
- **Synced calendar events have no transcript.** A Google Calendar event carries a
  title, a time, a link and an invite list — never a recording. Past events therefore
  import as meetings with participants and timings but no transcript, summary, action
  items or highlights, and the UI says so. Record one with the live feature to get those.
- **Share copies the URL.** There is no sharing endpoint.
- **No sign-out in the UI.** `useSession().signOut` exists; the avatar menu has no dropdown.
- **No recordings.** No audio or video is stored; playback is simulated, and the UI says so.
- **Celery has no tasks.** The broker, worker and config are wired; summarisation would go
  there.
- **An expired session shows errors rather than redirecting.** `RequireAuth` checks that a
  token exists, not that it is valid.
- **Upcoming meetings have no duration.** The model stores `scheduled_start` but no
  scheduled end, so the calendar shows "in 2 days" instead.
