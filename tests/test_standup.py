"""Tests for standup — scanner and formatter."""
import os
import subprocess
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import pytest

from standup.scanner import scan, find_git_repos, _extract_ticket, Commit
from standup.formatter import (
    StandupReport, format_text, format_markdown, format_json, _dedup
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path, name: str = "testrepo") -> Path:
    """Create a minimal git repo with one commit."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"],
                   cwd=repo, check=True, capture_output=True)
    (repo / "readme.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit"],
                   cwd=repo, check=True, capture_output=True)
    return repo


def _make_commit(repo: Path, message: str, filename: str = None) -> None:
    fname = filename or f"file_{message[:5].replace(' ', '_')}.txt"
    (repo / fname).write_text(message)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message],
                   cwd=repo, check=True, capture_output=True)


def _make_commit_obj(subject: str, repo: str = "myrepo") -> Commit:
    return Commit(
        repo=repo, repo_path="/tmp/" + repo,
        hash="abc12345", subject=subject, body="",
        author="test@example.com",
        timestamp=datetime.now(timezone.utc),
        branch="main",
    )


# ---------------------------------------------------------------------------
# _extract_ticket
# ---------------------------------------------------------------------------

class TestExtractTicket:
    def test_jira_style(self):
        assert _extract_ticket("PROJ-123: fix login") == "PROJ-123"

    def test_github_issue(self):
        assert _extract_ticket("Fix #42 null pointer") == "42"

    def test_fixes_syntax(self):
        result = _extract_ticket("closes #99 memory leak")
        assert result == "99"

    def test_no_ticket(self):
        assert _extract_ticket("refactor login module") is None

    def test_multiple_picks_first(self):
        result = _extract_ticket("PROJ-1 and PROJ-2")
        assert result in ("PROJ-1", "PROJ-2")


# ---------------------------------------------------------------------------
# find_git_repos
# ---------------------------------------------------------------------------

class TestFindGitRepos:
    def test_finds_direct_repo(self, tmp_path):
        repo = _make_repo(tmp_path)
        found = find_git_repos(str(repo))
        assert str(repo) in found

    def test_finds_nested_repo(self, tmp_path):
        repo = _make_repo(tmp_path)
        found = find_git_repos(str(tmp_path))
        assert str(repo) in found

    def test_no_repos_returns_empty(self, tmp_path):
        (tmp_path / "empty_dir").mkdir()
        found = find_git_repos(str(tmp_path / "empty_dir"))
        assert found == []

    def test_depth_limit(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        repo_path = deep / "repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        # depth=2 should not find repo 4 levels deep
        found = find_git_repos(str(tmp_path), max_depth=2)
        assert str(repo_path) not in found


# ---------------------------------------------------------------------------
# scan()
# ---------------------------------------------------------------------------

class TestScan:
    def test_scan_finds_today_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        _make_commit(repo, "add feature X")
        today = date.today()
        commits = scan([str(repo)], since=today, until=today, author=None)
        subjects = [c.subject for c in commits]
        assert any("add feature X" in s for s in subjects)

    def test_scan_author_filter(self, tmp_path):
        repo = _make_repo(tmp_path)
        _make_commit(repo, "fix: something important")
        today = date.today()
        # filter by wrong author → no commits
        commits = scan([str(repo)], since=today, until=today,
                       author="nobody@nowhere.com")
        assert commits == []

    def test_scan_returns_commit_objects(self, tmp_path):
        repo = _make_repo(tmp_path)
        today = date.today()
        commits = scan([str(repo)], since=today, until=today, author=None)
        for c in commits:
            assert isinstance(c, Commit)

    def test_scan_commit_has_repo_name(self, tmp_path):
        repo = _make_repo(tmp_path, "myproject")
        today = date.today()
        commits = scan([str(repo)], since=today, until=today, author=None)
        if commits:
            assert commits[0].repo == "myproject"

    def test_scan_no_commits_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Look for commits 10 years ago
        past = date(2010, 1, 1)
        commits = scan([str(repo)], since=past, until=past, author=None)
        assert commits == []

    def test_scan_multiple_repos(self, tmp_path):
        repo1 = _make_repo(tmp_path, "repo1")
        repo2 = _make_repo(tmp_path, "repo2")
        _make_commit(repo1, "work in repo1")
        _make_commit(repo2, "work in repo2")
        today = date.today()
        commits = scan([str(tmp_path)], since=today, until=today, author=None)
        repos_found = {c.repo for c in commits}
        assert "repo1" in repos_found
        assert "repo2" in repos_found


# ---------------------------------------------------------------------------
# _dedup
# ---------------------------------------------------------------------------

class TestDedup:
    def test_removes_duplicate_subject(self):
        c1 = _make_commit_obj("fix login bug")
        c2 = _make_commit_obj("fix login bug")
        result = _dedup([c1, c2])
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        c1 = _make_commit_obj("Fix Login Bug")
        c2 = _make_commit_obj("fix login bug")
        assert len(_dedup([c1, c2])) == 1

    def test_keeps_different_commits(self):
        commits = [_make_commit_obj(f"commit {i}") for i in range(5)]
        assert len(_dedup(commits)) == 5


# ---------------------------------------------------------------------------
# StandupReport
# ---------------------------------------------------------------------------

class TestStandupReport:
    def _report(self, *subjects):
        commits = [_make_commit_obj(s) for s in subjects]
        return StandupReport(date=date.today(), commits=commits, author="test@x.com")

    def test_total_commits(self):
        r = self._report("a", "b", "c")
        assert r.total_commits == 3

    def test_repos_touched_single(self):
        r = self._report("a", "b")
        assert r.repos_touched == 1

    def test_by_repo_groups_correctly(self):
        c1 = _make_commit_obj("feat A", repo="repo1")
        c2 = _make_commit_obj("feat B", repo="repo2")
        r = StandupReport(date=date.today(), commits=[c1, c2], author=None)
        assert "repo1" in r.by_repo
        assert "repo2" in r.by_repo

    def test_empty_report(self):
        r = StandupReport(date=date.today(), commits=[], author=None)
        assert r.total_commits == 0
        assert r.repos_touched == 0


# ---------------------------------------------------------------------------
# format_text
# ---------------------------------------------------------------------------

class TestFormatText:
    def _report(self, subjects=None):
        commits = [_make_commit_obj(s) for s in (subjects or [])]
        return StandupReport(date=date.today(), commits=commits, author=None)

    def test_contains_yesterday_header(self):
        out = format_text(self._report())
        assert "Yesterday" in out

    def test_no_commits_message(self):
        out = format_text(self._report([]))
        assert "No commits" in out

    def test_commit_subject_in_output(self):
        out = format_text(self._report(["fix login bug"]))
        assert "fix login bug" in out

    def test_contains_today_section(self):
        out = format_text(self._report(), tomorrow_hint=True)
        assert "Today" in out

    def test_no_today_section_when_disabled(self):
        out = format_text(self._report(), tomorrow_hint=False)
        assert "Today" not in out

    def test_ticket_shown(self):
        c = _make_commit_obj("PROJ-42: fix login")
        c.ticket = "PROJ-42"
        r = StandupReport(date=date.today(), commits=[c], author=None)
        assert "PROJ-42" in format_text(r)


# ---------------------------------------------------------------------------
# format_markdown
# ---------------------------------------------------------------------------

class TestFormatMarkdown:
    def test_has_markdown_headers(self):
        r = StandupReport(date=date.today(), commits=[], author=None)
        out = format_markdown(r)
        assert "##" in out

    def test_commit_in_list_item(self):
        c = _make_commit_obj("add new feature")
        r = StandupReport(date=date.today(), commits=[c], author=None)
        out = format_markdown(r)
        assert "- add new feature" in out


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------

class TestFormatJson:
    def test_returns_dict(self):
        r = StandupReport(date=date.today(), commits=[], author=None)
        out = format_json(r)
        assert isinstance(out, dict)

    def test_has_required_keys(self):
        r = StandupReport(date=date.today(), commits=[], author=None)
        out = format_json(r)
        for key in ("date", "total_commits", "repos_touched", "by_repo"):
            assert key in out

    def test_commit_serialized(self):
        c = _make_commit_obj("fix bug", repo="myrepo")
        r = StandupReport(date=date.today(), commits=[c], author=None)
        out = format_json(r)
        assert "myrepo" in out["by_repo"]
        assert out["by_repo"]["myrepo"][0]["subject"] == "fix bug"
