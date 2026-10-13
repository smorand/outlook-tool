"""Tests for the calendar service."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import respx

from graph_client import GraphClient
from models import CalendarEventInput, CalendarEventSummary, Recipient
from services.calendar import CalendarService

if TYPE_CHECKING:
    from config import Settings
    from tests.conftest import StubAuth

GRAPH = "https://graph.microsoft.com/v1.0"


def _service(settings: Settings, stub_auth: StubAuth, client: httpx.AsyncClient) -> CalendarService:
    return CalendarService(settings, GraphClient(settings, stub_auth, client))


@respx.mock
async def test_create_event(settings: Settings, stub_auth: StubAuth) -> None:
    """create_event posts a Graph event with start/end/attendees and returns it."""
    route = respx.post(f"{GRAPH}/me/events").mock(return_value=httpx.Response(201, json={"id": "E1"}))
    event = CalendarEventInput(
        subject="Nuit",
        start="2026-07-29T03:00:00",
        end="2026-07-29T03:30:00",
        attendees=[Recipient(email="seb.morand@gmail.com")],
    )
    async with httpx.AsyncClient() as client:
        created = await _service(settings, stub_auth, client).create_event(event)
    assert created["id"] == "E1"
    body = json.loads(route.calls.last.request.content)
    assert body["start"]["dateTime"] == "2026-07-29T03:00:00"
    assert body["attendees"][0]["emailAddress"]["address"] == "seb.morand@gmail.com"


@respx.mock
async def test_list_events(settings: Settings, stub_auth: StubAuth) -> None:
    """list_events parses calendarView values and sends the timezone Prefer header."""
    route = respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "E1",
                        "subject": "Nuit",
                        "start": {"dateTime": "2026-07-29T03:00:00.0000000", "timeZone": "Europe/Paris"},
                        "end": {"dateTime": "2026-07-29T03:30:00.0000000", "timeZone": "Europe/Paris"},
                        "organizer": {"emailAddress": {"address": "me@corp.com"}},
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        events = await _service(settings, stub_auth, client).list_events(
            start="2026-07-29T00:00:00", end="2026-07-30T00:00:00"
        )
    assert len(events) == 1
    assert events[0].organizer == "me@corp.com"
    assert 'outlook.timezone="Europe/Paris"' in route.calls.last.request.headers["Prefer"]


@respx.mock
async def test_update_event(settings: Settings, stub_auth: StubAuth) -> None:
    """update_event patches the given fields."""
    route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).update_event("E1", {"subject": "Nuit v2"})
    assert route.called
    assert json.loads(route.calls.last.request.content)["subject"] == "Nuit v2"


@respx.mock
async def test_delete_event(settings: Settings, stub_auth: StubAuth) -> None:
    """delete_event issues a DELETE for the event id."""
    route = respx.delete(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(204))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).delete_event("E1")
    assert route.called


@respx.mock
async def test_create_event_with_show_as(settings: Settings, stub_auth: StubAuth) -> None:
    """create_event includes showAs in the Graph payload when provided."""
    route = respx.post(f"{GRAPH}/me/events").mock(return_value=httpx.Response(201, json={"id": "E2"}))
    event = CalendarEventInput(
        subject="Congés",
        start="2026-08-17T00:00:00",
        end="2026-08-28T23:59:59",
        show_as="oof",
    )
    async with httpx.AsyncClient() as client:
        created = await _service(settings, stub_auth, client).create_event(event)
    assert created["id"] == "E2"
    body = json.loads(route.calls.last.request.content)
    assert body["showAs"] == "oof"


@respx.mock
async def test_update_event_show_as(settings: Settings, stub_auth: StubAuth) -> None:
    """update_event passes showAs as a direct field (not nested)."""
    route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).update_event("E1", {"showAs": "oof"})
    assert route.called
    assert json.loads(route.calls.last.request.content)["showAs"] == "oof"


@respx.mock
async def test_create_event_with_categories(settings: Settings, stub_auth: StubAuth) -> None:
    """create_event includes categories in the Graph payload when provided."""
    route = respx.post(f"{GRAPH}/me/events").mock(return_value=httpx.Response(201, json={"id": "E3"}))
    event = CalendarEventInput(
        subject="Anniversaire",
        start="2026-08-17T00:00:00",
        end="2026-08-17T23:59:59",
        categories=["Red category"],
    )
    async with httpx.AsyncClient() as client:
        created = await _service(settings, stub_auth, client).create_event(event)
    assert created["id"] == "E3"
    body = json.loads(route.calls.last.request.content)
    assert body["categories"] == ["Red category"]


def test_create_event_without_categories_omits_field() -> None:
    """to_graph_event omits the categories key when none are set."""
    event = CalendarEventInput(subject="Nuit", start="2026-07-29T03:00:00", end="2026-07-29T03:30:00")
    assert "categories" not in event.to_graph_event()


def test_calendar_event_summary_from_graph_categories() -> None:
    """from_graph parses categories, defaulting to an empty list when absent."""
    with_categories = CalendarEventSummary.from_graph(
        {
            "id": "E1",
            "subject": "Nuit",
            "start": {"dateTime": "2026-07-29T03:00:00"},
            "end": {"dateTime": "2026-07-29T03:30:00"},
            "categories": ["Blue category"],
        }
    )
    assert with_categories.categories == ["Blue category"]

    without_categories = CalendarEventSummary.from_graph(
        {
            "id": "E2",
            "subject": "Nuit",
            "start": {"dateTime": "2026-07-29T03:00:00"},
            "end": {"dateTime": "2026-07-29T03:30:00"},
        }
    )
    assert without_categories.categories == []


@respx.mock
async def test_update_event_categories(settings: Settings, stub_auth: StubAuth) -> None:
    """update_event passes categories as a direct field (not nested)."""
    route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).update_event("E1", {"categories": ["Green category"]})
    assert route.called
    assert json.loads(route.calls.last.request.content)["categories"] == ["Green category"]


@respx.mock
async def test_accept_event(settings: Settings, stub_auth: StubAuth) -> None:
    """accept_event POSTs to /me/events/{id}/accept with sendResponse=False."""
    route = respx.post(f"{GRAPH}/me/events/E1/accept").mock(return_value=httpx.Response(202))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).accept_event("E1")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"sendResponse": False}


def _graph_event(event_id: str = "E1", **overrides: object) -> dict[str, object]:
    """Build a Graph event resource shaped like a real one."""
    event: dict[str, object] = {
        "id": event_id,
        "subject": "Nuit",
        "start": {"dateTime": "2026-07-29T03:00:00.0000000", "timeZone": "Europe/Paris"},
        "end": {"dateTime": "2026-07-29T03:30:00.0000000", "timeZone": "Europe/Paris"},
        "organizer": {"emailAddress": {"address": "me@corp.com"}},
    }
    event.update(overrides)
    return event


@respx.mock
async def test_list_events_missing_response_status(settings: Settings, stub_auth: StubAuth) -> None:
    """SPEC-0004/E2E-012: a missing responseStatus maps to 'Not yet responded' and selects the field."""
    route = respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(200, json={"value": [_graph_event()]})
    )
    async with httpx.AsyncClient() as client:
        events = await _service(settings, stub_auth, client).list_events(
            start="2026-07-29T00:00:00", end="2026-07-30T00:00:00"
        )
    assert events[0].response_status == "Not yet responded"
    assert "responseStatus" in str(route.calls.last.request.url)


@respx.mock
async def test_list_events_response_status_with_malformed_fields(settings: Settings, stub_auth: StubAuth) -> None:
    """SPEC-0004/E2E-018: malformed location/organizer do not prevent the response state."""
    event = _graph_event(location="not-an-object", organizer=None, responseStatus={"response": "accepted"})
    respx.get(url__regex=r".*/me/calendarView.*").mock(return_value=httpx.Response(200, json={"value": [event]}))
    async with httpx.AsyncClient() as client:
        events = await _service(settings, stub_auth, client).list_events(
            start="2026-07-29T00:00:00", end="2026-07-30T00:00:00"
        )
    assert events[0].response_status == "Accepted"


@respx.mock
async def test_get_event_missing_response_status(settings: Settings, stub_auth: StubAuth) -> None:
    """SPEC-0004/E2E-013: get_event fetches one event by id; missing state maps to 'Not yet responded'."""
    route = respx.get(url__regex=rf"{GRAPH}/me/events/E1\?.*").mock(
        return_value=httpx.Response(200, json=_graph_event())
    )
    async with httpx.AsyncClient() as client:
        event = await _service(settings, stub_auth, client).get_event("E1")
    assert event.id == "E1"
    assert event.response_status == "Not yet responded"
    assert "responseStatus" in str(route.calls.last.request.url)
