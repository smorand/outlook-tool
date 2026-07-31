"""Tests for the mail service (send and read)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import respx

from graph_client import GraphClient
from models import Attachment, OutgoingMessage, Recipient
from services.mail import MailService

if TYPE_CHECKING:
    from pathlib import Path

    from config import Settings
    from tests.conftest import StubAuth

GRAPH = "https://graph.microsoft.com/v1.0"


def _message(**overrides: object) -> OutgoingMessage:
    base = {
        "subject": "Test",
        "body": "<b>hi</b>",
        "to": [Recipient(email="seb.morand@gmail.com")],
    }
    base.update(overrides)
    return OutgoingMessage(**base)  # type: ignore[arg-type]


@respx.mock
async def test_send_inline_small_message(settings: Settings, stub_auth: StubAuth) -> None:
    """A message without large attachments is sent via a single sendMail call."""
    route = respx.post(f"{GRAPH}/me/sendMail").mock(return_value=httpx.Response(202))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.send(_message())
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["saveToSentItems"] is True
    assert body["message"]["subject"] == "Test"
    assert body["message"]["toRecipients"][0]["emailAddress"]["address"] == "seb.morand@gmail.com"


@respx.mock
async def test_send_via_draft_with_upload_session(settings: Settings, stub_auth: StubAuth, tmp_path: Path) -> None:
    """Large attachments trigger the draft + upload-session path.

    settings caps inline at 10 bytes and chunk size at 4, so a 20-byte file goes
    through createUploadSession with multiple chunked PUTs, while a 5-byte file is
    posted directly as a fileAttachment.
    """
    small = tmp_path / "small.txt"
    small.write_bytes(b"12345")
    large = tmp_path / "large.bin"
    large.write_bytes(b"0123456789ABCDEFGHIJ")  # 20 bytes

    draft = respx.post(f"{GRAPH}/me/messages").mock(return_value=httpx.Response(201, json={"id": "MSG"}))
    add_small = respx.post(f"{GRAPH}/me/messages/MSG/attachments").mock(return_value=httpx.Response(201, json={}))
    create_session = respx.post(f"{GRAPH}/me/messages/MSG/attachments/createUploadSession").mock(
        return_value=httpx.Response(201, json={"uploadUrl": "https://upload.example/session"})
    )
    put_chunk = respx.put("https://upload.example/session").mock(return_value=httpx.Response(200, json={}))
    send_draft = respx.post(f"{GRAPH}/me/messages/MSG/send").mock(return_value=httpx.Response(202))

    message = _message(
        attachments=[Attachment.from_path(small), Attachment.from_path(large)],
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.send(message)

    assert draft.called
    assert add_small.called
    assert create_session.called
    assert send_draft.called
    # 20 bytes / 4-byte chunks = 5 PUTs, none carrying an Authorization header.
    assert put_chunk.call_count == 5
    first_chunk = put_chunk.calls[0].request
    assert "Authorization" not in first_chunk.headers
    assert first_chunk.headers["Content-Range"] == "bytes 0-3/20"


@respx.mock
async def test_search_messages(settings: Settings, stub_auth: StubAuth) -> None:
    """search_messages issues a $search query and parses summaries."""
    route = respx.get(url__regex=r".*/me/messages\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "S1",
                        "subject": "Report Q3",
                        "from": {"emailAddress": {"address": "alice@corp.com"}},
                        "receivedDateTime": "2026-07-29T10:00:00Z",
                        "bodyPreview": "see attached",
                        "hasAttachments": True,
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        messages = await service.search_messages("report", top=5)
    assert len(messages) == 1
    assert messages[0].subject == "Report Q3"
    assert "%24search" in str(route.calls.last.request.url)


@respx.mock
async def test_move_and_archive_message(settings: Settings, stub_auth: StubAuth) -> None:
    """move_message posts destinationId; archive_message targets the Archive folder."""
    route = respx.post(f"{GRAPH}/me/messages/MSG/move").mock(return_value=httpx.Response(201, json={"id": "NEW"}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        moved = await service.move_message("MSG", "deleteditems")
        assert moved["id"] == "NEW"
        assert json.loads(route.calls.last.request.content)["destinationId"] == "deleteditems"
        await service.archive_message("MSG")
        assert json.loads(route.calls.last.request.content)["destinationId"] == "archive"


@respx.mock
async def test_list_messages(settings: Settings, stub_auth: StubAuth) -> None:
    """list_messages parses Graph values into summaries."""
    respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "A",
                        "subject": "Hello",
                        "from": {"emailAddress": {"address": "x@y.com"}},
                        "receivedDateTime": "2026-07-29T10:00:00Z",
                        "bodyPreview": "hi",
                        "hasAttachments": False,
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        messages = await service.list_messages(top=5)
    assert len(messages) == 1
    assert messages[0].sender == "x@y.com"


@respx.mock
async def test_mark_read(settings: Settings, stub_auth: StubAuth) -> None:
    """mark_read PATCHes isRead=True."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.mark_read("MSG", read=True)
    assert route.called
    assert json.loads(route.calls.last.request.content) == {"isRead": True}


