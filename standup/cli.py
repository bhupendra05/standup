"""CLI for standup."""
from __future__ import annotations
import json
import sys
from datetime import date, timedelta

import click

from .scanner import scan
from .formatter import StandupReport, format_text, format_markdown, format_json


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise click.BadParameter(f"Expected YYYY-MM-DD, got {s!r}")


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True), default=None)
@click.option("--yesterday", "period", flag_value="yesterday", default=True,
              help="Show yesterday's commits (default).")
@click.option("--today", "period", flag_value="today",
              help="Show today's commits so far.")
@click.option("--date", "specific_date", default=None, metavar="YYYY-MM-DD",
              help="Show commits on a specific date.")
@click.option("--days", default=1, show_default=True,
              help="Look back N days.")
@click.option("--author", "-a", default=None,
              help="Filter by author email (partial match). Defaults to your git config.")
@click.option("--format", "fmt", default="text",
              type=click.Choice(["text", "markdown", "json"]),
              show_default=True, help="Output format.")
@click.option("--copy", is_flag=True, help="Copy output to clipboard.")
@click.option("--depth", default=3, show_default=True,
              help="How deep to search for git repos inside given paths.")
def main(paths, period, specific_date, days, author, fmt, copy, depth):
    """
    Auto-generate your daily standup from git commits.

    PATHS: directories to scan. Defaults to current directory.
    Searches recursively for git repos up to --depth levels.

    \b
    Examples:
      standup                          # yesterday's commits in .
      standup ~/Developer              # scan all repos under ~/Developer
      standup --today                  # today's work so far
      standup --days 3                 # last 3 days
      standup --date 2024-06-10        # specific date
      standup --format markdown        # markdown output
      standup --copy                   # auto-copy to clipboard
    """
    scan_paths = list(paths) if paths else ["."]

    today = date.today()
    if specific_date:
        since = _parse_date(specific_date)
        until = since
    elif period == "today":
        since = until = today
    else:  # yesterday
        since = today - timedelta(days=days)
        until = today - timedelta(days=1)

    commits = scan(scan_paths, since=since, until=until, author=author, search_depth=depth)
    report = StandupReport(date=since, commits=commits, author=author)

    if fmt == "json":
        output = json.dumps(format_json(report), indent=2)
    elif fmt == "markdown":
        output = format_markdown(report)
    else:
        output = format_text(report)

    click.echo(output)

    if copy:
        try:
            import subprocess
            import platform
            if platform.system() == "Darwin":
                subprocess.run(["pbcopy"], input=output.encode(), check=True)
                click.echo("\n✅ Copied to clipboard!", err=True)
            elif platform.system() == "Linux":
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=output.encode(), check=True)
                click.echo("\n✅ Copied to clipboard!", err=True)
        except Exception as e:
            click.echo(f"\n⚠️  Could not copy: {e}", err=True)


if __name__ == "__main__":
    main()
