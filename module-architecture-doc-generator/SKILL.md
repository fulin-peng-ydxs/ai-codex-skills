---
name: module-architecture-doc-generator
description: 分析项目代码与现有文档后，按业务模块、平台模块或技术子系统生成和更新架构设计文档。用于用户要求梳理项目架构、为每个模块生成 architecture 文档、补全核心技术/业务架构/使用说明/流程/风险事项、建立模块文档索引、同步 README 与 AGENTS 文档入口的场景。
---

# 模块架构文档生成器

## 核心规则

按模块生成当前事实架构文档，不写愿景文档、历史流水或未落地方案。每个结论必须能在代码、配置、路由、数据结构、测试或权威文档中找到依据。

除命令、代码、文件名、机器字段和目标仓库已有英文约定外，默认使用简体中文；用户明确要求英文时再改用英文。

## 执行流程

1. 发现模块和事实源。
   - 读取 `README.md`、`AGENTS.md`、已有架构/设计/API/需求文档、主要源码目录、路由、服务、存储、前端页面、测试和配置。
   - 运行 `scripts/detect_architecture_modules.py <repo-root>` 收集候选模块、现有架构文档、API/服务/前端/测试入口。
   - 输出目录按固定顺序决策：用户指定目录 > 项目已有架构目录 > `agent-works/architecture/`。没有现成架构目录时，创建并使用 `agent-works/architecture/`。

2. 选择模块边界。
   - 读取 `references/module-discovery.md`。
   - 按业务闭环、用户入口、API/CLI 边界、数据所有权、平台能力或技术子系统划分模块。
   - 不把每个文件夹机械生成成一篇文档；也不把多个职责强行塞进一篇大文档。

3. 确定文档结构。
   - 完整读取并遵守 `references/output-contract.md`，使用固定 Markdown 二级章节、固定顺序和最低内容。
   - 读取 `references/architecture-doc-model.md`，按业务、平台、数据、前端、集成或运维模块调整固定章节内的内容，不改变默认章节名称和信息归属。
   - 用户明确指定结构或仓库存在必须保持的文档/机器契约时才偏离默认骨架，并在交付说明中记录原因。

4. 验证事实。
   - 读取 `references/evidence-and-quality.md`。
   - 文档中的路径、API、命令、表名、配置项、页面入口和测试名称必须回查确认。
   - 不确定的内容不要写成事实；需要用户决策时先给推荐方案和依据。

5. 落地与索引。
   - 一项模块一篇文档，文件名使用稳定 kebab-case：`<output-dir>/<module-slug>.md`。
   - 有现有文档时优先更新原文件，不重复创建相同模块文档。
   - 对每个输出文件运行 `scripts/validate_architecture_doc_structure.py <document-path>`；存在已说明的结构例外时改用 `--custom-structure`。校验失败时先修复，不交付未通过的文档。
   - 同步需要的文档入口，例如 README 的文档索引或架构目录索引；不要复制全文。
   - 汇报写入文件的绝对路径、覆盖模块、证据来源和未覆盖风险。

## 文档边界

- 架构文档：解释当前模块如何工作、由哪些代码和数据支撑、如何使用、有哪些风险。
- README：只做项目入口和文档索引，不承载每个模块全部细节。
- AGENTS.md：AI 协作约束，只引用稳定架构入口，不复制模块说明。
- 需求/计划/开发留痕：记录目标、计划和过程；架构文档只沉淀当前已成立事实。

## 资源入口

- `references/module-discovery.md`：模块识别和拆分规则。
- `references/output-contract.md`：固定章节、最低内容、内容归属和已有文档迁移规则；生成或重构时必须完整读取。
- `references/architecture-doc-model.md`：不同模块类型在固定章节中的内容适配方式。
- `references/evidence-and-quality.md`：证据、去冗余、风险和落地检查。
- `scripts/detect_architecture_modules.py`：项目模块候选扫描脚本，只辅助发现，不替代代码阅读。
- `scripts/validate_architecture_doc_structure.py`：校验固定章节、顺序、重复标题、空章节和占位内容。
