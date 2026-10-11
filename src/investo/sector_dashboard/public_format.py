"""Shared human-readable formatting for public price observations."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from investo.models.sector import MetricValue


def format_public_metric(metric: MetricValue, unit: str) -> str:
    if metric.value is None:
        return "—"
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        displayed = (metric.value * Decimal(100)).quantize(Decimal("0.01"))
    if displayed == 0:
        displayed = Decimal("0.00")
    sign = "+" if displayed > 0 else ""
    return f"{sign}{displayed:.2f} {unit}"
