"""Mail operations on Microsoft Graph: send (with attachments) and read."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from models import Attachment, MailSummary, OutgoingMessage
from tracing import trace_span

if TYPE_CHECKING:
    from config import Settings
    from graph_client import GraphClient

logger = logging.getLogger(__name__)

_LIST_SELECT = "id,subject,from,receivedDateTime,bodyPreview,hasAttachments"
_READ_SELECT = "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,hasAttachments"


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

    async def list_messages(self, *, top: int = 10, folder: str = "inbox") -> list[MailSummary]:
        """List recent messages from a mail folder, newest first."""
        query = urlencode({"$top": top, "$select": _LIST_SELECT, "$orderby": "receivedDateTime desc"}, safe=" ,")
        response = await self._graph.get(f"/me/mailFolders/{folder}/messages?{query}")
        items = response.json().get("value", [])
        return [MailSummary.from_graph(item) for item in items]

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
        """Fetch a single message with its full body."""
        query = urlencode({"$select": _READ_SELECT}, safe=" ,")
        response = await self._graph.get(f"/me/messages/{message_id}?{query}")
        item: dict[str, Any] = response.json()
        return item
