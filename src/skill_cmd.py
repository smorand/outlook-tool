"""skill / skill learn commands for outlook-mail.

Mirrors the pattern from email-manager:
  - `outlook-mail skill`        → print embedded skill.md + concat user knowledge files
  - `outlook-mail skill learn`  → append a rule to ~/.config/outlook-mail/regles-tri.md
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

_SKILL_CONFIG_DIR = "outlook-mail"
_SKILL_RULES_FILE = "regles-tri.md"
_DIR_PERM = 0o755
_FILE_PERM = 0o644


def _skill_config_dir() -> Path:
    """Return ~/.config/outlook-mail (or $XDG_CONFIG_HOME/outlook-mail).

    Deliberately avoids os.path.expanduser("~/Library/Application Support") on
    macOS — same rationale as email-manager.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg) / _SKILL_CONFIG_DIR
    return Path.home() / ".config" / _SKILL_CONFIG_DIR


def _load_embedded_skill() -> str:
    """Return the content of skill.md bundled alongside this module."""
    skill_file = Path(__file__).parent / "skill.md"
    return skill_file.read_text(encoding="utf-8")


def _iter_knowledge_files(config_dir: Path) -> list[Path]:
    """Return sorted .md files in config_dir (non-recursive)."""
    if not config_dir.is_dir():
        return []
    return sorted(p for p in config_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md")


def register_skill_commands(app: typer.Typer) -> None:
    """Attach `skill` and `skill learn` to *app*."""
    skill_app = typer.Typer(help="Print the agent skill (mode d'emploi for AI agents).")
    app.add_typer(skill_app, name="skill")

    @skill_app.callback(invoke_without_command=True)
    def _skill_root(ctx: typer.Context) -> None:
        """Print embedded skill.md, then append user knowledge files."""
        if ctx.invoked_subcommand is not None:
            return

        typer.echo(_load_embedded_skill())

        config_dir = _skill_config_dir()
        knowledge_files = _iter_knowledge_files(config_dir)
        if not knowledge_files:
            return

        typer.echo()
        typer.echo("---")
        typer.echo()
        typer.echo(f"# Connaissance utilisateur (depuis {config_dir})")
        typer.echo()
        for path in knowledge_files:
            try:
                content = path.read_text(encoding="utf-8").rstrip("\n")
            except OSError as exc:
                print(f"Warning: cannot read {path}: {exc}", file=sys.stderr)
                continue
            typer.echo(f"## {path.name}")
            typer.echo()
            typer.echo(content)
            typer.echo()

    @skill_app.command("learn")
    def _skill_learn(
        rule: Annotated[str, typer.Option("--rule", help="Rule text to append (required)")],
    ) -> None:
        """Persist a sorting rule learned from the user."""
        rule = rule.strip()
        if not rule:
            typer.echo("Error: --rule must not be empty", err=True)
            raise typer.Exit(code=2)

        config_dir = _skill_config_dir()
        config_dir.mkdir(mode=_DIR_PERM, parents=True, exist_ok=True)

        rules_path = config_dir / _SKILL_RULES_FILE
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{stamp}] {rule}\n"

        with rules_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        rules_path.chmod(_FILE_PERM)

        typer.echo(f"Rule appended to {rules_path}", err=True)
