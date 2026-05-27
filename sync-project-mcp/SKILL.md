---
name: sync-project-mcp
description: 检测当前项目 .codex-mcp 目录和 .mcp.json 中声明的本地 MCP 服务，对比 Codex 的 ~/.codex/config.toml 中 mcp_servers 注册项，自动注册缺失的项目 MCP，并通过 JSON-RPC initialize/tools-list 握手验证每个项目 MCP，最后用中文输出当前项目 MCP 列表。适用于用户要求同步、注册、检测、验证、列出或修复当前项目 Codex MCP 注册的场景。
---

# 同步项目 MCP

## 工作流

使用随技能提供的脚本完成整个流程：

```bash
python3 "$CODEX_HOME/skills/sync-project-mcp/scripts/sync_project_mcp.py" --project "$PWD"
```

如果 `CODEX_HOME` 未设置，使用：

```bash
python3 "$HOME/.codex/skills/sync-project-mcp/scripts/sync_project_mcp.py" --project "$PWD"
```

脚本必须完成以下动作：

1. 从 `.mcp.json` 的 `mcpServers` 和 `.codex-mcp/*/run.sh` 发现项目 MCP 候选项。
2. 从 `${CODEX_HOME:-$HOME/.codex}/config.toml` 的 `[mcp_servers.<name>]` 读取 Codex 已注册 MCP。
3. 如果某个 MCP 的解析后 `command` 路径已经存在于 Codex 配置中，即使注册名不同，也视为已注册。
4. 对缺失的 MCP 追加注册到 Codex 配置；优先使用 `.mcp.json` 中的服务名。如果该名称已被其他命令占用，使用 `<项目目录名>-<服务名>`。
5. 启动每个项目 MCP 命令，通过 stdio 发送 JSON-RPC `initialize` 和 `tools/list` 请求进行验证。
6. 用中文报告已存在、新增注册、验证失败和跳过项。

## 安全要求

- 修改 `config.toml` 前必须创建带时间戳的备份。
- 不删除、不重写无关 MCP 注册。
- 保留现有配置文本，只在文件末尾追加新的 `[mcp_servers.<name>]` 配置块。
- 如果验证失败，保留注册项，但清楚报告 MCP 名称、命令路径和错误原因，方便用户修复环境变量或依赖。
- 如果项目 MCP 都已经注册，明确说明“没有需要注册的 MCP”，并列出当前项目 MCP 注册列表。

## 常用命令

只检查和验证，不写入 Codex 配置：

```bash
python3 "$HOME/.codex/skills/sync-project-mcp/scripts/sync_project_mcp.py" --project "$PWD" --dry-run
```

只检查注册状态，不启动 MCP 进行验证：

```bash
python3 "$HOME/.codex/skills/sync-project-mcp/scripts/sync_project_mcp.py" --project "$PWD" --no-validate
```
