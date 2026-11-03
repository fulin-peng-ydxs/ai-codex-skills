# Codex 全局 Skills 说明

这个目录存放当前用户自定义的 Codex 全局技能。每个技能使用独立目录管理，核心入口文件为 `SKILL.md`。

本文维护技能清单、场景选择和资源导航；具体触发条件、执行流程、产物与验证要求以各技能的 `SKILL.md` 及其引用资源为准。

## 目录用途

- 作用范围：放在 `~/.codex/skills/` 下的技能，可在 Codex 会话中作为全局技能被发现和使用。
- 适用场景：沉淀可复用的工作流、固定交付格式、项目化规范、数据库/MCP 接入流程和自动化排障能力。
- 组织方式：一个技能一个目录；有补充模板、参考文档或脚本时，放在技能子目录内统一维护。

## 当前技能

以下列表只包含当前仓库中带有 `SKILL.md` 的用户自定义技能目录；`.system/`、`.git/`、`.idea/` 和未提供技能入口的辅助目录不计入“当前技能”。

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

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `development-workflow` | 自动承接开发或计划请求，组织可执行、可验证的任务。 | 默认普通模式直接承接自然语言，不强制 PRD；涉及页面时询问 HTML/结构图原型选择。专业模式要求正式需求文档及适用页面原型。 | 按意图自动调用，开发已获授权时按计划继续，只要计划则不开发；自动调用不额外生成计划文件，范围、覆盖、进度及两种模式的验证要求由技能维护。 |
| `requirement-closure-design` | 把粗需求补全为可落地的业务闭环。 | 分析角色、入口、操作、状态、权限、异常与范围，明确建议状态及未决事项。 | 默认先对话分析，要求保存或确认闭环可落地时保存当前成果；保留内容与确认状态，不自动转正式需求。 |
| `requirement-doc-authoring` | 生成可追溯、可验收的正式需求文档。 | 明确请求 PRD 或需求文档时，继承上游、核实项目事实，形成稳定编号、业务与页面契约、适用的非功能目标和验收。 | 产物格式与保存边界见技能入口；保存草案不等于确认；内部实现归计划，原型交给独立技能，复用已有有效成果。 |
| `frontend-prototype-design` | 制作 HTML 交互原型或结构图原型。 | 独立或承接需求/计划，形式未明确时询问选择；HTML 模拟交互，结构图提供页面线框和操作/状态说明，按形式验证。 | 默认在本次功能目录使用 `prototypes/{page-slug}.html` 或 `.md`；不要求先有 PRD，继承已有选择，不自动修改生产页面。 |

### 项目文档与架构治理

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `ai-constraint-doc-authoring` | 生成项目级 AI 协作规则和 Claude 薄入口。 | 按适用最低内容和项目结构生成或重构项目级 `AGENTS.md` 与 `CLAUDE.md`，按授权选择单文件或双文件交付与校验；基于仓库事实和实际命令验证落地，入口能引导后续 Agent 定位适用事实源。 | 统一维护命令发现、验证及权威文档，供 README 技能复用；验证范围按本次维护对象确定，专项事实与约束由调用方提供；入口保留 AI 约束，面向人的操作细节归 README 或专门指南，不反向依赖 README 生成。 |
| `skill-authoring-standard` | 统一用户自有技能的命名、编写和整体重构方式。 | 按统一一级领域、必要细分对象与任务能力命名，组织职责、输入、流程、约束、产出和验证，复用系统技能创建与基础校验能力。 | 创建或重命名先读命名规范并运行命名检查；结构要求见技能入口，重构须对照原核心契约并推演关键分支，格式通过不等于语义保留。 |
| `ai-instruction-refactoring` | 为 AI 规则和提示词去重、压缩并明确边界。 | 精简、重构和规范 AI 约束文档、`DESIGN.md`、技能说明、自动化规则与提示词规范，保留最新事实和稳定执行约束；同时保留目标读者理解和执行所需的说明。 | 合并相近规则但不删除面向开发者、运维或业务读者的必要操作步骤；README 和操作指南须保留主要路径。 |
| `project-module-architecture-doc-authoring` | 基于系统代码生成专一技术主题说明。 | 支持功能模块、平台子系统、系统架构、部署架构和特定技术解析，解释组成、机制、依赖、接入与变更影响。 | 技术机制在所属专题维护；逐环节业务明细引用闭环文档，具体环境操作归运维手册，整体交付评估归接手报告。 |
| `project-handover-analysis` | 评估项目或多仓交付包的接手条件。 | 生成指定版本的完整性、风险与接手路径快照，保留系统全景、关键模块及最小接手链路。 | 引用已有技术专题和业务闭环事实，不复制长期手册；缺失须有预期证据，静态确认与实际运行分开。 |
| `project-readme-authoring` | 维护面向使用者和开发者的项目入口。 | 生成、重构或局部更新 README，提供定位、最小使用路径、常用开发任务及文档导航。 | 命令复用 AI 约束技能维护的 AGENTS 或其命令正文；来源缺少或失效时先调用该技能补齐，不独立发现和验证命令。 |

