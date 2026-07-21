"""Pure canonical public watermark rendering shared across adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from investo.models.segments import (
    SEGMENT_MARKET_TZ,
    SEGMENT_MARKET_TZ_LABEL,
    MarketSegment,
)

_WATERMARK_PREFIX = "**기준 시각**:"


def render_timestamp_watermark(target_date: date, segment: MarketSegment) -> str:
    """Render the canonical half-open source-window watermark."""

    market_tz = SEGMENT_MARKET_TZ[segment]
    tz_label = SEGMENT_MARKET_TZ_LABEL[segment]
    start_local = datetime.combine(target_date, time.min, tzinfo=market_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    end_str = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    return (
        f"**기준 시각**: {target_date.isoformat()} {tz_label} · "
        f"수집창 {start_str} ~ {end_str} (종료 미포함)"
    )


def replace_timestamp_watermark_line(
    text: str,
    *,
    target_date: date,
    segment: MarketSegment,
) -> str:
    """Replace one existing watermark line without touching sibling copy."""

    canonical = render_timestamp_watermark(target_date, segment)
    replacements = 0
    output: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if line.startswith(_WATERMARK_PREFIX):
            newline = raw_line[len(line) :]
            output.append(canonical + newline)
            replacements += 1
        else:
            output.append(raw_line)
    if replacements != 1:
        return text
    return "".join(output)


__all__ = ["render_timestamp_watermark", "replace_timestamp_watermark_line"]
