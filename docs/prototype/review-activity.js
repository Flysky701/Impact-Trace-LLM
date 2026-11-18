/* Fixed TinyDB scenario, manually summarized from the two commits. */
function activityBreadcrumb() {
  return `<div class="activity-breadcrumb"><button data-activity-level="overview" aria-current="${state.activityLevel==='overview'?'step':'false'}">文档更新场景</button><span>›</span><button data-activity-level="module" aria-current="${state.activityLevel==='module'?'step':'false'}">Table 模块</button><span>›</span><button data-activity-level="function">update 函数</button></div>`;
}
function activityGraph(after=false, plain=false) {
  const moduleLevel=state.activityLevel==='module';
  const shade=plain?'':after?'amber':'red';
  const stages=moduleLevel?[
    ['准备更新 ID',after?'分开保存请求与结果':'以全部请求 ID 初始化结果',true,'function'],
    ['读取表数据','_update_table → storage.read',false,'read'],
    [after?'仅更新存在的文档':'更新全部请求文档','展开 doc_ids 分支',true,'function'],
    ['写回存储','storage.write(tables)',false,'persist'],
    ['清理缓存并返回结果','clear_cache → 返回 updated_ids',false,'return']
  ]:[
    ['提交更新请求','调用方提供字段与文档 ID',false,'input'],
    ['更新文档','Table 模块 · 展开内部活动',true,'module'],
    ['接收更新结果',after?'实际更新的 ID':'正常完成时返回 updated_ids',false,'result']
  ];
  const gap=moduleLevel?94:142, height=moduleLevel?550:490, start=moduleLevel?42:60;
  const arrow='activity-'+(after?'new':'old');
  return `<svg class="flow activity-flow" style="--arrow:url(#${arrow})" viewBox="0 0 400 ${height}" role="img" aria-label="${moduleLevel?'Table 模块活动':'文档更新整体活动'}，${after?'修改后':'修改前'}，点击标红活动逐层展开">${marker(arrow)}<circle cx="200" cy="18" r="6" fill="#596675"/>
    <path class="edge" d="M200 24 V${start}"/>
    ${stages.map(([name,owner,changed,target],i)=>{
      const y=start+i*gap;
      return `${i?`<path class="edge" d="M200 ${y-gap+64} V${y}"/>`:''}<g class="node ${changed?shade:''}" data-activity="${target}" role="button" tabindex="0" aria-label="${esc(name)}，${changed?'含改动，展开详情':'查看依据'}"><rect x="55" y="${y}" width="290" height="64" rx="10"/><text x="200" y="${y+24}" text-anchor="middle">${esc(name)}</text><text class="sub" x="200" y="${y+46}" text-anchor="middle">${esc(owner)}</text>${changed&&!plain?`<text class="status" x="351" y="${y+20}">${moduleLevel?'修改':'含改动'}</text>`:''}</g>`;
    }).join('')}<path class="edge" d="M200 ${start+(stages.length-1)*gap+64} V${height-25}"/><circle cx="200" cy="${height-15}" r="8" fill="none" stroke="#596675"/><circle cx="200" cy="${height-15}" r="4" fill="#596675"/></svg>`;
}
function activityView(){
  const plain=state.mode==='original';
  return `${activityBreadcrumb()}<div class="scope-note">${state.activityLevel==='module'?'模块内部活动':'整体场景活动'} · 正常完成路径的人工摘要；异常路径未展开。红色表示活动内含代码改动。</div><div class="diagram-grid ${state.mode==='split'?'':'single'}"><section class="diagram-panel"><div class="diagram-title"><strong>${plain?'原始活动图':'修改前 · 标记变化'}</strong><code>8a2dc20</code></div><div class="diagram-scroll">${activityGraph(false,plain)}</div></section>${state.mode==='split'?`<section class="diagram-panel"><div class="diagram-title"><strong>修改后</strong><code>76d21d2</code></div><div class="diagram-scroll">${activityGraph(true)}</div></section>`:''}</div><div class="legend"><span><i class="red"></i>旧版活动含改动</span><span><i class="amber"></i>新版活动含改动</span><span><i></i>上下文保留，未判定无影响</span></div>`;
}
function activityEvidence(){
  const moduleLevel=state.activityLevel==='module';
  return `<h2>活动依据</h2><h3>${moduleLevel?'Table 模块更新文档':'文档更新场景'}</h3><p>点击标红的活动可继续展开。父活动标红表示内部含改动，不表示整个模块都被修改。</p><h3>本次变化</h3><p>update 的 doc_ids 分支新增 ID 筛选。整体活动顺序不变，模块内部的行为发生变化。</p><h3>源码与场景范围</h3><a href="${sourceUrl('before',437,451)}" target="_blank" rel="noreferrer">旧版 update · L437–451 ↗</a><a href="${sourceUrl('after',441,464)}" target="_blank" rel="noreferrer">新版 update · L441–464 ↗</a><a href="${sourceUrl('before',766,816)}" target="_blank" rel="noreferrer">旧版读取、回调、写入与缓存 ↗</a><a href="${sourceUrl('after',787,837)}" target="_blank" rel="noreferrer">新版读取、回调、写入与缓存 ↗</a><p>当前为一次文档更新的正常完成路径，不覆盖 TinyDB 的查询、插入、删除或所有异常。Activity 的名称由人工概括，源码依据可逐项核对。</p><button data-activity-level="${moduleLevel?'function':'module'}">${moduleLevel?'进入函数流程':'展开 Table 模块'}</button>`;
}
function dataModelView(){
  return `<div class="wide-panel"><div class="panel-toolbar"><h2>TinyDB 数据模型</h2><div class="segmented"><button data-arch="modules">模块依赖</button><button data-arch="calls">调用关系</button><button data-arch="data" class="active">数据模型</button></div></div><div class="scope-note">目标快照 · 逻辑存储结构 · TinyDB 没有固定关系表 schema，此图不表示 SQL 外键关系。</div><div class="data-model-canvas"><article class="data-entity"><h3>数据库映射</h3><code>表名称 → 表数据</code><p>包含零个或多个命名表</p></article><div class="data-link">包含 ↓</div><article class="data-entity"><h3>表数据</h3><code>文档 ID → 文档内容</code><p>存储时将文档 ID 转成字符串</p></article><div class="data-link">包含 ↓</div><article class="data-entity"><h3>文档内容</h3><code>字段名 → 值</code><p>字段由使用方定义，没有固定字段清单</p></article></div><div class="section-body"><h3>模型依据</h3><p>结构取自 _update_table 中读取数据库映射、按表名定位、按文档 ID 读写的代码。此例只显示目标版本结构，未生成数据库结构差异。</p><a href="${sourceUrl('after',801,834)}" target="_blank" rel="noreferrer">查看 table.py L801–834 ↗</a><p>关系型项目后续从 ORM、迁移或 schema 提取表、字段、主外键与基数；无依据的关系保持未知。</p></div></div>`;
}
