# GitHub Notification

[English](README.md) | 中文

列出、清空或按主题状态清理 GitHub 通知。所有命令默认使用 `--unread`，传入 `--all` 则包含已读通知。可选传入 `OWNER/REPO` 或 GitHub 仓库 URL 限定范围，不传则选择所有仓库。

| 命令 | 行为 |
| --- | --- |
| `list` | 列出各种主题类型的通知，不执行修改。 |
| `clear` | 将选中的通知标记为完成。 |
| `sweep` | 仅将选中通知中草稿、已合并或已关闭 PR，以及已关闭 Issue 的通知标记为完成。 |

`--unread` 和 `--all` 互斥。`clear` 和 `sweep` 会立即执行修改，添加 `--dry-run` 可仅预览。

## 依赖

- [uv](https://docs.astral.sh/uv/)（管理 Python 3.11+ 和测试依赖）。
- 支持 `gh api --slurp` 的 [GitHub CLI](https://cli.github.com/)，通过 `gh auth login` 或 `GH_TOKEN` / `GITHUB_TOKEN` 完成认证。

Python 代码仅使用标准库，通过 `asyncio.TaskGroup` 中的任务启动异步 `gh` 子进程调用 API，主题查询和清理均最多同时执行五个请求。获取全部分页并完成主题检查后才开始清理。如果任务失败，会取消其余任务并等待它们结束后退出。

## 用法

在当前目录运行：

```bash
# 列出未读通知（前两条命令等价）
uv run github-notification list
uv run github-notification list --unread
uv run github-notification list --all

# 清空未读通知，或同时包含已读通知
uv run github-notification clear
uv run github-notification clear --all

# 预览已处理主题的通知，然后清理
uv run github-notification sweep --dry-run
uv run github-notification sweep
uv run github-notification sweep --all

# 将任意命令限定到一个仓库
uv run github-notification list --all OWNER/REPO
uv run github-notification clear --all --dry-run OWNER/REPO
uv run github-notification sweep https://github.com/OWNER/REPO
```

无需克隆仓库，直接从 GitHub 运行：

```bash
uv run --python 3.11 https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification/github_notification.py list --unread
```

清理会[将通知标记为完成](https://docs.github.com/en/rest/activity/notifications#mark-a-thread-as-done)，从通知收件箱中移除。API 调用失败时会报错退出，此前成功的修改仍然生效。

## 测试

```bash
uv run --locked pytest
```

测试使用模拟的 GitHub 请求，不会修改真实通知。
