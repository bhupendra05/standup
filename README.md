# standup

**Auto-generate your daily standup from git commits. One command, paste into Slack.**

Stop trying to remember what you did yesterday. `standup` reads your git history and writes your standup for you.

```bash
pip install standup
standup ~/Developer
```

[![CI](https://github.com/bhupendra05/standup/actions/workflows/ci.yml/badge.svg)](https://github.com/bhupendra05/standup/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

**Example output:**

```
📋 Standup — Wednesday, June 12

✅ Yesterday:
  [context-store]
    • feat: add SQLite backend with persistent storage
    • fix: TTL expiry check on search results
  [api-service]
    • PROJ-142: refactor auth middleware (PROJ-142)
    • chore: update dependencies

🔜 Today:
  • (add your plans here)

🚧 Blockers:
  • None

  5 commit(s) across 2 repo(s)
```

---

## Usage

```bash
# Scan current directory for git repos, show yesterday's commits
standup

# Scan all your projects under ~/Developer
standup ~/Developer

# Show today's commits so far
standup --today

# Last 3 days
standup --days 3

# Specific date
standup --date 2024-06-10

# Filter by author
standup --author your@email.com

# Markdown output (for GitHub/Notion)
standup --format markdown

# JSON output (for scripts/CI)
standup --format json

# Auto-copy to clipboard (macOS/Linux)
standup --copy

# Scan multiple locations
standup ~/Developer ~/work/company-repo
```

---

## How it works

1. **Finds** all git repos recursively under the paths you give it (up to 3 levels deep)
2. **Reads** all your commits from yesterday (filters by your `git config user.email`)
3. **Extracts** JIRA tickets (`PROJ-123`) and GitHub issues (`#42`) automatically
4. **Groups** commits by repo and deduplicates identical messages
5. **Formats** into a ready-to-paste standup with Yesterday / Today / Blockers sections

---

## Python API

```python
from standup import scan, StandupReport, format_text
from datetime import date, timedelta

commits = scan(
    paths=["~/Developer"],
    since=date.today() - timedelta(days=1),
    author="me@example.com",
)

report = StandupReport(date=date.today(), commits=commits, author=None)
print(format_text(report))
```

---

## Tips

```bash
# Add as a shell alias
alias standup='standup ~/Developer --copy'

# Run every morning automatically (macOS launchd or Linux cron)
# 9:00 AM daily: standup ~/Developer | pbcopy
```

---

## License

MIT © [Bhupendra Tale](https://github.com/bhupendra05)
