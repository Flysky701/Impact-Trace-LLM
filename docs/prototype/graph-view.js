/* Product preview: fixed-snapshot AST relationships, never a runtime call graph. */
window.codeGraph = (() => {
  const data = window.prototypeGraphData;
  const state = {view:'graph', level:'modules', selected:'table', showImpact:true, focus:false, zoom:1, query:''};
  let noChanges = false, partial = false;
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const descriptions = {__init__:'公共导出入口',database:'数据库与表访问',table:'文档操作',queries:'查询条件',storages:'存储接口',utils:'通用工具',version:'版本信息',middlewares:'存储中间件',operations:'更新操作工具',mypy_plugin:'类型检查插件'};
  const modulePositions = {__init__:[30,140],database:[260,140],table:[490,240],queries:[725,130],storages:[725,345],utils:[965,235],version:[260,25],middlewares:[70,510],operations:[380,510],mypy_plugin:[690,510]};
  const functionPositions = {upsert:[30,40],contains:[30,340],insert_multiple:[30,170],update_multiple:[30,470],update:[290,40],insert:[290,170],get:[290,340],search:[290,470],remove:[550,40],_get_next_id:[550,230],_update_table:[820,100],_read_table:[820,380]};
  const module = id => data.modules.find(m=>m.id===id);
  const uniqueEdges = edges => [...new Map(edges.map(e=>[e.from+'|'+e.to,e])).values()];
  function analysis(level){
    const edges=uniqueEdges(level==='modules'?data.imports:data.calls);
    const changed=noChanges?[]:level==='modules'?['table']:['update','remove','upsert'];
    const depths=new Map(), parents=new Map();
    // A changed caller can still be a direct candidate of another changed callee.
    for(const start of changed){const queue=[[start,0]],seen=new Set([start]);while(queue.length){const [to,depth]=queue.shift();for(const e of edges.filter(e=>e.to===to)){if(seen.has(e.from))continue;seen.add(e.from);const next=depth+1;if(!depths.has(e.from)||next<depths.get(e.from)){depths.set(e.from,next);parents.set(e.from,to);}queue.push([e.from,next]);}}}
    return {edges,changed,depths,parents};
  }
  function flags(id, result){const changed=result.changed.includes(id),depth=result.depths.get(id);return {changed,depth,kind:changed?'changed':depth===1?'direct':depth>1?'indirect':'context'};}
  function label(id, result){const f=flags(id,result);return [f.changed?'有改动':'',f.depth===1?'直接候选':f.depth>1?'间接候选':''].filter(Boolean).join(' · ')||'上下文';}
  function selectedInfo(){
    if(state.level==='modules')return {id:state.selected,name:state.selected+'.py',module:state.selected,line:1};
    if(state.selected.startsWith('definition|')){const [,mod,name,line]=state.selected.split('|');return {id:name.startsWith('Table.')?name.split('.')[1]:name,name,module:mod,line:Number(line)};}
    const def=module('table').defs.find(d=>d.name==='Table.'+state.selected);
    return {id:state.selected,name:'Table.'+state.selected,module:'table',line:def?.line||1};
  }
  function sourceLink(mod,line){return `https://github.com/msiemens/tinydb/blob/${data.sha}/${module(mod).path}#L${line}`;}
  function pathFor(id,result){const seen=new Set(),chain=[id];let current=id;while(result.parents.has(current)&&!seen.has(current)){seen.add(current);current=result.parents.get(current);chain.unshift(current);}return chain.join(' → ');}
  function inspector(){
    const info=selectedInfo(),level=info.module==='table'&&state.level==='functions'?'functions':'modules';
    const result=analysis(level),id=level==='modules'?info.module:info.id;
    const relation=result.edges.find(e=>e.from===id&&e.to===result.parents.get(id));
    const f=flags(id,result);const source=relation?sourceLink(level==='modules'?relation.from:'table',relation.line):sourceLink(info.module,info.line);
    return `<aside class="graph-inspector"><div class="eyebrow">SELECTED NODE</div><h3>${esc(info.name)}</h3><div class="node-status ${f.kind}">${esc(label(id,result))}</div><p>${f.changed?'该实体在固定历史修复中有改动。':f.depth?'它依赖发生变化的代码，是需要核对的潜在影响位置。':'保留在图中帮助理解全貌；未标记影响不等于已证明安全。'}</p>${f.depth?`<div class="trace-box"><small>影响传播路径</small><strong>${esc(pathFor(id,result))}</strong></div>`:''}
    ${state.level==='modules'?`<p class="inspector-note">当前为模块导入依赖。导入关系只能支持粗粒度候选，不能说明模块中每个函数都会受影响。</p>`:`<p class="inspector-note">调用来自同类 self.method() 语法候选。动态调用与类型遮蔽仍需核对。</p>`}
    ${relation?`<div class="graph-evidence"><strong>依赖依据</strong><p>${esc(relation.from)} → ${esc(relation.to)}</p><small>${level==='modules'?esc(module(relation.from).path):'tinydb/table.py'} : ${relation.line}</small></div>`:`<div class="graph-evidence"><strong>所在位置</strong><p>${esc(module(info.module).path)}</p><small>${state.level==='modules'?'模块入口':'定义起始行 '+info.line}</small></div>`}
    <a class="button secondary small" href="${source}" target="_blank" rel="noopener noreferrer">查看固定版本源码 ↗</a>
    ${info.module==='table'&&state.level==='modules'?'<button class="button small" data-graph-level="functions">展开 Table 函数 →</button>':''}
    <p class="inspector-note">固定版本 ${data.sha.slice(0,8)}<br>静态关系已从该版本提取；影响为保守候选，尚非正式分析引擎结果。</p></aside>`;
  }
  function graph(){
    const level=state.level,result=analysis(level),positions=level==='modules'?modulePositions:functionPositions;
    const ids=Object.keys(positions),w=level==='modules'?1180:1040,h=650,nodeW=level==='modules'?175:185,nodeH=74;
    function curve(from,to,offset=0){const [x1,y1]=positions[from],[x2,y2]=positions[to];const forward=x2>=x1;const sx=x1+(forward?nodeW:0),tx=x2+(forward?0:nodeW),sy=y1+nodeH/2+offset,ty=y2+nodeH/2+offset;
      // Route long dependencies around intervening nodes; crossings are not junctions.
      const lanes=level==='modules'?{
        '__init__|queries':[[220,sy],[220,112],[707,112],[707,ty]],
        '__init__|storages':[[216,sy],[216,442],[707,442],[707,ty]],
        'database|storages':[[453,sy],[453,418],[707,418],[707,ty]],
        'database|utils':[[455,sy],[455,100],[937,100],[937,ty]],
      }:{
        'update|_update_table':[[510,sy],[510,20],[797,20],[797,ty]],
        'insert_multiple|_get_next_id':[[240,sy],[240,286],[532,286],[532,ty]],
        'insert_multiple|_update_table':[[229,sy],[229,320],[781,320],[781,ty]],
        'update_multiple|_update_table':[[240,sy],[240,566],[797,566],[797,ty]],
      };
      const lane=lanes[from+'|'+to];if(lane)return `M${sx},${sy} `+lane.map(([x,y])=>`L${x},${y}`).join(' ')+` L${tx},${ty}`;
      const bend=Math.max(40,Math.abs(tx-sx)/2);return `M${sx},${sy} C${sx+(forward?bend:-bend)},${sy} ${tx+(forward?-bend:bend)},${ty} ${tx},${ty}`;}
    const edges=result.edges.filter(e=>positions[e.from]&&positions[e.to]);
    const edgeMarkup=edges.map(e=>`<path class="dependency-edge ${state.focus&&!result.depths.has(e.from)?'dimmed':''}" d="${curve(e.from,e.to,-5)}" marker-end="url(#dependency-arrow)"><title>${esc(e.from)} 依赖 ${esc(e.to)} · 第 ${e.line} 行</title></path>`).join('');
    const impactMarkup=state.showImpact?[...result.parents].filter(([to,from])=>positions[from]&&positions[to]).map(([to,from])=>`<path class="impact-edge ${result.depths.get(to)>1?'indirect':''}" d="${curve(from,to,8)}" marker-end="url(#${result.depths.get(to)>1?'indirect':'impact'}-arrow)"><title>潜在影响：${esc(from)} → ${esc(to)}</title></path>`).join(''):'';
    const nodes=ids.map(id=>{const [x,y]=positions[id],f=flags(id,result),selected=state.selected===id,style=state.showImpact?f.kind:'context';return `<g class="graph-node ${style} ${selected?'selected':''} ${state.focus&&f.kind==='context'?'dimmed':''}" transform="translate(${x} ${y})" role="button" tabindex="0" aria-label="${esc(id)} ${esc(label(id,result))}" aria-pressed="${selected}" data-graph-node="${id}"><rect width="${nodeW}" height="${nodeH}" rx="10"/><text x="14" y="28" class="graph-node-name">${esc(level==='modules'?id+'.py':id+'()')}</text><text x="14" y="53" class="graph-node-caption">${esc(state.showImpact?label(id,result):level==='modules'?descriptions[id]:'Table 方法')}</text>${f.changed&&state.showImpact?`<circle cx="${nodeW-13}" cy="13" r="4" class="change-dot"/>`:''}</g>`;}).join('');
    return `<div class="graph-canvas" tabindex="0" aria-label="代码关系画布，可横向滚动"><svg viewBox="0 0 ${w} ${h}" style="width:${state.zoom*100}%;min-width:${Math.round(710*state.zoom)}px" role="group" aria-label="${level==='modules'?'全部 10 个模块的相对导入关系':'Table 的主要函数调用关系'}"><defs><marker id="dependency-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#afbbb6"/></marker><marker id="impact-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#c48828"/></marker><marker id="indirect-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8767b0"/></marker></defs>${level==='modules'?'<rect class="graph-group" x="20" y="470" width="900" height="140" rx="14"/><text class="group-label" x="40" y="493">其他模块 · 当前规则未提取到相对导入边</text>':'<text class="group-label" x="30" y="620">Table 主要调用子图 · 完整定义请切换“结构树”</text>'}${edgeMarkup}${impactMarkup}${nodes}</svg></div>`;
  }
  function tree(){const result=analysis('modules'),functions=analysis('functions'),q=state.query.toLowerCase();return `<div class="structure-tree"><label class="tree-search">查找模块或定义 <input id="graph-search" type="text" value="${esc(state.query)}" placeholder="例如 table、update、Storage"></label><p class="graph-scope">10 个模块 · ${data.modules.reduce((n,m)=>n+m.defs.length,0)} 条定义记录（含类、重载和内部函数）。搜索不改变影响分析范围。</p><div id="tree-results">${treeResults(q,result,functions)}</div></div>`;}
  function treeResults(q,result=analysis('modules'),functions=analysis('functions')){const matches=data.modules.map(m=>({m,defs:m.id.toLowerCase().includes(q)?m.defs:m.defs.filter(d=>d.name.toLowerCase().includes(q))})).filter(({m,defs})=>!q||m.id.toLowerCase().includes(q)||defs.length);if(!matches.length)return '<p class="empty">没有匹配的模块或定义。</p>';return matches.map(({m,defs})=>`<details class="tree-module" ${q||m.id==='table'?'open':''}><summary><span>${esc(m.path)}</span><span class="tree-badge ${flags(m.id,result).kind}">${esc(label(m.id,result))}</span><small>${defs.length} 条定义</small></summary><button class="text-button tree-module-select" data-tree-module="${m.id}">查看模块依据</button><div>${defs.map(d=>{const id=d.name.startsWith('Table.')?d.name.split('.')[1]:d.name,kind=m.id==='table'?flags(id,functions).kind:'context';return `<button class="tree-definition ${kind}" data-tree-definition="${esc(m.id+'|'+d.name+'|'+d.line)}"><span>${d.kind==='class'?'C':'ƒ'}</span><strong>${esc(d.name)}</strong><small>L${d.line}</small>${m.id==='table'&&kind!=='context'?`<em>${esc(label(id,functions))}</em>`:''}</button>`;}).join('')}</div></details>`).join('');}
  function impactList(){return `<div class="impact-list"><h3>从模块到函数，逐项核对</h3><p class="graph-scope">模块候选来自相对导入；函数候选来自 Table 内调用。两个粒度分别统计。</p>${['modules','functions'].map(level=>{const r=analysis(level),ids=[...new Set([...r.changed,...r.depths.keys()])];return `<h4>${level==='modules'?'模块范围':'Table 函数范围'}</h4>${ids.length?ids.map(id=>`<button class="impact-row" data-list-node="${id}" data-list-level="${level}"><span class="status-mark ${flags(id,r).kind}"></span><span><strong>${esc(id)}${level==='modules'?'.py':'()'}</strong><small>${esc(r.depths.has(id)?pathFor(id,r):'历史提交中有改动')}</small></span><span class="tree-badge ${flags(id,r).kind}">${esc(label(id,r))}</span><span>↗</span></button>`).join(''):'<p class="empty">当前比较没有变更，因此没有影响候选。</p>'}`;}).join('')}<div class="callout">此固定案例中，upsert 同时是变更实体和 update 的直接影响候选。没有据此虚构更多函数级间接影响。</div></div>`;}
  function render(options={}){noChanges=Boolean(options.empty);partial=Boolean(options.partial);const result=analysis(state.level);return `<section class="code-workspace"><div class="graph-title"><div><h2>在项目全貌中查看影响</h2><p>保留整体关系，把本次改动和可能传播的影响叠加在同一视图上。</p></div><span class="tag">固定快照 · 静态关系</span></div>
    <div class="graph-toolbar"><div class="graph-switch" aria-label="展示方式">${[['graph','关系图'],['tree','结构树'],['list','影响清单']].map(([key,name])=>`<button data-graph-view="${key}" class="${state.view===key?'active':''}" aria-pressed="${state.view===key}">${name}</button>`).join('')}</div>${state.view==='graph'?`<div class="graph-switch" aria-label="图的粒度"><button data-graph-level="modules" class="${state.level==='modules'?'active':''}">模块总览</button><button data-graph-level="functions" class="${state.level==='functions'?'active':''}">Table 函数</button></div><label class="check"><input id="graph-overlay" type="checkbox" ${state.showImpact?'checked':''}>标注影响</label><label class="check"><input id="graph-focus" type="checkbox" ${state.focus?'checked':''}>淡化其他节点</label><div class="graph-zoom"><button data-graph-zoom="out" aria-label="缩小关系图">−</button><button data-graph-zoom="reset" aria-label="重置关系图缩放">${Math.round(state.zoom*100)}%</button><button data-graph-zoom="in" aria-label="放大关系图">＋</button></div>`:''}</div>
    <div class="graph-legend"><span><i class="changed"></i>有改动</span><span><i class="direct"></i>直接影响候选</span><span><i class="indirect"></i>间接影响候选</span><span><i class="context"></i>上下文 / 未判定</span></div>
    ${noChanges?'<div class="graph-alert">这两个版本没有变更，保留结构全貌，不标注影响。</div>':''}${partial?'<div class="graph-alert">部分解析情形预览：下方保留参考图，不代表本次已完整解析；真实版会定位失败文件并标明缺口。</div>':''}
    <div class="graph-layout"><div class="graph-primary">${state.view==='graph'?graph():state.view==='tree'?tree():impactList()}</div>${inspector()}</div>
    <div class="graph-caption"><span><b>实线 A → B：</b>A 导入或调用 B。<b>彩色虚线 B → A：</b>B 的改动可能影响 A。</span><span>${state.view==='graph'?(state.level==='modules'?'模块图覆盖 tinydb/ 的全部 10 个 Python 文件；仅提取同包相对导入。':'函数图展示 12 个主要方法；其余定义和内部函数在结构树中。'):'树与清单共享同一快照；点击条目可查看右侧依据。'} 动态转发未可靠解析，图中无标记不代表无影响。</span></div></section>`;}
  function redraw(){window.render();}
  document.addEventListener('click',event=>{const t=event.target.closest('[data-graph-view],[data-graph-level],[data-graph-node],[data-graph-zoom],[data-tree-module],[data-tree-definition],[data-list-node]');if(!t)return;
    if(t.dataset.graphView){state.view=t.dataset.graphView;if(state.view==='graph'&&state.selected.startsWith('definition|')){const info=selectedInfo();if(info.module==='table'&&functionPositions[info.id]){state.level='functions';state.selected=info.id;}else{state.level='modules';state.selected=info.module;}}}
    if(t.dataset.graphLevel){state.level=t.dataset.graphLevel;state.selected=state.level==='modules'?'table':'update';state.view='graph';state.zoom=1;}
    if(t.dataset.graphNode)state.selected=t.dataset.graphNode;
    if(t.dataset.graphZoom)state.zoom=t.dataset.graphZoom==='reset'?1:Math.max(.8,Math.min(1.8,state.zoom+(t.dataset.graphZoom==='in'?.2:-.2)));
    if(t.dataset.treeModule){state.level='modules';state.selected=t.dataset.treeModule;}
    if(t.dataset.treeDefinition){state.level='functions';state.selected='definition|'+t.dataset.treeDefinition;}
    if(t.dataset.listNode){state.level=t.dataset.listLevel;state.selected=t.dataset.listNode;}
    const canvas=document.querySelector('.graph-canvas'),x=canvas?.scrollLeft||0,y=canvas?.scrollTop||0;
    redraw();const updated=document.querySelector('.graph-canvas');if(updated){updated.scrollLeft=x;updated.scrollTop=y;}
  });
  document.addEventListener('keydown',event=>{if(event.target.matches('[data-graph-node]')&&['Enter',' '].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
  document.addEventListener('change',event=>{if(event.target.id==='graph-overlay'){state.showImpact=event.target.checked;redraw();}if(event.target.id==='graph-focus'){state.focus=event.target.checked;redraw();}});
  document.addEventListener('input',event=>{if(event.target.id==='graph-search'){state.query=event.target.value;document.getElementById('tree-results').innerHTML=treeResults(state.query.toLowerCase());}});
  return {render};
})();
