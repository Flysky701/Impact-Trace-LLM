'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const data = window.reviewData;
const graph = window.prototypeGraphData;
const state = {page:'compare', mode:'split', diagram:'flow', activityLevel:'overview', file:'tinydb/table.py', selected:'filter', arch:'modules', module:'table', reviews:[]};
const sourceUrl = (side, start, end=start) => `https://github.com/msiemens/tinydb/blob/${side==='before'?data.base:data.head}/tinydb/table.py#L${start}-L${end}`;
const markerMarkup = '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#83909e"/></marker></defs>';
const marker = id => markerMarkup.replace('id="arrow"', `id="${id}"`);
function node(id,y,title,sub,kind='',status='') {
  return `<g class="node ${kind} ${state.selected===id?'selected':''}" data-node="${id}" role="button" tabindex="0" aria-label="${esc(title)}，查看源码依据"><rect x="70" y="${y}" width="260" height="58" rx="6"/><text x="200" y="${y+23}" text-anchor="middle">${esc(title)}</text><text class="sub" x="200" y="${y+43}" text-anchor="middle">${esc(sub)}</text>${status?`<text class="status" x="340" y="${y+20}">${status}</text>`:''}</g>`;
}
function flow(after=false, plain=false) {
  const side=after?'after':'before';
  const edge=(y1,y2)=>`<path class="edge" d="M200 ${y1} V${y2}"/>`;
  const change=plain?'':after?'amber':'red';
  return `<svg class="flow" style="--arrow:url(#arrow-${side})" viewBox="0 0 400 550" role="img" aria-label="${after?'修改后先过滤不存在的 ID，再更新并返回实际更新 ID':'修改前直接更新所有请求 ID；红色表示被修改的步骤'}">${marker('arrow-'+side)}
    ${edge(88,120)}${after?edge(178,210)+edge(268,300):edge(178,300)}${edge(358,400)}${edge(458,490)}
    ${node('collect',30,after?'保存请求 ID，初始化结果':'收集全部请求 ID',after?'requested_ids / updated_ids = []':'updated_ids = list(doc_ids)',change,plain?'':after?'修改':'改动')}
    ${node('entry',120,'进入 updater(table)',after?'L451 · 在表的当前数据上执行':'L443 · 在表的当前数据上执行')}
    ${after?node('filter',210,'筛选当前存在的 ID','先完成筛选，再逐个更新','green','新增'):!plain?'<rect class="annotation" x="18" y="212" width="166" height="55" rx="5"/><text class="annotation-text" x="29" y="233">目标版本在此新增过滤</text><text class="annotation-text" x="29" y="252">对比注释 · 旧版无此步骤</text><path class="annotation" d="M184 240 H200"/>':''}
    ${node('update',300,after?'逐个更新筛选后的 ID':'逐个更新全部请求 ID',after?'L458–459 · perform_update':'L445–446 · perform_update',change,plain?'':'修改')}
    ${node('write',400,'完成 _update_table 回调',after?'L462 · 存储内部流程未展开':'L449 · 存储内部流程未展开')}
    <text x="200" y="509" text-anchor="middle">${after?'返回实际更新的 ID':'返回 updated_ids'}</text><text class="sub" x="200" y="531" text-anchor="middle">${after?'L464':'L451'} · ${after?'76d21d2':'8a2dc20'}</text>
  </svg>`;
}
const evidence = {
  collect:{title:'请求与结果分开保存',text:'旧版直接将请求 ID 作为更新结果。新版保留 requested_ids，并将 updated_ids 初始化为空列表。',before:[441,441],after:[448,449]},
  entry:{title:'updater 的执行范围',text:'两个版本都将 updater 交给 _update_table。此图仅展开 doc_ids 分支；条件查询、用户回调及存储内部流程不在本图范围。',before:[443,449],after:[451,462]},
  filter:{title:'更新前筛选存在的 ID',text:'新版在执行任何更新前收集表中存在的 ID。旧版没有这个过滤步骤，图上的红色虚线框仅用于标记新增位置。',before:[441,446],after:[448,459]},
  update:{title:'更新输入发生变化',text:'perform_update 调用仍然存在，输入从全部请求 ID 变为筛选后的 ID。缺失 ID 的旧行为可由 table[doc_id] 的访问位置核对。',before:[426,446],after:[430,459]},
  write:{title:'回调仍交由同一入口执行',text:'两个版本都调用 _update_table(updater)。此处只标示流程汇合，不声称存储内部逻辑发生变化。',before:[448,451],after:[461,464]}
};
function evidencePanel(){
  const item=evidence[state.selected]||evidence.filter;
  const selected=data.after.filter(row=>row.line>=item.after[0]&&row.line<=item.after[1]).slice(0,14);
  return `<h2>源码依据</h2><div class="evidence-title"><h3>${item.title}</h3></div><span class="fact">人工核对 · 固定提交</span><p>${item.text}</p><h3>版本定位</h3><a href="${sourceUrl('before',...item.before)}" target="_blank" rel="noreferrer">修改前 · L${item.before.join('–')} ↗</a><a href="${sourceUrl('after',...item.after)}" target="_blank" rel="noreferrer">修改后 · L${item.after.join('–')} ↗</a><pre>${selected.map(row=>esc(row.line+'  '+row.text.trimStart())).join('\n')}</pre><h3>关联影响</h3><p><code>upsert → update</code> 是调用方向；update 改变后，需要核对 upsert。upsert 在该提交中也有修改。</p><a href="${sourceUrl('after',598,606)}" target="_blank" rel="noreferrer">查看 upsert 调用位置 ↗</a><details><summary>围绕这次变更提问</summary><button class="question" id="question-button">为什么要检查 upsert？</button><div id="question-answer"></div></details>`;
}
function files(){return `<aside class="file-panel"><h2>变更文件 · 3</h2>${['tinydb/table.py','tests/test_tinydb.py','docs/changelog.rst'].map((name,i)=>`<button class="file-item ${state.file===name?'selected':''}" data-file="${name}">${name}<span>${['3 个方法发生变化','新增回归用例','更新行为说明'][i]}</span></button>`).join('')}<p class="file-note">当前范围<br><strong>${state.diagram==='activity'?'文档更新场景':'Table.update'}</strong><br>${state.diagram==='activity'?'活动可逐层展开':'仅展开 doc_ids 分支'}</p><p class="file-note">检查数据<br>覆盖率未导入<br>测试未执行</p></aside>`;}
function diff(){return `<div class="source-view"><pre>${data.diffs[state.file].split('\n').map(line=>`<span class="code-line ${line.startsWith('+')&&!line.startsWith('+++')?'plus':line.startsWith('-')&&!line.startsWith('---')?'minus':''}">${esc(line)||' '}</span>`).join('')}</pre></div>`;}
function compare(){
  const isDiff=state.mode==='diff'||state.file!=='tinydb/table.py';
  const modes=[['split','前后对照'],['overlay','旧图标注'],['original','原始旧图'],['diff','代码差异']];
  let content=isDiff?diff():`<div class="scope-note">doc_ids 分支摘要 · 点击步骤查看源码 · ${state.mode==='original'?'原始旧图不显示变更标记':'红色表示代码变化，不表示故障或风险等级'}</div><div class="diagram-grid ${state.mode==='split'?'':'single'}"><section class="diagram-panel"><div class="diagram-title"><strong>${state.mode==='original'?'原始流程':'修改前 · 标记变化'}</strong><code>8a2dc20</code></div><div class="diagram-scroll">${flow(false,state.mode==='original')}</div></section>${state.mode==='split'?`<section class="diagram-panel"><div class="diagram-title"><strong>修改后</strong><code>76d21d2</code></div><div class="diagram-scroll">${flow(true)}</div></section>`:''}</div><div class="legend"><span><i class="red"></i>旧图改动位置</span><span><i class="green"></i>新图新增步骤</span><span><i class="amber"></i>新图修改步骤</span><span><i></i>保留上下文</span></div>`;
  const activity=state.diagram==='activity'&&!isDiff;
  if(activity)content=activityView();
  return `<div class="workbench">${files()}<section class="center-panel"><div class="diagram-kind"><span>图种</span><button data-diagram="flow" aria-pressed="${state.diagram==='flow'}">函数流程图</button><button data-diagram="activity" aria-pressed="${state.diagram==='activity'}">活动图</button></div><div class="panel-toolbar"><h2>${isDiff?esc(state.file):activity?'文档更新活动':'Table.update'}</h2><div class="segmented">${modes.map(([id,label])=>`<button data-mode="${id}" class="${state.mode===id?'active':''}" aria-pressed="${state.mode===id}">${label}</button>`).join('')}</div></div>${content}</section><aside class="evidence-panel">${activity?activityEvidence():evidencePanel()}</aside></div>`;
}
function codePage(){return `<div class="wide-panel"><div class="panel-toolbar"><h2>tinydb/table.py</h2><span class="muted">目标版本 76d21d2 · L429–464 摘录</span></div><div class="source-view"><pre>${data.after.map(row=>`<span class="code-line"><span class="num">${row.line}</span>${esc(row.text)}</span>`).join('')}</pre></div><div class="legend"><a href="${sourceUrl('after',429,464)}" target="_blank" rel="noreferrer">完整源码 ↗</a><a href="tinydb-LICENSE.txt">TinyDB · MIT License</a><button data-page="compare">查看流程变化</button></div></div>`;}
function architecture(){
  if(state.arch==='data')return dataModelView();
  const call=state.arch==='calls';
  const rels=graph.imports.filter(e=>e.from===state.module);
  const targets=[...new Set(rels.map(e=>e.to))];
  let drawing='';
  if(call){
    drawing=`<svg class="flow" style="--arrow:url(#arrow-arch)" viewBox="0 0 800 420" role="img" aria-label="upsert 调用 update 和 insert，调用点来自固定快照">${marker('arrow-arch')}<path class="edge" d="M400 120 V190 H220 V250"/><path class="edge" d="M400 190 H580 V250"/><text x="230" y="177">调用 · L598</text><text x="500" y="177">调用 · L606</text><g class="node amber"><rect x="290" y="60" width="220" height="60" rx="6"/><text x="400" y="95" text-anchor="middle">Table.upsert · 有改动</text></g><g class="node red" data-node="update" tabindex="0" role="button" aria-label="查看 update 流程变化"><rect x="110" y="250" width="220" height="60" rx="6"/><text x="220" y="285" text-anchor="middle">Table.update · 有改动</text></g><g class="node"><rect x="470" y="250" width="220" height="60" rx="6"/><text x="580" y="285" text-anchor="middle">Table.insert</text></g><text class="sub" x="400" y="360" text-anchor="middle">实线是调用方向；潜在影响从 update 反向到 upsert。</text></svg>`;
  }else{
    const width=800;
    drawing=`<svg class="flow" style="--arrow:url(#arrow-arch)" viewBox="0 0 ${width} 420" role="img" aria-label="${esc(state.module)} 模块的直接导入关系">${marker('arrow-arch')}${targets.map((target,i)=>{const x=width/(targets.length+1)*(i+1);return `<path class="edge" d="M400 120 V${165+i*15} H${x} V260"/><text class="sub" x="${x}" y="247" text-anchor="middle">导入 · L${rels.find(e=>e.to===target).line}</text><g class="node" data-module="${target}" role="button" tabindex="0" aria-label="展开 ${target} 的直接依赖"><rect x="${x-70}" y="260" width="140" height="60" rx="6"/><text x="${x}" y="294" text-anchor="middle">${esc(target)}</text></g>`;}).join('')}<g class="node ${state.module==='table'?'amber':''}"><rect x="290" y="60" width="220" height="60" rx="6"/><text x="400" y="95" text-anchor="middle">${esc(state.module)}</text></g>${targets.length?'':`<text x="400" y="235" text-anchor="middle">未提取到同包顶层相对导入</text><text class="sub" x="400" y="260" text-anchor="middle">不代表没有动态或外部依赖。</text>`}</svg>`;
  }
  return `<div class="wide-panel"><div class="panel-toolbar"><h2>${call?'Table.upsert 的直接调用':state.module+' 的直接导入'}</h2><div class="segmented"><button data-arch="modules" class="${call?'':'active'}">模块依赖</button><button data-arch="calls" class="${call?'active':''}">调用关系</button><button data-arch="data">数据模型</button></div></div><div class="scope-note">目标快照 · ${call?'固定 self.method() 语法候选，不是运行时追踪':'逐层展开，同一层只显示模块；来自固定快照的 AST 提取'}</div><div class="arch-body"><div class="arch-diagram">${drawing}</div><aside class="arch-side"><h3>${call?'调用依据':'模块 · 10'}</h3>${call?`<p>upsert 调用 update（L598）和 insert（L606）。点击 update 打开流程对照。</p><a href="${sourceUrl('after',598,606)}" target="_blank" rel="noreferrer">对应源码 ↗</a>`:graph.modules.map(m=>`<button class="file-item ${state.module===m.id?'selected':''}" data-module="${m.id}">${esc(m.id)}<span>${m.defs.length} 条定义记录</span></button>`).join('')}<p>当前视图不是完整项目调用图。动态转发、运行时对象类型及跨模块调用尚未解析。</p></aside></div></div>`;
}
function checks(){const tests=['test_update_ids_missing','test_update_ids_mixed','test_remove_ids_missing','test_remove_ids_mixed','test_doc_id_missing_consistency'];return `<div class="wide-panel"><div class="panel-toolbar"><h2>检查与覆盖率</h2><span class="muted">当前目标提交 · 76d21d2</span></div><div class="metric-list"><div class="metric"><span>变更范围</span><strong>3 个文件</strong><small>Git diff · +95 / −20</small></div><div class="metric"><span>变更行覆盖率</span><strong>未导入</strong><small>需要目标提交的覆盖率报告</small></div><div class="metric"><span>分支覆盖率</span><strong>未导入</strong><small>与行覆盖率分别记录</small></div><div class="metric"><span>测试运行结果</span><strong>未执行</strong><small>平台未运行被分析仓库测试</small></div></div><div class="table-wrap"><table><thead><tr><th>已有测试线索</th><th>所在文件</th><th>状态</th></tr></thead><tbody>${tests.map(t=>`<tr><td><code>${t}</code></td><td>tests/test_tinydb.py</td><td>存在于目标版本 · 未执行</td></tr>`).join('')}</tbody></table></div><div class="section-body"><h3>指标边界</h3><p>项目自身的测试覆盖率不能作为 TinyDB 的覆盖率。报告必须带有仓库、提交、测试范围与采集时间；来源缺失显示“未导入”，不能显示 0%。</p><p>后续优先导入已有 CI 报告，展示变更可执行行的覆盖情况。自动执行测试与综合质量评分暂不加入。</p></div></div>`;}
function reviews(){return `<div class="wide-panel"><div class="panel-toolbar"><h2>当前比较的审阅记录</h2><span class="muted">固定两个提交 · 预览数据</span></div>${state.reviews.length?`<div class="section-body">${state.reviews.map(r=>`<article class="review-record"><h3>${esc(r.decision)} <span class="badge">审核者预览</span></h3><p>${esc(r.note)}</p><span class="muted">${esc(r.time)} · 测试未执行</span></article>`).join('')}</div>`:'<div class="empty-state"><h2>尚无审阅记录</h2><p>核对流程变化、源码及测试线索后填写意见。</p><button class="primary" data-review>提交审阅</button></div>'}</div>`;}
function render(){
  document.querySelectorAll('[data-page]').forEach(button=>{button.classList.toggle('active',button.dataset.page===state.page);if(button.closest('nav'))button.setAttribute('aria-current',button.dataset.page===state.page?'page':'false');});
  $('workspace').innerHTML=({compare,code:codePage,architecture,checks,reviews}[state.page])();
  $('review-count').textContent=state.reviews.length;
}
function navigate(page){state.page=page;render();}
document.addEventListener('click',event=>{
  const page=event.target.closest('[data-page]');if(page){navigate(page.dataset.page);return;}
  const kind=event.target.closest('[data-diagram]');if(kind){state.diagram=kind.dataset.diagram;state.file='tinydb/table.py';if(state.mode==='diff')state.mode='split';render();return;}
  const level=event.target.closest('[data-activity-level]');if(level){if(level.dataset.activityLevel==='function'){state.diagram='flow';state.selected='filter';}else{state.diagram='activity';state.activityLevel=level.dataset.activityLevel;}state.file='tinydb/table.py';if(state.mode==='diff')state.mode='split';render();return;}
  const activity=event.target.closest('[data-activity]');if(activity){const target=activity.dataset.activity;if(target==='module'){state.activityLevel='module';render();}else if(target==='function'){state.diagram='flow';state.selected='filter';render();}else{const panel=document.querySelector('.evidence-panel');panel.innerHTML=activityEvidence()+'<p role="status">当前活动为场景上下文，暂无更细展开；可通过上述源码核对。</p>';}return;}
  const mode=event.target.closest('[data-mode]');if(mode){state.mode=mode.dataset.mode;if(state.mode!=='diff')state.file='tinydb/table.py';render();return;}
  const file=event.target.closest('[data-file]');if(file){state.file=file.dataset.file;state.mode='diff';render();return;}
  const step=event.target.closest('[data-node]');if(step){state.selected=step.dataset.node;if(state.page==='architecture'){state.page='compare';state.mode='split';state.diagram='flow';state.file='tinydb/table.py';render();}else{document.querySelector('.evidence-panel').innerHTML=evidencePanel();document.querySelectorAll('[data-node]').forEach(n=>n.classList.toggle('selected',n.dataset.node===state.selected));}$('announce').textContent='已显示'+evidence[state.selected].title+'的源码依据';return;}
  const arch=event.target.closest('[data-arch]');if(arch){state.arch=arch.dataset.arch;render();return;}
  const module=event.target.closest('[data-module]');if(module){state.module=module.dataset.module;render();return;}
  if(event.target.closest('[data-review]')||event.target.id==='review-open')$('review-dialog').showModal();
  if(event.target.id==='review-close')$('review-dialog').close();
  if(event.target.id==='question-button')$('question-answer').innerHTML='<p>人工示例回答：upsert 调用 update，并在未更新任何文档时转入 insert。这次 update 会跳过不存在的 ID，upsert 也移除了捕获 KeyError 的分支，需要一起核对。</p><p>依据：目标版 table.py L594–606；不是实时模型回答。</p>';
});
document.addEventListener('keydown',event=>{const el=event.target.closest('g[role="button"]');if(el&&(event.key==='Enter'||event.key===' ')){event.preventDefault();el.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
$('review-form').addEventListener('submit',event=>{event.preventDefault();const form=new FormData(event.target);const note=String(form.get('note')).trim();if(!note){event.target.elements.note.setCustomValidity('请填写审核意见');event.target.elements.note.reportValidity();return;}state.reviews.push({decision:form.get('decision'),note,time:new Date().toLocaleString('zh-CN')});$('review-dialog').close();event.target.reset();navigate('reviews');});
$('review-form').elements.note.addEventListener('input',event=>event.target.setCustomValidity(''));
render();
