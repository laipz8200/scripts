import argparse
import asyncio
import json
import re


def repository(value):
    value = re.sub(r"^https?://github\.com/", "", value).removesuffix("/").removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value) or any(
        part in {".", ".."} for part in value.split("/")
    ):
        raise argparse.ArgumentTypeError("Expected OWNER/REPO or a github.com repository URL")
    return value


async def api(endpoint, *options):
    process = await asyncio.create_subprocess_exec(
        "gh", "api", "--hostname", "github.com", endpoint, *options,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate()
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode().strip() or f"gh api failed: {endpoint}")
    return json.loads(stdout) if stdout.strip() else None


async def run(command, repo=None, all_notifications=False, dry_run=False):
    endpoint = f"/repos/{repo}/notifications" if repo else "/notifications"
    pages = await api(
        f"{endpoint}?all={str(all_notifications).lower()}&per_page=50", "--paginate", "--slurp"
    )
    # Snapshot all pages before deleting so pagination cannot skip threads.
    threads = [thread for page in pages for thread in page if all_notifications or thread["unread"]]
    limit = asyncio.Semaphore(5)

    async def request(endpoint, *options):
        async with limit:
            return await api(endpoint, *options)

    async def status(thread):
        if command != "sweep":
            return "unread" if thread["unread"] else "read"
        subject = thread["subject"]
        if subject["type"] not in {"PullRequest", "Issue"}:
            return None
        url = subject.get("url")
        if not url:
            return None
        if not url.startswith("https://api.github.com/"):
            raise ValueError(f"Unexpected GitHub API URL: {url}")
        item = await request(url.removeprefix("https://api.github.com"))
        if subject["type"] == "PullRequest":
            if item.get("draft"):
                return "draft"
            if item.get("merged"):
                return "merged"
        return "closed" if item.get("state") == "closed" else None

    async with asyncio.TaskGroup() as tasks:
        statuses = [tasks.create_task(status(thread)) for thread in threads]
    async with asyncio.TaskGroup() as tasks:
        for thread, task in zip(threads, statuses):
            if state := task.result():
                prefix = f"{thread['repository']['full_name']}: " if not repo else ""
                print(f"[{state}] {prefix}{thread['subject']['title']}")
                if command != "list" and not dry_run:
                    tasks.create_task(request(f"/notifications/threads/{thread['id']}", "--method", "DELETE"))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="github-notification", description="List, clear, or sweep GitHub notifications."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("list", "List notifications without changing them."),
        ("clear", "Mark notifications done."),
        ("sweep", "Mark notifications for draft/merged/closed PRs and closed issues done."),
    ):
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("repo", nargs="?", type=repository, metavar="OWNER/REPO",
                             help="repository name or URL; omit for all repositories")
        scope = command.add_mutually_exclusive_group()
        scope.add_argument("--unread", dest="all_notifications", action="store_false",
                           help="select unread notifications (default)")
        scope.add_argument("--all", dest="all_notifications", action="store_true",
                           help="select read and unread notifications")
        command.set_defaults(all_notifications=False, dry_run=False)
        if name != "list":
            command.add_argument("--dry-run", action="store_true", help="preview without changes")
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(**vars(args)))
    except* (OSError, RuntimeError, ValueError) as errors:
        parser.exit(1, f"error: {errors.exceptions[0]}\n")


if __name__ == "__main__":
    main()
