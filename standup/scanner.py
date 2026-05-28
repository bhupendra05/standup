"""Scan local git repos for commits from yesterday (or a given date)."""
from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class Commit:
    repo: str           # repo folder name
    repo_path: str      # full path
    hash: str
    subject: str
    body: str
    author: str
    timestamp: datetime
    branch: str
    files_changed: int = 0
    ticket: Optional[str] = None   # extracted JIRA/GH issue


_TICKET_RE = re.compile(
    r"\b([A-Z]{2,10}-\d+)\b|"          # JIRA: PROJECT-123
    r"#(\d{1,6})\b|"                   # GitHub: #123
    r"(?:fix|close|resolve)[sd]?\s+#(\d+)",  # "Fixes #123"
    re.IGNORECASE
)


def _extract_ticket(text: str) -> Optional[str]:
    m = _TICKET_RE.search(text)
    if m:
        return next(g for g in m.groups() if g)
    return None


def _git(*args, cwd: str) -> str:
    try:
        return subprocess.check_output(
            ["git"] + list(args),
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _is_git_repo(path: str) -> bool:
    return _git("rev-parse", "--git-dir", cwd=path) != ""


def _current_branch(path: str) -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path) or "unknown"


def _commits_on_date(repo_path: str, since: date, until: date, author: Optional[str]) -> List[Commit]:
    since_ts = datetime.combine(since, datetime.min.time()).isoformat()
    until_ts = datetime.combine(until + timedelta(days=1), datetime.min.time()).isoformat()

    fmt = "%H\x1f%s\x1f%b\x1f%ae\x1f%ai"
    args = [
        "log",
        f"--after={since_ts}",
        f"--before={until_ts}",
        "--format=" + fmt,
        "--no-merges",
    ]
    if author:
        args.append(f"--author={author}")

    raw = _git(*args, cwd=repo_path)
    if not raw:
        return []

    repo_name = Path(repo_path).name
    branch = _current_branch(repo_path)
    commits = []

    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) < 5:
            continue
        h, subject, body, email, ts_str = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            ts = datetime.fromisoformat(ts_str.strip())
        except ValueError:
            continue

        # Count files changed for this commit
        stat = _git("show", "--stat", "--format=", h, cwd=repo_path)
        files_changed = sum(1 for l in stat.splitlines() if l.strip() and "changed" not in l and "|" in l)

        ticket = _extract_ticket(subject) or _extract_ticket(body)
        commits.append(Commit(
            repo=repo_name,
            repo_path=repo_path,
            hash=h[:8],
            subject=subject.strip(),
            body=body.strip(),
            author=email,
            timestamp=ts,
            branch=branch,
            files_changed=files_changed,
            ticket=ticket,
        ))

    return commits


def find_git_repos(root: str, max_depth: int = 3) -> List[str]:
    """Walk directory tree looking for git repos up to max_depth."""
    root_path = Path(root).expanduser().resolve()
    repos = []

    def walk(p: Path, depth: int):
        if depth > max_depth:
            return
        if (p / ".git").exists():
            repos.append(str(p))
            return  # don't recurse into submodules
        try:
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    walk(child, depth + 1)
        except PermissionError:
            pass

    walk(root_path, 0)
    return repos


def scan(
    paths: List[str],
    since: Optional[date] = None,
    until: Optional[date] = None,
    author: Optional[str] = None,
    search_depth: int = 3,
) -> List[Commit]:
    """
    Scan git repos for commits.

    Args:
        paths: list of directories (individual repos OR parent dirs to search)
        since: start date (inclusive). Defaults to yesterday.
        until: end date (inclusive). Defaults to since.
        author: filter by author email substring. Defaults to git config user.email.
        search_depth: how deep to search for nested repos.
    """
    today = date.today()
    if since is None:
        since = today - timedelta(days=1)
    if until is None:
        until = since

    # Auto-detect git user email
    if author is None:
        try:
            author = subprocess.check_output(
                ["git", "config", "--global", "user.email"],
                text=True, stderr=subprocess.DEVNULL
            ).strip() or None
        except Exception:
            author = None

    all_commits: List[Commit] = []
    visited: set = set()

    for path in paths:
        path = str(Path(path).expanduser().resolve())
        if _is_git_repo(path):
            repos = [path]
        else:
            repos = find_git_repos(path, max_depth=search_depth)

        for repo in repos:
            if repo in visited:
                continue
            visited.add(repo)
            all_commits.extend(_commits_on_date(repo, since, until, author))

    # Sort by timestamp ascending
    all_commits.sort(key=lambda c: c.timestamp)
    return all_commits
