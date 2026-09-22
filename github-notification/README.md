# GitHub Notification

English | [中文](README.zh-CN.md)

List, clear, or sweep GitHub notifications. Every command defaults to `--unread`; use `--all` to include read notifications. Optionally pass `OWNER/REPO` or a GitHub repository URL to limit the scope; omitting it selects all repositories.

| Command | Behavior |
| --- | --- |
| `list` | List notifications of every subject type without changing them. |
| `clear` | Mark selected notifications done. |
| `sweep` | Mark selected notifications done only for draft, merged, or closed PRs and closed issues. |

`--unread` and `--all` are mutually exclusive. `clear` and `sweep` make changes immediately; add `--dry-run` to preview them.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.11+ and the test dependencies).
- [GitHub CLI](https://cli.github.com/) with `gh api --slurp` support, authenticated with `gh auth login` or `GH_TOKEN` / `GITHUB_TOKEN`.

The Python code uses only the standard library. API calls run through asynchronous `gh` subprocesses in `asyncio.TaskGroup` tasks, with up to five concurrent requests for both subject lookups and clearing. Clearing starts after all pages and subject checks finish. If a task fails, the remaining tasks are cancelled and awaited before exiting.

## Usage

From this directory:

```bash
# List unread notifications (the first two commands are equivalent)
uv run github-notification list
uv run github-notification list --unread
uv run github-notification list --all

# Clear unread notifications, or include read notifications
uv run github-notification clear
uv run github-notification clear --all

# Preview resolved notifications, then sweep them
uv run github-notification sweep --dry-run
uv run github-notification sweep
uv run github-notification sweep --all

# Limit any command to a repository
uv run github-notification list --all OWNER/REPO
uv run github-notification clear --all --dry-run OWNER/REPO
uv run github-notification sweep https://github.com/OWNER/REPO
```

Run directly from GitHub without cloning:

```bash
uv run --python 3.11 https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification/github_notification.py list --unread
```

Clearing [marks threads done](https://docs.github.com/en/rest/activity/notifications#mark-a-thread-as-done), removing them from the notification inbox. A failed API call exits with an error; any earlier successful changes remain applied.

## Testing

```bash
uv run --locked pytest
```

Tests mock GitHub requests and never modify real notifications.
