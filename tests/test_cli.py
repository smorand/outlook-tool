"""End-to-end CLI tests using Typer's runner with a mocked Graph and cached token."""

from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from typer.testing import CliRunner, Result

import outlook_tool
from auth import TokenSet
from outlook_tool import app

if TYPE_CHECKING:
    from pathlib import Path

GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
DEVICECODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"

runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate cwd/logs and seed a valid cached token; return the cache path."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / "token.json"
    cache.write_text(TokenSet(access_token="tok", expires_at=time.time() + 3600).model_dump_json())
    monkeypatch.setenv("OUTLOOK_TOOL_TOKEN_CACHE_PATH", str(cache))
    return cache


def test_version() -> None:
    """The version command prints the package version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


@respx.mock
def test_send_command(cli_env: Path) -> None:
    """send with a cached token issues a sendMail call and reports success."""
    route = respx.post(f"{GRAPH}/me/sendMail").mock(return_value=httpx.Response(202))
    result = runner.invoke(
        app,
        ["send", "--to", "seb.morand@gmail.com", "--subject", "Hi", "--body", "<b>x</b>"],
    )
    assert result.exit_code == 0, result.stdout
    assert route.called


def test_send_requires_body(cli_env: Path) -> None:
    """send without a body exits with code 2."""
    result = runner.invoke(app, ["send", "--to", "a@b.com", "--subject", "s"])
    assert result.exit_code == 2


@respx.mock
def test_draft_command(cli_env: Path) -> None:
    """draft with a cached token creates a message in Drafts and does not call /send."""
    draft_route = respx.post(f"{GRAPH}/me/messages").mock(
        return_value=httpx.Response(201, json={"id": "DRAFTX", "isDraft": True})
    )
    send_route = respx.post(f"{GRAPH}/me/messages/DRAFTX/send").mock(return_value=httpx.Response(202))
    result = runner.invoke(
        app,
        ["draft", "--to", "kelly@ibm.com", "--subject", "Re: RFP", "--body", "<p>Body</p>"],
    )
    assert result.exit_code == 0, result.stdout
    assert draft_route.called
    assert not send_route.called
    assert "Draft saved" in result.stdout


@respx.mock
def test_draft_requires_body(cli_env: Path) -> None:
    """draft without a body exits with code 2."""
    result = runner.invoke(app, ["draft", "--to", "a@b.com", "--subject", "s"])
    assert result.exit_code == 2


def test_draft_requires_to_or_reply_to(cli_env: Path) -> None:
    """draft without --to and without --reply-to exits with code 2."""
    result = runner.invoke(app, ["draft", "--subject", "s", "--body", "b"])
    assert result.exit_code == 2


def test_draft_reply_all_requires_reply_to(cli_env: Path) -> None:
    """--reply-all without --reply-to exits with code 2."""
    result = runner.invoke(app, ["draft", "--reply-all", "--to", "a@b.com", "--subject", "s", "--body", "b"])
    assert result.exit_code == 2


@respx.mock
def test_draft_reply_to_command(cli_env: Path) -> None:
    """draft --reply-to creates a threaded reply via createReply, prepending the body."""
    reply_route = respx.post(f"{GRAPH}/me/messages/ORIG1/createReply").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "REPLYX",
                "subject": "RE: Hello",
                "conversationId": "CONVX",
                "body": {"contentType": "HTML", "content": "<html><body>quoted original</body></html>"},
            },
        )
    )
    patch_route = respx.patch(f"{GRAPH}/me/messages/REPLYX").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["draft", "--reply-to", "ORIG1", "--body", "My reply text"])
    assert result.exit_code == 0, result.stdout
    assert reply_route.called
    assert patch_route.called
    sent = json.loads(patch_route.calls.last.request.content)
    assert "My reply text" in sent["body"]["content"]
    assert "quoted original" in sent["body"]["content"]
    assert "Draft saved" in result.stdout


@respx.mock
def test_draft_reply_all_command(cli_env: Path) -> None:
    """draft --reply-to --reply-all calls createReplyAll."""
    reply_all_route = respx.post(f"{GRAPH}/me/messages/ORIG1/createReplyAll").mock(
        return_value=httpx.Response(
            201, json={"id": "REPLYY", "body": {"contentType": "HTML", "content": "<body></body>"}}
        )
    )
    result = runner.invoke(app, ["draft", "--reply-to", "ORIG1", "--reply-all"])
    assert result.exit_code == 0, result.stdout
    assert reply_all_route.called


@respx.mock
def test_draft_reply_to_overrides_to(cli_env: Path) -> None:
    """draft --reply-to --to overrides the recipients Graph auto-populated."""
    respx.post(f"{GRAPH}/me/messages/ORIG1/createReply").mock(
        return_value=httpx.Response(
            201, json={"id": "REPLYZ", "body": {"contentType": "HTML", "content": "<body></body>"}}
        )
    )
    patch_route = respx.patch(f"{GRAPH}/me/messages/REPLYZ").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["draft", "--reply-to", "ORIG1", "--to", "override@corp.com", "--cc", "cc@corp.com"])
    assert result.exit_code == 0, result.stdout
    sent = json.loads(patch_route.calls.last.request.content)
    assert sent["toRecipients"][0]["emailAddress"]["address"] == "override@corp.com"
    assert sent["ccRecipients"][0]["emailAddress"]["address"] == "cc@corp.com"


@respx.mock
def test_draft_update_body_only(cli_env: Path) -> None:
    """draft-update --body PATCHes the message body and reports success."""
    route = respx.patch(f"{GRAPH}/me/messages/DRAFTU1").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["draft-update", "DRAFTU1", "--body", "<p>Corrected</p>"])
    assert result.exit_code == 0, result.stdout
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"body": {"contentType": "HTML", "content": "<p>Corrected</p>"}}
    assert "Draft updated" in result.stdout


@respx.mock
def test_draft_update_add_and_remove_attach(cli_env: Path, tmp_path: Path) -> None:
    """draft-update combines --add-attach and --remove-attach in one call."""
    new_file = tmp_path / "v2.pdf"
    new_file.write_bytes(b"PDF")
    add_route = respx.post(f"{GRAPH}/me/messages/DRAFTU2/attachments").mock(return_value=httpx.Response(201, json={}))
    remove_route = respx.delete(f"{GRAPH}/me/messages/DRAFTU2/attachments/ATT1").mock(return_value=httpx.Response(204))
    result = runner.invoke(
        app,
        ["draft-update", "DRAFTU2", "--add-attach", str(new_file), "--remove-attach", "ATT1"],
    )
    assert result.exit_code == 0, result.stdout
    assert add_route.called
    assert remove_route.called


def test_draft_update_requires_an_action(cli_env: Path) -> None:
    """draft-update without --body/--add-attach/--remove-attach exits with code 2."""
    result = runner.invoke(app, ["draft-update", "DRAFTU3"])
    assert result.exit_code == 2


@respx.mock
def test_draft_send_command(cli_env: Path) -> None:
    """draft-send POSTs to the /send action and reports success."""
    route = respx.post(f"{GRAPH}/me/messages/DRAFTU4/send").mock(return_value=httpx.Response(202))
    result = runner.invoke(app, ["draft-send", "DRAFTU4"])
    assert result.exit_code == 0, result.stdout
    assert route.called
    assert "Sent" in result.stdout


def test_login_required_without_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A command with no cached token exits with the login-required code."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OUTLOOK_TOOL_TOKEN_CACHE_PATH", str(tmp_path / "absent.json"))
    result = runner.invoke(app, ["mail", "list"])
    assert result.exit_code == 2


@respx.mock
def test_mail_list_command(cli_env: Path) -> None:
    """mail list renders received messages from Graph."""
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
    result = runner.invoke(app, ["mail", "list", "--top", "5"])
    assert result.exit_code == 0, result.stdout
    assert "Hello" in result.stdout


@respx.mock
def test_mail_list_json_has_full_id(cli_env: Path) -> None:
    """mail list --json emits parseable JSON with untruncated ids."""
    long_id = "A" * 60
    respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": long_id,
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
    result = runner.invoke(app, ["mail", "list", "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed[0]["id"] == long_id


@respx.mock
def test_cal_list_json_has_full_id(cli_env: Path) -> None:
    """cal list --json emits parseable JSON with untruncated ids."""
    long_id = "E" * 80
    respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": long_id,
                        "subject": "Nuit",
                        "start": {"dateTime": "2026-07-29T03:00:00.0000000", "timeZone": "Europe/Paris"},
                        "end": {"dateTime": "2026-07-29T03:30:00.0000000", "timeZone": "Europe/Paris"},
                        "organizer": {"emailAddress": {"address": "me@corp.com"}},
                    }
                ]
            },
        )
    )
    result = runner.invoke(
        app, ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00", "--json"]
    )
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed[0]["id"] == long_id


@respx.mock
def test_mail_search_command(cli_env: Path) -> None:
    """mail search renders matching messages."""
    respx.get(url__regex=r".*/me/messages\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "S1",
                        "subject": "Report Q3",
                        "from": {"emailAddress": {"address": "alice@corp.com"}},
                        "receivedDateTime": "2026-07-29T10:00:00Z",
                        "bodyPreview": "x",
                        "hasAttachments": False,
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["mail", "search", "report"])
    assert result.exit_code == 0, result.stdout
    assert "Report Q3" in result.stdout


@respx.mock
def test_mail_archive_command(cli_env: Path) -> None:
    """mail archive moves the message to Archive and prints the new id."""
    respx.post(f"{GRAPH}/me/messages/MSG/move").mock(return_value=httpx.Response(201, json={"id": "NEW"}))
    result = runner.invoke(app, ["mail", "archive", "MSG"])
    assert result.exit_code == 0, result.stdout
    assert "NEW" in result.stdout


@respx.mock
def test_mail_move_command(cli_env: Path) -> None:
    """mail move moves the message to an arbitrary folder."""
    route = respx.post(f"{GRAPH}/me/messages/MSG/move").mock(return_value=httpx.Response(201, json={"id": "NEW"}))
    result = runner.invoke(app, ["mail", "move", "MSG", "deleteditems"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content)["destinationId"] == "deleteditems"


@respx.mock
def test_mail_read_command(cli_env: Path) -> None:
    """mail read prints the message body."""
    respx.get(url__regex=r".*/me/messages/A.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "A",
                "subject": "Hello",
                "from": {"emailAddress": {"address": "x@y.com"}},
                "receivedDateTime": "2026-07-29T10:00:00Z",
                "body": {"contentType": "HTML", "content": "the-body"},
            },
        )
    )
    result = runner.invoke(app, ["mail", "read", "A"])
    assert result.exit_code == 0, result.stdout
    assert "the-body" in result.stdout


@respx.mock
def test_mail_attachments_command(cli_env: Path) -> None:
    """mail attachments lists attachment metadata."""
    respx.get(url__regex=r".*/me/messages/MSG/attachments\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "ATT1", "name": "report.docx", "contentType": "application/x", "size": 42, "isInline": False}
                ]
            },
        )
    )
    result = runner.invoke(app, ["mail", "attachments", "MSG"])
    assert result.exit_code == 0, result.stdout
    assert "report.docx" in result.stdout


@respx.mock
def test_mail_download_command(cli_env: Path) -> None:
    """mail download writes non-inline attachments to the output dir."""
    respx.get(url__regex=r".*/me/messages/MSG/attachments\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "ATT1", "name": "report.txt", "contentType": "text/plain", "size": 3, "isInline": False},
                    {"id": "IMG", "name": "logo.png", "contentType": "image/png", "size": 3, "isInline": True},
                ]
            },
        )
    )
    respx.get(url__regex=r".*/me/messages/MSG/attachments/ATT1$").mock(
        return_value=httpx.Response(
            200, json={"id": "ATT1", "name": "report.txt", "contentBytes": base64.b64encode(b"abc").decode()}
        )
    )
    out_dir = cli_env.parent
    result = runner.invoke(app, ["mail", "download", "MSG", "--out", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    saved = out_dir / "report.txt"
    assert saved.read_bytes() == b"abc"
    # inline image is skipped by default
    assert not (out_dir / "logo.png").exists()


@respx.mock
def test_mail_download_no_match(cli_env: Path) -> None:
    """mail download exits 1 when no attachment matches the filter."""
    respx.get(url__regex=r".*/me/messages/MSG/attachments\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "ATT1", "name": "report.txt", "contentType": "text/plain", "size": 3, "isInline": False}
                ]
            },
        )
    )
    result = runner.invoke(app, ["mail", "download", "MSG", "--name", "nomatch", "--out", str(cli_env.parent)])
    assert result.exit_code == 1


@respx.mock
def test_cal_add_and_list_and_update_and_delete(cli_env: Path) -> None:
    """cal add/list/update/delete drive the calendar service end to end."""
    add_route = respx.post(f"{GRAPH}/me/events").mock(return_value=httpx.Response(201, json={"id": "E1"}))
    respx.get(url__regex=r".*/me/calendarView.*").mock(
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
                        "categories": ["Red category"],
                    }
                ]
            },
        )
    )
    update_route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    respx.delete(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(204))

    add = runner.invoke(
        app,
        [
            "cal",
            "add",
            "--subject",
            "Nuit",
            "--start",
            "2026-07-29T03:00:00",
            "--end",
            "2026-07-29T03:30:00",
            "--attendee",
            "seb.morand@gmail.com",
            "--category",
            "Red category",
        ],
    )
    assert add.exit_code == 0, add.stdout
    assert "E1" in add.stdout
    assert json.loads(add_route.calls.last.request.content)["categories"] == ["Red category"]

    listed = runner.invoke(
        app, ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00", "--json"]
    )
    assert listed.exit_code == 0, listed.stdout
    listed_events = json.loads(listed.stdout)
    assert listed_events[0]["subject"] == "Nuit"
    assert listed_events[0]["categories"] == ["Red category"]

    updated = runner.invoke(app, ["cal", "update", "E1", "--subject", "Nuit v2", "--category", "Green category"])
    assert updated.exit_code == 0, updated.stdout
    assert json.loads(update_route.calls.last.request.content)["categories"] == ["Green category"]

    deleted = runner.invoke(app, ["cal", "delete", "E1"])
    assert deleted.exit_code == 0, deleted.stdout


def test_cal_update_requires_change(cli_env: Path) -> None:
    """cal update with no field to change exits with code 2."""
    result = runner.invoke(app, ["cal", "update", "E1"])
    assert result.exit_code == 2


@respx.mock
def test_cal_list_table_renders_categories_column(cli_env: Path) -> None:
    """cal list (table mode, no --json) renders successfully with a categories column."""
    respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "E1",
                        "subject": "Nuit",
                        "start": {"dateTime": "2026-07-29T03:00:00.0000000"},
                        "end": {"dateTime": "2026-07-29T03:30:00.0000000"},
                        "categories": ["Red category"],
                    }
                ]
            },
        )
    )
    result = runner.invoke(
        app,
        ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00"],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.stdout
    assert "categories" in result.stdout
    assert "Red category" in result.stdout


@respx.mock
def test_cal_update_category_repeatable(cli_env: Path) -> None:
    """cal update accepts multiple --category to assign several categories at once."""
    route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    result = runner.invoke(app, ["cal", "update", "E1", "--category", "Red category", "--category", "Green category"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content)["categories"] == ["Red category", "Green category"]


@respx.mock
def test_cal_update_clear_categories(cli_env: Path) -> None:
    """cal update --clear-categories sends an empty categories list."""
    route = respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
    result = runner.invoke(app, ["cal", "update", "E1", "--clear-categories"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content)["categories"] == []


def test_cal_update_category_and_clear_conflict(cli_env: Path) -> None:
    """cal update rejects --category combined with --clear-categories, without any network call."""
    result = runner.invoke(app, ["cal", "update", "E1", "--category", "Red category", "--clear-categories"])
    assert result.exit_code == 2
    assert "cannot pass both" in result.stdout


@respx.mock
def test_login_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """login runs the device-code flow and caches a token (browser open patched)."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / "token.json"
    monkeypatch.setenv("OUTLOOK_TOOL_TOKEN_CACHE_PATH", str(cache))
    monkeypatch.setattr(outlook_tool.webbrowser, "open", lambda _url: True)
    respx.post(DEVICECODE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "device_code": "DEV",
                "user_code": "ABCD",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 0,
            },
        )
    )
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "issued", "expires_in": 3600}))
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 0, result.stdout
    assert cache.exists()


