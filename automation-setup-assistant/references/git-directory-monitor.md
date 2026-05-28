# Git 目录监测示例

当用户希望 Codex 按计划监测本地 Git 目录，并提交所有 Git 可见变化时，使用这个模式。

## 用户输入

- 要监测的目录：
  - `/Users/pengshuaifeng/.codex/skills`
  - `/Users/pengshuaifeng/.claude/skills`
- 运行时间：每天 `23:00`。
- 变化规则：提交任何 Git 可见的新增、修改或删除文件；忽略 `.gitignore` 排除的文件。
- 暂存规则：`git add -A`。
- 提交消息规则：参考 `/Users/pengshuaifeng/.claude/skills/git-commit-msg/SKILL.md`。
- 推送规则：提交成功后自动 push。
- 输出语言：中文。

## 预检查

创建或更新自动化前，运行这些检查：

```bash
git -C /Users/pengshuaifeng/.codex/skills rev-parse --show-toplevel
git -C /Users/pengshuaifeng/.claude/skills rev-parse --show-toplevel
ls -la /Users/pengshuaifeng/.claude/skills/git-commit-msg
git -C /Users/pengshuaifeng/.codex/skills status --porcelain --untracked-files=all
git -C /Users/pengshuaifeng/.claude/skills status --porcelain --untracked-files=all
```

## 自动化配置

- 类型：`cron`
- 名称：`每晚提交技能目录变更`
- RRULE: `FREQ=DAILY;BYHOUR=23;BYMINUTE=0;BYSECOND=0`
- 执行环境：`local`
- 工作区：
  - `/Users/pengshuaifeng/.codex/skills`
  - `/Users/pengshuaifeng/.claude/skills`

提示词应要求：

```text
监测以下两个 Git 仓库中未被 .gitignore 忽略的文件变化：
/Users/pengshuaifeng/.codex/skills
/Users/pengshuaifeng/.claude/skills

对每个仓库执行 git -C <仓库路径> status --porcelain --untracked-files=all。
如果没有 Git 可见变化，报告该仓库没有变化。
如果存在任何新增、修改或删除，执行 git -C <仓库路径> add -A。
然后参考 /Users/pengshuaifeng/.claude/skills/git-commit-msg/SKILL.md 中的提交消息模板和规则生成简洁提交信息。
使用 git -C <仓库路径> commit -m "<提交信息>" 创建提交。
随后必须使用显式命令 git -C /Users/pengshuaifeng/.codex/skills push 或 git -C /Users/pengshuaifeng/.claude/skills push 推送对应仓库。
最终用中文报告每个仓库的处理结果、创建的提交 hash，以及 push 是否成功或失败。
```

## 授权验证

创建自动化后，对精确的 push 命令触发一次授权：

```bash
git -C /Users/pengshuaifeng/.codex/skills push
git -C /Users/pengshuaifeng/.claude/skills push
```

使用 `sandbox_permissions: require_escalated`，并为每条命令设置匹配的持久 `prefix_rule`。

## 失败诊断

如果运行结果显示已经创建提交，但 push 因 DNS 或网络错误失败，说明本地提交已经成功，缺少的只是网络授权。

如果运行结果显示没有 Git 可见变化，用下面命令验证：

```bash
git -C <repo> status --porcelain --untracked-files=all
```

如果运行结果未能创建提交，检查仓库状态、Git 身份配置、hooks，以及 `git add -A` 是否被允许写入仓库。
