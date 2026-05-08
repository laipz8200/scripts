# GitHub Notification Sweeper

English | [中文](README.zh-CN.md)

`github-notification-sweeper.sh` helps clean up unread GitHub notifications for any repository on GitHub. It accepts either `OWNER/REPO` or a `github.com` repository URL, finds notification threads whose subject is already resolved, prints them, and only marks them done when you pass `--apply`.

## What It Matches

- Pull requests that are draft, merged, or closed.
- Issues that are closed.

## Requirements

- GitHub CLI: `gh`
- JSON processor: `jq`
- An authenticated GitHub CLI session: `gh auth login`

## Usage

Run a dry check directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification-sweeper/github-notification-sweeper.sh | bash -s -- OWNER/REPO
```

Mark matching notification threads done directly from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification-sweeper/github-notification-sweeper.sh | bash -s -- --apply OWNER/REPO
```

If you have the repository locally, run it from this directory instead:

```bash
./github-notification-sweeper.sh OWNER/REPO
```

You can also pass a repository URL:

```bash
./github-notification-sweeper.sh https://github.com/OWNER/REPO
```

Mark matching notification threads done:

```bash
./github-notification-sweeper.sh --apply OWNER/REPO
```

## Notes

- Without `--apply`, the script only prints matching notifications.
- With `--apply`, the script calls the GitHub notifications API through `gh api` and removes matching threads from your notification inbox.
- The target repository is required on every run.

## Testing

```bash
./test-github-notification-sweeper.sh
```
