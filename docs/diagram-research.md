# 架构图与代码审阅设计参考

调研日期：2026-11-06。用途：从公开 GitHub skills 和代码理解项目中提取适合 ImpactTrace 的设计方法。未安装或执行外部 skill；以下是参考方法，不是引入这些项目为运行依赖。

## 参考与采用方式

| 来源 | 值得采用的做法 | 在本项目中的应用 |
| --- | --- | --- |
| [C4 Codebase Architecture skill](https://github.com/lmammino/c4-codebase-architecture-skill/blob/main/skills/c4-codebase-architecture/SKILL.md) | 先核对入口、部署、路由等证据；分清观察事实和推断；不强迫库项目套完整服务架构 | 模块、组件、服务分层；TinyDB 先画模块依赖，不虚构服务拓扑；缺证据的职责标为推断 |
| [Diagramming skill](https://github.com/arjunprabhulal/agent-skills/blob/main/skills/docs/diagramming/SKILL.md) | 按读者问题选图种；同图保持同一抽象层；控制节点数量；给箭头写语义；绑定版本 | 流程图和调用图分开；默认小范围，逐步展开；明确“调用方向”和“影响方向” |
| [LikeC4 官方 DSL skill](https://github.com/likec4/likec4/blob/main/skills/likec4-dsl/SKILL.md) | 模型和视图分离，按元素范围生成视图，结构视图与动态视图区分 | 共用版本化实体与证据，生成不同阅读视图；保存布局锚点；不让 LLM 直接生成不可追溯的一整张图 |
| [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open/blob/main/README.md)及[API 说明](https://github.com/AsyncFuncAI/deepwiki-open/blob/main/api/README.md) | 仓库结构、图解、文档与检索式问答放在同一个代码理解环境中 | 借鉴仓库上下文和带代码依据的问答；主页面仍围绕一次变更审阅，暂不建设完整百科或多轮研究系统 |

这些资料说明各自的设计与能力，不证明其生成结果对本项目的样例准确。LikeC4 的模型变化表达也不等于已解决任意 Git 代码的自动语义差异。

## 具体取舍

1. 默认先看仓库和提交比较，再进入函数流程；项目总体架构可从单版本独立浏览。
2. 左旧右新保持布局可对照；旧版改动标红，新版新增标绿，潜在影响使用独立标记。用户要求旧图标红，因此不照搬参考 skill 中默认不设颜色的规则；文字和线型同时表达语义。
3. 箭头明确表示导入、调用、控制流或数据流，一张图的方向规则一致。调用关系不能直接当作实际执行顺序。
4. 图默认约 5～9 个主要节点是可读性起点，不是算法上限；复杂内容分组展开，完整定义仍可检索。
5. 自动提取的结构先保存为统一记录，显示层按阅读目标生成视图；人工摘要和模型推断不混入确定关系。
6. 问答帮助解释选中代码；指标帮助决定检查重点。两者都不挤占前后流程对照的主视觉区域。

## Git 与覆盖率依据

- [GitHub 比较说明](https://docs.github.com/en/pull-requests/reference/branches)：PR 默认三点比较，比较 merge-base 与 head；直接比较两个提交采用两点语义。页面必须显示实际参与比较的 SHA。
- [Coverage.py 分支覆盖率说明](https://coverage.readthedocs.io/en/7.14.1/branch.html)：执行过某行不代表该行的所有分支都被覆盖，行与分支指标分别呈现。变更行覆盖率还需要用 Git diff 映射目标版本的可执行行。

设计产物见[产品设计 v0.3](product-design.md)和[仓库审阅原型](prototype/review.html)。首版不安装上述工具、不批量生成全部图种；待正式解析数据稳定后，再按交互和导出需要选择渲染方案。
