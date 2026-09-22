import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import github_notification as app


def notification(number, kind="Issue", unread=True, repo="octo/repo"):
    resource = "pulls" if kind == "PullRequest" else "issues"
    return {
        "id": str(number), "unread": unread, "repository": {"full_name": repo},
        "subject": {"type": kind, "title": f"{kind} {number}",
                    "url": f"https://api.github.com/repos/{repo}/{resource}/{number}"},
    }


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("scope", [[], ["--unread"], ["--all"]])
def test_sweep(monkeypatch, capsys, dry_run, scope):
    cases = [
        ("PullRequest", {"draft": True, "merged": True, "state": "closed"}, "draft"),
        ("PullRequest", {"merged": True, "state": "closed"}, "merged"),
        ("PullRequest", {"state": "closed"}, "closed"),
        ("Issue", {"state": "closed"}, "closed"),
        ("PullRequest", {"state": "open"}, None),
        ("Issue", {"state": "open"}, None),
    ] * 2 + [("Issue", {"state": "closed"}, "closed")]
    threads = [notification(i, kind, unread=i < 12) for i, (kind, _, _) in enumerate(cases)]
    threads += [notification(21, "Release"), notification(22)]
    threads[-1]["subject"]["url"] = None
    all_notifications = scope == ["--all"]
    selected = [(thread, case) for thread, case in zip(threads, cases)
                if all_notifications or thread["unread"]]
    requests, active, peak = [], 0, 0

    async def api(endpoint, *options):
        nonlocal active, peak
        requests.append((endpoint, options))
        if "notifications?" in endpoint:
            assert endpoint == (
                f"/repos/octo/repo/notifications?all={str(all_notifications).lower()}&per_page=50"
            )
            assert options == ("--paginate", "--slurp")
            return [threads[:3], threads[3:]]
        if options:
            assert options == ("--method", "DELETE")
            assert len([url for url, opts in requests if not opts]) == len(selected)
            return None
        number = int(endpoint.rsplit("/", 1)[1])
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return cases[number][1]

    monkeypatch.setattr(app, "api", api)
    app.main(["sweep", "https://github.com/octo/repo.git/", *scope,
              *(["--dry-run"] if dry_run else [])])
    matched = [(thread, case[2]) for thread, case in selected if case[2]]
    assert capsys.readouterr().out.splitlines() == [
        f"[{state}] {thread['subject']['title']}" for thread, state in matched
    ]
    assert [url for url, opts in requests if opts == ("--method", "DELETE")] == (
        [] if dry_run else [f"/notifications/threads/{thread['id']}" for thread, _ in matched]
    )
    assert peak == 5


@pytest.mark.parametrize("repo", [None, "octo/repo"])
@pytest.mark.parametrize("scope", [[], ["--unread"], ["--all"]])
@pytest.mark.parametrize("command,dry_run", [("list", False), ("clear", False), ("clear", True)])
def test_list_and_clear(monkeypatch, capsys, repo, scope, command, dry_run):
    threads = [notification(1), notification(2, "Release", unread=False), notification(3, "Release")]
    threads[-1]["subject"]["url"] = None
    if not repo:
        threads.append(notification(4, repo="other/repo"))
    all_notifications = scope == ["--all"]
    selected = [thread for thread in threads if all_notifications or thread["unread"]]
    api = AsyncMock(side_effect=[[threads[:1], threads[1:]], *([None] * len(threads))])
    monkeypatch.setattr(app, "api", api)
    app.main([command, *scope, *([repo] if repo else []), *(["--dry-run"] if dry_run else [])])
    endpoint = f"/repos/{repo}/notifications" if repo else "/notifications"
    assert api.call_args_list[0].args == (
        f"{endpoint}?all={str(all_notifications).lower()}&per_page=50", "--paginate", "--slurp"
    )
    assert [call.args for call in api.call_args_list[1:]] == (
        [(f"/notifications/threads/{thread['id']}", "--method", "DELETE") for thread in selected]
        if command == "clear" and not dry_run else []
    )
    assert capsys.readouterr().out.splitlines() == [
        f"[{'unread' if thread['unread'] else 'read'}] "
        f"{thread['repository']['full_name'] + ': ' if not repo else ''}{thread['subject']['title']}"
        for thread in selected
    ]


@pytest.mark.parametrize("command", ["list", "clear", "sweep"])
def test_empty_notifications(monkeypatch, capsys, command):
    api = AsyncMock(return_value=[[]])
    monkeypatch.setattr(app, "api", api)
    app.main([command])
    api.assert_awaited_once_with("/notifications?all=false&per_page=50", "--paginate", "--slurp")
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("argv,code", [
    ([], 2), (["--help"], 0), (["invalid"], 2), (["list", "../repo"], 2),
    (["list", "https://example.com/octo/repo"], 2), (["list", "octo/repo/extra"], 2),
    (["list", "octo/repo", "extra"], 2), (["list", "--unknown"], 2),
    (["list", "--unread", "--all"], 2), (["clear", "--unread", "--all"], 2),
    (["sweep", "--unread", "--all"], 2), (["list", "--dry-run"], 2),
])
def test_cli_rejects_invalid_arguments_before_network(monkeypatch, argv, code):
    api = AsyncMock()
    monkeypatch.setattr(app, "api", api)
    with pytest.raises(SystemExit) as error:
        app.main(argv)
    assert error.value.code == code
    api.assert_not_called()