# ---------------------------------------------------------------------------
# mail get
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_get_command(cli_env: Path) -> None:
    """mail get prints subject/from/body."""
    respx.get(url__regex=r".*/me/messages/MSG1.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "MSG1",
                "subject": "Get subject",
                "from": {"emailAddress": {"address": "alice@corp.com"}},
                "receivedDateTime": "2026-07-30T09:00:00Z",
                "body": {"contentType": "HTML", "content": "body-content"},
            },
        )
    )
    result = runner.invoke(app, ["mail", "get", "MSG1"])
    assert result.exit_code == 0, result.stdout
    assert "body-content" in result.stdout


@respx.mock
def test_mail_get_json(cli_env: Path) -> None:
    """mail get --json emits raw Graph JSON."""
    respx.get(url__regex=r".*/me/messages/MSG2.*").mock(
        return_value=httpx.Response(200, json={"id": "MSG2", "subject": "JS"})
    )
    result = runner.invoke(app, ["mail", "get", "MSG2", "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["id"] == "MSG2"


# ---------------------------------------------------------------------------
# mail mark-read / mark-unread
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_mark_read_command(cli_env: Path) -> None:
    """mail mark-read PATCHes isRead=true."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG3").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["mail", "mark-read", "MSG3"])
    assert result.exit_code == 0, result.stdout
    assert route.called
    assert json.loads(route.calls.last.request.content) == {"isRead": True}


@respx.mock
def test_mail_mark_unread_command(cli_env: Path) -> None:
    """mail mark-unread PATCHes isRead=false."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG4").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["mail", "mark-unread", "MSG4"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content) == {"isRead": False}


# ---------------------------------------------------------------------------
# mail trash
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_trash_command(cli_env: Path) -> None:
    """mail trash moves to deleteditems."""
    route = respx.post(f"{GRAPH}/me/messages/MSG5/move").mock(return_value=httpx.Response(201, json={"id": "MSG5-NEW"}))
    result = runner.invoke(app, ["mail", "trash", "MSG5"])
    assert result.exit_code == 0, result.stdout
    assert route.called
    assert json.loads(route.calls.last.request.content)["destinationId"] == "deleteditems"


# ---------------------------------------------------------------------------
# mail flag / unflag
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_flag_command(cli_env: Path) -> None:
    """mail flag sets flagStatus=flagged."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG6").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["mail", "flag", "MSG6"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content) == {"flag": {"flagStatus": "flagged"}}


@respx.mock
def test_mail_unflag_command(cli_env: Path) -> None:
    """mail flag --unflag sets flagStatus=notFlagged."""
    route = respx.patch(f"{GRAPH}/me/messages/MSG7").mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(app, ["mail", "flag", "MSG7", "--unflag"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(route.calls.last.request.content) == {"flag": {"flagStatus": "notFlagged"}}


# ---------------------------------------------------------------------------
# mail list --unread
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_list_unread_flag(cli_env: Path) -> None:
    """mail list --unread passes $filter=isRead eq false to Graph."""
    route = respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    result = runner.invoke(app, ["mail", "list", "--unread", "--top", "5"])
    assert result.exit_code == 0, result.stdout
    assert "%24filter" in str(route.calls.last.request.url) or "$filter" in str(route.calls.last.request.url)


# ---------------------------------------------------------------------------
# skill / skill learn
# ---------------------------------------------------------------------------


def test_skill_prints_embedded(cli_env: Path) -> None:
    """outlook-tool skill prints the embedded skill.md."""
    result = runner.invoke(app, ["skill"])
    assert result.exit_code == 0, result.stdout
    assert "outlook-tool" in result.stdout.lower()


def test_skill_includes_user_knowledge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """skill concatenates .md files from XDG_CONFIG_HOME/outlook-tool."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / "token.json"
    cache.write_text(TokenSet(access_token="tok", expires_at=time.time() + 3600).model_dump_json())
    monkeypatch.setenv("OUTLOOK_TOOL_TOKEN_CACHE_PATH", str(cache))

    config_dir = tmp_path / "config" / "outlook-tool"
    config_dir.mkdir(parents=True)
    (config_dir / "regles-tri.md").write_text("- règle test\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["skill"])
    assert result.exit_code == 0, result.stdout
    assert "règle test" in result.stdout


def test_skill_learn_appends_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """skill learn --rule appends a timestamped entry to regles-tri.md."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / "token.json"
    cache.write_text(TokenSet(access_token="tok", expires_at=time.time() + 3600).model_dump_json())
    monkeypatch.setenv("OUTLOOK_TOOL_TOKEN_CACHE_PATH", str(cache))

    config_dir = tmp_path / "config" / "outlook-tool"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["skill", "learn", "--rule", "always archive iec@us.ibm.com"])
    assert result.exit_code == 0, result.output
    rules_path = config_dir / "regles-tri.md"
    assert rules_path.exists()
    content = rules_path.read_text()
    assert "always archive iec@us.ibm.com" in content


def test_skill_learn_requires_rule(cli_env: Path) -> None:
    """skill learn without --rule exits with code 2."""
    result = runner.invoke(app, ["skill", "learn"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# cal accept
# ---------------------------------------------------------------------------


@respx.mock
def test_cal_accept_command(cli_env: Path) -> None:
    """cal accept POSTs to the accept endpoint and prints the confirmed status."""
    route = respx.post(f"{GRAPH}/me/events/E99/accept").mock(return_value=httpx.Response(202))
    respx.get(url__regex=rf"{GRAPH}/me/events/E99\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "E99",
                "subject": "Nuit",
                "start": {"dateTime": "2026-07-29T03:00:00"},
                "end": {"dateTime": "2026-07-29T03:30:00"},
                "responseStatus": {"response": "accepted"},
            },
        )
    )
    result = runner.invoke(app, ["cal", "accept", "E99"])
    assert result.exit_code == 0, result.stdout
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"sendResponse": False}
    assert "Accepted event id=E99 (confirmed status: Accepted)" in result.stdout


@respx.mock
def test_cal_accept_command_tentative_to_accepted(cli_env: Path) -> None:
    """SPEC-0004/E2E-017: accepting a tentatively-accepted invitation confirms Accepted."""
    respx.post(f"{GRAPH}/me/events/E98/accept").mock(return_value=httpx.Response(202))
    respx.get(url__regex=rf"{GRAPH}/me/events/E98\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "E98",
                "subject": "Nuit",
                "start": {"dateTime": "2026-07-29T03:00:00"},
                "end": {"dateTime": "2026-07-29T03:30:00"},
                "responseStatus": {"response": "accepted"},
            },
        )
    )
    result = runner.invoke(app, ["cal", "accept", "E98"])
    assert result.exit_code == 0, result.stdout
    assert "Accepted event id=E98 (confirmed status: Accepted)" in result.stdout


@respx.mock
def test_cal_accept_command_confirmation_fails(cli_env: Path) -> None:
    """SPEC-0004/E2E-010: accept succeeds even when the confirmation re-fetch fails."""
    respx.post(f"{GRAPH}/me/events/E97/accept").mock(return_value=httpx.Response(202))
    respx.get(url__regex=rf"{GRAPH}/me/events/E97\?.*").mock(return_value=httpx.Response(500))
    result = runner.invoke(app, ["cal", "accept", "E97"])
    assert result.exit_code == 0, result.stdout
    assert "Accepted event id=E97 (status could not be confirmed)" in result.stdout


@respx.mock
def test_cal_accept_command_unknown_id_fails(cli_env: Path) -> None:
    """SPEC-0004/E2E-011/E2E-MOD-002: accept on an unknown id still fails; re-fetch never called."""
    respx.post(f"{GRAPH}/me/events/E96/accept").mock(return_value=httpx.Response(404))
    refetch_route = respx.get(url__regex=rf"{GRAPH}/me/events/E96\?.*").mock(return_value=httpx.Response(200))
    result = runner.invoke(app, ["cal", "accept", "E96"])
    assert result.exit_code != 0
    assert "confirmed status" not in result.stdout
    assert "could not be confirmed" not in result.stdout
    assert not refetch_route.called


@respx.mock
def test_cal_accept_command_already_accepted(cli_env: Path) -> None:
    """SPEC-0004/E2E-016: re-accepting an already-accepted event still confirms Accepted."""
    respx.post(f"{GRAPH}/me/events/E95/accept").mock(return_value=httpx.Response(202))
    respx.get(url__regex=rf"{GRAPH}/me/events/E95\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "E95",
                "subject": "Nuit",
                "start": {"dateTime": "2026-07-29T03:00:00"},
                "end": {"dateTime": "2026-07-29T03:30:00"},
                "responseStatus": {"response": "accepted"},
            },
        )
    )
    result = runner.invoke(app, ["cal", "accept", "E95"])
    assert result.exit_code == 0, result.stdout
    assert "Accepted event id=E95 (confirmed status: Accepted)" in result.stdout


# ---------------------------------------------------------------------------
# cal deny
# ---------------------------------------------------------------------------


def _deny_event_json(event_id: str, response: str | None) -> dict[str, object]:
    """Build a Graph event payload with the given raw response status."""
    event: dict[str, object] = {
        "id": event_id,
        "subject": "Team sync",
        "start": {"dateTime": "2026-07-29T03:00:00"},
        "end": {"dateTime": "2026-07-29T03:30:00"},
    }
    if response is not None:
        event["responseStatus"] = {"response": response}
    return event


def _mock_deny(event_id: str, *, post: int = 202, get: httpx.Response | None = None) -> tuple[respx.Route, respx.Route]:
    """Mock the decline POST and the confirmation GET; return both routes."""
    post_route = respx.post(f"{GRAPH}/me/events/{event_id}/decline").mock(return_value=httpx.Response(post))
    get_route = respx.get(url__regex=rf"{GRAPH}/me/events/{event_id}\?.*").mock(
        return_value=get or httpx.Response(200, json=_deny_event_json(event_id, "declined"))
    )
    return post_route, get_route


@respx.mock
def test_cal_deny_unanswered(cli_env: Path) -> None:
    """SPEC-0005/E2E-001: deny prints the confirmed Declined status."""
    _mock_deny("E1")
    result = runner.invoke(app, ["cal", "deny", "E1"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E1 (confirmed status: Declined)" in result.stdout
    assert "could not be confirmed" not in result.stdout


@respx.mock
def test_cal_deny_accepted_event(cli_env: Path) -> None:
    """SPEC-0005/E2E-002: deny on a previously accepted event confirms Declined."""
    _mock_deny("E2")
    result = runner.invoke(app, ["cal", "deny", "E2"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E2 (confirmed status: Declined)" in result.stdout


@respx.mock
def test_cal_deny_unknown_id_fails(cli_env: Path) -> None:
    """SPEC-0005/E2E-003: unknown id fails, no confirmation text, no re-check."""
    _, get_route = _mock_deny("E96", post=404)
    result = runner.invoke(app, ["cal", "deny", "E96"])
    assert result.exit_code != 0
    assert "confirmed status" not in result.stdout
    assert "could not be confirmed" not in result.stdout
    assert not get_route.called


@respx.mock
def test_cal_deny_confirmation_fails(cli_env: Path) -> None:
    """SPEC-0005/E2E-004: a failing re-check still succeeds with the fallback message."""
    _mock_deny("E97", get=httpx.Response(500))
    result = runner.invoke(app, ["cal", "deny", "E97"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E97 (status could not be confirmed)" in result.stdout


@respx.mock
def test_cal_deny_refused_fails(cli_env: Path) -> None:
    """SPEC-0005/E2E-005: a refused operation fails with no success message and no re-check."""
    _, get_route = _mock_deny("E95", post=403)
    result = runner.invoke(app, ["cal", "deny", "E95"])
    assert result.exit_code != 0
    assert "Declined event id=" not in result.stdout
    assert not get_route.called


@respx.mock
def test_cal_deny_sends_no_response_email(cli_env: Path) -> None:
    """SPEC-0005/E2E-006: the decline request asks Graph not to notify the organizer."""
    post_route, _ = _mock_deny("E1")
    result = runner.invoke(app, ["cal", "deny", "E1"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(post_route.calls.last.request.content) == {"sendResponse": False}


@respx.mock
def test_cal_deny_already_declined(cli_env: Path) -> None:
    """SPEC-0005/E2E-007: denying an already declined event succeeds and confirms Declined."""
    _mock_deny("E3")
    result = runner.invoke(app, ["cal", "deny", "E3"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E3 (confirmed status: Declined)" in result.stdout


@respx.mock
def test_cal_deny_unrecognised_state(cli_env: Path) -> None:
    """SPEC-0005/E2E-008: an unknown state after the refusal reads 'Not yet responded'."""
    _mock_deny("E4", get=httpx.Response(200, json=_deny_event_json("E4", "somethingNew")))
    result = runner.invoke(app, ["cal", "deny", "E4"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E4 (confirmed status: Not yet responded)" in result.stdout


@respx.mock
def test_cal_deny_then_get_and_list_show_declined(cli_env: Path) -> None:
    """SPEC-0005/E2E-009: after a deny, cal get and cal list both show Declined."""
    _mock_deny("E2")
    respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(200, json={"value": [_deny_event_json("E2", "declined")]})
    )
    assert runner.invoke(app, ["cal", "deny", "E2"]).exit_code == 0
    got = runner.invoke(app, ["cal", "get", "E2", "--json"])
    assert json.loads(got.stdout)["response_status"] == "Declined"
    listed = runner.invoke(
        app, ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00", "--json"]
    )
    assert json.loads(listed.stdout)[0]["response_status"] == "Declined"


@respx.mock
def test_cal_deny_confirmation_fails_on_accepted_event(cli_env: Path) -> None:
    """SPEC-0005/E2E-010: re-check failure after denying an accepted event still succeeds."""
    _mock_deny("E5", get=httpx.Response(500))
    result = runner.invoke(app, ["cal", "deny", "E5"])
    assert result.exit_code == 0, result.stdout
    assert "Declined event id=E5 (status could not be confirmed)" in result.stdout


@respx.mock
def test_cal_deny_requires_id(cli_env: Path) -> None:
    """SPEC-0005/E2E-011: a missing id is a usage error and calls nothing."""
    result = runner.invoke(app, ["cal", "deny"])
    assert result.exit_code == 2
    assert not respx.calls


# ---------------------------------------------------------------------------
# mail read strips HTML
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_read_strips_html_tags(cli_env: Path) -> None:
    """mail read displays plain text, not raw HTML tags."""
    respx.get(url__regex=r".*/me/messages/HTML9.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "HTML9",
                "subject": "Invite",
                "from": {"emailAddress": {"address": "x@y.com"}},
                "receivedDateTime": "2026-08-01T09:00:00Z",
                "body": {"contentType": "HTML", "content": "<p>Hello <b>world</b></p>"},
            },
        )
    )
    result = runner.invoke(app, ["mail", "read", "HTML9"])
    assert result.exit_code == 0, result.stdout
    assert "Hello" in result.stdout
    assert "world" in result.stdout
    assert "<b>" not in result.stdout
    assert "<p>" not in result.stdout


# ---------------------------------------------------------------------------
# mail list --json includes is_meeting_request
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_list_json_includes_is_meeting_request(cli_env: Path) -> None:
    """mail list --json includes is_meeting_request for each message."""
    respx.get(url__regex=r".*/me/mailFolders/inbox/messages.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "INV2",
                        "subject": "Meeting invite",
                        "@odata.type": "#microsoft.graph.eventMessageRequest",
                        "from": {"emailAddress": {"address": "host@corp.com"}},
                        "receivedDateTime": "2026-08-01T09:00:00Z",
                        "bodyPreview": "",
                        "hasAttachments": False,
                    },
                    {
                        "id": "REG2",
                        "subject": "Normal mail",
                        "from": {"emailAddress": {"address": "x@y.com"}},
                        "receivedDateTime": "2026-08-01T10:00:00Z",
                        "bodyPreview": "",
                        "hasAttachments": False,
                    },
                ]
            },
        )
    )
    result = runner.invoke(app, ["mail", "list", "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    by_id = {m["id"]: m for m in parsed}
    assert by_id["INV2"]["is_meeting_request"] is True
    assert by_id["REG2"]["is_meeting_request"] is False


# ---------------------------------------------------------------------------
# mail get --json exposes startDateTime/endDateTime for eventMessageRequest
# ---------------------------------------------------------------------------


@respx.mock
def test_mail_get_json_exposes_meeting_datetimes(cli_env: Path) -> None:
    """mail get --json includes startDateTime and endDateTime for meeting invites."""
    meeting_payload = {
        "id": "MEET9",
        "@odata.type": "#microsoft.graph.eventMessageRequest",
        "subject": "Sync",
        "startDateTime": {"dateTime": "2026-08-04T09:00:00.0000000", "timeZone": "Europe/Paris"},
        "endDateTime": {"dateTime": "2026-08-04T10:00:00.0000000", "timeZone": "Europe/Paris"},
        "body": {"contentType": "Text", "content": "join us"},
    }
    # First: plain message fetch to detect @odata.type
    respx.get(url__regex=r".*/me/messages/MEET9\?").mock(return_value=httpx.Response(200, json=meeting_payload))
    # Second: cast URL fetch
    respx.get(url__regex=r".*/me/messages/MEET9/microsoft\.graph\.eventMessage.*").mock(
        return_value=httpx.Response(200, json=meeting_payload)
    )
    result = runner.invoke(app, ["mail", "get", "MEET9", "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["@odata.type"] == "#microsoft.graph.eventMessageRequest"
    assert parsed["startDateTime"]["dateTime"] == "2026-08-04T09:00:00.0000000"
    assert parsed["endDateTime"]["dateTime"] == "2026-08-04T10:00:00.0000000"


def _cal_event(event_id: str, response: str | None) -> dict[str, object]:
    """Build a Graph event resource shaped like a real one, optionally with a responseStatus."""
    event: dict[str, object] = {
        "id": event_id,
        "subject": "Nuit",
        "start": {"dateTime": "2026-07-29T03:00:00.0000000", "timeZone": "Europe/Paris"},
        "end": {"dateTime": "2026-07-29T03:30:00.0000000", "timeZone": "Europe/Paris"},
        "organizer": {"emailAddress": {"address": "me@corp.com"}},
        "location": {"displayName": "Home"},
    }
    if response is not None:
        event["responseStatus"] = {"response": response, "time": "2026-01-01T00:00:00Z"}
    return event


@pytest.fixture
def wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widen the shared rich console so table cells are not ellipsized under CliRunner."""
    monkeypatch.setattr(outlook_tool.console, "_width", 250)


def _invoke_cal_list(response: str, *extra: str) -> Result:
    respx.get(url__regex=r".*/me/calendarView.*").mock(
        return_value=httpx.Response(200, json={"value": [_cal_event("E1", response)]})
    )
    return runner.invoke(app, ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00", *extra])


@pytest.mark.parametrize(
    ("response", "label"),
    [
        ("accepted", "Accepted"),  # SPEC-0004/E2E-001
        ("notResponded", "Not yet responded"),  # SPEC-0004/E2E-002
        ("organizer", "Organizer"),  # SPEC-0004/E2E-003
    ],
)
@respx.mock
def test_cal_list_shows_response_status(cli_env: Path, wide_console: None, response: str, label: str) -> None:
    """SPEC-0004/E2E-001..003: cal list shows each event's response state in a status column."""
    result = _invoke_cal_list(response)
    assert result.exit_code == 0, result.stdout
    assert "status" in result.stdout
    assert label in result.stdout


@respx.mock
def test_cal_list_json_has_response_status(cli_env: Path) -> None:
    """SPEC-0004/E2E-004: cal list --json includes response_status."""
    result = _invoke_cal_list("tentativelyAccepted", "--json")
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)[0]["response_status"] == "Tentatively accepted"


@pytest.mark.parametrize(
    ("response", "label"),
    [
        ("tentativelyAccepted", "Tentatively accepted"),  # SPEC-0004/E2E-005
        ("declined", "Declined"),  # SPEC-0004/E2E-008
    ],
)
@respx.mock
def test_cal_get_shows_response_status(cli_env: Path, wide_console: None, response: str, label: str) -> None:
    """SPEC-0004/E2E-005, E2E-008: cal get prints a single-row table with the status."""
    respx.get(url__regex=rf"{GRAPH}/me/events/E1\?.*").mock(
        return_value=httpx.Response(200, json=_cal_event("E1", response))
    )
    result = runner.invoke(app, ["cal", "get", "E1"])
    assert result.exit_code == 0, result.stdout
    assert "status" in result.stdout
    assert label in result.stdout
    assert "Nuit" in result.stdout


@respx.mock
def test_cal_get_json_has_response_status(cli_env: Path) -> None:
    """SPEC-0004/E2E-006: cal get --json emits one object with response_status."""
    long_id = "E" * 80
    respx.get(url__regex=rf"{GRAPH}/me/events/{long_id}\?.*").mock(
        return_value=httpx.Response(200, json=_cal_event(long_id, "accepted"))
    )
    result = runner.invoke(app, ["cal", "get", long_id, "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["id"] == long_id
    assert parsed["response_status"] == "Accepted"


@pytest.mark.parametrize("status_code", [404, 403])  # SPEC-0004/E2E-007, E2E-015
@respx.mock
def test_cal_get_unknown_or_forbidden_id_fails(cli_env: Path, status_code: int) -> None:
    """SPEC-0004/E2E-007, E2E-015: an unknown or inaccessible id exits non-zero and prints no event."""
    route = respx.get(url__regex=rf"{GRAPH}/me/events/BAD\?.*").mock(
        return_value=httpx.Response(status_code, json={"error": {"code": "ErrorItemNotFound", "message": "nope"}})
    )
    result = runner.invoke(app, ["cal", "get", "BAD"])
    assert route.called
    assert result.exit_code != 0
    assert "status" not in result.stdout
    assert "response_status" not in result.stdout
    assert result.stdout.strip() == ""
