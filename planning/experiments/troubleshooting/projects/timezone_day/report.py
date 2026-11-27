from datetime import datetime, timezone


def day_label(ts):
    """UTC calendar day (YYYY-MM-DD) of a unix timestamp."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def daily_counts(timestamps):
    out = {}
    for ts in timestamps:
        d = day_label(ts)
        out[d] = out.get(d, 0) + 1
    return out
