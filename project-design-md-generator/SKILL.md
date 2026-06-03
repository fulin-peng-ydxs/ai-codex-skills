---
name: project-design-md-generator
description: 为当前项目生成或更新项目专属的 `DESIGN.md`。这是 `VoltAgent/awesome-design-md` 同类能力的本地化技能：扫描当前项目前端，把页面、组件、样式、主题和设计 token 沉淀成 AI 可读取的项目级 UI 规范；如果前端不统一或缺少关键规范，先给出补齐建议并确认后再生成。执行时使用技能内置的固定结构、规则和模板，不依赖外部仓库。
---

# Project DESIGN.md Generator

为当前项目的前端实现生成项目专属 `DESIGN.md`，让后续 AI 能按项目已有视觉语言和可确认的规范持续生成一致界面。

本技能对应的是 `VoltAgent/awesome-design-md` 这类“把网站/项目提炼成 DESIGN.md”的能力，但规则已经固化在技能本地文件中。执行时不要联网读取外部模板。

## 适用范围

在以下场景使用本技能：

- 用户要求根据当前项目前端生成、补齐或更新 `DESIGN.md`
- 用户要求把现有页面、组件、样式、主题、设计 token 沉淀成 AI 可读取的 UI 约束文档
- 用户要求先检查前端是否规范，再决定如何生成 `DESIGN.md`

本技能的目标是生成或更新文档，不直接修改业务前端代码，除非用户另外要求。

## 核心原则

- 本技能已把 `awesome-design-md` 同类能力内化为本地固定流程和模板；执行时不要再临时学习外部仓库。
- `DESIGN.md` 必须基于当前项目真实前端实现、可验证样式和已存在的设计模式生成。
- 如果项目现有前端明显不统一、缺少必要规范或多个风格冲突，不要强行把混乱现状写成规范；先提出收敛建议并等待用户确认。
- 生成 `DESIGN.md` 时优先抽取稳定事实，其次才是合理补全；补全内容必须明确是建议性决策，而不是伪装成既有事实。

## 固定规则来源

本技能执行时只使用技能目录中的本地规则，不依赖外部仓库或在线文档。

执行时按以下方式落地：

1. 先读取 `references/design-md-structure.md`
2. 再读取 `references/frontend-audit-checklist.md`
3. 需要写入时读取 `references/design-md-template.md`
4. 按本地规则扫描项目并生成或更新 `DESIGN.md`

其中：

- `references/design-md-structure.md` 定义固定的 `DESIGN.md` 结构、章节顺序、token 粒度和写作方式
- `references/frontend-audit-checklist.md` 定义何时可直接生成、何时必须先给建议并等待确认
- `references/design-md-template.md` 定义最终输出骨架，生成时应优先套用该模板

不要在执行过程中临时依赖外部资料重新学习模板，也不要把外部品牌文案、品牌叙事或第三方专属组件体系写入当前项目的 `DESIGN.md`。

## 信息来源

按以下顺序收集证据：

1. 用户给出的项目路径、页面范围、产品定位和额外约束
2. 当前项目中的前端入口、页面、组件、样式文件、主题文件、设计 token 文件
3. 运行中的样式约定：颜色变量、字体栈、间距、圆角、阴影、边框、断点、组件状态
4. 项目已有设计文档、组件库文档、品牌规范、设计系统文件
5. 项目已有 `DESIGN.md`，如果存在
6. 技能内置的 `references/design-md-structure.md` 和 `references/design-md-template.md`

不要把未经查看的样式、未验证的视觉规律或主观偏好写成事实。

## 扫描范围

优先检查这些文件类型：

- 页面和组件：`*.html`、`*.jsx`、`*.tsx`、`*.vue`
- 样式和主题：`*.css`、`*.scss`、`*.less`、`tailwind.config.*`、`theme.*`、`tokens.*`
- 设计系统线索：组件库目录、布局组件、基础表单组件、按钮、表格、弹窗、导航

默认不要深挖后端、数据库、接口或无关脚本，除非它们直接决定前端文案、状态或主题配置来源。

扫描时先全局定位候选文件，再重点阅读代表性文件。应优先使用 `rg` 或等价工具查找以下线索：

- 颜色：hex、rgb、hsl、CSS 变量、主题色变量
- 字体：`font-family`、字号、字重、行高
- 间距和尺寸：`margin`、`padding`、`gap`、容器宽度、断点
- 形状和层级：`border-radius`、`box-shadow`、`border`
- 组件状态：hover、active、focus、disabled、loading、error、success

## 输出位置

默认输出到项目根目录：