@pytest.mark.parametrize("returncode,stdout,expected", [
    (0, b'{"state":"closed"}', {"state": "closed"}),
    (0, b"", None), (1, b"", RuntimeError), (0, b"invalid", json.JSONDecodeError),
])
def test_api(monkeypatch, returncode, stdout, expected):
    process = SimpleNamespace(
        returncode=returncode, communicate=AsyncMock(return_value=(stdout, b"API failed"))
    )
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    if isinstance(expected, type):
        with pytest.raises(expected):
            asyncio.run(app.api("/notifications"))
    else:
        assert asyncio.run(app.api("/notifications")) == expected
    assert spawn.call_args.args == ("gh", "api", "--hostname", "github.com", "/notifications")


def test_cancellation_stops_subprocess(monkeypatch):
    process = SimpleNamespace(returncode=None, kill=Mock(), communicate=AsyncMock(
        side_effect=[asyncio.CancelledError, (b"", b"")]
    ))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(app.api("/notifications"))
    process.kill.assert_called_once()
    assert process.communicate.await_count == 2


@pytest.mark.parametrize("failure", [FileNotFoundError("gh missing"), RuntimeError("HTTP 403")])
def test_network_failure_exits_without_deleting(monkeypatch, capsys, failure):
    api = AsyncMock(side_effect=failure)
    monkeypatch.setattr(app, "api", api)
    with pytest.raises(SystemExit) as error:
        app.main(["clear", "--all"])
    assert error.value.code == 1
    assert str(failure) in capsys.readouterr().err
    assert api.await_count == 1


def test_rejects_untrusted_subject_url(monkeypatch):
    thread = notification(1)
    thread["subject"]["url"] = "https://example.com/repos/octo/repo/issues/1"
    api = AsyncMock(return_value=[[thread]])
    monkeypatch.setattr(app, "api", api)
    with pytest.raises(SystemExit) as error:
        app.main(["sweep", "octo/repo"])
    assert error.value.code == 1
    assert api.await_count == 1


def test_clear_reports_task_failure(monkeypatch, capsys):
    api = AsyncMock(side_effect=[[[notification(1)]], RuntimeError("HTTP 403")])
    monkeypatch.setattr(app, "api", api)
    with pytest.raises(SystemExit) as error:
        app.main(["clear"])
    assert error.value.code == 1
    assert api.await_count == 2
    assert api.call_args.args == ("/notifications/threads/1", "--method", "DELETE")
    assert capsys.readouterr().err == "error: HTTP 403\n"


@pytest.mark.parametrize("command", ["clear", "sweep"])
def test_clearing_runs_concurrently_and_waits_for_completion(monkeypatch, command):
    active, peak, completed = 0, 0, set()

    async def api(endpoint, *options):
        nonlocal active, peak
        if "notifications?" in endpoint:
            return [[notification(i) for i in range(12)]]
        if not options:
            return {"state": "closed"}
        assert options == ("--method", "DELETE")
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        completed.add(endpoint)

    monkeypatch.setattr(app, "api", api)
    app.main([command])
    assert peak == 5
    assert active == 0
    assert completed == {f"/notifications/threads/{i}" for i in range(12)}


@pytest.mark.parametrize("command", ["clear", "sweep"])
def test_task_failure_cancels_siblings_before_run_returns(monkeypatch, command):
    async def check():
        ready = asyncio.Event()
        started, cancelled, jobs = set(), set(), set()

        async def api(endpoint, *options):
            if "notifications?" in endpoint:
                return [[notification(i) for i in range(12)]]
            if command == "sweep":
                assert not options  # Failed subject checks must never start clearing.
            started.add(endpoint)
            jobs.add(asyncio.current_task())
            if len(started) == 5:
                ready.set()
            if endpoint.endswith("/0"):
                await ready.wait()
                raise RuntimeError("HTTP 403")
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.add(endpoint)
                raise

        monkeypatch.setattr(app, "api", api)
        with pytest.raises(ExceptionGroup) as error:
            await app.run(command)
        assert str(error.value.exceptions[0]) == "HTTP 403"
        assert cancelled == {endpoint for endpoint in started if not endpoint.endswith("/0")}
        assert all(task.done() for task in jobs)

    async def timed_check():
        await asyncio.wait_for(check(), timeout=1)

    asyncio.run(timed_check())
