"""Pydantic value models for mail and calendar operations."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path  # noqa: TC003 - runtime type used by a pydantic model field

from pydantic import BaseModel, EmailStr, Field, field_validator


class Recipient(BaseModel):
    """An email recipient."""

    model_config = {"frozen": True}

    email: EmailStr
    name: str | None = None

    def to_graph(self) -> dict[str, object]:
        """Serialize to a Graph emailAddress recipient object."""
        address: dict[str, object] = {"address": str(self.email)}
        if self.name:
            address["name"] = self.name
        return {"emailAddress": address}

    @classmethod
    def parse(cls, raw: str) -> Recipient:
        """Parse 'Name <addr@x>' or 'addr@x' into a Recipient."""
        raw = raw.strip()
        if "<" in raw and raw.endswith(">"):
            name, _, addr = raw.partition("<")
            return cls(email=addr[:-1].strip(), name=name.strip() or None)
        return cls(email=raw)


class Attachment(BaseModel):
    """A file attachment resolved from a local path."""

    model_config = {"frozen": True}

    path: Path
    name: str
    content_type: str
    content_bytes: bytes

    @property
    def size(self) -> int:
        """Attachment size in bytes."""
        return len(self.content_bytes)

    @classmethod
    def from_path(cls, path: Path) -> Attachment:
        """Load an attachment from disk, guessing its MIME type."""
        resolved = path.expanduser()
        if not resolved.is_file():
            msg = f"attachment not found: {resolved}"
            raise FileNotFoundError(msg)
        guessed, _ = mimetypes.guess_type(resolved.name)
        return cls(
            path=resolved,
            name=resolved.name,
            content_type=guessed or "application/octet-stream",
            content_bytes=resolved.read_bytes(),
        )

    def to_file_attachment(self) -> dict[str, object]:
        """Serialize to a Graph #microsoft.graph.fileAttachment object."""
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": self.name,
            "contentType": self.content_type,
            "contentBytes": base64.b64encode(self.content_bytes).decode("ascii"),
        }


class AttachmentSummary(BaseModel):
    """A lightweight summary of a message attachment (metadata only)."""

    model_config = {"frozen": True}

    id: str
    name: str
    content_type: str
    size: int
    is_inline: bool

    @classmethod
    def from_graph(cls, item: dict[str, object]) -> AttachmentSummary:
        """Build a summary from a Graph attachment resource."""
        size = item.get("size") or 0
        return cls(
            id=str(item.get("id", "")),
            name=str(item.get("name") or "(unnamed)"),
            content_type=str(item.get("contentType") or "application/octet-stream"),
            size=int(size) if isinstance(size, (int, str)) else 0,
            is_inline=bool(item.get("isInline", False)),
        )


class OutgoingMessage(BaseModel):
    """A message to send via Graph sendMail."""

    subject: str
    body: str
    is_html: bool = True
    to: list[Recipient] = Field(min_length=1)
    cc: list[Recipient] = Field(default_factory=list)
    bcc: list[Recipient] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)

    @property
    def total_attachment_size(self) -> int:
        """Sum of all attachment sizes in bytes."""
        return sum(att.size for att in self.attachments)

    def to_graph_message(self, *, include_attachments: bool) -> dict[str, object]:
        """Serialize to a Graph message object.

        Args:
            include_attachments: If True, inline attachments as base64 fileAttachments.
                Set False when attachments are uploaded separately (draft + upload session).
        """
        message: dict[str, object] = {
            "subject": self.subject,
            "body": {"contentType": "HTML" if self.is_html else "Text", "content": self.body},
            "toRecipients": [r.to_graph() for r in self.to],
        }
        if self.cc:
            message["ccRecipients"] = [r.to_graph() for r in self.cc]
        if self.bcc:
            message["bccRecipients"] = [r.to_graph() for r in self.bcc]
        if include_attachments and self.attachments:
            message["attachments"] = [att.to_file_attachment() for att in self.attachments]
        return message


class MailSummary(BaseModel):
    """A lightweight summary of a received message."""

    model_config = {"frozen": True}

    id: str
    subject: str
    sender: str
    received: str
    preview: str
    has_attachments: bool
    is_meeting_request: bool = False

    @classmethod
    def from_graph(cls, item: dict[str, object]) -> MailSummary:
        """Build a summary from a Graph message resource."""
        sender_obj = item.get("from") or item.get("sender") or {}
        address = ""
        if isinstance(sender_obj, dict):
            email_addr = sender_obj.get("emailAddress")
            if isinstance(email_addr, dict):
                address = str(email_addr.get("address", ""))
        odata_type = str(item.get("@odata.type") or "")
        return cls(
            id=str(item.get("id", "")),
            subject=str(item.get("subject") or "(no subject)"),
            sender=address,
            received=str(item.get("receivedDateTime", "")),
            preview=str(item.get("bodyPreview") or "").strip(),
            has_attachments=bool(item.get("hasAttachments", False)),
            is_meeting_request=odata_type == "#microsoft.graph.eventMessageRequest",
        )


