# DESIGN.md 参考输出模板

归纳已有项目或初始化新项目的 `DESIGN.md` 时按需使用。本模板展示内容类型，不要求逐章复制。示例数值应替换为有效事实或已确认/授权范围内的设计值；未知项删除示例并说明缺口。

```md
---
version: alpha
name: 项目名称
description: 一句话说明项目的界面定位、主要用户和整体视觉方向
colors:
  primary: "#000000"
  secondary: "#000000"
  background: "#ffffff"
  surface: "#ffffff"
  text-primary: "#111111"
  text-secondary: "#666666"
  border: "#e5e7eb"
  success: "#16a34a"
  warning: "#f59e0b"
  danger: "#dc2626"
typography:
  heading-lg:
    fontFamily: 项目字体或字体栈
    fontSize: 24px
    fontWeight: 600
    lineHeight: 32px
  body-md:
    fontFamily: 项目字体或字体栈
    fontSize: 14px
    fontWeight: 400
    lineHeight: 22px
  label-sm:
    fontFamily: 项目字体或字体栈
    fontSize: 12px
    fontWeight: 400
    lineHeight: 18px
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
  input-default:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.sm}"
  card-default:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.md}"
---

# 项目名称 Design System

在已有适当位置或此处简述范围与依据、决策状态、实现状态及验证范围。初始化时明确哪些规则已确认但待实现，页面渲染尚未验证；已有项目按实际证据填写。

## 1. Visual Theme & Atmosphere

说明整体视觉主题、使用场景、信息密度和风格；已有项目对照有效契约和实现归纳，初始化采用已确认或授权范围内的设计方案。

用短句列出后续 AI 必须保持的关键特征，沿用项目已有表达与结构。

## 2. Color Palette & Roles

说明主色、辅助色、背景色、表面色、文本色、边框色和状态色的语义角色。若项目已有 CSS 变量或主题 token，应说明来源。

应说明哪些颜色可用于交互，哪些颜色只用于背景、文本、边框或状态，不要只列色值。

## 3. Typography Rules

说明标题、正文、标签、按钮、表单等主要文字层级。必须写清字体栈、字号、字重和行高的使用方式。

应包含字体家族、层级表和排版原则。

## 4. Component Stylings

说明本次需要的已有或已确认规划组件角色。按钮、输入框、卡片、表格、弹层和导航按首批任务选择，规划组件标为待实现，不伪造源码入口。

按任务与能力清单覆盖适用的任务反馈、组件状态及恢复路径；已确认但尚未实现的状态标为待实现，未确定规则列为缺口。

若项目已有或首批需求包含后台台账、业务列表、筛选页、弹窗或抽屉，这一章还应明确：

- 按结构规则补齐高密度界面所需的组件与承载策略

## 5. Layout Principles

说明页面容器、栅格、内容密度、间距节奏、断点和响应式策略。若项目没有明确断点，应写入 Known Gaps。

应包含 spacing scale、grid/container、whitespace philosophy。

若项目已有或首批需求包含高密度后台界面，这一章还应明确：

- 按结构规则补齐主数据区空间利用与滚动层级规则

## 6. Depth & Elevation

说明圆角、边框、阴影、分割线、透明度、遮罩、浮层和层级的使用规则。不要把偶然样式写成系统规则。

应说明项目如何表达层级：阴影、边框、背景差异、透明度、z-index、图片深度或无层级策略。

## 7. Do's and Don'ts

写可执行的使用规则，帮助后续 AI 在新增页面或组件时保持一致。Do 写应遵循的做法，Don't 写明确禁止的反模式。

## 8. Responsive Behavior

说明项目支持的视口、组件折叠及图片/表格/导航退化方式；移动布局、触摸或原生输入只在适用时覆盖。

如果项目没有明确响应式策略，应写入 Known Gaps。

若项目主要面向桌面端，说明项目实际支持的代表性视口下：

- 按结构规则补齐桌面降级策略

## 9. Agent Prompt Guide

给后续 AI 使用的快速提示指南，包含：

- Quick Color Reference
- Example Component Prompts
- Iteration Guide

提示内容必须基于本项目真实规范。

## 10. Known Gaps

记录未确定规则、实现偏差与验证缺口，并区分其性质。初始化整体待实现可在依据与状态说明中统一标注，不逐条重复。说明首个代表性页面落地后需校准的真实接入入口与验收证据；不自动安排开发或后续任务。
```

## 使用要求

- front matter 中的示例值必须替换为有效事实或已确认/授权范围内的设计值；未知时不保留示例，不把候选值伪装成已确认值。
- 组件状态与页面反馈按 [任务与能力规范覆盖](frontend-audit-checklist.md#任务与能力规范覆盖) 检查；格式与高密度界面要求见 [结构规则](design-md-structure.md)。
- 项目缺少某类 token 时，先判断是否需要用户确认；不影响主体系的缺口可写入 `## 10. Known Gaps`。
- 组件只写当前范围已有或已确认规划的必要角色，分别标注实现状态。
- 章节可按项目适配，无内容不建空章节；影响使用或验证的缺口必须说明，既有 token 和机器字段保持兼容。
- 布局与响应式可合并；Agent Prompt Guide 仅在能提供正文之外的接入指导时保留，不复制已有规则。只有项目机器契约或用户要求才固定章节。
- 项目已有 token 文件时引用来源及角色，不把示例 front matter 复制成第二份数值事实源。
- 初始化没有 token 实现时，DESIGN 可暂存已确认初始值；独立 token 入口建立后，在后续规范更新中迁移权威来源并改为引用。
