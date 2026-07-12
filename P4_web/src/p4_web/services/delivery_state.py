from __future__ import annotations

from datetime import date, datetime, timedelta

DELIVERY_STATUS_STAGE_COUNT = 5
DELIVERY_STATUS_DEFAULT_INTERVAL_DAYS = 90

DELIVERY_STAGE_LABELS = [
    {"status": 1, "id": "new", "label": "Captured"},
    {"status": 2, "id": "in_work", "label": "In Work"},
    {"status": 3, "id": "freigegeben", "label": "Released"},
    {"status": 4, "id": "in_translation", "label": "In Translation"},
    {"status": 5, "id": "closed", "label": "Closed"},
]


def normalize_delivery_status(value: object, default: int | None = 0) -> int | None:
    try:
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        value = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if value < 0 or value > DELIVERY_STATUS_STAGE_COUNT:
        return default
    return value


def parse_delivery_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ")
    candidates: list[str] = []
    for item in (text, text.split(" ", 1)[0] if " " in text else text, text[:10] if len(text) >= 10 else text):
        if item and item not in candidates:
            candidates.append(item)
    for item in candidates:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y.%m.%d"):
            try:
                return datetime.strptime(item, fmt).date()
            except ValueError:
                continue
    return None


def parse_delivery_state_from_runner_logs(logs: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in logs:
        text = line.strip()
        if not text.startswith("DELIVERY_STATE "):
            continue
        payload = text[len("DELIVERY_STATE ") :]
        for part in payload.split():
            if part.startswith("status="):
                metadata["delivery_status"] = part.split("=", 1)[1]
    return metadata


def parse_delivery_interval_days(value: object, default: int = DELIVERY_STATUS_DEFAULT_INTERVAL_DAYS) -> int:
    try:
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def delivery_status_initialized(metadata: dict[str, str]) -> bool:
    return normalize_delivery_status(metadata.get("delivery_status"), default=None) is not None


LEGACY_STAGE_TO_STATUS = {
    "new": 1,
    "in_work": 2,
    "freigegeben": 3,
    "in_translation": 4,
    "closed": 5,
}


def build_enriched_delivery_state(
    metadata: dict[str, str],
    legacy_delivery: dict[str, object] | None,
    *,
    has_project_sheet: bool,
) -> dict[str, object] | None:
    state = build_delivery_state(metadata)
    if state:
        enriched = dict(state)
        enriched["can_advance"] = has_project_sheet and bool(state.get("has_delivery_status"))
        enriched["source"] = "project_sheet"
        return enriched

    if not has_project_sheet:
        return None

    legacy = legacy_delivery or {}
    stage = str(legacy.get("stage", ""))
    if stage == "error":
        return None

    delivery_date = parse_delivery_date(metadata.get("delivery_date"))
    return {
        "status": 0,
        "current_deadline": None,
        "is_complete": False,
        "is_overdue": False,
        "is_activated": False,
        "delivery_date": delivery_date.isoformat() if delivery_date else None,
        "has_delivery_status": False,
        "can_advance": False,
        "source": "project_sheet",
        "steps": DELIVERY_STAGE_LABELS,
    }


def build_delivery_state(metadata: dict[str, str]) -> dict[str, object] | None:
    if not delivery_status_initialized(metadata):
        return None

    raw_status = metadata.get("delivery_status")
    status = normalize_delivery_status(raw_status, default=None)
    status_is_initialized = status is not None
    if not status_is_initialized:
        status = 0

    delivery_date = parse_delivery_date(metadata.get("delivery_date"))
    deadlines = _delivery_stage_deadlines(metadata, delivery_date)
    current_deadline = None
    if 1 <= status <= DELIVERY_STATUS_STAGE_COUNT:
        current_deadline = deadlines[status - 1]
    elif status == 0 and deadlines:
        current_deadline = deadlines[0]

    is_complete = status == DELIVERY_STATUS_STAGE_COUNT
    is_overdue = False
    if current_deadline and status > 0:
        is_overdue = date.today() > current_deadline

    return {
        "status": status,
        "current_deadline": current_deadline.isoformat() if current_deadline else None,
        "is_complete": is_complete,
        "is_overdue": is_overdue,
        "is_activated": bool(delivery_date) and status_is_initialized,
        "delivery_date": delivery_date.isoformat() if delivery_date else None,
        "has_delivery_status": True,
        "steps": DELIVERY_STAGE_LABELS,
    }


def _delivery_stage_deadlines(
    metadata: dict[str, str],
    delivery_date: date | None,
) -> list[date | None]:
    if delivery_date is None:
        return [None] * DELIVERY_STATUS_STAGE_COUNT

    time_step_interval = parse_delivery_interval_days(
        metadata.get("time_step"),
        default=DELIVERY_STATUS_DEFAULT_INTERVAL_DAYS,
    )
    default_interval = parse_delivery_interval_days(
        metadata.get("delivery_status_interval"),
        default=time_step_interval,
    )
    intervals = [
        parse_delivery_interval_days(
            metadata.get(f"delivery_status_interval_{stage}"),
            default=default_interval,
        )
        for stage in range(1, DELIVERY_STATUS_STAGE_COUNT + 1)
    ]

    deadlines = [delivery_date] * DELIVERY_STATUS_STAGE_COUNT
    current_deadline = delivery_date
    deadlines[DELIVERY_STATUS_STAGE_COUNT - 1] = current_deadline
    for idx in range(DELIVERY_STATUS_STAGE_COUNT - 2, -1, -1):
        current_deadline = current_deadline - timedelta(days=intervals[idx + 1])
        deadlines[idx] = current_deadline
    return deadlines
