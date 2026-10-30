# DESIGN.md 参考输出模板

归纳已有项目或初始化新项目的 `DESIGN.md` 时按需使用。本模板展示内容类型，不要求逐章复制。示例数值应替换为有效事实或已确认/授权范围内的设计值；未知项删除示例并说明缺口。

产出文档按 SKILL.md 的“产出文档边界”补充用途与内容归属；已有适用范围章节可合并承载，不重复定义 token 等机器事实源。

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

# 项目名称 设计系统

在已有适当位置或此处简述范围与依据、决策状态、实现状态及验证范围。初始化时明确哪些规则已确认但待实现，页面渲染尚未验证；已有项目按实际证据填写。

## 1. 设计方向与适用范围

说明视觉主题、目标用户、使用场景、信息密度及必须保持的特征；注明有效契约、已确认/授权选择和实现依据。项目整体的决策、实现及验证状态可在此统一说明，差异留在对象旁。

## 2. 基础语义与共享规则

- 色彩：主色、辅助色、背景/表面、文本、边框、状态色的角色与交互边界；引用实际 token 来源，不另抄数值。
- 排版：字体栈与标题、正文、标签、按钮、表单层级，说明字号、字重、行高的用途和权威来源。
- 空间与层级：间距刻度、容器/栅格、留白、信息密度、通用断点与响应式策略；圆角、边框、阴影、分割线、透明度、遮罩及 z-index 的表达方式；有图片深度或无层级策略时说明其适用范围。

共用规则写适用条件、依据及判据；没有明确断点或层级机制时说明缺口，不把偶然实现提升为规范。

## 3. 组件与页面模式

### {组件或页面模式名称}

说明适用任务、选择依据、真实接入入口及 token 角色；已有或已确认规划组件按本次范围选择，拟建项标为待实现，不伪造 API/路径。

将使用方式、主次操作、组件状态、任务反馈与失败恢复、禁用方式及可观察判据放在一起。按实际覆盖加载、空、错误、权限、提交等适用状态；记录局部决策/实现/验证差异。

布局说明容器、内容密度、间距、滚动层级和浮层承载；视口变化说明字段/图片/表格/导航折叠、长内容入口及任务如何继续。触摸、移动或原生输入仅在适用时覆盖。

后台台账、列表、筛选、弹窗/抽屉等高密度场景按结构规则落实主数据区空间、末项/操作可达、列宽与长内容、主次操作、容器选择和桌面退化判据，不另抄一套无对象的布局或响应式清单。

## 4. 未决事项与接入索引

汇总尚待决定的规则、实现偏差和验证缺口，回指所属对象并说明影响。初始化整体待实现在开头统一标注；首个代表性页面落地后需校准真实入口与验收证据，不自动安排开发任务。

需要时提供真实组件/token/规范入口及新增规则的维护位置。AI 提示示例与迭代指南仅保留正文之外的接入指导；不复制色彩速查和禁用规则。
```

## 使用要求

- front matter 中的示例值必须替换为有效事实或已确认/授权范围内的设计值；未知时不保留示例，不把候选值伪装成已确认值。
- 组件状态与页面反馈按 [任务与能力规范覆盖](frontend-audit-checklist.md#任务与能力规范覆盖) 检查；格式与高密度界面要求见 [结构规则](design-md-structure.md)。
- 项目缺少某类 token 时，先判断是否需要用户确认；不影响主体系的缺口可写入未决事项的对应位置。
- 组件只写当前范围已有或已确认规划的必要角色，分别标注实现状态。
- 章节可按项目适配，无内容不建空章节；影响使用或验证的缺口必须说明，既有 token 和机器字段保持兼容。
- 布局与响应式可合并；“AI 提示指南”仅在能提供正文之外的接入指导时保留，不复制已有规则。只有项目机器契约或用户要求才固定章节。
- 项目已有 token 文件时引用来源及角色，不把示例 front matter 复制成第二份数值事实源。
- 初始化没有 token 实现时，DESIGN 可暂存已确认初始值；独立 token 入口建立后，在后续规范更新中迁移权威来源并改为引用。
