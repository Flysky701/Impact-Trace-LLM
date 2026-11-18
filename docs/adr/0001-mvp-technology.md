# ADR-0001：单人课程原型的技术基线

- 状态：已接受为实施基线；框架依赖已锁定、仓库浏览集成已验证，模型连接与正式影响分析待实现。
- 日期：2026-10-02。
- 决策参与者：项目发起者授权推进，助手依据约束与小样例验证形成方案。

## 背景与约束

1 人、一个月以内、本机 Web 演示、双角色、10 个用户功能及覆盖率 ≥75%。用户无技术偏好，希望样例较小且 Git 历史足够长。模型候选为 DeepSeek 或 OpenAI OAuth。

## 候选与决定

| 方向 | 决定 | 取舍 |
| --- | --- | --- |
| 首批语言 | Python | 标准库 AST 可用于快速验证；动态语言解析缺口须明确 |
| 解析 | ast + 有限符号解析 | Tree-sitter 和 SCIP 保留为后续多语言/语义索引方案；它们的接入与符号能力需分别验证 |
| 后端 | Python 3.13 + FastAPI | 与解析代码共用语言，已有本机环境；Django 的管理后台不是当前重点 |
| 存储 | SQLite + SQLAlchemy 2.x | 节点/边按版本存表，Python 做有限遍历；Neo4j、PostgreSQL 留作并发与规模增长后的候选 |
| 前端 | Vue 3 + TypeScript + Vite + Cytoscape.js | 单应用内完成关系图和报告，组件化测试；不增加独立可视化服务 |
| 样例 | TinyDB 固定历史 | 多模块、744 个可达提交、19 个 Python 源码/测试文件；动态转发作为已知限制 |
| 测试 | 后端 pytest、前端 Vitest，少量浏览器流程 | 前后端自有业务源码的行覆盖率分别达到 75%，同时报告分支指标 |

已生成后端 `requirements.lock` 与前端 `package-lock.json`，并完成仓库浏览、权限、源码读取的前后端及浏览器验证。当前本机 Python 3.13.15、Node 24.21.0、Git 2.55.0.windows.5 已检查。Cytoscape.js 与模型适配器尚未接入，不将基础应用验证视为全部组件验证。

## 验证依据

[样例验证](../sample-validation.md)记录完整 SHA、源码行数和语法实验。19 个文件解析成功，SQLite 存储语法候选后可查出直接与多跳反向路径。尚未验证真实前后端请求、完整符号解析、所有历史案例和模型效果。

官方资料核对日期为 2026-10-02：

- [Python AST](https://docs.python.org/3.13/library/ast.html)：提供语法树及源码位置；调用语义仍需应用实现。
- [FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)：支持基于 TestClient 的 pytest 测试。
- [SQLite 适用场景](https://www.sqlite.org/whentouse.html)：本地应用存储适合本原型；并发写入与网络数据库需求需另评估。
- [SQLAlchemy](https://www.sqlalchemy.org/)：作为数据库访问层，避免接口直接依赖零散 SQL。
- [Vue 起步](https://vuejs.org/guide/quick-start.html)、[Cytoscape.js](https://github.com/cytoscape/cytoscape.js)：用于组件界面与交互关系图。
- [测试方案](../testing-plan.md)列出覆盖率工具资料；[技术选型计划](../technology-evaluation.md)保留模型授权依据。

## 后果与复评条件

图谱是带类型、版本与来源的代码关系数据，不要求必须部署图数据库。首版解析范围有限，所有报告必须包含未解析关系和潜在影响措辞。框架版本兼容性、OAuth 资格与用量不能从静态实验推断。

出现第二语言硬性要求、大仓库遍历瓶颈、多人并发写入、远程部署或现有模型认证无法使用时，新增 ADR 重新评估。完整设计见[实施方案](../implementation-plan.md)。
