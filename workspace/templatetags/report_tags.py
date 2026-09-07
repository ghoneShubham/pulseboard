"""
Custom template tags. Teen types:
  @register.filter        -> value transform  ({{ x|minutes_as_hours }})
  @register.simple_tag    -> compute + return ({% utilisation a b %})
  @register.inclusion_tag -> chhota sub-template render
"""
from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def minutes_as_hours(value) -> str:
    try:
        minutes = int(value or 0)
    except (TypeError, ValueError):
        return "0h"
    return f"{minutes // 60}h {minutes % 60:02d}m"


@register.simple_tag
def health_badge(health: str):
    colors = {"healthy": "#16a34a", "at_risk": "#d97706", "over_budget": "#dc2626"}
    return format_html(
        '<span style="color:{};font-weight:600">{}</span>',
        colors.get(health, "#6b7280"), health.replace("_", " "),
    )


@register.inclusion_tag("workspace/_summary_card.html")
def summary_card(summary: dict):
    total = summary.get("total") or 0
    done = summary.get("done") or 0
    return {"summary": summary, "completion": round(done / total * 100, 1) if total else 0}
