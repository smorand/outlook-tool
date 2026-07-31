"""Mail operations on Microsoft Graph: send (with attachments) and read."""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from models import Attachment, MailSummary, OutgoingMessage
from tracing import trace_span

if TYPE_CHECKING:
    from config import Settings
    from graph_client import GraphClient

logger = logging.getLogger(__name__)

_LIST_SELECT = "id,subject,from,receivedDateTime,bodyPreview,hasAttachments"
_READ_SELECT = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,hasAttachments,startDateTime,endDateTime"
)


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text converter using the stdlib parser."""

    __slots__ = ("_parts",)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        """Return concatenated text with blank lines collapsed."""
        text = "\n".join(self._parts)
        # Collapse runs of blank lines to a single blank line
        lines = [line.rstrip() for line in text.splitlines()]
        result: list[str] = []
        prev_blank = False
        for line in lines:
            is_blank = not line
            if is_blank and prev_blank:
                continue
            result.append(line)
            prev_blank = is_blank
        return "\n".join(result).strip()


def _html_to_text(content: str) -> str:
    """Strip HTML tags and return readable plain text."""
    parser = _TextExtractor()
    parser.feed(content)
    return parser.get_text()


class MailService:
    """Sends and reads mail via Microsoft Graph."""

    __slots__ = ("_graph", "_settings")

    def __init__(self, settings: Settings, graph: GraphClient) -> None:
        self._settings = settings
        self._graph = graph

    async def send(self, message: OutgoingMessage) -> None:
        """Send a message, choosing inline vs upload-session delivery by size.

        Small payloads use a single sendMail call. When attachments exceed the
        inline limit, a draft is created, attachments are uploaded (small ones
        directly, large ones via an upload session), then the draft is sent.
        """
        with trace_span("mail.send", attributes={"mail.attachments": len(message.attachments)}):
            if message.total_attachment_size <= self._settings.attachment_inline_limit:
                await self._send_inline(message)
            else:
                await self._send_via_draft(message)
            logger.info("sent message '%s' to %d recipient(s)", message.subject, len(message.to))

    async def _send_inline(self, message: OutgoingMessage) -> None:
        body = {"message": message.to_graph_message(include_attachments=True), "saveToSentItems": True}
        await self._graph.post("/me/sendMail", json=body)

    async def _send_via_draft(self, message: OutgoingMessage) -> None:
        draft = (
            await self._graph.post("/me/messages", json=message.to_graph_message(include_attachments=False))
        ).json()
        message_id = str(draft["id"])
        for attachment in message.attachments:
            await self._add_attachment(message_id, attachment)
        await self._graph.post(f"/me/messages/{message_id}/send")

    async def _add_attachment(self, message_id: str, attachment: Attachment) -> None:
        if attachment.size <= self._settings.attachment_inline_limit:
            await self._graph.post(f"/me/messages/{message_id}/attachments", json=attachment.to_file_attachment())
        else:
            await self._upload_large_attachment(message_id, attachment)

    async def _upload_large_attachment(self, message_id: str, attachment: Attachment) -> None:
        session_body = {
            "AttachmentItem": {
                "attachmentType": "file",
                "name": attachment.name,
                "size": attachment.size,
                "contentType": attachment.content_type,
            }
        }
        session = (
            await self._graph.post(f"/me/messages/{message_id}/attachments/createUploadSession", json=session_body)
        ).json()
        upload_url = str(session["uploadUrl"])
        data = attachment.content_bytes
        total = attachment.size
        chunk_size = self._settings.upload_chunk_size
        start = 0
        while start < total:
            end = min(start + chunk_size, total)
            chunk = data[start:end]
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end - 1}/{total}",
            }
            await self._graph.request(
                "PUT", upload_url, content=chunk, headers=headers, absolute=True, authenticated=False
            )
            start = end

    async def search_messages(self, query: str, *, top: int = 10) -> list[MailSummary]:
        """Full-text search across the mailbox via Graph $search.

        Accepts free text or KQL-style terms (e.g. 'from:alice subject:report').
        $search cannot be combined with $orderby; Graph returns results by relevance.
        """
        params = urlencode({"$search": f'"{query}"', "$top": top, "$select": _LIST_SELECT}, safe=" ,")
        response = await self._graph.get(f"/me/messages?{params}")
        items = response.json().get("value", [])
        return [MailSummary.from_graph(item) for item in items]

    async def move_message(self, message_id: str, destination: str) -> dict[str, Any]:
        """Move a message to another folder, returning the moved copy (new id).

        destination accepts a folder id or a well-known name (archive, deleteditems,
        inbox, junkemail, drafts, sentitems).
        """
        with trace_span("mail.move", attributes={"mail.destination": destination}):
            response = await self._graph.post(f"/me/messages/{message_id}/move", json={"destinationId": destination})
            moved: dict[str, Any] = response.json()
            logger.info("moved message %s to %s", message_id, destination)
            return moved

    async def archive_message(self, message_id: str) -> dict[str, Any]:
        """Archive a message (move to the well-known Archive folder)."""
        return await self.move_message(message_id, "archive")

    async def get_message(self, message_id: str) -> dict[str, Any]:
        """Fetch a single message with its full body.

        For eventMessageRequest items, startDateTime and endDateTime are included
        when returned by Graph (direct properties of the EventMessage resource).
        """
        query = urlencode({"$select": _READ_SELECT}, safe=" ,")
        response = await self._graph.get(f"/me/messages/{message_id}?{query}")
        item: dict[str, Any] = response.json()
        return item

    def body_as_text(self, item: dict[str, Any]) -> str:
        """Return the message body as plain text, stripping HTML if needed."""
        body = item.get("body") or {}
        content = str(body.get("content", "")) if isinstance(body, dict) else ""
        content_type = str(body.get("contentType", "")).lower() if isinstance(body, dict) else ""
        if content_type == "html":
            return _html_to_text(content)
        return content

    async def mark_read(self, message_id: str, *, read: bool = True) -> None:
        """Mark a message as read or unread."""
        with trace_span("mail.mark_read", attributes={"mail.read": read}):
            await self._graph.patch(f"/me/messages/{message_id}", json={"isRead": read})
            logger.info("marked message %s read=%s", message_id, read)

    async def trash_message(self, message_id: str) -> dict[str, Any]:
        """Move a message to the Deleted Items folder."""
        return await self.move_message(message_id, "deleteditems")

    async def flag_message(self, message_id: str, *, unflag: bool = False) -> None:
        """Set or clear the follow-up flag on a message."""
        status = "notFlagged" if unflag else "flagged"
        with trace_span("mail.flag", attributes={"mail.flag_status": status}):
            await self._graph.patch(f"/me/messages/{message_id}", json={"flag": {"flagStatus": status}})
            logger.info("flagged message %s status=%s", message_id, status)

    async def list_messages(
        self, *, top: int = 10, folder: str = "inbox", unread_only: bool = False
    ) -> list[MailSummary]:
        """List recent messages from a mail folder, newest first."""
        params: dict[str, str | int] = {
            "$top": top,
            "$select": _LIST_SELECT,
            "$orderby": "receivedDateTime desc",
        }
        if unread_only:
            params["$filter"] = "isRead eq false"
        query = urlencode(params, safe=" ,")
        response = await self._graph.get(f"/me/mailFolders/{folder}/messages?{query}")
        items = response.json().get("value", [])
        return [MailSummary.from_graph(item) for item in items]
