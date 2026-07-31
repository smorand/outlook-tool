"""CLI entry point for outlook-tool: send/read mail and manage calendar via Graph."""

from __future__ import annotations

import asyncio
import json
import logging
import webbrowser
from collections.abc import Awaitable, Callable
from pathlib import Path  # noqa: TC003 - runtime type used by Typer option resolution
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from auth import Authenticator, DeviceCodePrompt, LoginRequiredError
from config import Settings
from graph_client import GraphClient
from logging_config import setup_logging
from models import Attachment, CalendarEventInput, OutgoingMessage, Recipient
from services.calendar import CalendarService
from services.mail import MailService
from skill_cmd import register_skill_commands
from tracing import configure_tracing
from version import __version__

logger = logging.getLogger(__name__)
# soft_wrap avoids hard line breaks that would corrupt machine-readable output
# (message/event IDs) when stdout is not a TTY.
console = Console(soft_wrap=True)

app = typer.Typer(help="Send/read Outlook mail and manage calendar via Microsoft Graph (no client secret).")
mail_app = typer.Typer(help="Read mail.")
cal_app = typer.Typer(help="Manage calendar events.")
app.add_typer(mail_app, name="mail")
app.add_typer(cal_app, name="cal")
register_skill_commands(app)

type ServiceFn[T] = Callable[[Authenticator, MailService, CalendarService], Awaitable[T]]


async def _with_services[T](settings: Settings, fn: ServiceFn[T]) -> T:
    """Build the async dependency graph and run fn against it."""
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        authenticator = Authenticator(settings, client)
        graph = GraphClient(settings, authenticator, client)
        mail = MailService(settings, graph)
        calendar = CalendarService(settings, graph)
        return await fn(authenticator, mail, calendar)


def _run[T](settings: Settings, fn: ServiceFn[T]) -> T:
    """Synchronous bridge for Typer commands, with friendly auth errors."""
    try:
        return asyncio.run(_with_services(settings, fn))
    except LoginRequiredError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Increase verbosity: -v info, -vv debug (default: errors only)"
        ),
    ] = 0,
) -> None:
    """Configure logging/tracing and share settings with subcommands."""
    settings = Settings()
    setup_logging(app_name=settings.app_name, verbosity=verbose, log_dir=settings.log_dir)
    configure_tracing(app_name=settings.app_name, log_dir=settings.log_dir)
    ctx.obj = settings


def _render_mail_table(messages: list[Any], title: str) -> None:
    """Render a list of MailSummary as a rich table."""
    table = Table(title=title)
    table.add_column("received", style="cyan", no_wrap=True)
    table.add_column("from", style="magenta")
    table.add_column("subject")
    table.add_column("att", justify="center")
    table.add_column("id", style="dim", no_wrap=True)
    for msg in messages:
        table.add_row(msg.received, msg.sender, msg.subject, "yes" if msg.has_attachments else "", msg.id[:16])
    console.print(table)


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def login(ctx: typer.Context) -> None:
    """Run the interactive device-code login and cache the token."""
    settings: Settings = ctx.obj

    async def _do(authenticator: Authenticator, _mail: MailService, _cal: CalendarService) -> None:
        def on_prompt(prompt: DeviceCodePrompt) -> None:
            console.print(
                f"\nOpen [bold]{prompt.verification_uri}[/bold] and enter code [bold]{prompt.user_code}[/bold]"
            )
            webbrowser.open(prompt.verification_uri)
            console.print("Waiting for you to complete sign-in in the browser...")

        await authenticator.login(on_prompt)
        console.print("[green]Login OK, token cached.[/green]")

    _run(settings, _do)


@app.command()
def send(
    ctx: typer.Context,
    to: Annotated[list[str], typer.Option("--to", help="Recipient (repeatable). 'Name <a@b>' or 'a@b'")],
    subject: Annotated[str, typer.Option("--subject", "-s", help="Subject")],
    body: Annotated[str | None, typer.Option("--body", "-b", help="Body content")] = None,
    body_file: Annotated[Path | None, typer.Option("--body-file", help="Read body from file")] = None,
    cc: Annotated[list[str] | None, typer.Option("--cc", help="Cc recipient (repeatable)")] = None,
    bcc: Annotated[list[str] | None, typer.Option("--bcc", help="Bcc recipient (repeatable)")] = None,
    attach: Annotated[list[Path] | None, typer.Option("--attach", "-a", help="Attachment path (repeatable)")] = None,
    html: Annotated[bool, typer.Option("--html/--text", help="Body is HTML (default) or plain text")] = True,
) -> None:
    """Send an email (HTML by default, with optional attachments)."""
    settings: Settings = ctx.obj
    if body is None and body_file is None:
        console.print("[red]provide --body or --body-file[/red]")
        raise typer.Exit(code=2)
    content = body if body is not None else body_file.read_text(encoding="utf-8")  # type: ignore[union-attr]
    message = OutgoingMessage(
        subject=subject,
        body=content,
        is_html=html,
        to=[Recipient.parse(r) for r in to],
        cc=[Recipient.parse(r) for r in (cc or [])],
        bcc=[Recipient.parse(r) for r in (bcc or [])],
        attachments=[Attachment.from_path(p) for p in (attach or [])],
    )

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        await mail.send(message)
        console.print(f"[green]Sent[/green] '{subject}' to {', '.join(to)}")

    _run(settings, _do)


