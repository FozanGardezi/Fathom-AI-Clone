"""Database connection configuration.

Split out of settings.py because the connection is the one piece of config
that differs most between a laptop and production, and the differences are
worth explaining rather than burying in a one-line `env.db()` call.

Two ways to point this at a database, checked in order:

1.  ``DATABASE_URL`` - a single connection string. This is what managed hosts
    hand you (Neon, Supabase, Railway, RDS, Heroku), so it is what production
    normally uses.
2.  ``POSTGRES_DB`` / ``POSTGRES_USER`` / ``POSTGRES_PASSWORD`` /
    ``POSTGRES_HOST`` / ``POSTGRES_PORT`` - the discrete parts, which is how
    docker-compose already describes the service.

Everything else - SSL, connection reuse, timeouts - is derived from where the
database actually is, so the defaults are right for both without anyone having
to remember to set them.
"""

from django.core.exceptions import ImproperlyConfigured

#: Hosts that mean "this machine or this compose network". Used only to pick
#: defaults; anything here is assumed to be reachable without TLS.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db", "postgres", "database"})

DEFAULT_ENGINE = "django.db.backends.postgresql"
DEFAULT_NAME = "fathom"
DEFAULT_PORT = "5433"


def is_local_host(host: str) -> bool:
    """Whether `host` looks like a database on this machine or compose network."""
    return (host or "").strip().lower() in LOCAL_HOSTS


def _from_parts(env) -> dict:
    """Build a connection from the discrete POSTGRES_* variables."""
    return {
        "ENGINE": env("DB_ENGINE", default=DEFAULT_ENGINE),
        "NAME": env("POSTGRES_DB", default=DEFAULT_NAME),
        "USER": env("POSTGRES_USER", default=DEFAULT_NAME),
        "PASSWORD": env("POSTGRES_PASSWORD", default=DEFAULT_NAME),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": str(env("POSTGRES_PORT", default=DEFAULT_PORT)),
    }


def _check_configured(env, config: dict, *, debug: bool) -> None:
    """Refuse to let production quietly talk to localhost.

    Pointing a deployed service at a database that does not exist fails at the
    first request with a connection error that looks like a network problem.
    Failing at startup, by name, is far easier to act on. An explicitly
    configured local host is left alone - running the app and the database on
    one box is a legitimate choice, just not an accidental one.
    """
    if debug:
        return
    explicitly_set = env("DATABASE_URL", default=None) or env("POSTGRES_HOST", default=None)
    if explicitly_set:
        return
    raise ImproperlyConfigured(
        "No database configured and DEBUG is off. Set DATABASE_URL, or the "
        "POSTGRES_HOST/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD group. "
        "Refusing to fall back to %s, which is almost certainly not the "
        "database you meant." % config.get("HOST")
    )


def build_databases(env, *, debug: bool = False) -> dict:
    """Return the ``DATABASES`` setting.

    `env` is the ``environ.Env`` instance settings.py already built, so .env
    has been read and the same instance answers every lookup.
    """
    url = env("DATABASE_URL", default=None)
    config = env.db_url_config(url) if url else _from_parts(env)

    host = config.get("HOST") or ""
    local = is_local_host(host)

    _check_configured(env, config, debug=debug)

    # Reusing connections saves the TCP and TLS handshake on every request,
    # which is most of the cost of a fast query.
    #
    # Keyed on DEBUG rather than on where the database is: a compose stack
    # talks to `db` over a local network and still benefits from reuse, while
    # a dev server holding connections open is a nuisance - it blocks dropping
    # and recreating the database.
    #
    # Set this to 0 on serverless platforms: each invocation is its own
    # process, so a "persistent" connection is just one that never gets closed.
    conn_max_age = env.int("CONN_MAX_AGE", default=0 if debug else 60)
    config["CONN_MAX_AGE"] = conn_max_age

    # Reused connections go stale - the server restarts, or a pooler drops
    # them - and Django hands the dead one to the next request. This makes it
    # check first and reconnect, which is only worth paying for when
    # connections are actually being reused.
    config["CONN_HEALTH_CHECKS"] = env.bool(
        "CONN_HEALTH_CHECKS", default=conn_max_age > 0
    )

    options = dict(config.get("OPTIONS") or {})

    # A managed database is reached across a network, so TLS is required
    # unless the URL already said otherwise. Locally `prefer` keeps it working
    # against a plain container without disabling TLS for anyone whose local
    # server happens to offer it.
    options.setdefault("sslmode", env("DB_SSLMODE", default="prefer" if local else "require"))

    # Without this a network blackhole hangs the worker until the platform
    # kills it, turning one slow database into an outage.
    options.setdefault("connect_timeout", env.int("DB_CONNECT_TIMEOUT", default=10))

    # Names the connection in pg_stat_activity, so "what is holding this lock"
    # has an answer when the web app, Celery and a shell are all connected.
    options.setdefault("application_name", env("DB_APP_NAME", default="fathom-backend"))

    config["OPTIONS"] = options
    return {"default": config}
