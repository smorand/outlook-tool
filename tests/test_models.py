"""Tests for the value models."""

from __future__ import annotations

import base64
from pathlib import Path

from models import (
    Attachment,
    CalendarEventInput,
    CalendarEventSummary,
    MailSummary,
    OutgoingMessage,
    Recipient,
)


def test_recipient_parse_plain() -> None:
    """A bare address parses without a name."""
    recipient = Recipient.parse("a@b.com")
    assert recipient.email == "a@b.com"
    assert recipient.name is None
    assert recipient.to_graph() == {"emailAddress": {"address": "a@b.com"}}


def test_recipient_parse_named() -> None:
    """A 'Name <addr>' string parses name and address."""
    recipient = Recipient.parse("Seb Morand <seb.morand@gmail.com>")
    assert recipient.name == "Seb Morand"
    assert recipient.email == "seb.morand@gmail.com"
    assert recipient.to_graph()["emailAddress"] == {"address": "seb.morand@gmail.com", "name": "Seb Morand"}


def test_attachment_from_path_and_encoding(tmp_path: Path) -> None:
    """Attachment loads bytes, guesses type and base64-encodes for Graph."""
    file_path = tmp_path / "note.txt"
    file_path.write_bytes(b"hello")
    attachment = Attachment.from_path(file_path)
    assert attachment.name == "note.txt"
    assert attachment.content_type == "text/plain"
    assert attachment.size == 5
    graph = attachment.to_file_attachment()
    assert graph["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert base64.b64decode(str(graph["contentBytes"])) == b"hello"


def test_outgoing_message_graph_serialization() -> None:
    """Message serializes recipients, HTML body and optional attachments."""
    message = OutgoingMessage(
        subject="Hi",
        body="<b>x</b>",
        to=[Recipient(email="a@b.com")],
        cc=[Recipient(email="c@d.com")],
    )
    without = message.to_graph_message(include_attachments=False)
    assert without["subject"] == "Hi"
    assert without["body"] == {"contentType": "HTML", "content": "<b>x</b>"}
    assert without["toRecipients"] == [{"emailAddress": {"address": "a@b.com"}}]
    assert without["ccRecipients"] == [{"emailAddress": {"address": "c@d.com"}}]
    assert "attachments" not in without


def test_outgoing_message_total_size() -> None:
    """Total attachment size sums all parts."""
    attachment = Attachment(path=Path("x"), name="x", content_type="text/plain", content_bytes=b"1234")
    message = OutgoingMessage(subject="s", body="b", to=[Recipient(email="a@b.com")], attachments=[attachment])
    assert message.total_attachment_size == 4
    assert "attachments" in message.to_graph_message(include_attachments=True)


def test_mail_summary_from_graph() -> None:
    """MailSummary extracts sender address and flags from a Graph message."""
    summary = MailSummary.from_graph(
        {
            "id": "AAA",
            "subject": "Re: test",
            "from": {"emailAddress": {"address": "x@y.com", "name": "X"}},
            "receivedDateTime": "2026-07-29T10:00:00Z",
            "bodyPreview": "  hello  ",
            "hasAttachments": True,
        }
    )
    assert summary.sender == "x@y.com"
    assert summary.preview == "hello"
    assert summary.has_attachments is True


def test_calendar_event_input_graph() -> None:
    """CalendarEventInput serializes start/end with time zone and attendees."""
    event = CalendarEventInput(
        subject="Nuit",
        start="2026-07-29T03:00:00",
        end="2026-07-29T03:30:00",
        attendees=[Recipient(email="seb.morand@gmail.com")],
        location="Home",
    )
    graph = event.to_graph_event()
    assert graph["start"] == {"dateTime": "2026-07-29T03:00:00", "timeZone": "Europe/Paris"}
    assert graph["location"] == {"displayName": "Home"}
    assert graph["attendees"][0]["type"] == "required"
    assert graph["attendees"][0]["emailAddress"]["address"] == "seb.morand@gmail.com"


def test_calendar_event_summary_from_graph() -> None:
    """CalendarEventSummary extracts start/end, organizer and location."""
    summary = CalendarEventSummary.from_graph(
        {
            "id": "E1",
            "subject": "Nuit",
            "start": {"dateTime": "2026-07-29T03:00:00.0000000", "timeZone": "Europe/Paris"},
            "end": {"dateTime": "2026-07-29T03:30:00.0000000", "timeZone": "Europe/Paris"},
            "organizer": {"emailAddress": {"address": "me@corp.com"}},
            "location": {"displayName": "Home"},
        }
    )
    assert summary.organizer == "me@corp.com"
    assert summary.location == "Home"
    assert summary.start.startswith("2026-07-29T03:00:00")


def test_mail_summary_is_meeting_request_true() -> None:
    """MailSummary.is_meeting_request is True for eventMessageRequest."""
    summary = MailSummary.from_graph(
        {
            "id": "M1",
            "subject": "Invite",
            "@odata.type": "#microsoft.graph.eventMessageRequest",
            "from": {"emailAddress": {"address": "boss@corp.com"}},
            "receivedDateTime": "2026-08-01T09:00:00Z",
            "bodyPreview": "You are invited",
            "hasAttachments": False,
        }
    )
    assert summary.is_meeting_request is True


def test_mail_summary_is_meeting_request_false_for_regular_mail() -> None:
    """MailSummary.is_meeting_request is False when @odata.type is absent or a plain message."""
    summary = MailSummary.from_graph(
        {
            "id": "M2",
            "subject": "Hello",
            "from": {"emailAddress": {"address": "a@b.com"}},
            "receivedDateTime": "2026-08-01T10:00:00Z",
            "bodyPreview": "hi",
            "hasAttachments": False,
        }
    )
    assert summary.is_meeting_request is False