@mail_app.command("list")
def mail_list(
    ctx: typer.Context,
    top: Annotated[int, typer.Option("--top", "-n", help="Number of messages")] = 10,
    folder: Annotated[str, typer.Option("--folder", "-f", help="Mail folder")] = "inbox",
    unread: Annotated[bool, typer.Option("--unread", help="Only unread messages")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable JSON with full ids")] = False,
) -> None:
    """List recent messages in a folder."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        messages = await mail.list_messages(top=top, folder=folder, unread_only=unread)
        if as_json:
            typer.echo(json.dumps([m.model_dump() for m in messages], ensure_ascii=False))
            return
        title = f"{folder} ({'unread' if unread else 'latest'} {len(messages)})"
        _render_mail_table(messages, title)

    _run(settings, _do)


@mail_app.command("search")
def mail_search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search text or KQL terms, e.g. 'from:alice subject:report'")],
    top: Annotated[int, typer.Option("--top", "-n", help="Max results")] = 10,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable JSON with full ids")] = False,
) -> None:
    """Full-text search across the mailbox."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        messages = await mail.search_messages(query, top=top)
        if as_json:
            typer.echo(json.dumps([m.model_dump() for m in messages], ensure_ascii=False))
            return
        _render_mail_table(messages, f"search '{query}' ({len(messages)})")

    _run(settings, _do)


@mail_app.command("get")
def mail_get(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable JSON")] = False,
) -> None:
    """Fetch a single message with its full body."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        item = await mail.get_message(message_id)
        if as_json:
            # startDateTime/endDateTime are included by Graph for eventMessageRequest items;
            # they are already in item when present, so the dict is passed through as-is.
            typer.echo(json.dumps(item, ensure_ascii=False))
            return
        console.print(f"[bold]Subject:[/bold] {item.get('subject', '')}")
        sender = (item.get("from") or {}).get("emailAddress", {}).get("address", "")
        console.print(f"[bold]From:[/bold] {sender}")
        console.print(f"[bold]Received:[/bold] {item.get('receivedDateTime', '')}")
        console.print("\n" + mail.body_as_text(item))

    _run(settings, _do)


@mail_app.command("mark-read")
def mail_mark_read(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
) -> None:
    """Mark a message as read."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        await mail.mark_read(message_id, read=True)
        console.print(f"[green]Marked read[/green] id={message_id}")

    _run(settings, _do)


@mail_app.command("mark-unread")
def mail_mark_unread(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
) -> None:
    """Mark a message as unread."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        await mail.mark_read(message_id, read=False)
        console.print(f"[green]Marked unread[/green] id={message_id}")

    _run(settings, _do)


@mail_app.command("trash")
def mail_trash(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
) -> None:
    """Move a message to the Deleted Items folder."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        moved = await mail.trash_message(message_id)
        console.print(f"[green]Trashed[/green] new id={moved.get('id', '')}")

    _run(settings, _do)


@mail_app.command("flag")
def mail_flag(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
    unflag: Annotated[bool, typer.Option("--unflag", help="Clear the flag instead of setting it")] = False,
) -> None:
    """Set (or clear) the follow-up flag on a message."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        await mail.flag_message(message_id, unflag=unflag)
        action = "Unflagged" if unflag else "Flagged"
        console.print(f"[green]{action}[/green] id={message_id}")

    _run(settings, _do)


@mail_app.command("archive")
def mail_archive(ctx: typer.Context, message_id: Annotated[str, typer.Argument(help="Message id")]) -> None:
    """Archive a message (move to the Archive folder)."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        moved = await mail.archive_message(message_id)
        console.print(f"[green]Archived[/green] new id={moved.get('id', '')}")

    _run(settings, _do)


@mail_app.command("move")
def mail_move(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message id")],
    destination: Annotated[
        str, typer.Argument(help="Folder id or well-known name (archive, deleteditems, inbox, ...)")
    ],
) -> None:
    """Move a message to another folder."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        moved = await mail.move_message(message_id, destination)
        console.print(f"[green]Moved[/green] to {destination}, new id={moved.get('id', '')}")

    _run(settings, _do)


@mail_app.command("read")
def mail_read(ctx: typer.Context, message_id: Annotated[str, typer.Argument(help="Message id")]) -> None:
    """Show a message with its body as plain text (alias for mail get)."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, mail: MailService, _cal: CalendarService) -> None:
        item = await mail.get_message(message_id)
        console.print(f"[bold]Subject:[/bold] {item.get('subject', '')}")
        sender = (item.get("from") or {}).get("emailAddress", {}).get("address", "")
        console.print(f"[bold]From:[/bold] {sender}")
        console.print(f"[bold]Received:[/bold] {item.get('receivedDateTime', '')}")
        console.print("\n" + mail.body_as_text(item))

    _run(settings, _do)


@cal_app.command("list")
def cal_list(
    ctx: typer.Context,
    start: Annotated[str, typer.Option("--start", help="Window start, ISO 8601")],
    end: Annotated[str, typer.Option("--end", help="Window end, ISO 8601")],
    tz: Annotated[str, typer.Option("--tz", help="Time zone")] = "Europe/Paris",
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable JSON with full ids")] = False,
) -> None:
    """List events in a time window."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, _mail: MailService, cal: CalendarService) -> None:
        events = await cal.list_events(start=start, end=end, time_zone=tz)
        if as_json:
            typer.echo(json.dumps([e.model_dump() for e in events], ensure_ascii=False))
            return
        table = Table(title=f"events {start} -> {end}")
        table.add_column("start", style="cyan", no_wrap=True)
        table.add_column("end", style="cyan", no_wrap=True)
        table.add_column("subject")
        table.add_column("location")
        table.add_column("id", style="dim", no_wrap=True)
        for event in events:
            table.add_row(event.start, event.end, event.subject, event.location, event.id[:16])
        console.print(table)

    _run(settings, _do)


@cal_app.command("add")
def cal_add(
    ctx: typer.Context,
    subject: Annotated[str, typer.Option("--subject", "-s", help="Event subject")],
    start: Annotated[str, typer.Option("--start", help="Start, ISO 8601 local (e.g. 2026-07-29T03:00:00)")],
    end: Annotated[str, typer.Option("--end", help="End, ISO 8601 local")],
    tz: Annotated[str, typer.Option("--tz", help="Time zone")] = "Europe/Paris",
    location: Annotated[str | None, typer.Option("--location", help="Location")] = None,
    body: Annotated[str | None, typer.Option("--body", help="Event body")] = None,
    attendee: Annotated[list[str] | None, typer.Option("--attendee", help="Attendee (repeatable)")] = None,
    show_as: Annotated[str | None, typer.Option("--show-as", help="Status: free|tentative|busy|oof|workingElsewhere|unknown")] = None,
) -> None:
    """Create a calendar event."""
    settings: Settings = ctx.obj
    event = CalendarEventInput(
        subject=subject,
        start=start,
        end=end,
        time_zone=tz,
        location=location,
        body=body,
        attendees=[Recipient.parse(a) for a in (attendee or [])],
        show_as=show_as,
    )

    async def _do(_auth: Authenticator, _mail: MailService, cal: CalendarService) -> None:
        created = await cal.create_event(event)
        console.print(f"[green]Created[/green] '{subject}' id={created.get('id', '')}")

    _run(settings, _do)


@cal_app.command("update")
def cal_update(
    ctx: typer.Context,
    event_id: Annotated[str, typer.Argument(help="Event id")],
    subject: Annotated[str | None, typer.Option("--subject", "-s")] = None,
    start: Annotated[str | None, typer.Option("--start")] = None,
    end: Annotated[str | None, typer.Option("--end")] = None,
    tz: Annotated[str, typer.Option("--tz")] = "Europe/Paris",
    show_as: Annotated[str | None, typer.Option("--show-as", help="Status: free|tentative|busy|oof|workingElsewhere|unknown")] = None,
) -> None:
    """Update fields on an existing event."""
    settings: Settings = ctx.obj
    changes: dict[str, Any] = {}
    if subject is not None:
        changes["subject"] = subject
    if start is not None:
        changes["start"] = {"dateTime": start, "timeZone": tz}
    if end is not None:
        changes["end"] = {"dateTime": end, "timeZone": tz}
    if show_as is not None:
        changes["showAs"] = show_as
    if not changes:
        console.print("[red]nothing to update; pass --subject/--start/--end/--show-as[/red]")
        raise typer.Exit(code=2)

    async def _do(_auth: Authenticator, _mail: MailService, cal: CalendarService) -> None:
        await cal.update_event(event_id, changes)
        console.print(f"[green]Updated[/green] id={event_id}")

    _run(settings, _do)


@cal_app.command("delete")
def cal_delete(ctx: typer.Context, event_id: Annotated[str, typer.Argument(help="Event id")]) -> None:
    """Delete an event by id."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, _mail: MailService, cal: CalendarService) -> None:
        await cal.delete_event(event_id)
        console.print(f"[green]Deleted[/green] id={event_id}")

    _run(settings, _do)


@cal_app.command("accept")
def cal_accept(ctx: typer.Context, event_id: Annotated[str, typer.Argument(help="Event id")]) -> None:
    """Accept a meeting invitation (no response email sent)."""
    settings: Settings = ctx.obj

    async def _do(_auth: Authenticator, _mail: MailService, cal: CalendarService) -> None:
        await cal.accept_event(event_id)
        console.print(f"[green]Accepted[/green] event id={event_id}")

    _run(settings, _do)


if __name__ == "__main__":
    app()
