# Codex 全局 Skills 说明

这个目录存放当前用户自定义的 Codex 全局技能。每个技能使用独立目录管理，核心入口文件为 `SKILL.md`。

本文用于选择技能和定位资源；执行前读取所属 `SKILL.md` 及本次分支需要的资源，具体触发条件、流程、产物与验证要求由该入口维护。

## 目录用途

- 作用范围：放在 `~/.codex/skills/` 下的技能，可在 Codex 会话中作为全局技能被发现和使用。
- 适用场景：沉淀可复用的工作流、固定交付格式、项目化规范、数据库/MCP 接入流程和自动化排障能力。
- 组织方式：一个技能一个目录；有补充模板、参考文档或脚本时，放在技能子目录内统一维护。

## 当前技能

以下仅列带有 `SKILL.md` 的顶层自有技能，系统技能与辅助目录不计入。

当前共有 27 个用户自定义技能，按主要使用场景分为以下八类：

- [需求设计与开发交付](#需求设计与开发交付)：从需求闭环、正式需求到原型与开发计划。
- [项目文档与架构治理](#项目文档与架构治理)：维护协作约束、README、设计规范、架构和项目接手文档。
- [审查与业务分析](#审查与业务分析)：检查代码质量、业务闭环与内存风险，并还原已实现的业务流程。
- [服务器运维](#服务器运维)：按授权执行服务器操作、维护单位手册并完成 Git 留痕。
- [系统资源诊断](#系统资源诊断)：分析磁盘空间和进程资源占用，辅助定位清理目标与卡顿来源。
- [前端设计与体验治理](#前端设计与体验治理)：覆盖视觉设计、UX、设计规范合规与前端复用。
- [自动化与工具集成](#自动化与工具集成)：管理 Codex 自动化以及跨工具、MCP 配置同步。
- [Git 协作](#git-协作)：生成提交消息并按授权完成提交与推送。

### 需求设计与开发交付

| 技能入口 | 用途 |
| --- | --- |
| [development-workflow](development-workflow/SKILL.md) | 自动承接开发或计划请求，组织可执行、可验证的任务。 |
| [requirement-closure-design](requirement-closure-design/SKILL.md) | 把粗需求补全为可落地的业务闭环。 |
| [requirement-doc-authoring](requirement-doc-authoring/SKILL.md) | 生成可追溯、可验收的正式需求文档。 |
| [frontend-prototype-design](frontend-prototype-design/SKILL.md) | 制作 HTML 交互原型或结构图原型。 |

### 项目文档与架构治理

| 技能入口 | 用途 |
| --- | --- |
| [ai-constraint-doc-authoring](ai-constraint-doc-authoring/SKILL.md) | 生成项目级 AI 协作规则和 Claude 薄入口。 |
| [skill-authoring-standard](skill-authoring-standard/SKILL.md) | 统一用户自有技能的命名、编写和整体重构方式。 |
| [ai-instruction-refactoring](ai-instruction-refactoring/SKILL.md) | 为 AI 规则和提示词去重、压缩并明确边界。 |
| [project-module-architecture-doc-authoring](project-module-architecture-doc-authoring/SKILL.md) | 基于系统代码生成专一技术主题说明。 |
| [project-handover-analysis](project-handover-analysis/SKILL.md) | 评估项目或多仓交付包的接手条件。 |
| [project-readme-authoring](project-readme-authoring/SKILL.md) | 维护面向使用者和开发者的项目入口。 |

### 审查与业务分析

| 技能入口 | 用途 |
| --- | --- |
| [backend-memory-risk-analysis](backend-memory-risk-analysis/SKILL.md) | 识别后端内存泄漏、溢出和异常增长风险。 |
| [business-closed-loop-analysis](business-closed-loop-analysis/SKILL.md) | 面向开发者还原已实现业务目标的完整闭环。 |
| [business-feature-audit](business-feature-audit/SKILL.md) | 判断当前改动放回业务链路后是否完整成立。 |
| [code-review](code-review/SKILL.md) | 审查本地差异或远程 PR 的代码质量。 |

### 服务器运维

| 技能入口 | 用途 |
| --- | --- |
| [operation-workflow](operation-workflow/SKILL.md) | 接入服务器，按命令通配策略和获批方案操作、验证、归档。 |

### 系统资源诊断

| 技能入口 | 用途 |
| --- | --- |
| [system-disk-usage-analysis](system-disk-usage-analysis/SKILL.md) | 统计磁盘容量、目录占用并识别可安全清理目标。 |
| [system-process-usage-analysis](system-process-usage-analysis/SKILL.md) | 统计 CPU、内存和 IO 高占用进程并定位卡顿嫌疑。 |

### 前端设计与体验治理

| 技能入口 | 用途 |
| --- | --- |
| [design-compliance-audit](design-compliance-audit/SKILL.md) | 审核设计契约及实现遵循。 |
| [frontend-design](frontend-design/SKILL.md) | 指导页面新建、重构和局部视觉交互修改。 |
| [frontend-reuse-governance](frontend-reuse-governance/SKILL.md) | 判断及实施前端复用。 |
| [frontend-ux-audit](frontend-ux-audit/SKILL.md) | 审核可观察的页面体验。 |
| [design-spec-authoring](design-spec-authoring/SKILL.md) | 归纳已有项目规范或初始化新项目规范。 |

“优化页面”按目标选择：改善呈现用设计，找体验问题用 UX，核对设计契约用合规，治理重复实现用复用。混合任务只组合实际需要的技能；验证及联合审核复用 [前端验证规范](~/ai-agent-config/config/force/frontend/frontend-verification.md)。

### 自动化与工具集成

| 技能入口 | 用途 |
| --- | --- |
| [automation-management](automation-management/SKILL.md) | 配置、优化和排查 Codex 定时或自动化任务。 |
| [config-codex-sync](config-codex-sync/SKILL.md) | 将 Codex 技能与协作说明对齐到 Claude。 |
| [config-project-mcp-sync](config-project-mcp-sync/SKILL.md) | 注册、更新并验证当前项目的本地 MCP 服务。 |

### Git 协作

| 技能入口 | 用途 |
| --- | --- |
| [git-commit-message-authoring](git-commit-message-authoring/SKILL.md) | 根据确定的改动范围生成规范提交消息。 |
| [git-push](git-push/SKILL.md) | 按确定范围完成暂存、提交和已授权的推送。 |

## 使用方式

1. 直接描述目标，按上方技能清单选择适用入口；需要指定技能时使用 `$技能名称`。实际触发条件及显式调用要求由对应技能维护。
2. 执行前读取目标目录的 `SKILL.md`，按当前分支加载必要资源；不把 README 的能力摘要作为完整执行契约。
3. 需求协作按当前阶段选闭环、正式需求、原型或开发计划，阶段衔接见 [共用契约](~/ai-agent-config/config/force/requirement/requirement-collaboration.md)。已有成果按其角色继承，不因进入一个阶段自动补齐全链路。
4. 页面任务按 [前端设计与体验治理](#前端设计与体验治理) 选择所需技能；业务闭环核查、技术解释和项目接手评估分别从对应技能进入。

## 文档输出规则入口

- [文档编写规范](~/ai-agent-config/config/force/document-output.md)：内容组织、引用、保存和读者验收。
- [需求协作共用契约](~/ai-agent-config/config/force/requirement/requirement-collaboration.md)：需求、原型、计划的成果继承与交接。
- [固定模板设计与校验](skill-authoring-standard/references/template-validation.md)：模板语法与检查；具体产物从上方所属技能进入其唯一模板。

`.system/` 下的系统技能按各自入口维护契约：[skill-creator](.system/skill-creator/SKILL.md) 创建和更新技能，[review-agent](.system/review-agent/SKILL.md) 执行受委派的只读代码审查，[openai-docs](.system/openai-docs/SKILL.md) 提供 OpenAI 产品、API 与 Codex 文档指引，[imagegen](.system/imagegen/SKILL.md) 生成或编辑图像，[skill-installer](.system/skill-installer/SKILL.md) 安装技能。本 README 不另行定义这些技能的产物结构。

## 编写与维护入口

创建、重构或重命名自有技能使用 [技能编写规范](skill-authoring-standard/SKILL.md)；精简与职责审查使用 [AI 指令精简与重构](ai-instruction-refactoring/SKILL.md)。具体设计、命名及验证要求只在对应入口维护。

- 修改能力、触发条件、职责或资源入口时，先维护所属技能及权威资源，再同步受影响的消费者；本 README 仅更新用途、选用方式和入口摘要。
- 新增、删除或重命名顶层技能时同步“当前技能”清单；不将状态枚举、完整目录、流程门禁、命令清单或产物字段另抄到 README。

## 备注

本文只导航 Codex 全局技能；其他工具的安装与同步按对应任务执行。
