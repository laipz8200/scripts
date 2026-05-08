# GitHub Notification Sweeper

[English](README.md) | 中文

`github-notification-sweeper.sh` 用来清理 GitHub 上任意仓库的未读通知。它支持传入 `OWNER/REPO` 或 `github.com` 仓库 URL，会找出主题已经处理完的通知并打印出来，只有在传入 `--apply` 时才会将这些通知标记为完成。

## 匹配范围

- 草稿、已合并或已关闭的 Pull Request。
- 已关闭的 Issue。

## 依赖

- GitHub CLI：`gh`
- JSON 处理工具：`jq`
- 已登录的 GitHub CLI：`gh auth login`

## 用法

直接从 GitHub 执行 dry run：

```bash
curl -fsSL https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification-sweeper/github-notification-sweeper.sh | bash -s -- OWNER/REPO
```

直接从 GitHub 运行，并将匹配的通知标记为完成：

```bash
curl -fsSL https://raw.githubusercontent.com/laipz8200/scripts/main/github-notification-sweeper/github-notification-sweeper.sh | bash -s -- --apply OWNER/REPO
```

如果已经克隆了这个仓库，可以在当前目录运行：

```bash
./github-notification-sweeper.sh OWNER/REPO
```

也可以传入仓库 URL：

```bash
./github-notification-sweeper.sh https://github.com/OWNER/REPO
```

将匹配的通知标记为完成：

```bash
./github-notification-sweeper.sh --apply OWNER/REPO
```

## 说明

- 不传 `--apply` 时，脚本只会打印匹配到的通知。
- 传入 `--apply` 时，脚本会通过 `gh api` 调用 GitHub 通知接口，并将匹配的通知从收件箱中移除。
- 每次运行都需要传入目标仓库。

## 测试

```bash
./test-github-notification-sweeper.sh
```
