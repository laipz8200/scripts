# GitHub Notification

English | [中文](README.zh-CN.md)

Preview and clear GitHub notifications. By default, matches unread notifications for draft, merged, or closed pull requests and closed issues in one repository. `--clear-all` matches every notification, including read notifications and other subject types. Changes require `--apply`.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.11+ and the test dependencies).
- [GitHub CLI](https://cli.github.com/) with `gh api --slurp` support, authenticated with `gh auth login` or `GH_TOKEN` / `GITHUB_TOKEN`.

The Python code uses only the standard library. API calls run through asynchronous `gh` subprocesses, with up to five concurrent subject lookups. Notifications are marked done sequentially after all pages and subject checks finish.

## Usage

From this directory:

```bash
# Preview resolved unread notifications
uv run github-notification OWNER/REPO
uv run github-notification https://github.com/OWNER/REPO

# Mark matching notifications done
uv run github-notification --apply OWNER/REPO

# Preview every notification in one repository, then clear them
uv run github-notification --clear-all OWNER/REPO
uv run github-notification --clear-all --apply OWNER/REPO

# Preview every notification across all repositories, then clear them
uv run github-notification --clear-all
uv run github-notification --clear-all --apply
```

Run directly from GitHub without cloning (append `--apply` to make changes):

```bash
uv run --python 3.11 https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification/github_notification.py OWNER/REPO
```

`OWNER/REPO` is required unless `--clear-all` is used. Clearing [marks threads done](https://docs.github.com/en/rest/activity/notifications#mark-a-thread-as-done), removing them from the notification inbox. A failed API call exits with an error; any earlier successful changes remain applied.

## Testing

```bash
uv run --locked pytest
```

Tests mock GitHub requests and never modify real notifications.
