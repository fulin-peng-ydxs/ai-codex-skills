---
name: sync-codex-config
description: 将 Codex 全局技能集合和 AGENTS.md 同步到 Claude Code 与 Kimi Code 的用户级安装目录；同名技能或文档已存在时以 Codex 内容更新。用于用户要求同步、刷新、复制或对齐 Codex、Claude、Kimi 的全局技能和协作指令时。
---

# 同步 Codex 配置

将 Codex 作为唯一来源，同步用户级技能和 `AGENTS.md`。使用随技能提供的 `scripts/sync_codex_config.py`，不要临时拼接复制命令。

## 默认路径

- Codex：`${CODEX_HOME:-~/.codex}/skills` 与 `${CODEX_HOME:-~/.codex}/AGENTS.md`
- Claude：`${CLAUDE_CONFIG_DIR:-${CLAUDE_HOME:-~/.claude}}/skills` 与同根目录下的 `AGENTS.md`
- Kimi：`${KIMI_CODE_HOME:-~/.kimi-code}/skills` 与同根目录下的 `AGENTS.md`

命令行路径参数优先于环境变量。不要把展开后的个人绝对路径写入技能或脚本。

## 执行流程

1. 先运行预览：

   ```bash
   python3 scripts/sync_codex_config.py --dry-run
   ```

2. 检查输出中的源、目标、技能数量和错误。
3. 用户的请求明确授权同步时，执行：

   ```bash
   python3 scripts/sync_codex_config.py
   ```

4. 报告每个目标新增、更新、未变化的技能数量以及文档状态。提示重新启动或新建 Claude、Kimi 会话以加载新配置。

只同步一个目标时使用 `--target claude` 或 `--target kimi`。非默认安装位置使用 `--codex-root`、`--claude-root`、`--kimi-root`。

## 同步规则

- 只同步 Codex skills 根目录中含 `SKILL.md` 的一级技能目录，以及具有有效 YAML frontmatter 的一级 Markdown 技能文件。
- 禁止同步任何 MCP 相关技能，不区分创建、同步、审计、监控、安全或其他用途。技能目录名、技能文件名或 YAML frontmatter 中出现 `MCP`（不区分大小写）时，预览与执行均排除，并在输出中列出。
- 忽略 skills 仓库元数据、隐藏的系统目录、编辑器目录、缓存和构建依赖。
- 目标中不存在的技能创建；已存在技能中的同名文件按 Codex 内容更新。
- 保留目标技能目录中仅目标端存在的文件，也保留仅目标端存在的技能；此技能不执行删除式镜像。
- 将 Codex 的 `AGENTS.md` 原样覆盖到每个目标安装根目录的 `AGENTS.md`，使用原子替换避免半写入。
- 路径类型冲突、源缺失或目标位于源内部时停止，不猜测处理，也不删除冲突目标。
- 不同步任何 MCP 相关技能，也不同步凭据、会话、日志、MCP 配置、插件缓存或其他安装文件。

## 参数查询

需要完整参数时运行：

```bash
python3 scripts/sync_codex_config.py --help
```
