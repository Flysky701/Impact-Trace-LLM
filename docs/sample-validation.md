# 开源样例与初步验证

核对日期：2026-10-02。结论：采用 [msiemens/tinydb](https://github.com/msiemens/tinydb) 作为首个分析样例。这里只进行了 Git 数据读取、语法解析和关系存取实验，没有运行 TinyDB 业务或测试，也没有调用模型。

## 样例选择

TinyDB 是纯 Python 的轻量文档数据库。它有数据库入口、表、查询、存储和缓存等模块，适合展示结构及修改影响。相较核心集中在单文件的 [schedule](https://github.com/dbader/schedule)，本项目优先用 TinyDB 展示模块关系；schedule 留作简化备选。

本地使用完整历史克隆，不使用 shallow clone。样例位于被忽略的 `data/local/tinydb/`，不作为平台源码提交。原仓库 [MIT 许可证](https://github.com/msiemens/tinydb/blob/18d73a15066a04c77f19ae9a8c03d582bd344c0d/LICENSE) 已读取；如在交付物中分发实质源码，保留原版权与许可文本。

| 指标 | 本地核对结果 |
| --- | --- |
| 固定快照 | `18d73a15066a04c77f19ae9a8c03d582bd344c0d` |
| 该快照可达提交数 | 744 |
| 根提交 | `b01cf23013c745c551f6bdffc78d737bf8e5f1f2`，2013-07-03 |
| 快照提交日期 | 2026-09-19（Git 提交日期） |
| `tinydb/` Python 文件 | 10 个，共 2,288 文本行，含注释/文档/空行 |
| `tests/` Python 文件 | 9 个，共 2,147 文本行，含注释/文档/空行 |
| AST 解析 | 19/19 文件成功，0 个语法错误 |
| 同类 `self.method()` 语法调用候选 | 54 个调用点 |

上述数量由固定快照测得，不用上游 README 的近似行数，也不代表代码覆盖率或调用解析准确率。

## 固定历史案例

### A：关闭缓存后拒绝读写

- 基准：`bd034d0e95d64a1da0e86387daa950eed3534fff`。
- 目标：`18d73a15066a04c77f19ae9a8c03d582bd344c0d`。
- [上游变更](https://github.com/msiemens/tinydb/commit/18d73a15066a04c77f19ae9a8c03d582bd344c0d)：修改 `CachingMiddleware` 的初始化、read、write、flush、close，并增加回归测试。
- 已核对：`write()` 和 `close()` 调用 `flush()`；应能从这些直接语法关系展示潜在影响。
- 回归线索：`tests/test_middlewares.py::test_caching_rejects_use_after_close`。它是提交中新增的真实测试；首版允许人工关联，不能声称已自动解析所有测试到存储的动态调用。

### B：更新和删除时跳过不存在的文档 ID

- 基准：`8a2dc204c265c07ce8506a3599a28e720b6dcdd7`。
- 目标：`76d21d26c682e1ca6ca25bd8e81edf9f609ac52f`。
- [上游变更](https://github.com/msiemens/tinydb/commit/76d21d26c682e1ca6ca25bd8e81edf9f609ac52f)：修改 `Table.update`、`remove` 和 `upsert`，并修改文档及 `tests/test_tinydb.py`。
- 已核对：`Table.upsert` 调用 `self.update(...)`，所以 update 的行为变化可能影响 upsert；实验反向查询能找出这条路径。
- 回归线索：`test_update_ids_missing`、`test_update_ids_mixed`、`test_remove_ids_missing`、`test_remove_ids_mixed`、`test_doc_id_missing_consistency`。未运行这些测试，不推断其当前通过状态。

两组基准都是对应目标的第一父提交，已通过本地 Git 解析确认。

两组案例的四个快照均运行了检查脚本，语法解析错误均为 0；案例 A 基准可找到 `flush → close` 和 `flush → write` 的反向候选路径，案例 B 前后版本均可找到 `update → upsert`。正式变更映射与业务行为测试尚未实现。

## 可复现实验

运行 `python scripts/inspect_sample.py data/local/tinydb --revision 18d73a15066a04c77f19ae9a8c03d582bd344c0d`，或传入案例 B 的目标 SHA 和 `--changed tinydb.table.Table.update`。

脚本通过 Git 读取文件，不导入样例模块。它统计 AST，提取同类方法调用语法候选，写入内存 SQLite 边表，再执行反向查询及广度优先遍历。

以 `Table._read_table` 为假设变化起点，得到 10 条首次访问路径，其中包括：

- `_read_table → get → contains`；
- `_read_table → _get_next_id → insert → upsert`。

箭头表示潜在影响传播方向；实际调用方向与之相反。此项仅验证遍历机制，不能说上述函数在固定快照提交中发生了变化。对不存在的快照查询返回 0 条边；这只是基本过滤检查，完整两版本隔离仍需正式测试。

## 已知局限与下一步

- `TinyDB.__getattr__` 动态转发到默认 Table，简单 AST 无法可靠解析这条链。首版应展示导入/结构关系并标记动态调用缺口。
- 实验只统计 `self.method()` 语法，没有完成类型、遮蔽、继承、装饰器或回调解析；54 个候选不能等同于 54 条已确认语义调用。
- 下一步实现有作用域约束的符号解析、版本差异映射和小型自建回归样例，再验证新增/删除实体、循环及不确定匹配。
- 上游历史修复不声称来自 AI；AI 修改记录演示需要另准备真实任务、操作记录和固定提交。
