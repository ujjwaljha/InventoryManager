from datetime import date, datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    SHOP_TZ = ZoneInfo("Asia/Jakarta")
except Exception:
    # Windows frozen builds need the tzdata package; WIB has no DST.
    SHOP_TZ = timezone(timedelta(hours=7), name="WIB")


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def today_shop() -> str:
    return datetime.now(SHOP_TZ).date().isoformat()


def parse_iso(iso: str) -> datetime:
    raw = iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def shop_date(iso: str) -> str:
    return parse_iso(iso).astimezone(SHOP_TZ).date().isoformat()


def shop_day_bounds(day: str | None = None) -> tuple[str, str]:
    """UTC ISO bounds for a calendar day in Asia/Jakarta (inclusive start, exclusive end)."""
    d = date.fromisoformat(day) if day else datetime.now(SHOP_TZ).date()
    start_local = datetime.combine(d, time.min, tzinfo=SHOP_TZ)
    end_local = start_local + timedelta(days=1)
    start = start_local.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    end = end_local.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return start, end


def add_shop_days(day: str, days: int) -> str:
    return (date.fromisoformat(day[:10]) + timedelta(days=int(days))).isoformat()


def overdue_days(due_date: str | None, issued_at: str | None = None, today: str | None = None) -> int:
    if due_date:
        start = date.fromisoformat(due_date[:10])
    elif issued_at:
        start = date.fromisoformat(shop_date(issued_at))
    else:
        return 0
    end = date.fromisoformat(today or today_shop())
    return max(0, (end - start).days)


def age_days(issued_at: str | None, today: str | None = None) -> int:
    if not issued_at:
        return 0
    start = date.fromisoformat(shop_date(issued_at))
    end = date.fromisoformat(today or today_shop())
    return max(0, (end - start).days)


def aging_bucket(days: int) -> str:
    if days <= 30:
        return "d0_30"
    if days <= 60:
        return "d31_60"
    if days <= 90:
        return "d61_90"
    return "d90_plus"


def range_bounds(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    start_day = date_from or today_shop()
    end_day = date_to or start_day
    start, _ = shop_day_bounds(start_day)
    _, end = shop_day_bounds(end_day)
    return start, end
