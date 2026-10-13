"""Calendar operations on Microsoft Graph: list, get, create, update, delete, accept."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from graph_client import GraphError
from models import CalendarEventInput, CalendarEventSummary
from tracing import trace_span

if TYPE_CHECKING:
    from config import Settings
    from graph_client import GraphClient

logger = logging.getLogger(__name__)

_EVENT_SELECT = "id,subject,start,end,organizer,location,categories,responseStatus"


class CalendarService:
    """Manages calendar events via Microsoft Graph."""

    __slots__ = ("_graph", "_settings")

    def __init__(self, settings: Settings, graph: GraphClient) -> None:
        self._settings = settings
        self._graph = graph

    async def get_event(self, event_id: str) -> CalendarEventSummary:
        """Fetch one event by id; a missing or inaccessible id raises GraphError."""
        with trace_span("calendar.get", attributes={"event.id": event_id}):
            response = await self._graph.get(f"/me/events/{event_id}?$select={_EVENT_SELECT}")
            logger.info("fetched event id=%s", event_id)
            return CalendarEventSummary.from_graph(response.json())

    async def list_events(
        self, *, start: str, end: str, time_zone: str = "Europe/Paris", top: int = 50
    ) -> list[CalendarEventSummary]:
        """List events overlapping the [start, end] window (ISO 8601 datetimes)."""
        query = urlencode(
            {
                "startDateTime": start,
                "endDateTime": end,
                "$select": _EVENT_SELECT,
                "$orderby": "start/dateTime",
                "$top": top,
            },
            safe=" ,/:",
        )
        headers = {"Prefer": f'outlook.timezone="{time_zone}"'}
        response = await self._graph.get(f"/me/calendarView?{query}", headers=headers)
        items = response.json().get("value", [])
        return [CalendarEventSummary.from_graph(item) for item in items]

    async def create_event(self, event: CalendarEventInput) -> dict[str, Any]:
        """Create a calendar event and return the created resource."""
        with trace_span("calendar.create", attributes={"event.subject": event.subject}):
            response = await self._graph.post("/me/events", json=event.to_graph_event())
            created: dict[str, Any] = response.json()
            logger.info("created event '%s' (id=%s)", event.subject, created.get("id", ""))
            return created

    async def update_event(self, event_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Patch fields on an existing event and return the updated resource."""
        with trace_span("calendar.update", attributes={"event.id": event_id}):
            response = await self._graph.patch(f"/me/events/{event_id}", json=changes)
            logger.info("updated event id=%s", event_id)
            updated: dict[str, Any] = response.json()
            return updated

    async def delete_event(self, event_id: str) -> None:
        """Delete an event by id."""
        with trace_span("calendar.delete", attributes={"event.id": event_id}):
            await self._graph.delete(f"/me/events/{event_id}")
            logger.info("deleted event id=%s", event_id)

    async def accept_event(self, event_id: str) -> str | None:
        """Accept a meeting invitation and return the confirmed response status, or None if unconfirmable."""
        with trace_span("calendar.accept", attributes={"event.id": event_id}):
            await self._graph.post(f"/me/events/{event_id}/accept", json={"sendResponse": False})
            logger.info("accepted event id=%s", event_id)
            try:
                event = await self.get_event(event_id)
            except GraphError:
                logger.info("could not confirm response status for event id=%s", event_id)
                return None
            return event.response_status
