---
name: config-project-mcp-sync
description: 检查或同步项目 .mcp.json、.codex-mcp 中的本地 MCP 启动配置到 Codex config.toml，注册缺失项、更新参数并按请求验证 stdio 握手；支持只列出和不写配置的检查模式。
---

# 项目 MCP 同步

## 职责与边界

使用随技能提供的 `scripts/sync_project_mcp.py` 完成发现、配置同步及 JSON-RPC 握手，不另写注册逻辑。只处理目标项目声明的本地服务。

## 输入与前置条件

确定项目根目录、`.mcp.json`、`.codex-mcp` 启动入口及 Codex 配置路径。配置默认 `${CODEX_HOME:-$HOME/.codex}/config.toml`，可用 `--config` 指定；先根据请求选择模式：

| 请求 | 参数 | 副作用 |
| --- | --- | --- |
| 实际同步并验证 | 不加模式标志 | 按差异写配置，启动候选服务做握手 |
| 检查并验证 | `--dry-run` | 不写配置，但启动候选服务 |
| 仅列出状态 | `--dry-run --no-validate` | 不写配置、不启动服务 |
| 同步但跳过握手 | `--no-validate` | 仍写配置，不启动服务 |

仅列出时同时使用 `--dry-run --no-validate`；只跳过握手但仍需同步时使用 `--no-validate`，避免混淆启动与写入边界。

## 执行流程

1. **预览入口**：核实目标项目及所选模式，需要完整参数时运行脚本 `--help`。
2. **执行脚本**：从实际技能安装位置调用；下列为默认安装路径示例，`--project` 使用已核实的项目目录，按上表追加模式参数：

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/config-project-mcp-sync/scripts/sync_project_mcp.py" --project "$PWD"
   ```

3. **核对计划与写入**：候选来自 `.mcp.json` 的 `mcpServers` 和 `.codex-mcp/*/run.sh`，同命令以 `.mcp.json` 为准。优先按同名同命令、再按解析后的命令匹配；新增优先用服务名，冲突时用项目名前缀及脚本的唯一名处理。核对实际新增、更新、已有和跳过项。
4. **核对握手**：运行模式允许时，脚本用候选命令、参数、cwd 和环境启动服务，执行 `initialize`、`tools/list`。失败保留已写注册，报告服务名、命令路径及脱敏原因；跳过握手不报告运行通过。

## 核心约束

- 同步字段为 `command`、`args`、`env`、`env_vars`、`cwd`、`experimental_environment`；不能只按命令判断一致。保留 Codex 独有的超时、启停、审批等选项及无关注册。
- 实际修改前创建时间戳备份；新增追加，更新原位替换匹配配置块，不重写其他配置。
- 结果只显示参数数量，不展示环境变量值；错误和服务输出也须检查是否含敏感内容。
- 脚本直接启动的 stdio 握手不等于 Codex 宿主加载验证；`env_vars` 的宿主传递及 `experimental_environment` 的实际生效须有对应宿主证据，不能由配置写入或脚本握手推定。

## 产出边界与交付

用中文分别报告已有、新增、参数更新、失败与跳过项，区分预览和实际写入。无新增时仍列出项目注册状态，不能将“没有需要注册的 MCP”误报为参数无变化或握手通过。

## 验证与完成标准

核对全部同步字段、备份和 Codex 专用选项保留情况；分别报告配置结果、实际握手结果及宿主验证限制。修改脚本时运行 `python3 -m unittest discover -s <本技能目录>/tests -p 'test_*.py'`，仅文本维护不启动真实服务。
