"""Tests for the calendar service."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import respx

from graph_client import GraphClient
from models import CalendarEventInput, Recipient
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
async def test_accept_event(settings: Settings, stub_auth: StubAuth) -> None:
    """accept_event POSTs to /me/events/{id}/accept with sendResponse=False."""
    route = respx.post(f"{GRAPH}/me/events/E1/accept").mock(return_value=httpx.Response(202))
    async with httpx.AsyncClient() as client:
        await _service(settings, stub_auth, client).accept_event("E1")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"sendResponse": False}
