# 本机启动与开发

当前可用：本地账号登录、双角色权限、项目接入与编辑、**全景白话架构与程序流导览**、**两版本与工作区（`WORKTREE`）变更流程对照与影响波及分析**、**自动难维护热点体检与避坑便签**、**上下文随手问答**、**AI 多模型密钥可视化配置**及**审核与测试记录持久化**。

## 首次安装（Windows PowerShell）

在仓库根目录运行，需要 Python 3.13、Node 24 和 Git：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock -r backend/requirements-analysis.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
```

后端完整依赖固定在 `backend/requirements.lock`，前端固定在 `frontend/package-lock.json`。后端原始依赖清单为 `backend/requirements.in`。未来更新依赖后重新执行测试，不以安装成功替代兼容验证。

## 启动演示

```powershell
.\scripts\start-local.ps1
```

打开 <http://127.0.0.1:8765>。脚本先初始化演示账号，再启动服务，按 Ctrl+C 停止。若 PowerShell 执行策略限制脚本，可以按下面的等效命令启动，无需改变系统策略：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.bootstrap
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8765
```

首次生成 `developer` 与 `reviewer` 两个账号，随机密码保存在本机 `data/local/demo-credentials.txt`。文件已被 Git 忽略，供本机演示使用；重复初始化不重置已有密码。不要将密码文件放入课程报告或提交到仓库。平台只监听回环地址，当前没有公开注册和远程部署配置。

## 接入 TinyDB

已有 `data/local/tinydb/` 时直接使用。新环境从根目录取得样例：

```powershell
git clone --no-checkout https://github.com/msiemens/tinydb.git data/local/tinydb
```

开发者登录后点击“接入项目”，填写名称和该目录的绝对路径，选择 `reviewer` 作为审核者。读取提交后，点击提交和文件即可查看固定版本源码。审核者只能看到分配给自己的项目，不能创建项目。Git 读取不要求检出文件，也不会执行仓库代码。

默认允许接入 `data/local/`（若本机存在 `D:\Project`，`start-local.ps1` 会自动一并加入允许目录，可直接填入 `D:\Project\LimingjieDesktop`）。如需自定义目录或预设模型密钥，可复制 `.env.example` 为 `.env` 并修改 `IMPACT_REPOSITORY_ROOTS`，或登录后点击页面右上角 **「AI 模型设置」** 一键填入 DeepSeek / OpenAI / Gemini / Claude / 硅基流动 / 通义千问等任意密钥（未配密钥时系统自动以本地零消耗规则提炼模式运行）。

## 开发模式

后端按上面的命令启动，前端在另一个终端运行 `npm.cmd run dev`。浏览器访问 Vite 输出的本机地址，`/api` 由 Vite 代理到 8765 端口。当前不开放跨站接口权限。

## 验证

日常开发沿用全局分级规则：局部行为修改只运行相关测试文件或用例，文档/文案小改检查实际效果即可。后端可向 `pytest` 传入相关文件或 `-k` 选择条件；前端使用 `npm.cmd run test -- <相关测试文件>`。不必在每次修改后同时运行构建、完整覆盖率和浏览器流程。

以下是阶段合入、课程最终验收或确有全局影响时使用的完整命令。覆盖率 ≥75% 的课程要求不变。