SHOW_AS_VALUES = frozenset({"free", "tentative", "busy", "oof", "workingElsewhere", "unknown", "away"})


class CalendarEventInput(BaseModel):
    """Input for creating or updating a calendar event."""

    subject: str
    start: str  # ISO 8601 local datetime, e.g. 2026-07-29T03:00:00
    end: str
    time_zone: str = "Europe/Paris"
    body: str | None = None
    is_html: bool = True
    location: str | None = None
    attendees: list[Recipient] = Field(default_factory=list)
    show_as: str | None = None  # free | tentative | busy | oof | workingElsewhere | unknown
    categories: list[str] = Field(default_factory=list)

    @field_validator("show_as")
    @classmethod
    def _validate_show_as(cls, value: str | None) -> str | None:
        if value is not None and value not in SHOW_AS_VALUES:
            msg = f"show_as must be one of {sorted(SHOW_AS_VALUES)}, got {value!r}"
            raise ValueError(msg)
        return value

    @field_validator("start", "end")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    def to_graph_event(self) -> dict[str, object]:
        """Serialize to a Graph event object."""
        event: dict[str, object] = {
            "subject": self.subject,
            "start": {"dateTime": self.start, "timeZone": self.time_zone},
            "end": {"dateTime": self.end, "timeZone": self.time_zone},
        }
        if self.body is not None:
            event["body"] = {"contentType": "HTML" if self.is_html else "Text", "content": self.body}
        if self.location:
            event["location"] = {"displayName": self.location}
        if self.attendees:
            event["attendees"] = [
                {"emailAddress": r.to_graph()["emailAddress"], "type": "required"} for r in self.attendees
            ]
        if self.show_as is not None:
            event["showAs"] = self.show_as
        if self.categories:
            event["categories"] = self.categories
        return event


_RESPONSE_STATUS_LABELS = {
    "accepted": "Accepted",
    "tentativelyAccepted": "Tentatively accepted",
    "declined": "Declined",
    "organizer": "Organizer",
}
_DEFAULT_RESPONSE_STATUS = "Not yet responded"


def map_response_status(response_status: object) -> str:
    """Map a Graph responseStatus object to its display label (O(1)); unknown shapes are 'Not yet responded'."""
    if not isinstance(response_status, dict):
        return _DEFAULT_RESPONSE_STATUS
    return _RESPONSE_STATUS_LABELS.get(str(response_status.get("response")), _DEFAULT_RESPONSE_STATUS)


class CalendarEventSummary(BaseModel):
    """A lightweight summary of a calendar event."""

    model_config = {"frozen": True}

    id: str
    subject: str
    start: str
    end: str
    organizer: str
    location: str
    categories: list[str] = Field(default_factory=list)
    response_status: str

    @classmethod
    def from_graph(cls, item: dict[str, object]) -> CalendarEventSummary:
        """Build a summary from a Graph event resource."""
        start_obj = item.get("start") or {}
        end_obj = item.get("end") or {}
        organizer_obj = item.get("organizer") or {}
        organizer_addr = ""
        if isinstance(organizer_obj, dict):
            email_addr = organizer_obj.get("emailAddress")
            if isinstance(email_addr, dict):
                organizer_addr = str(email_addr.get("address", ""))
        location_obj = item.get("location") or {}
        location_name = ""
        if isinstance(location_obj, dict):
            location_name = str(location_obj.get("displayName", ""))
        categories_obj = item.get("categories") or []
        categories = [str(c) for c in categories_obj] if isinstance(categories_obj, list) else []
        return cls(
            id=str(item.get("id", "")),
            subject=str(item.get("subject") or "(no subject)"),
            start=str(start_obj.get("dateTime", "")) if isinstance(start_obj, dict) else "",
            end=str(end_obj.get("dateTime", "")) if isinstance(end_obj, dict) else "",
            organizer=organizer_addr,
            location=location_name,
            categories=categories,
            response_status=map_response_status(item.get("responseStatus")),
        )
