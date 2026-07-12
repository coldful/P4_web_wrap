from datetime import date

from p4_web.services.delivery_state import (
    build_delivery_state,
    build_enriched_delivery_state,
    delivery_status_initialized,
    normalize_delivery_status,
    parse_delivery_date,
    parse_delivery_state_from_runner_logs,
)


def test_normalize_delivery_status_defaults() -> None:
    assert normalize_delivery_status("", default=0) == 0
    assert normalize_delivery_status(None, default=None) is None
    assert normalize_delivery_status("3", default=0) == 3
    assert normalize_delivery_status("9", default=0) == 0


def test_parse_delivery_date_accepts_common_formats() -> None:
    assert parse_delivery_date("2026-06-15") == date(2026, 6, 15)
    assert parse_delivery_date("15.06.2026") == date(2026, 6, 15)
    assert parse_delivery_date("") is None


def test_delivery_status_initialized_requires_key() -> None:
    assert not delivery_status_initialized({})
    assert delivery_status_initialized({"delivery_status": "0"})


def test_build_delivery_state_from_project_sheet_metadata() -> None:
    state = build_delivery_state(
        {
            "delivery_status": "2",
            "delivery_date": "2026-12-01",
            "delivery_status_interval": "30",
            "time_step": "30",
        }
    )
    assert state is not None
    assert state["status"] == 2
    assert state["has_delivery_status"] is True
    assert state["is_activated"] is True
    assert state["is_complete"] is False
    assert state["delivery_date"] == "2026-12-01"
    assert state["current_deadline"] is not None


def test_build_delivery_state_returns_none_without_delivery_status_key() -> None:
    assert build_delivery_state({"delivery_date": "2026-12-01"}) is None


def test_build_enriched_delivery_state_allows_advance_without_delivery_status_key() -> None:
    state = build_enriched_delivery_state(
        {"delivery_date": "2026-12-01"},
        {"stage": "new"},
        has_project_sheet=True,
    )
    assert state is not None
    assert state["can_advance"] is True
    assert state["source"] == "project_sheet"
    assert state["status"] == 0
    assert state["has_delivery_status"] is False


def test_parse_delivery_state_from_runner_logs() -> None:
    metadata = parse_delivery_state_from_runner_logs(
        [
            "RUN python2.7 /opt/P4_legacy_runner/legacy_helpers.py advance-delivery-status",
            "DELIVERY_STATE status=2 overdue=0 complete=0 activated=1",
        ]
    )
    assert metadata == {"delivery_status": "2"}
