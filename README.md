# Codex 全局 Skills 说明

这个目录存放当前用户自定义的 Codex 全局技能。每个技能使用独立目录管理，核心入口文件为 `SKILL.md`。

## 目录用途

- 作用范围：放在 `~/.codex/skills/` 下的技能，可在 Codex 会话中作为全局技能被发现和使用。
- 适用场景：沉淀可复用的工作流、固定交付格式、项目化规范、数据库/MCP 接入流程和自动化排障能力。
- 组织方式：一个技能一个目录；有补充模板、参考文档或脚本时，放在技能子目录内统一维护。

## 当前技能

以下列表只包含当前仓库中带有 `SKILL.md` 的用户自定义技能目录；`.system/`、`.git/`、`.idea/` 和未提供技能入口的辅助目录不计入“当前技能”。

| 技能目录 | 主要用途 |
| --- | --- |
| `ai-instruction-simplifier` | 精简、重构和规范 AI 约束文档、技能说明、自动化规则与提示词规范，保留最新事实和稳定执行约束。 |
| `ai-trend-knowledge-maintainer` | 维护 AI 趋势投资知识库，处理候选信息、正式文档、元数据和校验闭环。 |
| `auto-plan-dev` | 在用户明确点名 `auto-plan-dev` 时，根据需求文档和已存在的 HTML 原型生成可执行开发计划与任务编排清单。 |
| `automation-setup-assistant` | 创建、更新、验证和排查 Codex 自动化任务，包括权限、网络、Git push、定时执行异常。 |
| `backend-memory-risk-report` | 分析 Java/Spring 等后端代码中的内存溢出、泄漏和异常增长风险，并输出结构化检查报告。 |
| `business-feature-audit` | 对当前改动做业务闭环核查，检查流程、状态、权限、上下游协同和数据一致性是否成立。 |
| `code-reviewer` | 对本地改动或远程 PR 做代码审查，重点关注正确性、可维护性和规范一致性。 |
| `development-trace` | 为当前需求生成开发留痕文档，沉淀改动目标、实现过程和最终结果。 |
| `dm-mcp-creator` | 创建并注册项目专用的达梦 DM 数据库 MCP 服务，补齐连接配置和安全限制。 |
| `project-design-md-generator` | 为前端项目生成或更新 `DESIGN.md`，沉淀 UI 规范、设计约束和复用规则。 |
| `requirement-closure-designer` | 先补全需求在系统中的完整功能闭环、页面入口、角色链路和状态流转，再决定是否进入正式需求文档编写。 |
| `requirement-doc-generator` | 基于已确认的需求闭环和项目现状生成正式 `requirement.md`；新增页面需配套 `prototypes/` 下的 HTML 原型，落地前先向用户确认。 |
| `sync-project-mcp` | 同步项目 `.codex-mcp` 与 Codex 本地 MCP 注册信息，并做握手验证。 |

## 使用方式

1. 在会话中直接描述需求，命中技能适用场景时，Codex 会按技能说明执行。
2. 如果想明确触发某个技能，可以在需求中直接点名技能名称或表达对应任务目标。
3. 使用前优先检查对应目录下的 `SKILL.md`，必要时补充 `references/`、模板或脚本资源。
4. 新增技能时，至少创建 `技能目录/SKILL.md`，写清名称、用途、触发条件、执行步骤和边界约束。
5. 如果技能要求显式触发，例如 `auto-plan-dev`，README 和 `SKILL.md` 都要同步写明“只有用户明确点名时才能使用”。
6. 需求类工作可先用 `requirement-closure-designer` 补齐闭环，再用 `requirement-doc-generator` 生成正式 `requirement.md`；两者职责不要混写。
7. 涉及页面需求时，`requirement-doc-generator` 负责判断是否创建 `prototypes/*.html` 并在落地前先做用户确认；`auto-plan-dev` 读取这些原型作为计划拆解、页面实现映射和验证依据，不得跳过原型直接按泛化文字拆任务。

## 编写建议

- 描述要聚焦“什么时候用、具体怎么做、哪些不能做”。
- 尽量把输出路径、交付物格式、确认节点和安全边界写死，减少执行歧义。
- 有固定模板或参考材料时，放进技能目录并在 `SKILL.md` 中显式引用。
- 技能面向复用，优先沉淀稳定流程，不把一次性上下文写进全局技能。
- 技能触发方式、关键资源、维护约束发生变化时，优先更新对应 `SKILL.md`，并同步检查本 README 的“当前技能”和使用说明是否仍准确。
- 对以需求文档为输入的技能，若新增或调整 `prototypes/`、README、脚本等关键依赖，也要同步检查 README 是否已写清资源职责和先后关系。

## 备注

- 本 README 只介绍 `~/.codex/skills/` 下的用户自定义技能，不包含 `~/.codex/skills/.system/` 里的系统内置技能。
- 技能内容调整后，建议同步更新对应目录的 `SKILL.md`，保持 README 与实际能力一致。
