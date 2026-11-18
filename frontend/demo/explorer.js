'use strict';
const $ = (q, root = document) => root.querySelector(q);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHtml;
const basename = path => path.split('/').pop();
const state = {tab:'activity',level:'overview',mode:'split',module:'all',filter:'',symbol:null,drawer:null,onlyChanged:false};
let data, indexes, changes, nodeRefs = [];
const nfmt = n => Number(n).toLocaleString('en-US');
const badge = (label, kind = '') => `<span class="badge ${kind}">${e(label)}</span>`;
const statusLabel = s => ({added:'新增',deleted:'删除',modified:'修改',unchanged:'未变'})[s] || s;
const legend = () => `<div class="legend"><span><i style="background:#d06e7a"></i>旧版受影响</span><span><i style="background:#55a582"></i>新增</span><span><i style="background:#d2a052"></i>修改</span><span><i style="background:#c1ccdc"></i>上下文</span></div>`;
const refButton = (symbol, label) => `<button data-symbol="${e(symbol.id)}">${e(label || symbol.qualified)}</button>`;
function flatten(items) { return items.flatMap(n => [n,...flatten(n.children || []),...(n.branches || []).flatMap(b => flatten(b.items))]); }
function findSymbol(name, side='after') { return Object.values(indexes[side]).find(s => !s.test && (s.name === name || s.qualified === name)); }
function activeSymbol(side) { return indexes[side][state.symbol] || null; }
function overlaps(path, side, line, end) { return (changes[path]?.[side] || []).some(([a,b]) => a <= end && b >= line); }
function colorNode(n, side, symbol) {
  if (symbol?.status === 'added') return side === 'after' ? 'green' : '';
  if (symbol?.status === 'deleted') return side === 'before' ? 'red' : '';
  return overlaps(n.path, side, n.line, n.end) ? side === 'before' ? 'red' : 'amber' : '';
}
function register(n, side, symbol) { nodeRefs.push({node:n,side,symbol}); return nodeRefs.length-1; }
function render() {
  nodeRefs = [];
  const views = {architecture:architecture,activity:activity,database:database,findings:findings};
  const nav = [['architecture','◇','代码架构'],['activity','⇄','活动与变更'],['database','▤','数据库'],['findings','⌕','改进线索']];
  const metrics = data.after.metrics;
  $('#app').innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand"><b>i</b>ImpactTrace</div><div class="small-label">本机代码仓库</div><div class="repo">${e(data.name)}</div><nav class="side-nav">${nav.map(([id,icon,title])=>`<button data-tab="${id}" class="${state.tab===id?'active':''}"><span>${icon}</span>${title}</button>`).join('')}</nav><div class="small-label">本次变更 · ${data.changes.length} 个文件</div><div class="side-files">${data.changes.map(c=>`<button data-file="${e(c.path)}" title="${e(c.path)}"><em>${c.status==='added'?'+':'M'}</em>${e(basename(c.path))}</button>`).join('')}</div><div class="side-foot">本机分析 · Kotlin<br>来源：Git 与工作区源码<br>DeepSeek：尚未接入<br>未运行目标项目测试</div></aside><div class="main"><header class="topbar"><span>代码图谱 <span class="quiet"> / ${e(data.name)}</span></span><small>采集于 ${new Date(data.generatedAt).toLocaleString('zh-CN')}</small></header><main class="content"><div class="heading"><div><h1>${nav.find(n=>n[0]===state.tab)[2]}</h1><p>${e(data.profile.description)}</p></div><div class="snapshot"><code>${e(data.before.commit.slice(0,8))}</code><span>→</span><code>${data.after.revision==='WORKTREE'?'工作区 · 未提交':e(data.after.commit.slice(0,8))}</code></div></div><div class="metrics"><div class="metric"><span>生产源码文件</span><strong>${nfmt(metrics.files)}</strong><span>${nfmt(metrics.lines)} 行 · 按来源去重</span></div><div class="metric"><span>函数声明 · 静态提取</span><strong>${nfmt(metrics.functions)}</strong><span>${nfmt(metrics.classes)} 个类 / 对象</span></div><div class="metric"><span>变更函数 · 含测试</span><strong>${Object.values(indexes.after).filter(s=>s.kind==='function'&&s.status!=='unchanged').length}</strong><span>${data.changes.length} 个变更文件</span></div><div class="metric"><span>目标项目测试覆盖率</span><strong>—</strong><span>${metrics.testFiles} 个测试文件 · 未测量</span></div></div>${views[state.tab]()}<footer class="footer"><details><summary>查看分析范围与限制${metrics.parseErrorFiles?` · ${metrics.parseErrorFiles} 个文件存在解析缺口`:''}</summary>${data.limitations.map(x=>`<p>${e(x)}</p>`).join('')}<p>排除 ${data.after.excluded.length} 个上游替换 / 平台文件；${data.after.derivedSources.length} 个机械派生来源以原始源码呈现。</p>${metrics.parseErrorFiles?data.after.files.filter(f=>f.errors.length).map(f=>`<p>${e(f.path)} · ${f.errors.length} 个语法恢复位置</p>`).join(''):''}</details></footer></main></div></div>${state.drawer?drawer():''}`;
}
function architecture() {
  const files = data.after.files.filter(f=>!f.test);
  const modules = [...new Set(files.map(f=>f.module))];
  const positions = {app:[370,35],shared:[40,230],device:[270,230],ocr:[500,230],platform:[730,230]};
  const svg = `<svg class="graph" viewBox="0 0 970 440" role="img" aria-label="五个桌面模块的构建依赖图"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#a8b6ca"/></marker></defs>${data.after.buildEdges.map(edge=>{const a=positions[edge.source],b=positions[edge.target]; if(!a||!b)return '';if(a[1]===b[1])return `<path class="edge" d="M${a[0]+100} ${a[1]+94} C${a[0]+100} 425 ${b[0]+100} 425 ${b[0]+100} ${b[1]+94}"/><text class="edge-label" x="${(a[0]+b[0])/2+100}" y="414" text-anchor="middle">${e(edge.kind)}</text>`;return `<path class="edge" d="M${a[0]+100} ${a[1]+92} C${a[0]+100} 180 ${b[0]+100} 155 ${b[0]+100} ${b[1]}"/><text class="edge-label" x="${b[0]+100}" y="215" text-anchor="middle">${e(edge.kind)}</text>`;}).join('')}${modules.map(m=>{const [x,y]=positions[m]||[40,35],members=files.filter(f=>f.module===m),affected=members.filter(f=>f.status!=='unchanged').length;return `<g class="node ${affected?'changed':''}" data-module="${e(m)}" tabindex="0" role="button" aria-label="查看 ${e(m)} 模块"><rect x="${x}" y="${y}" width="200" height="94" rx="8"/><text class="title" x="${x+16}" y="${y+27}">${e(m)}</text><text class="sub" x="${x+16}" y="${y+49}">${e(data.profile.moduleLabels?.[m]||'')}</text><text class="sub" x="${x+16}" y="${y+73}">${members.length} 个文件${affected?` · ${affected} 个变更`:''}</text></g>`;}).join('')}</svg>`;
  return `<div class="panel"><div class="panel-title"><h2>模块依赖</h2>${badge('来自 Gradle 声明')}</div><div class="chart-scroll">${svg}</div><div class="panel-body quiet">箭头表示构建依赖。shared 内含桌面替身与筛选后的 Android 业务源码；点击模块查看文件和函数。</div></div><div class="toolbar"><div class="list-tabs">${['all',...modules].map(m=>`<button data-module="${e(m)}" class="${m===state.module?'active':''}">${m==='all'?'全部模块':e(m)}</button>`).join('')}</div><input class="filter" id="filter" placeholder="搜索文件或函数" aria-label="搜索文件或函数" value="${e(state.filter)}"></div><div id="file-results">${fileTable()}</div>`;
}
function fileTable() {
  const query = state.filter.trim().toLowerCase();
  const matches = data.after.files.filter(f=>!f.test && (state.module==='all'||f.module===state.module) && (!query||f.path.toLowerCase().includes(query)||f.symbols.some(s=>s.name.toLowerCase().includes(query))));
  const files = matches.slice().sort((a,b)=>(a.status==='unchanged')-(b.status==='unchanged')||b.lines-a.lines).slice(0,50);
  return `<div class="panel"><div class="panel-title"><h2>${state.module==='all'?'生产源码':e(state.module)} · ${matches.length} 个文件</h2><span class="quiet">按变更、文件长度排序 · 最多显示 50 项</span></div><table class="table"><thead><tr><th>文件 / 源码来源</th><th>函数</th><th>行数</th><th>状态</th></tr></thead><tbody>${files.map(f=>`<tr><td><button data-file="${e(f.path)}">${e(basename(f.path))}</button><span class="path">${e(f.path)}</span></td><td>${f.symbols.filter(s=>s.kind==='function').length}</td><td>${f.lines}</td><td>${badge(f.origin==='upstream'?'共享上游':'桌面')}${f.errors.length?' '+badge('解析缺口','amber'):''}${f.status!=='unchanged'?' '+badge(statusLabel(f.status),'amber'):''}</td></tr>`).join('')}</tbody></table>${files.length?'':'<div class="empty">没有匹配结果。</div>'}</div>`;
}
function activity() {
  const selected = activeSymbol('after') || activeSymbol('before');
  const functions = Object.values(indexes.after).filter(s=>s.flow&&!s.test);
  const title = state.level==='overview' ? data.profile.scenario.title : selected?.qualified || '选择函数';
  return `<div class="toolbar"><div class="toolbar-group"><button data-level="overview" class="${state.level==='overview'?'active':''}">场景活动图</button><button data-level="function" class="${state.level==='function'?'active':''}">函数活动图</button></div><div class="toolbar-group">${[['split','前后对照'],['before','旧图标红'],['after','当前版本']].map(([id,label])=>`<button data-mode="${id}" class="${state.mode===id?'active':''}">${label}</button>`).join('')}</div></div><div class="bread"><button data-level="overview">${e(data.profile.scenario.title)}</button>${state.level==='function'?`<span>›</span><span>${e(title)}</span>`:''}</div><div class="notice">${state.level==='overview'?e(data.profile.scenario.description):'自动从函数语法树提取。分支分栏、循环回到条件；lambda 单独显示，未假定它会立即执行。节点可查看源码，调用可继续定位。'}</div><div class="toolbar"><span class="quiet">${state.level==='function'&&selected?`${e(basename(selected.path))} · L${selected.line}–${selected.end}`:'红色父活动表示内部包含修改，可展开核对。'}</span>${legend()}</div><div class="${state.mode==='split'?'columns':'single-flow'}">${(state.mode==='split'?['before','after']:[state.mode]).map(side=>flowColumn(side)).join('')}</div><div class="panel"><div class="panel-title"><h2>可展开的函数</h2><span class="quiet">本次变更 + profile 指定入口</span></div><div class="panel-body calls">${functions.map(s=>`<button data-function="${e(s.id)}" title="${e(s.path)}">${e(s.qualified)} ${s.status!=='unchanged'?`· ${statusLabel(s.status)}`:''}</button>`).join('')}</div></div>`;
}
function flowColumn(side) {
  const s = state.level==='overview' ? findSymbol(data.profile.scenario.function,side) : activeSymbol(side);
  const content = !s ? '<div class="empty">此版本中不存在该函数。<br>新增行为仅在当前版本显示。</div>' : !s.flow ? '<div class="empty">该声明没有可展示的函数体。</div>' : state.level==='overview' ? scenarioFlow(s,side) : renderFlow(s.flow,side,s);
  return `<section class="panel flow-column"><div class="panel-title"><h2>${side==='before'?'变更之前':'变更之后'}</h2>${badge(side==='before'?data.before.commit.slice(0,8):data.after.revision==='WORKTREE'?'工作区快照':data.after.commit.slice(0,8),side==='before'?'red':'green')}</div><div class="activity"><span class="start">进入活动</span>${content}<span class="end">${state.level==='function'?'函数边界':'返回任务数据'}</span></div></section>`;
}
function scenarioFlow(s,side) {
  const nodes = flatten(s.flow);
  const scenario=data.profile.scenario;
  const order=scenario[side+'Order']||scenario.steps.map((_,i)=>i);
  const otherOrder=scenario[(side==='before'?'after':'before')+'Order']||order;
  return order.map((stepIndex,i)=>{
    const step=scenario.steps[stepIndex];
    const matched = nodes.filter(n=>step.contains.some(key=>n.code.includes(key)));
    // Prefer the narrowest matching nodes; a surrounding block is not a different behavior.
    const leaves = matched.filter(n=>!matched.some(other=>other!==n&&other.line>=n.line&&other.end<=n.end));
    const moved=otherOrder.indexOf(stepIndex)!==i;
    const affected = moved || leaves.some(n=>colorNode(n,side,s));
    return `<div class="flow-item ${affected?(side==='before'?'red':'amber'):''}"><button class="flow-button" data-function="${e(s.id)}"><strong>${i+1}. ${e(step.label)}</strong><small>${moved?'顺序变化 · 展开查看':affected?'内部有修改 · 展开查看':'源码行为分组 · 展开查看'}${leaves.length?` · L${Math.min(...leaves.map(n=>n.line))}`:''}</small></button></div>`;
  }).join('');
}
function renderFlow(items,side,s,depth=0) {
  if(depth>7) return '<div class="quiet">嵌套较深，请查看源码。</div>';
  return items.map(n=>{
    const index=register(n,side,s),color=colorNode(n,side,s);
    const icon=({if:'◇ ',choice:'◇ ',loop:'↻ ',exit:'● ',try:'⋈ ',scope:'↳ '})[n.kind]||'';
    const targets=[...new Set(s.calls.filter(c=>c.line>=n.line&&c.line<=n.end).flatMap(c=>c.targets))].filter(id=>indexes.after[id]?.flow);
    const drill=targets.length===1 && !n.children?.length && !n.branches?.length ? `<div class="boundary"><button data-function="${e(targets[0])}">展开 ${e(indexes.after[targets[0]].name)} →</button></div>`:'';
    return `<div class="flow-item ${color} ${n.kind==='exit'?'exit':''}"><button class="flow-button" data-node="${index}">${icon}${e(n.label)}<small>L${n.line}${n.end!==n.line?'–'+n.end:''}${n.kind==='exit'?' · 结束当前路径（含标号跳转）':''}${color?' · '+(side==='before'?'原行为受影响':s.status==='added'?'新增':'修改'):''}</small></button>${n.boundary?`<div class="boundary">${e(n.boundary)}</div>`:''}${n.branches?.length?`<div class="flow-branches">${n.branches.map(b=>`<div class="branch"><div class="branch-title">${e(b.label)}</div>${b.items.length?renderFlow(b.items,side,s,depth+1):'<div class="unchanged-path">继续</div>'}</div>`).join('')}</div>`:''}${n.children?.length?`<div class="flow-nested">${renderFlow(n.children,side,s,depth+1)}${n.kind==='loop'?'<div class="branch-title">↻ 返回循环条件；条件不满足时继续</div>':''}</div>`:''}${drill}</div>`;
  }).join('');
}
function database() {
  const entities=data.after.files.filter(f=>!f.test).flatMap(f=>f.entities);
  const pos={accounts:[390,25],feature_profiles:[35,265],automation_runs:[390,265],labyrinth_reroll_checkpoints:[745,265],labyrinth_routes:[35,510],labyrinth_run_states:[390,510],labyrinth_run_characters:[35,755],labyrinth_run_relics:[745,755],migration_checkpoints:[745,25]};
  const byName=Object.fromEntries(entities.map(x=>[x.name,x]));
  return `<div class="toolbar"><span class="quiet">${entities.length} 张表 · ${entities.reduce((n,t)=>n+t.foreignKeys.length,0)} 条显式外键</span>${badge('Room 注解自动提取')}</div><div class="notice">这里只表示 Room 关系。JSON 配置、日志和加密凭据存储尚未统一建模；同名字段不会被自动推断成外键。本次变更调整 DAO 行为，表结构未改。</div><div class="panel"><div class="panel-title"><h2>实体关系</h2><span class="quiet">子表 → 父表 · 点击查看全部字段与删除规则</span></div><div class="chart-scroll"><svg class="graph" viewBox="0 0 1080 960" role="img" aria-label="Room 数据库实体关系图"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#a8b6ca"/></marker></defs>${entities.flatMap(t=>t.foreignKeys.map(fk=>{const p=pos[t.table],q=pos[byName[fk.target]?.table]; if(!p||!q)return '';const start=[p[0]+145,p[1]],end=[q[0]+145,q[1]+146];return `<path class="edge" d="M${start} C${start[0]} ${start[1]-60} ${end[0]} ${end[1]+60} ${end}"/><text class="edge-label" x="${start[0]}" y="${start[1]-10}" text-anchor="middle">${e(fk.childColumns.join(', '))}</text>`;})).join('')}${entities.map(t=>{const [x,y]=pos[t.table]||[35,25];return `<g class="node" data-entity="${e(t.id)}" tabindex="0" role="button" aria-label="${e(t.table)} 表"><rect x="${x}" y="${y}" width="290" height="146" rx="7"/><text x="${x+15}" y="${y+26}" style="font-size:13px;font-weight:600">${e(t.table)}</text><line x1="${x}" x2="${x+290}" y1="${y+40}" y2="${y+40}" stroke="#e0e5ed"/>${t.fields.slice(0,3).map((f,i)=>`<text x="${x+15}" y="${y+62+i*21}" style="font-size:11px">${f.primary?'⌑ ':''}${e(f.name)}<tspan x="${x+272}" text-anchor="end" fill="#8b97aa">${e(f.type)}</tspan></text>`).join('')}<text class="sub" x="${x+15}" y="${y+131}">${t.fields.length} 个字段 · ${t.foreignKeys.length} 个外键 → 查看</text></g>`;}).join('')}</svg></div></div>`;
}
function findings() {
  const fs=data.after.files.filter(f=>!f.test), functions=fs.flatMap(f=>f.symbols).filter(s=>s.kind==='function');
  const largest=fs.slice().sort((a,b)=>b.lines-a.lines).slice(0,8);
  const branches=functions.slice().sort((a,b)=>b.branches-a.branches).slice(0,8);
  const suggestions=[
    {title:'先拆识别会话中的页面决策',body:'LabyrinthEntryRecognitionSession 集中了识别、页面状态、操作决策和动作派发。先从 handlePostEntryPage 抽出页面处理器，把输入状态与输出动作显式化，再复用现有回放测试；不要一次重写整个会话。',name:'handlePostEntryPage'},
    {title:'把桌面总控逐步收敛为装配入口',body:'DesktopAppGraph 同时装配设备、账号、识别、自动任务和退出流程。可先把共享账号准备单独提成服务，再提取任务生命周期；保留现有依赖注入接口、多 JVM 隔离与停止守卫。',name:'prepareSharedAccount'},
    {title:'核对账号投影事务之外的失败语义',body:'本次事务化绑定改善了同名账号冲突处理。数据库、内存凭据与设置仍在多个步骤更新：建议用离线故障注入明确“投影成功、后续步骤失败或取消”时的可重试状态。这是待验证的边界，不是已确认的数据损坏。',name:'bindSharedProjection'},
    {title:'按命令域拆分控制层分发',body:'GraphControlService.dispatch 按操作名处理账号、设备、任务、设置与导出。可先建立统一的命令参数模型，再分到对应处理器；继续在同一入口检查租约、忙碌状态与设备守卫。',name:'GraphControlService.dispatch'}
  ];
  return `<div class="notice">以下建议由代码证据人工核对；静态指标用于排序，不等同于缺陷或性能结论。未执行游戏、目标测试或性能测量。</div><div class="panel"><div class="panel-title"><h2>建议先处理的 4 个方向</h2>${badge('结合图谱的审阅意见')}</div>${suggestions.map((item,i)=>{const s=findSymbol(item.name);return `<article class="finding"><div class="rank">${i+1}</div><div><h3>${e(item.title)}</h3><p>${e(item.body)}</p>${s?`${refButton(s,'查看代码证据')}${s.flow?`<button data-function="${e(s.id)}">查看活动图</button>`:''}<span class="quiet">${s.lines} 行 · ${s.branches} 个条件 / 循环 / catch 节点</span>`:'<span class="quiet">本次快照未提取到该符号，请在源码列表定位。</span>'}</div></article>`;}).join('')}</div><div class="columns"><div class="panel"><div class="panel-title"><h2>生产源码长度</h2><span class="quiet">含空行和注释</span></div><table class="table"><tbody>${largest.map(f=>`<tr><td><button data-file="${e(f.path)}">${e(basename(f.path))}</button><span class="path">${e(f.module)} · ${f.origin==='upstream'?'共享上游':'桌面'}</span></td><td>${nfmt(f.lines)} 行</td></tr>`).join('')}</tbody></table></div><div class="panel"><div class="panel-title"><h2>分支热点</h2><span class="quiet">语法节点数，非圈复杂度</span></div><table class="table"><tbody>${branches.map(s=>`<tr><td>${refButton(s)}<span class="path">${s.parseError?'含解析缺口 · ':''}${s.lines} 行</span></td><td>${s.branches}</td></tr>`).join('')}</tbody></table></div></div>`;
}
function drawer() {
  const d=state.drawer, side=d.side||'after';
  const file=data[side].files.find(f=>f.path===d.path), symbol=d.symbol&&indexes[side][d.symbol];
  const entity=d.entity&&data[side].files.flatMap(f=>f.entities).find(t=>t.id===d.entity);
  const source=(data.sources[side][d.path]||'').split('\n');
  const line=d.line||symbol?.line||1, end=d.end||symbol?.end||line;
  const start=Math.max(1,line-4),finish=Math.min(source.length,Math.max(end+4,line+25),line+130);
  const calls=symbol?.calls||[];
  const imported=[...new Set(data[side].importEdges.filter(edge=>edge.source===d.path).map(edge=>edge.target))];
  const consumers=[...new Set(data[side].importEdges.filter(edge=>edge.target===d.path).map(edge=>edge.source))];
  const dependencyView=file?`<details class="dependency-view"><summary>文件引用关系 · ${imported.length} 个导入目标 / ${consumers.length} 个引用方</summary><p class="quiet">仅含可定位的显式 import；通配导入与运行时调用不计入。</p><div class="dependency-grid"><div><div class="branch-title">引用此文件</div>${consumers.slice(0,8).map(path=>`<button data-file="${e(path)}">${e(basename(path))}</button>`).join('')||'<span class="quiet">未提取到</span>'}</div><div class="dependency-center">→<br><strong>${e(basename(d.path))}</strong><br>→</div><div><div class="branch-title">此文件导入</div>${imported.slice(0,8).map(path=>`<button data-file="${e(path)}">${e(basename(path))}</button>`).join('')||'<span class="quiet">未提取到</span>'}</div></div>${imported.length>8||consumers.length>8?'<p class="quiet">每侧显示前 8 个邻接文件，完整关系保存在分析数据中。</p>':''}</details>`:'';
  return `<aside class="drawer" aria-label="代码证据"><div class="drawer-head"><button data-close aria-label="关闭代码证据">✕</button><strong>${e(entity?.table||symbol?.qualified||basename(d.path))}</strong><div class="source-path">${e(d.path)} · ${side==='before'?data.before.commit.slice(0,8):'工作区'} · L${line}</div></div><div class="drawer-content">${entity?`<p class="quiet">字段来自 Room 注解。</p><ul class="field-list">${entity.fields.map(f=>`<li><code>${f.primary?'PK ':''}${e(f.name)}</code><span>${e(f.type)}</span></li>`).join('')}</ul>${entity.foreignKeys.map(fk=>`<p class="quiet">${e(fk.childColumns.join(', '))} → ${e(fk.target)}.${e(fk.parentColumns.join(', '))}<br>删除规则：${e(fk.onDelete)}</p>`).join('')}`:''}${symbol?.flow?`<p><button data-function="${e(symbol.id)}">进入函数活动图 →</button></p>`:''}${dependencyView}${file?.errors.length?'<div class="notice warn">此文件有语法恢复位置。符号和调用结果可能不完整，以下原始源码可直接核对。</div>':''}<div class="source-code">${source.slice(start-1,finish).map((value,i)=>`<div class="code-line ${start+i>=line&&start+i<=end?'hit':''}"><b>${start+i}</b><span>${e(value)}</span></div>`).join('')}</div>${end>finish?'<p class="quiet">较长函数显示前 130 行；完整内容保存在本机 analysis.json 中。</p>':''}${calls.length?`<h3 style="font-size:13px">函数调用 · 候选定位</h3><p class="quiet">可点击的目标来自名称与导入关系，尚未经过类型解析。</p><div class="calls">${calls.slice(0,50).map(c=>c.targets.length?c.targets.slice(0,3).map(id=>`<button data-symbol="${e(id)}" title="L${c.line} · ${e(c.expression)}">${e(c.name)} →</button>`).join(''):`<span class="badge" title="L${c.line}">${e(c.expression)}</span>`).join('')}</div>`:''}${file?`<h3 style="font-size:13px">同文件函数 · ${file.symbols.filter(s=>s.kind==='function').length}</h3><div class="calls">${file.symbols.filter(s=>s.kind==='function').map(s=>refButton(s,s.qualified)).join('')}</div>`:''}</div></aside>`;
}
function selectFunction(id) {
  state.symbol=id;state.level='function';state.tab='activity';state.drawer=null;render();window.scrollTo({top:0,behavior:'smooth'});
}
document.addEventListener('click',event=>{
  const target=event.target.closest('[data-tab],[data-mode],[data-level],[data-module],[data-function],[data-file],[data-symbol],[data-node],[data-close],[data-entity]');
  if(!target||!data)return;
  const a=target.dataset;
  if(a.tab){state.tab=a.tab;state.drawer=null;}
  if(a.mode)state.mode=a.mode;
  if(a.level){state.level=a.level;if(!state.symbol)state.symbol=findSymbol(data.profile.defaultFunction)?.id;}
  if(a.module){state.module=a.module;state.tab='architecture';}
  if(a.function){selectFunction(a.function);return;}
  if(a.file)state.drawer={path:a.file};
  if(a.symbol){const s=indexes.after[a.symbol]||indexes.before[a.symbol]; if(s)state.drawer={path:s.path,line:s.line,end:s.end,symbol:s.id,side:indexes.after[s.id]?'after':'before'};}
  if(a.node!==undefined){const r=nodeRefs[+a.node];state.drawer={path:r.node.path,line:r.node.line,end:r.node.end,symbol:r.symbol.id,side:r.side};}
  if(a.entity){const entity=data.after.files.flatMap(f=>f.entities).find(t=>t.id===a.entity);if(entity)state.drawer={path:entity.path,line:entity.line,end:entity.end,entity:entity.id};}
  if(a.close!==undefined)state.drawer=null;
  render();
});
document.addEventListener('input',event=>{if(event.target.id==='filter'){state.filter=event.target.value;$('#file-results').innerHTML=fileTable();}});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&state.drawer){state.drawer=null;render();}if(event.key==='Enter'&&event.target.matches('g[role="button"]'))event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));});
fetch('analysis.json').then(response=>{if(!response.ok)throw new Error('无法读取 analysis.json，请先运行本机分析命令。');return response.json();}).then(result=>{
  data=result;changes=Object.fromEntries(data.changes.map(c=>[c.path,c]));indexes=Object.fromEntries(['before','after'].map(side=>[side,Object.fromEntries(data[side].files.flatMap(f=>f.symbols).map(s=>[s.id,s]))]));
  state.symbol=findSymbol(data.profile.defaultFunction)?.id;render();
}).catch(error=>{$('#app').innerHTML=`<div class="error-screen"><h1>暂时无法打开图谱</h1><p>${e(error.message)}</p><p>请通过本机 HTTP 地址打开，文件预览模式无法读取相邻 JSON。</p></div>`;});
