"""standup — auto-generate daily standup from git commits."""
from .scanner import scan, Commit, find_git_repos
from .formatter import StandupReport, format_text, format_markdown, format_json

__all__ = [
    "scan", "Commit", "find_git_repos",
    "StandupReport", "format_text", "format_markdown", "format_json",
]
__version__ = "0.1.0"
