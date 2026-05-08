#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage: github-notification-sweeper.sh [--apply] OWNER/REPO
       github-notification-sweeper.sh [--apply] https://github.com/OWNER/REPO

Lists unread GitHub notifications for a repository whose issue or pull request
subject is already resolved. Pass --apply to mark matching threads done.
USAGE
}

APPLY=""
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY="--apply"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      if [[ -n "$REPO" ]]; then
        echo "Unexpected argument: $1" >&2
        usage
        exit 2
      fi

      REPO="$1"
      shift
      ;;
  esac
done

if [[ $# -gt 0 ]]; then
  if [[ -n "$REPO" ]]; then
    echo "Unexpected argument: $1" >&2
    usage
    exit 2
  fi

  REPO="$1"
  shift
fi

if [[ $# -gt 0 ]]; then
  echo "Unexpected argument: $1" >&2
  usage
  exit 2
fi

if [[ -z "$REPO" ]]; then
  echo "Repository is required." >&2
  usage
  exit 2
fi

REPO="${REPO#https://github.com/}"
REPO="${REPO#http://github.com/}"
REPO="${REPO%/}"
REPO="${REPO%.git}"

if [[ ! "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "Repository must be OWNER/REPO or a github.com repository URL." >&2
  usage
  exit 2
fi

gh api "/notifications?all=false&per_page=100" --paginate |
  jq -r --arg repo "$REPO" '
  .[]
  | select(.repository.full_name == $repo)
  | select(.unread == true)
  | [.id, .subject.type, .subject.title, .subject.url]
  | @tsv
' |
  while IFS=$'\t' read -r thread_id type title url; do
    endpoint="${url#https://api.github.com}"
    item="$(gh api "$endpoint")"

    status=""

    if [[ "$type" == "PullRequest" ]]; then
      status="$(jq -r '
      if .draft == true then "draft"
      elif .merged == true then "merged"
      elif .state == "closed" then "closed"
      else empty
      end
    ' <<<"$item")"
    elif [[ "$type" == "Issue" ]]; then
      status="$(jq -r '
      if .state == "closed" then "closed"
      else empty
      end
    ' <<<"$item")"
    fi

    if [[ -n "$status" ]]; then
      echo "[$status] $title"

      if [[ "$APPLY" == "--apply" ]]; then
        gh api -X DELETE "/notifications/threads/$thread_id" >/dev/null
      fi
    fi
  done
