"""Format commit list into a standup report."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from .scanner import Commit


@dataclass
class StandupReport:
    date: date
    commits: List[Commit]
    author: Optional[str]

    # grouped
    by_repo: dict = field(default_factory=dict)

    def __post_init__(self):
        for c in self.commits:
            self.by_repo.setdefault(c.repo, []).append(c)

    @property
    def total_commits(self) -> int:
        return len(self.commits)

    @property
    def repos_touched(self) -> int:
        return len(self.by_repo)


def _dedup(commits: List[Commit]) -> List[Commit]:
    seen, out = set(), []
    for c in commits:
        key = c.subject.lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def format_text(report: StandupReport, tomorrow_hint: bool = True) -> str:
    """Plain-text standup — paste directly into Slack/Teams/email."""
    lines = []
    d = report.date.strftime("%A, %B %d")
    lines.append(f"📋 Standup — {d}")
    lines.append("")

    if not report.commits:
        lines.append("✅ Yesterday:")
        lines.append("  • No commits found. (Was it a meeting day? 😅)")
    else:
        lines.append("✅ Yesterday:")
        for repo, commits in sorted(report.by_repo.items()):
            lines.append(f"  [{repo}]")
            for c in _dedup(commits):
                ticket = f" ({c.ticket})" if c.ticket else ""
                lines.append(f"    • {c.subject}{ticket}")

    lines.append("")
    if tomorrow_hint:
        lines.append("🔜 Today:")
        lines.append("  • (add your plans here)")
        lines.append("")
        lines.append("🚧 Blockers:")
        lines.append("  • None")

    lines.append("")
    lines.append(f"  {report.total_commits} commit(s) across {report.repos_touched} repo(s)")
    return "\n".join(lines)


def format_markdown(report: StandupReport) -> str:
    """Markdown format — good for GitHub/GitLab PR descriptions or Notion."""
    lines = []
    d = report.date.strftime("%A, %B %d")
    lines.append(f"## 📋 Standup — {d}")
    lines.append("")
    lines.append("### ✅ Yesterday")
    lines.append("")

    if not report.commits:
        lines.append("- No commits found.")
    else:
        for repo, commits in sorted(report.by_repo.items()):
            lines.append(f"**{repo}**")
            for c in _dedup(commits):
                ticket = f" `{c.ticket}`" if c.ticket else ""
                lines.append(f"- {c.subject}{ticket}")
            lines.append("")

    lines.append("### 🔜 Today")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("### 🚧 Blockers")
    lines.append("")
    lines.append("- None")
    return "\n".join(lines)


def format_json(report: StandupReport) -> dict:
    return {
        "date": report.date.isoformat(),
        "total_commits": report.total_commits,
        "repos_touched": report.repos_touched,
        "by_repo": {
            repo: [
                {
                    "hash": c.hash,
                    "subject": c.subject,
                    "ticket": c.ticket,
                    "files_changed": c.files_changed,
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in commits
            ]
            for repo, commits in report.by_repo.items()
        },
    }