### 审查与业务分析

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `backend-memory-risk-analysis` | 识别后端内存泄漏、溢出和异常增长风险。 | 分析 Java/Spring 等后端代码中的内存溢出、泄漏和异常增长风险，并输出结构化检查报告。 | 优先延续同范围已有报告；无既有成果时默认输出到 `docs/check/memory/{日期}.md`。缺少运行时证据时只能标记为潜在或疑似风险。 |
| `business-closed-loop-analysis` | 面向开发者还原已实现业务目标的完整闭环。 | 深入跨模块链路中的角色、状态联动、权限、任务、表关系、字段赋值与消费口径，保留代码证据。 | 不替代共享技术机制或接手评估；默认对话交付，明确要求生成、保存或更新文档时才落盘。 |
| `business-feature-audit` | 判断当前改动放回业务链路后是否完整成立。 | 对当前改动做业务闭环核查，检查流程、状态、权限、上下游协同和数据一致性是否成立。 | 不替代页面 UX、DESIGN 合规或前端复用审查；写入报告前需确认范围。 |
| `code-review` | 审查本地差异或远程 PR 的代码质量。 | 对本地改动或远程 PR 做代码审查，重点关注正确性、可维护性和规范一致性。 | 先明确审查范围；以可复现的正确性问题和项目规范为主要依据。 |

### 服务器运维

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `operation-workflow` | 接入服务器，按命令通配策略和获批方案操作、验证、归档。 | 运维初始化、服务盘点、排障/变更及操作手册维护。 | 提供 JSON 模板与只读判定脚本；文件单个不超过 15 MB，提交前检查实际 Git 索引；不提供系统级隔离。 |

### 系统资源诊断

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `system-disk-usage-analysis` | 统计磁盘容量、目录占用并识别可安全清理目标。 | 分析当前电脑的磁盘使用情况，定位高占用目录和内容类型，评估可释放空间并给出分级清理建议。 | 默认只读分析；任何清理都要先列明完整路径、预计释放空间和风险，并取得用户明确确认。 |
| `system-process-usage-analysis` | 统计 CPU、内存和 IO 高占用进程并定位卡顿嫌疑。 | 分析当前电脑的进程数量、资源占用和类型分布，识别最可能引起卡顿的进程或程序类别。 | 结果是当前时刻快照；结束、重启或 `kill` 进程前必须取得用户明确同意。 |

### 前端设计与体验治理

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `design-compliance-audit` | 审核设计契约及实现遵循。 | 检查规范有效性、实现偏离、登记维护和验收缺口。 | 继承任务范围；只审核时不改实现或规范，不承担独立体验或代码重复评价。 |
| `frontend-design` | 指导页面新建、重构和局部视觉交互修改。 | 根据产品任务、设备与既有设计系统确定呈现；品牌页有设计自由时强化主题辨识度、字体版式与反模板化检查。 | 纯逻辑修复不启用；局部修改不自动重设计全页，视觉探索不覆盖指定风格或产品规范。 |
| `frontend-reuse-governance` | 判断及实施前端复用。 | 查找同类组件、状态、工具与样式，判断第二次出现及抽象边界。 | 只审核时给建议；开发或已授权修复时才抽取、迁移和验证消费者。 |
| `frontend-ux-audit` | 审核可观察的页面体验。 | 检查视觉、交互、反馈、控件必要性和原型实现偏差。 | 继承页面或 diff 范围；独立审核无范围时覆盖可访问页面，不以代码私有或共享 class 判 UX 缺陷。 |
| `design-spec-authoring` | 归纳已有项目规范或初始化新项目规范。 | 已有前端依据有效契约与实现更新 `DESIGN.md`；从零项目依据需求、品牌及已确认方案建立初版，无须先有代码。 | 默认只改文档；分别标注决策、实现与验证状态，必要设计方案由 `frontend-design` 协助，已有授权不重复确认。 |