```text
./DESIGN.md
```

如果用户明确指定其他路径，按用户要求处理。

## 执行流程

1. 定位项目根目录，确认当前项目是否存在可分析的前端代码。
2. 读取 `references/design-md-structure.md` 和 `references/frontend-audit-checklist.md`。
3. 检查项目根目录是否已有 `DESIGN.md`；如果存在，必须读取并判断是更新、合并还是重写。
4. 识别前端技术栈、样式组织方式、样式入口和设计 token 来源。
5. 全局定位候选页面、组件、样式和主题文件，再重点阅读代表性页面、基础组件和样式入口。
6. 对照 `references/frontend-audit-checklist.md` 判断项目是否具备直接生成或更新 `DESIGN.md` 的条件。
7. 如果条件充分且不存在必须确认的情况，读取 `references/design-md-template.md` 并生成或更新 `DESIGN.md`。
8. 如果存在明显缺口、冲突、已有文档覆盖风险或需要补规范，先输出“拟定规范建议”和“拟生成范围”，等待用户确认。
9. 用户确认后，按 `references/design-md-template.md` 的骨架生成项目专属 `DESIGN.md`。
10. 完成后汇报依据文件、更新策略、哪些内容来自事实抽取、哪些内容是经确认后的补全建议。

## 何时必须先确认

出现以下任一情况时，必须先向用户确认后再写入 `DESIGN.md`：

- 主色、字体、圆角、间距或阴影体系存在多套冲突方案
- 页面风格明显不统一，无法判断应以哪部分为主
- 项目缺少关键规范，无法完整定义组件或布局规则
- 需要在多个候选方向之间做产品级选择，例如“保留旧后台风格”还是“收敛为新的统一风格”
- 用户要求“顺便帮我补一套更合理规范”
- 项目已有 `DESIGN.md`，且本次会删除、重写或改变其中的关键设计决策

确认时应给出：

- 已识别到的前端现状摘要
- 发现的不一致或缺失项
- 建议采用的收敛方案
- 生成 `DESIGN.md` 后会写入的关键决策
- 如果已有 `DESIGN.md`，说明更新策略：保留、合并、修正或重写

用户未确认前，不要把这些建议性决策写入 `DESIGN.md`。

## DESIGN.md 写作要求

生成的 `DESIGN.md` 必须满足以下要求：

- 使用项目自己的名称和定位，不写成苹果、特斯拉或其他品牌的替身
- 使用技能内置模板结构，保持 `awesome-design-md` 同类 9 段式章节，内容完全根据项目前端归纳
- token 和 prose 同时存在：既要有可引用的颜色、字体、圆角、间距、组件 token，也要有解释这些 token 如何使用的章节
- 章节顺序和字段命名尽量兼容通用 `DESIGN.md` 规范
- 对缺失但必要的规范，只在用户确认后补入
- 避免空泛形容词，优先写可执行、可落地、可复用的规则

## 最低内容要求

生成的 `DESIGN.md` 至少应覆盖：

- 文件头部元数据：`version`、`name`、`description`
- 基础 token：`colors`、`typography`、`rounded`、`spacing`
- 关键组件：至少包含按钮、输入类组件、卡片/面板、导航或页面容器中的主要一种
- 说明章节：Visual Theme & Atmosphere、Color Palette & Roles、Typography Rules、Component Stylings、Layout Principles、Depth & Elevation、Do's and Don'ts、Responsive Behavior、Agent Prompt Guide
- 可选缺口章节：Known Gaps，用于记录项目缺少或无法确认的规范

如果项目确实没有某一类内容，可以省略细节，但要在文档中注明已知缺口。

## 建议输出格式

当需要先确认时，先输出：

```markdown
## 前端现状摘要

## 发现的问题

## 建议补齐的规范

## 拟写入 DESIGN.md 的关键决策

请确认是否按以上方案生成 `DESIGN.md`
```

确认后再创建最终文档。

## 输出约束

- 输出内容使用中文，`DESIGN.md` 中的 token 名和标准字段名可保留英文
- 不把“推测”“审美偏好”“参考品牌描述”写成项目事实
- 不直接复制第三方 `DESIGN.md` 的品牌文案
- 不为了凑完整度发明大量项目中根本不存在的组件
- 如项目前端过少、几乎无样式依据，明确说明无法可靠生成完整 `DESIGN.md`，并给出最小补充建议

## 参考文件

- 结构规则：`references/design-md-structure.md`
- 审核清单：`references/frontend-audit-checklist.md`
- 输出模板：`references/design-md-template.md`
