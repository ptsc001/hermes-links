"""
CalDAV Processor – creates iCloud Calendar events and Reminders from Brain Dump items.

On save, this module automatically:
- Meeting items → VEVENT in iCloud "Hermes" calendar (1h slot)
- Todo items → VTODO in iCloud Erinnerungen (with due date)
- Private items with dates → VEVENT in iCloud "Privat" calendar
- Business/Idea items with dates → VEVENT in "Hermes"
"""

import os, sys, json, re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Optional

import caldav
from icalendar import Calendar, Event, Todo

# ── Config ──────────────────────────────────────────────────────────

TZ = ZoneInfo("Europe/Berlin")
ICAL_USERNAME = "p.schuppan@icloud.com"
ICAL_PASSWORD = "juyg-hute-qpwg-fjuz"
CALDAV_URL = "https://caldav.icloud.com/"

# Category → target calendar mapping
CALENDAR_MAP = {
    "meeting": "Hermes",
    "todo": "Erinnerungen ⚠️",
    "private": "Privat",
    "business": "Hermes",
    "idea": "Hermes",
}

# ── Client (lazy singleton) ─────────────────────────────────────────

_client = None

def get_client():
    global _client
    if _client is None:
        _client = caldav.DAVClient(
            url=CALDAV_URL,
            username=ICAL_USERNAME,
            password=ICAL_PASSWORD,
        )
    return _client


# ── Calendar lookup ─────────────────────────────────────────────────

_calendar_cache = {}

def _get_calendar(name: str):
    """Find a calendar by display name (cached)."""
    if name in _calendar_cache:
        return _calendar_cache[name]

    client = get_client()
    principal = client.principal()
    for cal in principal.calendars():
        try:
            cal_name = cal.get_display_name()
        except Exception:
            continue
        if cal_name == name:
            _calendar_cache[name] = cal
            return cal
    return None


# ── Processing ──────────────────────────────────────────────────────

def parse_item_datetime(extracted_date: str, text: str) -> Optional[datetime]:
    """
    Try to extract a proper datetime from the item.
    Returns a timezone-aware datetime in Europe/Berlin.
    """
    now = datetime.now(TZ)

    if extracted_date:
        try:
            dt = datetime.fromisoformat(extracted_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(TZ)
        except (ValueError, TypeError):
            pass

    # Fallback: parse text
    t = text.lower()
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if "übermorgen" in t:
        base_date = base_date + timedelta(days=2)
    elif "morgen" in t:
        base_date = base_date + timedelta(days=1)

    time_match = re.search(r'(?:um\s+)?(\d{1,2})[.:]?(\d{2})\s*(?:uhr)?', t)
    if time_match:
        return base_date.replace(hour=int(time_match.group(1)), minute=int(time_match.group(2)))

    hour_match = re.search(r'(?:um\s+)?(\d{1,2})\s*uhr', t)
    if hour_match:
        return base_date.replace(hour=int(hour_match.group(1)), minute=0)

    return base_date if ("morgen" in t or "heute" in t or "übermorgen" in t) else None


def get_end_time(start: Optional[datetime], category: str) -> Optional[datetime]:
    if start is None:
        return None
    if category == "meeting":
        return start + timedelta(hours=1)
    return start + timedelta(hours=1)


def get_summary(text: str) -> str:
    """Create a clean summary."""
    cleaned = re.sub(
        r'^(?:morgen|heute|übermorgen)\s+(?:um\s+\d{1,2}[.:]?\d{0,2}\s*(?:uhr)?\s+)?',
        '', text, flags=re.IGNORECASE
    ).strip().capitalize()
    if len(cleaned) > 120:
        cleaned = cleaned[:117] + "..."
    return cleaned or "Brain Dump"


# ── Main processing function ────────────────────────────────────────

def process_item(item: dict) -> dict:
    """
    Process a single Brain Dump item through CalDAV.
    Returns dict with status and details.
    """
    text = item.get("text", "")
    category = item.get("category", "business")
    item_id = item.get("id")
    result = {"item_id": item_id, "category": category, "action": None, "success": False}

    # Only process meetings, todos, and items with dates
    has_date = item.get("has_date")
    if category not in ("meeting", "todo") and not has_date:
        result["status"] = "skipped"
        result["reason"] = "no date and not meeting/todo"
        result["success"] = True
        return result

    start = parse_item_datetime(item.get("extracted_date", ""), text)
    end = get_end_time(start, category)
    summary = get_summary(text)

    cal_name = CALENDAR_MAP.get(category, "Hermes")
    cal = _get_calendar(cal_name)
    if not cal:
        result["error"] = f"Calendar '{cal_name}' not found"
        return result

    try:
        if category == "todo":
            ical = Calendar()
            ical.add("prodid", "-//Hermes Brain//Todo//DE")
            ical.add("version", "2.0")
            todo = Todo()
            todo.add("uid", str(uuid4()))
            todo.add("summary", summary)
            todo.add("description", text)
            todo.add("dtstamp", datetime.now(timezone.utc))
            if start:
                todo.add("dtstart", start.astimezone(timezone.utc))
                todo.add("due", (start + timedelta(hours=24)).astimezone(timezone.utc))
            ical.add_component(todo)
            cal.save_event(ical.to_ical())
            result["action"] = f"Todo '{summary}' in {cal_name}"
        else:
            ical = Calendar()
            ical.add("prodid", "-//Hermes Brain//Event//DE")
            ical.add("version", "2.0")
            event = Event()
            event.add("uid", str(uuid4()))
            event.add("summary", summary)
            event.add("description", text)
            event.add("dtstamp", datetime.now(timezone.utc))
            if start:
                event.add("dtstart", start.astimezone(timezone.utc))
                event.add("dtend", (end or start + timedelta(hours=1)).astimezone(timezone.utc))
            ical.add_component(event)
            cal.save_event(ical.to_ical())
            result["action"] = f"Event '{summary}' in {cal_name}"

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        if "401" in str(e):
            global _client
            _client = None
            _calendar_cache.clear()

    return result


def batch_process(items: list) -> list:
    """Process a list of unprocessed items."""
    return [process_item(item) for item in items]


if __name__ == "__main__":
    test = {"id": 999, "text": "Test CalDAV Processor", "category": "meeting",
            "has_date": 1, "extracted_date": None, "is_processed": False}
    print(json.dumps(process_item(test), indent=2, ensure_ascii=False))