@respx.mock
async def test_mark_unread(settings: Settings, stub_auth: StubAuth) -> None:
    """mark_read with read=False PATCHes isRead=False."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.mark_read("MSG", read=False)
    assert route.called
    assert json.loads(route.calls.last.request.content) == {"isRead": False}


@respx.mock
async def test_trash_message(settings: Settings, stub_auth: StubAuth) -> None:
    """trash_message delegates to move_message with deleteditems."""
    route = respx.post(f"{GRAPH}/me/messages/MSG/move").mock(return_value=httpx.Response(201, json={"id": "NEW"}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        result = await service.trash_message("MSG")
    assert result["id"] == "NEW"
    assert json.loads(route.calls.last.request.content)["destinationId"] == "deleteditems"


@respx.mock
async def test_flag_message(settings: Settings, stub_auth: StubAuth) -> None:
    """flag_message PATCHes the flag status."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.flag_message("MSG")
    assert json.loads(route.calls.last.request.content) == {"flag": {"flagStatus": "flagged"}}


@respx.mock
async def test_unflag_message(settings: Settings, stub_auth: StubAuth) -> None:
    """flag_message with unflag=True PATCHes notFlagged."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.flag_message("MSG", unflag=True)
    assert json.loads(route.calls.last.request.content) == {"flag": {"flagStatus": "notFlagged"}}


@respx.mock
async def test_list_messages_unread_filter(settings: Settings, stub_auth: StubAuth) -> None:
    """list_messages with unread_only=True adds $filter=isRead eq false."""
    route = respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        await service.list_messages(top=5, unread_only=True)
    url_str = str(route.calls.last.request.url)
    assert "isRead" in url_str or "%24filter" in url_str


@respx.mock
async def test_body_as_text_strips_html(settings: Settings, stub_auth: StubAuth) -> None:
    """body_as_text converts HTML body to plain text without tags."""
    respx.get(url__regex=r".*/me/messages/HTML1.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "HTML1",
                "body": {
                    "contentType": "HTML",
                    "content": "<html><body><p>Hello <b>world</b></p><p>Second line</p></body></html>",
                },
            },
        )
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        item = await service.get_message("HTML1")
    text = service.body_as_text(item)
    assert "<" not in text
    assert "Hello" in text
    assert "world" in text
    assert "Second line" in text


@respx.mock
async def test_body_as_text_passes_through_plain_text(settings: Settings, stub_auth: StubAuth) -> None:
    """body_as_text returns plain text bodies unchanged."""
    respx.get(url__regex=r".*/me/messages/TXT1.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "TXT1",
                "body": {"contentType": "Text", "content": "plain text content"},
            },
        )
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        item = await service.get_message("TXT1")
    assert service.body_as_text(item) == "plain text content"


@respx.mock
async def test_get_message_uses_eventmessage_cast_for_meeting(settings: Settings, stub_auth: StubAuth) -> None:
    """get_message uses the OData cast URL for eventMessageRequest items (not $select fields)."""
    meeting_payload = {
        "id": "MEET1",
        "@odata.type": "#microsoft.graph.eventMessageRequest",
        "startDateTime": {"dateTime": "2026-08-04T09:00:00.0000000", "timeZone": "Europe/Paris"},
        "endDateTime": {"dateTime": "2026-08-04T10:00:00.0000000", "timeZone": "Europe/Paris"},
        "body": {"contentType": "Text", "content": "join us"},
    }
    # First request: plain /me/messages/{id} to detect @odata.type
    respx.get(url__regex=r".*/me/messages/MEET1\?").mock(
        return_value=httpx.Response(200, json=meeting_payload)
    )
    # Second request: cast URL — must NOT contain startDateTime in $select
    cast_route = respx.get(url__regex=r".*/me/messages/MEET1/microsoft\.graph\.eventMessage.*").mock(
        return_value=httpx.Response(200, json=meeting_payload)
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        item = await service.get_message("MEET1")
    cast_url = str(cast_route.calls.last.request.url)
    assert "microsoft.graph.eventMessage" in cast_url
    assert "startDateTime" not in cast_url
    assert "endDateTime" not in cast_url
    assert item["@odata.type"] == "#microsoft.graph.eventMessageRequest"
    assert isinstance(item["startDateTime"], dict)


@respx.mock
async def test_list_messages_is_meeting_request_field(settings: Settings, stub_auth: StubAuth) -> None:
    """list_messages correctly maps @odata.type to is_meeting_request."""
    respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "INV1",
                        "subject": "Invite",
                        "@odata.type": "#microsoft.graph.eventMessageRequest",
                        "from": {"emailAddress": {"address": "host@corp.com"}},
                        "receivedDateTime": "2026-08-01T09:00:00Z",
                        "bodyPreview": "",
                        "hasAttachments": False,
                    },
                    {
                        "id": "REG1",
                        "subject": "Regular",
                        "from": {"emailAddress": {"address": "x@y.com"}},
                        "receivedDateTime": "2026-08-01T10:00:00Z",
                        "bodyPreview": "",
                        "hasAttachments": False,
                    },
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        service = MailService(settings, GraphClient(settings, stub_auth, client))
        messages = await service.list_messages(top=5)
    assert messages[0].is_meeting_request is True
    assert messages[1].is_meeting_request is False