按用户目标选择主技能，只有任务需要时才组合：

| 用户目标 | 技能选择 |
| --- | --- |
| 新建页面、调整布局或视觉方向 | `frontend-design`；实现涉及复用时配合 `frontend-reuse-governance` |
| 局部样式、密度、界面文案或交互呈现修改 | 按需使用 `frontend-design`，继承受影响区域和消费者范围 |
| 请求、状态计算或事件逻辑修复 | 按代码任务处理；涉及前端复用判断时使用 `frontend-reuse-governance` |
| 体验审核、页面验收或体验修复后的复测 | `frontend-ux-audit` |
| 设计契约有效性与实现遵循审核 | `design-compliance-audit` |
| 重复实现、复用与抽象边界审核 | `frontend-reuse-governance` 的只读模式 |
| 从已有项目归纳、补齐或更新设计规范 | `design-spec-authoring` 的事实归纳或修订流程 |
| 新项目没有代码，先建立设计规范 | `design-spec-authoring` 的初始化流程；需要设计选择时配合 `frontend-design`，不自动开发页面 |
| 全面页面审核并修复 | 组合体验、合规与复用审核，共享证据、合并同根因问题，在授权范围内修复并复测 |

“优化页面”按意图判断：直接改善呈现选设计，先找体验问题选 UX，按规范整改选合规，减少重复选复用。混合任务按阶段组合；只有修复需要新的呈现方案时才追加设计技能，不默认加载全部技能。

通用任务与状态检查适用于桌面和移动端；触摸、原生输入、安装与缓存按实际能力选择。验证与联合审核的方法统一维护在 [前端验证规范](~/ai-agent-config/config/force/frontend-verification.md)。引用该规范不会自动启动 UX 审核；分发技能时须确保统一规范仓库在约定路径可读。

### 自动化与工具集成

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `automation-management` | 配置、优化和排查 Codex 定时或自动化任务。 | 创建、更新、精简、验证和排查 Codex 自动化任务，包括提示词职责边界、权限、网络、Git push 和定时执行异常。 | 提示词只写差异化约束；网络、推送和持久授权必须保持明确且最小化。 |
| `config-codex-sync` | 将 Codex 技能与协作说明对齐到 Claude 和 Kimi。 | 将 Codex 全局 skills 与协作说明同步到 Claude Code、Kimi Code 的用户级目录，默认先预览再执行正式同步；Claude 目标文档为 `CLAUDE.md`、Kimi 目标文档为 `AGENTS.md`，保留目标端独有技能或文件，并显式排除所有 MCP 相关技能。 | 必须先 `--dry-run`；运行时路径按目标环境适配，局部同步使用隔离临时源；默认增量保留，显式 `--delete` 仅清理符合管理清单或可信历史基线条件的受管内容，保留目标独有及已修改内容。 |
| `config-project-mcp-sync` | 注册、更新并验证当前项目的本地 MCP 服务。 | 将项目 `.mcp.json` 与 `.codex-mcp` 中声明的 MCP 启动参数同步到 Codex 本地注册信息，并做握手验证。 | 只处理项目真实声明的服务；实际同步后按请求做 JSON-RPC 握手；只检查用 `--dry-run`，只列出再加 `--no-validate`，避免泄露敏感配置。 |

### Git 协作

| 技能目录 | 简要功能说明 | 主要用途 | 使用注意事项 |
| --- | --- | --- | --- |
| `git-commit-message-authoring` | 根据确定的改动范围生成规范提交消息。 | 基于已确定的 Git 改动范围生成规范化提交消息，默认使用 `Agent` 项目标识，并按单行模板或完整模板输出提交文案；仅显式调用技能时交互确认范围，流程内自动调用时自行核定范围。 | 只输出提交文案，不执行 `git add`、`git commit` 或 `git push`。 |
| `git-push` | 按确定范围完成暂存、提交和已授权的推送。 | 按确定范围完成 Git 暂存、提交与用户已授权的推送，提交文案统一调用 `git-commit-message-authoring`；仅显式调用技能时执行文件范围、提交文案、staged 清单和 push 的交互确认，普通提交流程由 AI 自行核定并连续执行。 | 不扩大文件范围；只有用户要求推送时才执行 `git push`。 |

## 使用方式

