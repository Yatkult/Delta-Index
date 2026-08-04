#!/usr/bin/env python3
"""Validate source events and build the public Delta Index JSON feeds."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


PROJECT_NAME = "Delta Index"
CITIES = {
    "shenzhen": "sz",
    "hong-kong": "hk",
    "guangzhou": "gz",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "city",
    "start",
    "end",
    "venue",
    "description",
    "source_url",
    "last_verified",
}
OPTIONAL_FIELDS = {
    "organizer",
    "registration_url",
    "image_url",
    "price",
    "languages",
    "tags",
    "cancelled",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
ID_PATTERN = re.compile(r"^(sz|hk|gz)-[a-z0-9-]+$")


class EventValidationError(ValueError):
    """Raised when an event cannot safely enter a public feed."""


def parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise EventValidationError(f"{field} must be text in ISO 8601 format")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventValidationError(f"{field} is not a valid ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EventValidationError(f"{field} must include a UTC offset, such as +08:00")
    return parsed


def require_nonempty_text(event: dict, field: str, label: str) -> None:
    if not isinstance(event.get(field), str) or not event[field].strip():
        raise EventValidationError(f"{label} must be non-empty text")


def validate_url(value: object, label: str) -> None:
    if not isinstance(value, str):
        raise EventValidationError(f"{label} must be a web address")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EventValidationError(f"{label} must begin with http:// or https://")


def validate_string_list(value: object, label: str) -> None:
    if not isinstance(value, list):
        raise EventValidationError(f"{label} must be a JSON list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise EventValidationError(f"every item in {label} must be non-empty text")
    if len(value) != len(set(value)):
        raise EventValidationError(f"{label} cannot contain duplicates")


def validate_event(event: object, position: int) -> tuple[dict, datetime, datetime]:
    location = f"event #{position + 1}"
    if not isinstance(event, dict):
        raise EventValidationError(f"{location} must be a JSON object")

    event_id = event.get("id") if isinstance(event.get("id"), str) else location
    label = f"event {event_id!r}"

    missing = sorted(REQUIRED_FIELDS - event.keys())
    if missing:
        raise EventValidationError(f"{label} is missing: {', '.join(missing)}")
    unknown = sorted(event.keys() - ALLOWED_FIELDS)
    if unknown:
        raise EventValidationError(f"{label} has unknown fields: {', '.join(unknown)}")

    for field in ("id", "title", "description", "source_url", "last_verified"):
        require_nonempty_text(event, field, f"{label}.{field}")

    if not ID_PATTERN.fullmatch(event["id"]):
        raise EventValidationError(
            f"{label}.id must be lowercase and begin with sz-, hk-, or gz-"
        )

    city = event.get("city")
    if city not in CITIES:
        raise EventValidationError(
            f"{label}.city must be shenzhen, hong-kong, or guangzhou"
        )
    expected_prefix = f"{CITIES[city]}-"
    if not event["id"].startswith(expected_prefix):
        raise EventValidationError(
            f"{label}.id must begin with {expected_prefix!r} for {city}"
        )

    start = parse_timestamp(event.get("start"), f"{label}.start")
    end = parse_timestamp(event.get("end"), f"{label}.end")
    if end < start:
        raise EventValidationError(f"{label}.end cannot be earlier than its start")

    venue = event.get("venue")
    if not isinstance(venue, dict):
        raise EventValidationError(f"{label}.venue must contain name and address")
    if set(venue) - {"name", "address"}:
        extras = ", ".join(sorted(set(venue) - {"name", "address"}))
        raise EventValidationError(f"{label}.venue has unknown fields: {extras}")
    for field in ("name", "address"):
        if not isinstance(venue.get(field), str) or not venue[field].strip():
            raise EventValidationError(f"{label}.venue.{field} must be non-empty text")

    validate_url(event["source_url"], f"{label}.source_url")
    for field in ("registration_url", "image_url"):
        if field in event:
            validate_url(event[field], f"{label}.{field}")

    try:
        date.fromisoformat(event["last_verified"])
    except ValueError as exc:
        raise EventValidationError(
            f"{label}.last_verified must use YYYY-MM-DD"
        ) from exc

    for field in ("organizer", "price"):
        if field in event:
            require_nonempty_text(event, field, f"{label}.{field}")
    for field in ("languages", "tags"):
        if field in event:
            validate_string_list(event[field], f"{label}.{field}")
    if "cancelled" in event and not isinstance(event["cancelled"], bool):
        raise EventValidationError(f"{label}.cancelled must be true or false")

    return copy.deepcopy(event), start, end


def public_event(event: dict, start: datetime, end: datetime, now: datetime) -> dict:
    if event.get("cancelled", False):
        status = "cancelled"
    elif now < start:
        status = "upcoming"
    elif now <= end:
        status = "ongoing"
    else:
        status = "ended"
    event["status"] = status
    return event


def feed(events: list[dict], generated_at: str) -> dict:
    return {
        "project": PROJECT_NAME,
        "generated_at": generated_at,
        "count": len(events),
        "events": events,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build(source: Path, output: Path, now: datetime) -> dict[str, int]:
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EventValidationError(f"source file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise EventValidationError(
            f"{source}:{exc.lineno}:{exc.colno} is not valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(raw, list):
        raise EventValidationError(f"{source} must contain a JSON list of events")

    validated: list[tuple[dict, datetime, datetime]] = []
    seen_ids: set[str] = set()
    for position, candidate in enumerate(raw):
        event, start, end = validate_event(candidate, position)
        if event["id"] in seen_ids:
            raise EventValidationError(f"duplicate event id: {event['id']}")
        seen_ids.add(event["id"])
        validated.append((public_event(event, start, end, now), start, end))

    all_events = [item[0] for item in sorted(validated, key=lambda item: item[1])]
    current = [event for event in all_events if event["status"] in {"upcoming", "ongoing"}]
    archived = [event for event in all_events if event["status"] in {"ended", "cancelled"}]
    archived.sort(key=lambda event: parse_timestamp(event["start"], "start"), reverse=True)

    generated_at = now.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    write_json(output / "events.json", feed(all_events, generated_at))
    write_json(output / "upcoming.json", feed(current, generated_at))
    write_json(output / "archive.json", feed(archived, generated_at))
    for city in CITIES:
        city_events = [event for event in current if event["city"] == city]
        write_json(output / f"upcoming-{city}.json", feed(city_events, generated_at))

    return {
        "all": len(all_events),
        "current": len(current),
        "archived": len(archived),
    }


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return parse_timestamp(value, "--now")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=project_root / "data/events.json")
    parser.add_argument("--output", type=Path, default=project_root / "feeds")
    parser.add_argument(
        "--now",
        help="Override the current time for testing (ISO 8601 with UTC offset).",
    )
    args = parser.parse_args()

    try:
        counts = build(args.source, args.output, parse_now(args.now))
    except EventValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "Built Delta Index feeds: "
        f"{counts['all']} total, {counts['current']} current, "
        f"{counts['archived']} archived."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
