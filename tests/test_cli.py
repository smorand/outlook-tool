"""End-to-end CLI tests using Typer's runner with a mocked Graph and cached token."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from typer.testing import CliRunner

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
def test_cal_add_and_list_and_update_and_delete(cli_env: Path) -> None:
    """cal add/list/update/delete drive the calendar service end to end."""
    respx.post(f"{GRAPH}/me/events").mock(return_value=httpx.Response(201, json={"id": "E1"}))
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
                    }
                ]
            },
        )
    )
    respx.patch(f"{GRAPH}/me/events/E1").mock(return_value=httpx.Response(200, json={"id": "E1"}))
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
        ],
    )
    assert add.exit_code == 0, add.stdout
    assert "E1" in add.stdout

    listed = runner.invoke(app, ["cal", "list", "--start", "2026-07-29T00:00:00", "--end", "2026-07-30T00:00:00"])
    assert listed.exit_code == 0, listed.stdout
    assert "Nuit" in listed.stdout

    updated = runner.invoke(app, ["cal", "update", "E1", "--subject", "Nuit v2"])
    assert updated.exit_code == 0, updated.stdout

    deleted = runner.invoke(app, ["cal", "delete", "E1"])
    assert deleted.exit_code == 0, deleted.stdout


def test_cal_update_requires_change(cli_env: Path) -> None:
    """cal update with no field to change exits with code 2."""
    result = runner.invoke(app, ["cal", "update", "E1"])
    assert result.exit_code == 2


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
