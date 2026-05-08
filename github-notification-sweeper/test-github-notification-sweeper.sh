#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$TEST_DIR/github-notification-sweeper.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local needle="$1"
  local file="$2"

  grep -Fq "$needle" "$file" || fail "expected '$needle' in $file"
}

setup_fake_gh() {
  FAKE_BIN="$(mktemp -d)"
  GH_LOG="$FAKE_BIN/gh.log"
  export GH_LOG

  cat >"$FAKE_BIN/gh" <<'GH'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" >>"$GH_LOG"

if [[ "$1" != "api" ]]; then
  echo "unexpected gh command: $*" >&2
  exit 98
fi

shift

if [[ "${1:-}" == "-X" && "${2:-}" == "DELETE" ]]; then
  printf 'DELETE %s\n' "$3" >>"$GH_LOG"
  exit 0
fi

endpoint="${1:-}"

case "$endpoint" in
  "/notifications?all=false&per_page=100")
    cat <<'JSON'
[
  {
    "id": "thread-1",
    "unread": true,
    "repository": { "full_name": "octo/repo" },
    "subject": {
      "type": "PullRequest",
      "title": "Merged pull request",
      "url": "https://api.github.com/repos/octo/repo/pulls/1"
    }
  },
  {
    "id": "thread-2",
    "unread": true,
    "repository": { "full_name": "other/repo" },
    "subject": {
      "type": "Issue",
      "title": "Closed issue in another repo",
      "url": "https://api.github.com/repos/other/repo/issues/2"
    }
  },
  {
    "id": "thread-3",
    "unread": true,
    "repository": { "full_name": "octo/repo" },
    "subject": {
      "type": "Issue",
      "title": "Closed issue",
      "url": "https://api.github.com/repos/octo/repo/issues/3"
    }
  },
  {
    "id": "thread-4",
    "unread": false,
    "repository": { "full_name": "octo/repo" },
    "subject": {
      "type": "Issue",
      "title": "Read issue",
      "url": "https://api.github.com/repos/octo/repo/issues/4"
    }
  }
]
JSON
    ;;
  "/repos/octo/repo/pulls/1")
    printf '{"draft": false, "merged": true, "state": "closed"}\n'
    ;;
  "/repos/octo/repo/issues/3")
    printf '{"state": "closed"}\n'
    ;;
  *)
    echo "unexpected endpoint: $endpoint" >&2
    exit 99
    ;;
esac
GH

  chmod +x "$FAKE_BIN/gh"
  export PATH="$FAKE_BIN:$ORIGINAL_PATH"
}

test_requires_repo_argument() {
  local tmp
  tmp="$(mktemp -d)"
  setup_fake_gh

  set +e
  "$SCRIPT" >"$tmp/out" 2>"$tmp/err"
  local status=$?
  set -e

  [[ "$status" -eq 2 ]] || fail "expected missing repo to exit 2, got $status"
  assert_contains "Usage:" "$tmp/err"
  [[ ! -s "$GH_LOG" ]] || fail "gh should not be called when repo argument is missing"
}

test_dry_run_filters_target_repo_without_deleting() {
  local tmp
  tmp="$(mktemp -d)"
  setup_fake_gh

  "$SCRIPT" octo/repo >"$tmp/out"

  diff -u <(printf '[merged] Merged pull request\n[closed] Closed issue\n') "$tmp/out"
  ! grep -Fq 'DELETE' "$GH_LOG" || fail "dry run should not delete notification threads"
}

test_apply_accepts_github_url_and_deletes_matches() {
  local tmp
  tmp="$(mktemp -d)"
  setup_fake_gh

  "$SCRIPT" --apply https://github.com/octo/repo.git/ >"$tmp/out"

  diff -u <(printf '[merged] Merged pull request\n[closed] Closed issue\n') "$tmp/out"
  assert_contains "DELETE /notifications/threads/thread-1" "$GH_LOG"
  assert_contains "DELETE /notifications/threads/thread-3" "$GH_LOG"
}

ORIGINAL_PATH="$PATH"

test_requires_repo_argument
test_dry_run_filters_target_repo_without_deleting
test_apply_accepts_github_url_and_deletes_matches

echo "All tests passed."
