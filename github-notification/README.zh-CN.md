# GitHub Notification

[English](README.md) | 中文

预览并清理 GitHub 通知。默认匹配指定仓库中草稿、已合并或已关闭的 Pull Request，以及已关闭 Issue 的未读通知。`--clear-all` 匹配所有通知，包括已读通知和其他主题类型。只有传入 `--apply` 才会执行修改。

## 依赖

- [uv](https://docs.astral.sh/uv/)（管理 Python 3.11+ 和测试依赖）。
- 支持 `gh api --slurp` 的 [GitHub CLI](https://cli.github.com/)，通过 `gh auth login` 或 `GH_TOKEN` / `GITHUB_TOKEN` 完成认证。

Python 代码仅使用标准库，通过异步 `gh` 子进程调用 API，最多同时查询五个通知主题。获取全部分页并完成主题检查后，按顺序将通知标记为完成。

## 用法

在当前目录运行：

```bash
# 预览已处理的未读通知
uv run github-notification OWNER/REPO
uv run github-notification https://github.com/OWNER/REPO

# 将匹配的通知标记为完成
uv run github-notification --apply OWNER/REPO

# 预览指定仓库的全部通知，然后清理
uv run github-notification --clear-all OWNER/REPO
uv run github-notification --clear-all --apply OWNER/REPO

# 预览所有仓库的全部通知，然后清理
uv run github-notification --clear-all
uv run github-notification --clear-all --apply
```

无需克隆仓库，直接从 GitHub 运行（追加 `--apply` 执行修改）：

```bash
uv run --python 3.11 https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification/github_notification.py OWNER/REPO
```

除非使用 `--clear-all`，否则必须提供 `OWNER/REPO`。清理会[将通知标记为完成](https://docs.github.com/en/rest/activity/notifications#mark-a-thread-as-done)，从通知收件箱中移除。API 调用失败时会报错退出，此前成功的修改仍然生效。

## 测试

```bash
uv run --locked pytest
```

测试使用模拟的 GitHub 请求，不会修改真实通知。
