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


@pytest.mark.parametrize("apply", [False, True])
def test_resolved_notifications(monkeypatch, capsys, apply):
    cases = [
        ("PullRequest", {"draft": True, "merged": True, "state": "closed"}, "draft"),
        ("PullRequest", {"merged": True, "state": "closed"}, "merged"),
        ("PullRequest", {"state": "closed"}, "closed"),
        ("Issue", {"state": "closed"}, "closed"),
        ("PullRequest", {"state": "open"}, None),
        ("Issue", {"state": "open"}, None),
    ] * 2
    threads = [notification(i, kind) for i, (kind, _, _) in enumerate(cases)]
    threads += [notification(20, unread=False), notification(21, "Release"), notification(22)]
    threads[-1]["subject"]["url"] = None
    requests, active, peak = [], 0, 0

    async def api(endpoint, *options):
        nonlocal active, peak
        requests.append((endpoint, options))
        if "notifications?" in endpoint:
            assert endpoint == "/repos/octo/repo/notifications?all=false&per_page=50"
            assert options == ("--paginate", "--slurp")
            return [threads[:3], threads[3:]]
        if options:
            assert options == ("--method", "DELETE")
            assert len([url for url, opts in requests if not opts]) == len(cases)
            return None
        number = int(endpoint.rsplit("/", 1)[1])
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return cases[number][1]

    monkeypatch.setattr(app, "api", api)
    app.main(["https://github.com/octo/repo.git/", *(["--apply"] if apply else [])])
    matched = [(thread, case[2]) for thread, case in zip(threads, cases) if case[2]]
    assert capsys.readouterr().out.splitlines() == [
        f"[{state}] {thread['subject']['title']}" for thread, state in matched
    ]
    assert [url for url, opts in requests if opts == ("--method", "DELETE")] == (
        [f"/notifications/threads/{thread['id']}" for thread, _ in matched] if apply else []
    )
    assert peak == 5


@pytest.mark.parametrize("repo", [None, "octo/repo"])
@pytest.mark.parametrize("apply", [False, True])
def test_clear_all(monkeypatch, capsys, repo, apply):
    threads = [notification(1), notification(2, "Release", unread=False)]
    threads[-1]["subject"]["url"] = None
    if not repo:
        threads.append(notification(3, repo="other/repo"))
    api = AsyncMock(side_effect=[[threads[:1], threads[1:]], *([None] * len(threads))])
    monkeypatch.setattr(app, "api", api)
    app.main(["--clear-all", *([repo] if repo else []), *(["--apply"] if apply else [])])
    endpoint = f"/repos/{repo}/notifications" if repo else "/notifications"
    assert api.call_args_list[0].args == (
        f"{endpoint}?all=true&per_page=50", "--paginate", "--slurp"
    )
    assert [call.args for call in api.call_args_list[1:]] == (
        [(f"/notifications/threads/{thread['id']}", "--method", "DELETE") for thread in threads]
        if apply else []
    )
    assert len(capsys.readouterr().out.splitlines()) == len(threads)


@pytest.mark.parametrize("argv,code", [
    ([], 2), (["--help"], 0), (["invalid"], 2), (["../repo"], 2),
    (["https://example.com/octo/repo"], 2), (["octo/repo/extra"], 2),
    (["octo/repo", "extra"], 2), (["--unknown", "octo/repo"], 2),
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
        app.main(["--clear-all", "--apply"])
    assert error.value.code == 1
    assert str(failure) in capsys.readouterr().err
    assert api.await_count == 1


def test_rejects_untrusted_subject_url(monkeypatch):
    thread = notification(1)
    thread["subject"]["url"] = "https://example.com/repos/octo/repo/issues/1"
    api = AsyncMock(return_value=[[thread]])
    monkeypatch.setattr(app, "api", api)
    with pytest.raises(SystemExit) as error:
        app.main(["octo/repo", "--apply"])
    assert error.value.code == 1
    assert api.await_count == 1
