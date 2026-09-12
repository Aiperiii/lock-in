from datetime import datetime, timezone


def iso8601(dt: datetime | None) -> str | None:
    """Format a datetime as UTC ISO 8601 with a trailing Z.

    Every datetime in this app is meant to be UTC (see CLAUDE.md), but SQLite
    round-trips them as naive values regardless of how they were stored, so a
    naive value here is treated as already-UTC rather than converted.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def utcnow_naive() -> datetime:
    """Current UTC time as a naive datetime, matching how datetimes come back
    out of SQLite, so it can be compared directly against DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