1. 直接描述目标，按上方技能清单选择适用入口；需要指定技能时使用 `$技能名称`。实际触发条件及显式调用要求由对应技能维护。
2. 执行前读取目标目录的 `SKILL.md`，按当前分支加载必要资源；不把 README 的能力摘要作为完整执行契约。
3. 需求协作按当前阶段选闭环、正式需求、原型或开发计划，阶段衔接见 [共用契约](requirement-doc-authoring/references/workflow-contract.md)。已有成果按其角色继承，不因进入一个阶段自动补齐全链路。
4. 页面任务按“前端设计与体验治理”中的选择表组合所需技能；业务闭环核查、技术解释和项目接手评估分别从对应技能进入。

## 文档输出规则入口

通用规则见 [文档输出规范](~/ai-agent-config/config/force/document-output.md)，权威归属见 [文档边界规范](~/ai-agent-config/config/force/document-boundaries.md)。下表只按产物用途选择入口，不另定义结构策略、目录或字段。规范接入方式由 [技能编写规范](skill-authoring-standard/SKILL.md#核心约束) 维护，机器检查用法见 [模板检查器](skill-authoring-standard/references/template-validation.md)。

| 产物或任务 | 技能范围 | 权威入口 |
| --- | --- | --- |
| 需求闭环、正式需求与开发计划 | `requirement-closure-design`、`requirement-doc-authoring`、`development-workflow` | [需求协作共用契约](requirement-doc-authoring/references/workflow-contract.md)及各阶段唯一模板 |
| 页面原型 | `frontend-prototype-design` | [原型入口](frontend-prototype-design/SKILL.md)及其引用的结构图模板、HTML 交互契约 |
| 项目协作与技术事实文档 | `ai-constraint-doc-authoring`、`project-readme-authoring`、`project-module-architecture-doc-authoring`、`business-closed-loop-analysis`、`design-spec-authoring` | 各所属技能引用的唯一产物模板 |
| 分析与审核报告 | `code-review`、`backend-memory-risk-analysis`、`business-feature-audit`、`design-compliance-audit`、`frontend-ux-audit`、`system-disk-usage-analysis`、`system-process-usage-analysis` | 各所属技能的报告模板；分析方法及判断规则由其声明的入口维护 |
| 前端设计方案与复用反馈 | `frontend-design`、`frontend-reuse-governance` | [设计方案入口](frontend-design/SKILL.md)及[复用治理入口](frontend-reuse-governance/SKILL.md) |
| 项目接手评估 | `project-handover-analysis` | [接手报告模板](project-handover-analysis/assets/project-handover-report-template.md) |
| 运维方案、汇报、记录与手册 | `operation-workflow` | [运维流程](operation-workflow/SKILL.md)及[各类文档模板](operation-workflow/references/output-templates.md) |
| 文档维护、委派与对话审查 | `ai-instruction-refactoring`、`automation-management`、`config-codex-sync`、`code-review` | 各技能入口及目标文档的既有契约 |
| 提交消息与机器配置 | `git-commit-message-authoring`、`git-push`、`config-project-mcp-sync` | 提交消息 A/B 契约及 MCP 的配置字段、协议与结果分类 |

`.system/` 下的系统技能按各自入口维护契约：[skill-creator](.system/skill-creator/SKILL.md) 创建和更新技能，[review-agent](.system/review-agent/SKILL.md) 执行受委派的只读代码审查，[openai-docs](.system/openai-docs/SKILL.md) 提供 OpenAI 产品、API 与 Codex 文档指引，[imagegen](.system/imagegen/SKILL.md) 生成或编辑图像，[skill-installer](.system/skill-installer/SKILL.md) 安装技能。本 README 不另行定义这些技能的产物结构。

## 编写与维护入口

创建、重构或重命名自有技能使用 [技能编写规范](skill-authoring-standard/SKILL.md)；精简与职责审查使用 [AI 指令精简与重构](ai-instruction-refactoring/SKILL.md)。具体设计、命名及验证要求只在对应入口维护。

- 修改能力、触发条件、职责或资源入口时，先维护所属技能及权威资源，再同步受影响的消费者；本 README 仅更新用途、选用方式和入口摘要。
- 新增、删除或重命名顶层技能时同步“当前技能”清单；不将状态枚举、完整目录、流程门禁、命令清单或产物字段另抄到 README。

## 备注

- “当前技能”列表介绍 `~/.codex/skills/` 下的用户自定义技能；`.system/` 仅在输出规则入口说明相关契约，不列为用户自定义技能。
