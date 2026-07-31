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
        return event


class CalendarEventSummary(BaseModel):
    """A lightweight summary of a calendar event."""

    model_config = {"frozen": True}

    id: str
    subject: str
    start: str
    end: str
    organizer: str
    location: str

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
        return cls(
            id=str(item.get("id", "")),
            subject=str(item.get("subject") or "(no subject)"),
            start=str(start_obj.get("dateTime", "")) if isinstance(start_obj, dict) else "",
            end=str(end_obj.get("dateTime", "")) if isinstance(end_obj, dict) else "",
            organizer=organizer_addr,
            location=location_name,
        )
