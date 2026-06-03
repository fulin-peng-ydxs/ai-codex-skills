# DESIGN.md 结构参考

本文件用于约束生成结果的结构，不用于规定具体品牌风格。

## 作用

本文件是技能执行时直接使用的固定结构规则。

技能应把本文件视为稳定模板，不再临时查阅外部资料，也不要在不同项目之间随意改变章节结构、token 粒度和描述方式，除非用户明确要求调整。

## 目标

本地固定模板采用以下原则：

- 顶部 YAML front matter 放 token
- 正文使用 `##` 分节解释设计语言及落地方式
- token 提供精确值，正文解释如何使用

## 推荐文件结构

生成最终文件时优先使用 `references/design-md-template.md`。下面结构只用于说明关键区块：

```md
---
version: alpha
name: 项目名称
description: 项目设计系统描述
colors:
  primary: "#..."
  secondary: "#..."
typography:
  body-md:
    fontFamily: ...
    fontSize: ...
rounded:
  sm: 4px
  md: 8px
spacing:
  sm: 8px
  md: 16px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
---

# 项目名称 Design System

## 1. Visual Theme & Atmosphere

## 2. Color Palette & Roles

## 3. Typography Rules

## 4. Component Stylings

## 5. Layout Principles

## 6. Depth & Elevation

## 7. Do's and Don'ts

## 8. Responsive Behavior

## 9. Agent Prompt Guide

## 10. Known Gaps
```

## 字段要求

- `version`：建议使用 `alpha`
- `name`：项目名或产品名
- `description`：一句话说明整体视觉方向和使用场景
- `colors`：至少覆盖主色、辅助色、文本色、背景色、边框色、状态色中与项目直接相关的部分
- `typography`：至少覆盖标题、正文、按钮或标签中的主要文本样式
- `rounded`：给出可复用的圆角层级
- `spacing`：给出最小可复用间距刻度
- `components`：只写项目中真实存在且高频的关键组件

## 写作原则

- 优先使用 token 引用，不要在组件定义里反复内联 hex 值
- 优先写“稳定规律”，不要把偶然样式当成系统规则
- 组件状态可独立命名，如 `button-primary-active`
- 正文描述应解释风格和使用边界，而不是堆砌营销形容词
- 如果某些值是经确认后补全的，应保证与项目整体风格一致

## 稳定模板要求

应保持这些方面稳定：

- 章节拆分方式：固定使用 1-9 号章节，`Known Gaps` 作为第 10 章
- token 颗粒度
- 对组件和布局的描述方法
- 对已知缺口和注意事项的记录方式

不要出现这些问题：

- 品牌名称
- 品牌叙事
- 专属字体、专属视觉隐喻
- 与当前项目无关的组件体系

## 固定格式要求

应固定保留这些内容：

- 顶部 YAML front matter + 正文 Markdown 分层结构
- `colors`、`typography`、`rounded`、`spacing`、`components` 等常见 token 区块
- 使用 `{colors.primary}` 这类 token 引用，而不是重复硬编码
- `Visual Theme & Atmosphere`、`Color Palette & Roles`、`Typography Rules`、`Component Stylings`、`Layout Principles`、`Depth & Elevation`、`Do's and Don'ts`、`Responsive Behavior`、`Agent Prompt Guide` 的固定章节顺序

可按项目实际灵活处理的内容：

- 具体 token 命名，只要清晰稳定即可
- 组件覆盖范围，可按项目实际复杂度裁剪
- 已知缺口说明，统一写入 `## 10. Known Gaps`
