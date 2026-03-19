"""Shared utilities for scrapers."""
import re
from datetime import datetime, timedelta


def resolve_date(date_str: str) -> str:
    """Convert relative dates (Today, Yesterday) to YYYY-MM-DD format."""
    today = datetime.now()
    lower = date_str.lower().strip()

    if lower == "today":
        return today.strftime("%Y-%m-%d")
    if lower == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Try to parse dates like "Sunday, March 15th" or "Mar 15th"
    cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    cleaned = re.sub(r'^\w+day,?\s*', '', cleaned)

    for fmt in ("%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(cleaned.strip(), fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str
