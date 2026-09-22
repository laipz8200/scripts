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


async def sweep(repo, apply=False, clear_all=False):
    endpoint = f"/repos/{repo}/notifications" if repo else "/notifications"
    pages = await api(
        f"{endpoint}?all={str(clear_all).lower()}&per_page=50", "--paginate", "--slurp"
    )
    threads = [thread for page in pages for thread in page]
    limit = asyncio.Semaphore(5)

    async def status(thread):
        if clear_all:
            return "all"
        subject = thread["subject"]
        if not thread["unread"] or subject["type"] not in {"PullRequest", "Issue"}:
            return None
        url = subject.get("url")
        if not url:
            return None
        if not url.startswith("https://api.github.com/"):
            raise ValueError(f"Unexpected GitHub API URL: {url}")
        async with limit:
            item = await api(url.removeprefix("https://api.github.com"))
        if subject["type"] == "PullRequest":
            if item.get("draft"):
                return "draft"
            if item.get("merged"):
                return "merged"
        return "closed" if item.get("state") == "closed" else None

    # Snapshot all pages before deleting so pagination cannot skip threads.
    statuses = await asyncio.gather(*(status(thread) for thread in threads))
    for thread, state in zip(threads, statuses):
        if state:
            prefix = f"{thread['repository']['full_name']}: " if not repo else ""
            print(f"[{state}] {prefix}{thread['subject']['title']}")
            if apply:
                await api(f"/notifications/threads/{thread['id']}", "--method", "DELETE")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="github-notification", description="Preview GitHub notifications to mark done."
    )
    parser.add_argument("repo", nargs="?", type=repository, metavar="OWNER/REPO")
    parser.add_argument("--apply", action="store_true", help="mark matching threads done")
    parser.add_argument(
        "--clear-all", action="store_true",
        help="include read/unread notifications of every type; omit repo for all repositories",
    )
    args = parser.parse_args(argv)
    if not args.repo and not args.clear_all:
        parser.error("repository is required unless --clear-all is used")
    try:
        asyncio.run(sweep(args.repo, args.apply, args.clear_all))
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
