# DESIGN.md 结构参考

本文件定义 `DESIGN.md` 的参考结构。

## 基本要求

- 没有既有 token 事实源时可在 YAML front matter 定义；已有 token 文件引用其入口，机器契约优先
- 正文使用 `##` 分节
- token 提供精确值，正文解释如何使用

## 内容结构

新建文档参考 `references/design-md-template.md`；下列区块按项目适用性覆盖，既有机器契约优先：

```md
---
version: alpha
name: 项目名称
description: 项目设计系统描述
colors:
  primary: "#..."
  secondary: "#..."
  on-primary: "#..."
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

## Front Matter

- `version`：建议使用 `alpha`
- `name`：项目名或产品名
- `description`：一句话说明视觉方向和使用场景
- `colors`：至少覆盖与项目直接相关的主色、辅助色、文本色、背景色、边框色、状态色
- `typography`：至少覆盖标题、正文、按钮或标签中的主要文本样式
- `rounded`：给出可复用的圆角层级
- `spacing`：给出最小可复用间距刻度
- `components`：只写项目中真实存在且高频的关键组件

## 写作要求

- 优先使用 token 引用，不要在组件定义里反复内联 hex 值
- 优先写“稳定规律”，不要把偶然样式当成系统规则
- 组件状态可独立命名，如 `button-primary-active`
- 正文描述解释风格和使用边界，避免空话
- 如果某些值是经确认后补全的，应保证与项目整体风格一致

## 内容契约与可变项

内容契约：

- 新文档默认使用 YAML token + Markdown；已有项目采用其他 token 事实源时引用其入口，不复制第二份数值
- 模板章节作为信息检查项，标题和顺序可适配；已知缺口必须有明确承载位置
- `colors`、`typography`、`rounded`、`spacing`、`components` 等常见 token 区块
- token 颗粒度
- 对组件和布局的描述方法
- 对已知缺口和注意事项的记录方式
- 使用 `{colors.primary}` 这类 token 引用，而不是重复硬编码

可变项：

- 具体 token 命名，只要清晰稳定即可
- 组件覆盖范围，可按项目实际复杂度裁剪
- 已知缺口说明，写入已有或适配后的缺口说明位置

禁止把其他项目的品牌、叙事、专属字体、视觉隐喻或组件体系直接套入当前项目；当前项目已有品牌要求应保留。

## 高密度业务界面补充要求

项目包含后台、工作台或其他高密度界面时，按适用场景说明以下规则。已有有效契约优先；尚需选择的策略先给具体建议，不将示例直接写成强制规范。

| 方向 | 应明确的内容与选择依据 |
|---|---|
| 空间与滚动 | 主数据区如何使用可用空间、哪些区域独立滚动、怎样保证末项与操作可达；有明确分区的局部滚动可保留 |
| 列与长内容 | 按阅读、比较或编辑任务确定列宽、展示优先级及换行/截断/展开方式；截断须有完整内容入口，触摸或键盘路径不能只依赖 hover |
| 操作区 | 主次操作如何排序、分组、折叠；固定与自然布局依据任务和可用空间选择 |
| 容器承载 | 按信息量、编辑复杂度、上下文保留及返回成本选择弹窗、抽屉、全屏或独立页，组件名称不直接决定是否合格 |
| 视口退化 | 使用项目支持的最窄、典型和较宽视口，写清字段保留、折叠及详情承接；具体尺寸从项目来源读取 |

固定小高度、嵌套滚动或长文本换行只有在造成明确可用性问题或违反契约时才列为缺陷。项目没有此类界面时不要求补齐相关规则。

## 任务与能力的结构适配

按 [任务与能力规范覆盖](frontend-audit-checklist.md#任务与能力规范覆盖) 归纳本次适用契约，将结果放入组件、布局、状态、响应式或验证的现有章节。通用任务规则覆盖桌面和移动；触摸、原生输入与安装/缓存按实际能力补充，不要求每个检查方向新建章节。