后端，在项目根目录先创建临时父目录，再运行：

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
Set-Location backend
..\.venv\Scripts\python.exe -m pytest --basetemp=../tmp/pytest-foundation --cov=app --cov-report=term-missing --cov-report=xml --cov-report=html
```

`--basetemp` 是测试专用目录，pytest 会清理其中内容，不要在里面保存个人文件。测试创建独立 Git 仓库和临时数据库，不修改演示数据。覆盖统计包括整个 `app/`，行覆盖率门槛为 75%。

前端：

```powershell
Set-Location frontend
npm.cmd run build
npm.cmd run test:coverage
```

统计 `src/` 中全部 TypeScript 与 Vue 源码，行覆盖率门槛为 75%。此阶段指标只针对已实现模块，不能代表未来完整系统覆盖率。分支报告将在后续测试配置中独立补充，避免与行覆盖率门槛混算。

跨页面流程、登录或角色权限发生变化，以及正式演示验收时，按影响选择 `frontend/e2e/` 中的浏览器用例；无需因无关文案或局部修改运行完整流程。需要完整验收时，先启动演示服务、准备 TinyDB 和账号，再在前端目录运行 `npx.cmd playwright test`。默认使用本机 Edge；这项检查会在演示数据库中创建或复用“TinyDB 演示”项目并分配给审核者，截图放在 `reports/generated/`。

## 离线代码图谱 Demo

当前实验使用 `D:\Project\LimingjieDesktop`，只读取源码和 Git 对象，不构建/启动项目，也不连接模拟器或模型。分析器与查看器在本仓库维护，生成结果默认写入被 Git 忽略的 `reports/generated/limingjie-demo/`。

在本仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-analysis.txt
.\.venv\Scripts\python.exe scripts/analyze_repository.py D:\Project\LimingjieDesktop
.\.venv\Scripts\python.exe -m http.server 8878 --bind 127.0.0.1 --directory reports/generated/limingjie-demo
```

打开 <http://127.0.0.1:8878/>。页面提供场景/函数活动图、前后对照、旧图标红、模块依赖、文件与函数检索、源码与调用候选、Room 表和外键，以及维护热点与人工审阅建议。必须通过本机 HTTP 地址打开，直接打开 HTML 文件不能读取相邻 JSON。

默认基准为 `HEAD`，目标为 `WORKTREE`；提交引用解析为完整 SHA，工作区结果标记采集时间，刷新页面读取保存结果，不自动重扫。需要更新源码后重新分析时，再运行同一分析命令。也可指定两个提交：

```powershell
.\.venv\Scripts\python.exe scripts/analyze_repository.py D:\Project\LimingjieDesktop --base HEAD~1 --head HEAD
```

范围由 `analysis/profiles/limingjie.json` 决定：五个桌面模块、shared 实际复用的 Android 源码、独立统计的测试源码。解析上游排除清单，机械派生文件明确展示原始来源，不执行 Gradle。目录配置可扩展到其他 Kotlin 仓库；目前页面模块布局、中文场景和人工建议针对本样例，不声称可自动理解任意项目。

`analysis.json` 包含两版源码、声明、调用候选、导入边、构建边、活动结构、Room 实体、变化行范围和解析诊断；页面资产来自 `frontend/demo/`。结构化函数活动与 Room 图自动提取，场景的中文分组和先后顺序经人工核对。变更身份包括文件、词法容器、扩展接收者和参数，尚不匹配跨文件移动/重命名；换行格式差异不会标为代码变化。调用候选不是编译器已确认的调用边，回调不会直接展平成运行顺序。

首个真实样例：`cc9bcec5acc8f2855a37536d536f7ee37f45a7f8` → 当时工作区，290 个生产源码文件、64,616 行、222 个测试文件；3 个文件、5 个函数声明变化；9 张表、8 条显式外键。25 个文件仍有语法恢复位置，页面列出缺口，统计不等于完整语义分析。没有导入覆盖率报告或执行目标测试，覆盖率保持空值。

5 项定向测试覆盖语法活动、Room 关系、行差异、同名函数身份，以及含 CRLF 的临时 Git 仓库比较：

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests/test_code_graph.py -q --basetemp=tmp/graph-tests
```

这些是分析器测试，与目标项目的 222 个测试文件无关。基础应用无需安装可选解析依赖；未安装时跳过这组 Demo 测试。DeepSeek 适配与真实请求尚未实现，提供凭据后也需先明确真实付费调用的授权额度。

解析器使用 [Tree-sitter Python](https://tree-sitter.github.io/py-tree-sitter/)、[Kotlin grammar](https://github.com/tree-sitter-grammars/tree-sitter-kotlin) 和 [language-pack](https://github.com/xberg-io/tree-sitter-language-pack) 的锁定版本；逐文件选取语法恢复范围更小的结果，未解决的位置保留诊断。
