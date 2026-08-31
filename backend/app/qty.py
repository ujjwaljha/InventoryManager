from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

SCALE = 1000
_QUANTUM = Decimal("0.001")


def to_store(q) -> int:
    """Human units (0.5 m³, 2 sak) → integer thousandths."""
    if q is None:
        return 0
    d = Decimal(str(q)).quantize(_QUANTUM, rounding=ROUND_HALF_UP)
    return int(d * SCALE)


def from_store(n: int | None) -> float:
    """Integer thousandths → JSON-friendly human units."""
    if not n:
        return 0
    d = Decimal(int(n)) / SCALE
    if d == d.to_integral():
        return int(d)
    return float(d)


def money_qty(qty_millis: int, unit_cents: int) -> int:
    """qty in thousandths × price per 1 unit → sen."""
    return int(qty_millis) * int(unit_cents) // SCALE
