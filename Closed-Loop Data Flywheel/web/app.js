"use strict";
const $ = (s, root = document) => root.querySelector(s);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icons = {paper:"▤",image:"▧",video:"▷",cad:"◇",molecule:"⌬",table:"▥",code:"⌘",audio:"∿",geospatial:"⊕",sequence:"⋮"};
const names = {paper:"论文 / 文本",image:"科研图像",video:"实验视频",cad:"CAD / 几何",molecule:"分子 / 晶体",table:"表格 / 时序",code:"代码 / 仿真",audio:"音频 / 波形",geospatial:"地理 / 遥感",sequence:"生物序列"};
let state = null, token = "", current = "overview", activeJob = null, filters = {query:"",modality:"all",split:"all"}, taskFilter="all";
const statusName = {accepted:"已验证",review:"待审核",holdout:"封闭基准",train:"TRAIN",validation:"VALIDATION",completed:"已完成",completed_with_errors:"部分完成"};
const num = value => Number(value || 0).toLocaleString("en-US");
const pill = (status, label) => `<span class="pill ${esc(status)}">${esc(label || statusName[status] || status)}</span>`;
function toast(text) {const el=$("#toast");el.textContent=text;el.classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove("show"),5000);}
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json","X-Helix-Token":token},body:JSON.stringify(data)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
async function refresh() {state=await api("/api/state");render();}
function showModal(html) {$("#modal-content").innerHTML=html;$("#modal").showModal();}
const modalHead = title => `<div class="modal-head"><h2>${esc(title)}</h2><button class="ghost" data-action="close" aria-label="关闭弹窗">✕</button></div>`;
const pageTitle = (tag,title,desc,actions="") => `<div class="page-title"><div><div class="eyebrow accent">${tag}</div><h1>${title}</h1><p>${desc}</p></div><div class="actions">${actions}</div></div>`;
function orbit() {
  const nodes=[["01","采集","INGEST",300,38],["02","归档","ORGANIZE",482,129],["03","构造","SYNTHESIZE",482,291],["04","验证","VERIFY",300,382],["05","训练导出","EXPORT",118,291],["06","回流","FEEDBACK",118,129]];
  return `<svg class="orbit" viewBox="0 0 600 420" role="img" aria-label="数据飞轮六个阶段：采集、归档、构造、验证、训练导出、回流">
  <defs><radialGradient id="core"><stop stop-color="#305026" stop-opacity=".6"/><stop offset="1" stop-color="#14200f" stop-opacity="0"/></radialGradient></defs>
  <g transform="translate(0 0)"><circle cx="300" cy="210" r="190" fill="url(#core)"/>
  <ellipse class="outer" cx="300" cy="210" rx="210" ry="171"/><ellipse class="outer dash" cx="300" cy="210" rx="228" ry="190"/>
  <ellipse class="flow" cx="300" cy="210" rx="210" ry="171"/>
  <ellipse class="outer" cx="300" cy="210" rx="140" ry="92" transform="rotate(45 300 210)"/>
  <ellipse class="outer" cx="300" cy="210" rx="140" ry="92" transform="rotate(-45 300 210)"/>
  <circle class="outer dash" cx="300" cy="210" r="122"/>
  ${nodes.map(n=>`<path d="M300 210 L${n[3]} ${n[4]}" stroke="#263925" stroke-dasharray="3 7"/>`).join("")}
  <circle class="node-core" cx="300" cy="210" r="69"/>
  <text x="303" y="208" text-anchor="middle" class="orbit-name">HELIX</text>
  <text x="300" y="228" text-anchor="middle" class="orbit-sub">SCIENCE IN MOTION</text>
  ${nodes.map(n=>`<g><rect x="${n[3]-47}" y="${n[4]-25}" width="94" height="50" rx="6" class="node"/><text x="${n[3]-33}" y="${n[4]-6}" fill="#8aac7b" font-size="8">${n[0]}</text><text x="${n[3]+6}" y="${n[4]-4}" text-anchor="middle" class="caption">${n[1]}</text><text x="${n[3]}" y="${n[4]+13}" text-anchor="middle" fill="#647c60" font-size="7" letter-spacing="1">${n[2]}</text></g>`).join("")}
  </g></svg><div class="art-tag">EVIDENCE → REASONING → BETTER DATA</div>`;
}
function overview() {
  const s=state.stats;
  return `<div class="section-top"><div class="eyebrow">WORKSPACE / SCIENCE DATA FLYWHEEL</div><span class="status-chip"><i class="live-dot"></i> 本地引擎已连接</span></div>
  <section class="hero"><div class="hero-copy"><div class="eyebrow accent">AN OPEN FLYWHEEL FOR AI4SCIENCE</div><h1>让科学数据，<br><em>持续进化。</em></h1><p>连接开放科学的多模态证据，构造可验证的推理任务。每一次评测，都成为下一轮数据的起点。</p><div class="actions"><button class="primary" data-action="${s.assets?"run":"seed"}">${s.assets?"运行一轮飞轮":"载入演示数据"} <span>↗</span></button><a class="button" href="#assets">探索数据宇宙 <span>→</span></a></div><div class="hero-footnote">OPEN SOURCE · TRACEABLE · VERIFIABLE</div></div><div class="hero-art">${orbit()}</div></section>
  <section class="metrics" aria-label="本地运行统计">
  ${[[s.assets,"来源资产",`${s.demo_assets} 条原创演示标注`,"01"],[s.tasks,"构造产物","QA · Workflow · Research brief","02"],[s.accepted,"验证通过","含训练 / 验证集，已排除 holdout","03"],[s.runs,"飞轮运行",`${s.feedback} 条评测反馈`,"04"]].map(m=>`<div class="metric"><div class="metric-label">${m[1]}<span class="eyebrow">${m[3]}</span></div><div class="metric-number">${num(m[0])}</div><div class="metric-note">${m[2]}</div></div>`).join("")}</section>
  <div class="grid-two"><section class="panel flat"><div class="panel-head"><h2 class="panel-title">从原始证据，到推理数据 <span>THE LOOP</span></h2><a href="#quality" class="count">查看质量规则 ↗</a></div>
  <div class="pipeline-strip">${["开放采集","多模态归档","任务构造","五层验证","RL 导出","评测回流"].map((n,i)=>`<div class="stage"><b>0${i+1}</b>${n}<small>${["SOURCE","ASSET","TASK","VERIFY","TRAIN","LEARN"][i]}</small></div>`).join("")}</div>
  <hr class="thin-divider"><p class="hint">以证据约束生成，以独立验证筛选。原始来源家族决定数据划分，封闭基准始终隔离。科研级任务通过模型与专家扩展。</p>
  <div class="notice">当前为理论态参考实现。演示样本为原创合成数据；所有计数来自本地数据库，未宣称模型能力已提升。</div></section>
  <section class="panel"><div class="panel-head"><h2 class="panel-title">接入开放科学 <span>SOURCES</span></h2><button class="ghost" data-action="discover">接入 ↗</button></div>
  <div class="source-row"><span class="source-icon">aX</span><div class="source-name">arXiv<small>论文元数据 · 官方 API</small></div>${pill("neutral","可连接")}</div>
  <div class="source-row"><span class="source-icon">CR</span><div class="source-name">Crossref<small>DOI 检索 · 来源追溯</small></div>${pill("neutral","可连接")}</div>
  <div class="source-row"><span class="source-icon">＋</span><div class="source-name">开放资产 Manifest<small>图像 / 视频 / CAD / 分子 / 代码</small></div><button class="small" data-action="import">导入</button></div></section></div>
  <section class="more-space"><div class="panel-head"><h2 class="panel-title">运行记录 <span>RECENT RUNS</span></h2><button class="ghost" data-action="export">导出训练数据 ↓</button></div>${state.runs.length?state.runs.slice(0,4).map(r=>`<div class="run-row"><span class="eyebrow">${esc(r.id)}</span><div class="source-name">构造 ${r.created} 条 · 验证通过 ${r.accepted} 条<small>${esc(r.started_at)} · ${r.provider==="demo"?"模板演示":"模型生成"}</small></div>${pill(r.status)}</div>`).join(""):`<p class="hint">尚无运行记录。载入演示数据后，运行第一轮飞轮。</p>`}</section>`;
}
function assetCards() {
  const list=state.assets.filter(a=>(filters.modality==="all"||a.modality===filters.modality)&&(filters.split==="all"||a.split===filters.split)&&`${a.title} ${a.source_id} ${a.classification.primary}`.toLowerCase().includes(filters.query.toLowerCase()));
  return list.length?`<div class="asset-grid">${list.map(a=>`<button class="asset-card" data-action="asset" data-id="${a.id}"><div class="card-top"><span class="modality-icon">${icons[a.modality]||"◇"}</span>${pill(a.is_demo?"neutral":"accepted",a.is_demo?"原创演示":"外部来源")}</div><h3>${esc(a.title)}</h3><p>${esc(names[a.modality])} · ${esc(a.classification.primary==="unclassified"?"待分类":a.classification.top3[0].path.join(" / "))}</p><div class="card-bottom"><span>${esc(a.license)}</span><span>${esc(a.split.toUpperCase())} ↗</span></div></button>`).join("")}</div>`:`<div class="empty"><h3>这里等待新的科学证据</h3><p>调整筛选条件，或接入来源与资产清单。</p><button data-action="seed">载入原创演示数据</button></div>`;
}
function assets() {
  return pageTitle("01 / EVIDENCE UNIVERSE","数据宇宙","跨模态组织资产。每一条记录，都能回到它的来源。",`<button data-action="import">导入清单 ＋</button><button class="primary" data-action="discover">接入开放来源 ↗</button>`)
  +`<div class="toolbar"><input id="asset-search" class="search" aria-label="搜索资产" placeholder="搜索标题、学科、来源…" value="${esc(filters.query)}"><select id="modality-filter" aria-label="模态筛选"><option value="all">全部模态</option>${Object.entries(names).map(([k,v])=>`<option value="${k}" ${filters.modality===k?"selected":""}>${v}</option>`).join("")}</select><select id="split-filter" aria-label="数据划分"><option value="all">全部数据集</option>${["train","validation","holdout"].map(k=>`<option ${filters.split===k?"selected":""}>${k}</option>`).join("")}</select><span class="count">${num(state.assets.length)} ASSETS</span></div><div id="asset-results">${assetCards()}</div>`;
}
function taskRows() {
  const list=state.tasks.filter(t=>taskFilter==="all"||t.status===taskFilter);
  return list.length?list.slice(0,100).map(t=>`<button class="task-row" data-action="task" data-id="${t.id}"><span><strong>${esc(t.title)}</strong><small>${esc(t.type.toUpperCase())} / ${esc(t.op||t.provider)} / ${esc(t.id)}</small></span>${pill(t.status)}</button>`).join(""):`<div class="empty"><h3>从第一条任务开始</h3><p>选择构造方式，运行管线即可查看产物。</p></div>`;
}
function synthesis() {
  return pageTitle("02 / SYNTHESIS LAB","构造实验室","把科学证据转换成 QA、研究流程与训练任务。",`<button data-action="export">导出数据 ↓</button>`)
  +`<div class="synth-layout"><section class="panel config-panel"><h3>构造配置</h3><div class="eyebrow">GENERATION RECIPE</div>
  <label for="provider">生成器</label><select id="provider">
    <option value="demo">模板演示 · 离线可复现</option>
    <option value="model" ${state.model_available?"":"disabled"}>AI 模型 · ${state.model_available?"已配置":"未配置"}</option>
  </select>
  <label for="kind">产物类型</label><select id="kind">
    <option value="numeric">数值 QA → RL 数据</option>
    <option value="qa">证据问答 · 待审</option>
    <option value="pipeline">科研流程 DAG · 待审</option>
    <option value="paper">研究方案草稿 · 待审</option>
  </select>
  <label for="batch">批次上限</label><input id="batch" type="number" value="24" min="1" max="200">
  <label for="synth-asset">草稿来源（非数值任务）</label>
  <select id="synth-asset">${state.assets.filter(a=>a.split!=="holdout"&&["CC0-1.0","CC-BY-4.0","CC-BY-3.0","MIT","Apache-2.0"].includes(a.license)).map(a=>`<option value="${a.id}">${esc(a.title)}</option>`).join("")}</select>
  <button class="primary" data-action="synthesize">开始构造 <span>↗</span></button>
  <hr class="thin-divider"><p class="hint">数值任务采用固定计算契约，可由独立验证器复算。研究方案、流程与开放式问答进入审核区。</p>
  <div class="notice">模板模式仅处理原创演示。AI 模式需在服务端配置模型；科研级任务不以长度或术语数量判定正确性。</div></section>
  <section class="panel flat"><div class="panel-head"><h2 class="panel-title">构造产物</h2><span class="count">${state.tasks.length} ARTIFACTS</span></div><div class="tabs">${[["all","全部"],["accepted","已验证"],["review","待审核"],["holdout","封闭基准"]].map(([id,label])=>`<button data-action="task-filter" data-id="${id}" class="${taskFilter===id?"active":""}">${label}</button>`).join("")}</div><div id="task-results">${taskRows()}</div></section></div>`;
}
function quality() {
  const reviews=state.tasks.filter(t=>t.status!=="accepted");
  return pageTitle("03 / TRUST BY CONSTRUCTION","质量引擎","五层硬门槛。可信度来自证据与复算，不能由模型自报。")
  +`<div class="grid-two"><section class="panel"><div class="panel-head"><h2 class="panel-title">验证路径 <span>FIVE GATES</span></h2>${pill("accepted","规则 v1")}</div>${state.gates.map((g,i)=>`<div class="gate"><div class="gate-index">0${i+1}</div><div><h3>${g.name}</h3><p>${g.description}</p><div class="bar"><i style="width:${g.total?g.passed/g.total*100:0}%"></i></div></div><div class="gate-count">${g.passed}<small>/ ${g.total} 数值任务</small></div></div>`).join("")}</section>
  <div><section class="panel"><h2 class="panel-title">评分策略 <span>CONFIDENCE ≠ PROBABILITY</span></h2><div class="metrics" style="grid-template-columns:repeat(3,1fr);margin-bottom:16px">${[["99","3"],["95","2"],["90","1"]].map(([c,p])=>`<div class="metric"><div class="metric-label">≥ ${c}%</div><div class="metric-number">${p}<small>分</small></div></div>`).join("")}</div><p class="hint">保留策略文档的档位映射。只有经过标注集校准的置信度才能进入这套计分；当前关键词分类只提供检索分，绝不冒充 99% 正确率。</p></section>
  <section class="panel more-space"><div class="panel-head"><h2 class="panel-title">隔离与审核</h2><span class="count">${reviews.length} ITEMS</span></div>${reviews.length?reviews.slice(0,5).map(t=>`<div class="queue-item">${pill(t.status)} <button class="ghost" data-action="task" data-id="${t.id}">${esc(t.title)}</button><p>${esc(t.gates.filter(g=>!g.passed).map(g=>g.reason).join("；")||"开放式内容需要独立验证与专家审核")}</p></div>`).join(""):`<p class="hint">当前没有隔离或待审核产物。</p>`}</section></div></div>`;
}
function feedback() {
  return pageTitle("04 / LEARN FROM FAILURE","让失败，成为下一轮起点。","导入模型答题结果，以可计算奖励识别弱项，调整下一轮学科处理优先级。",`<button class="primary" data-action="feedback-form">记录评测结果 ＋</button>`)
  +`<div class="grid-two"><section class="panel"><div class="panel-head"><h2 class="panel-title">下一轮优先级</h2><span class="eyebrow">ERROR-DRIVEN SAMPLING</span></div>${state.priorities.map(p=>`<div class="priority"><div class="priority-head">${p.label}<span>${(p.weight*100).toFixed(1)}% · ${p.observations} 次观测</span></div><div class="bar"><i style="width:${p.weight*100}%"></i></div></div>`).join("")}</section><section class="panel flat"><div class="eyebrow accent">THE FEEDBACK RULE</div><h2 style="font-size:27px;font-weight:400;line-height:1.6">让数据分布<br>跟随模型的真实弱项。</h2><pre class="code">errorₜ = 0.7 · errorₜ₋₁ + 0.3 · (1 − reward)\npriority(d) ∝ 1 + 2 · error(d)</pre><p class="hint">无反馈时各学科权重一致。评测反馈只改变后续候选处理顺序；不会自动证明模型提升，也不会修改答案。封闭基准反馈不参与采样。</p><div class="notice">建议正式实验用验证集反馈；训练集答题反馈仅用于管线诊断。保留一份完全不参与调参的最终测试集。</div></section></div>
  <section class="panel flat more-space"><div class="panel-head"><h2 class="panel-title">评测记录</h2><span class="count">${state.feedback.length} OBSERVATIONS</span></div>${state.feedback.length?`<div class="table-wrap"><table><thead><tr><th>模型 / 运行名</th><th>任务</th><th>数据划分</th><th>奖励</th><th>时间</th></tr></thead><tbody>${state.feedback.slice(0,50).map(f=>`<tr><td>${esc(f.model)}</td><td>${esc(f.task_id)}</td><td>${esc(f.split)}</td><td class="${f.reward?"green":"orange"}">${f.reward.toFixed(1)}</td><td>${esc(f.created_at)}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty"><h3>尚无评测反馈</h3><p>先构造数值任务，再记录模型输出。这里展示实际提交的结果。</p></div>`}</section>`;
}
function inlineMarkdown(text) {
  return esc(text).replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>").replace(/\[([^\]]+)\]\((https:\/\/[^ )]+)\)/g,'<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>');
}
function markdown(text) {
  let code=false, table=false, result=[], buffer=[];
  for(const line of text.split("\n")) {
    if(line.startsWith("```")) {if(code){result.push(`<pre><code>${esc(buffer.join("\n"))}</code></pre>`);buffer=[];}code=!code;continue;}
    if(code){buffer.push(line);continue;}
    if(line.startsWith("|")) {if(!table){result.push('<div class="table-wrap"><table>');table=true;}if(/^\|[\s:|-]+\|$/.test(line))continue;result.push("<tr>"+line.split("|").slice(1,-1).map(c=>`<td>${inlineMarkdown(c.trim())}</td>`).join("")+"</tr>");continue;}
    if(table){result.push("</table></div>");table=false;}
    const h=line.match(/^(#{1,3}) (.*)/);
    if(h){result.push(`<h${h[1].length}>${inlineMarkdown(h[2])}</h${h[1].length}>`);}
    else if(line.startsWith("> ")){result.push(`<blockquote><p>${inlineMarkdown(line.slice(2))}</p></blockquote>`);}
    else if(line.startsWith("- ")){result.push(`<p>• ${inlineMarkdown(line.slice(2))}</p>`);}
    else if(line.trim()){result.push(`<p>${inlineMarkdown(line)}</p>`);}
  }
  if(table)result.push("</table></div>");
  return result.join("\n");
}
let handbookCache="";
async function loadHandbook(){try{if(!handbookCache)handbookCache=(await api("/api/handbook")).markdown;if(current==="handbook")$("#book-body").innerHTML=markdown(handbookCache);}catch(e){toast(e.message);}}
function render() {
  if(!state)return;
  current=location.hash.slice(1)||"overview";
  if(!["overview","assets","synthesis","quality","feedback","handbook"].includes(current))current="overview";
  document.querySelectorAll("[data-nav]").forEach(a=>a.classList.toggle("active",a.dataset.nav===current));
  const banner=activeJob?`<div class="job-banner"><span><span class="spin">◌</span> 正在执行任务 · ${esc(activeJob.label)}</span><span>${esc(activeJob.id)}</span></div>`:"";
  const views={overview,assets,synthesis,quality,feedback,handbook:()=>pageTitle("DOCUMENTATION / V0.1","项目手册","理论、算法、数据契约、运行方式与扩展路线。")+`<article class="book" id="book-body"><div class="loading">正在加载手册…</div></article>`};
  $("#app").innerHTML=banner+views[current]();
  if(current==="handbook")loadHandbook();
}
async function startJob(path,body,label){
  if(activeJob){toast("已有任务运行中");return;}
  const result=await api(path,body);activeJob={id:result.job_id,label};render();toast("任务已提交");
  watchJob();
}
async function watchJob(){
  if(!activeJob)return;
  try{
    const jobs=await api("/api/jobs");const job=jobs.find(j=>j.id===activeJob.id);
    if(job&&job.status!=="running"){activeJob=null;await refresh();toast(job.status==="failed"?`执行失败：${job.error}`:`任务完成${job.result?.created!==undefined?` · 新增 ${job.result.created} 条`:""}`);return;}
  }catch(e){toast("任务状态连接中断，请刷新页面恢复");activeJob=null;return;}
  setTimeout(watchJob,1100);
}
function assetDetail(id) {
  const a=state.assets.find(a=>a.id===id);if(!a)return;
  const url=/^https:\/\//.test(a.source_url)?`<a href="${esc(a.source_url)}" target="_blank" rel="noreferrer">${esc(a.source_url)} ↗</a>`:esc(a.source_url);
  showModal(modalHead(a.title)+`<div class="modal-meta">${pill("neutral",names[a.modality])}${pill(a.split)}${pill(a.is_demo?"review":"accepted",a.is_demo?"原创合成演示":"外部来源")}</div><dl class="detail-grid"><dt>来源</dt><dd>${url}</dd><dt>许可</dt><dd>${esc(a.license)}</dd><dt>存储状态</dt><dd>${esc(a.storage_status)} ${a.byte_size?`· ${num(a.byte_size)} bytes`:""}</dd><dt>内容指纹</dt><dd>${esc(a.fingerprint)}</dd><dt>来源家族</dt><dd>${esc(a.group_id)}</dd></dl><h3 class="panel-title">证据与标注</h3><pre class="code">${esc(a.text)}</pre>${a.note?`<div class="notice">${esc(a.note)}</div>`:""}<h3 class="panel-title">候选学科路径</h3>${a.classification.top3.map(c=>`<div class="source-row"><span>${esc(c.path.join(" → "))}</span><span class="count">检索分 ${c.retrieval_score}</span></div>`).join("")}<p class="hint">关键词基线，未经概率校准。人工提供的 discipline 标签优先。</p>`);
}
function taskDetail(id) {
  const t=state.tasks.find(t=>t.id===id);if(!t)return;
  const evidence=`<h3 class="panel-title">证据引用</h3><pre class="code">${esc(t.evidence?.quote||"")}</pre>`;
  showModal(modalHead(t.title)+`<div class="modal-meta">${pill(t.status)}${pill("neutral",t.type)}${pill("neutral",t.is_demo?"DEMO":"MODEL")}${pill(t.split)}</div>`
  +(t.type==="numeric_qa"?`<h3 class="panel-title">训练提示词</h3><pre class="code">${esc(t.prompt)}</pre><h3 class="panel-title">独立参考答案（不放入提示词）</h3><pre class="code">${esc(JSON.stringify(t.ground_truth,null,2))}</pre><h3 class="panel-title">候选与奖励</h3>${t.candidates.map(c=>`<div class="source-row"><code>${esc(c.text)}</code>${pill(c.reward?"accepted":"review",`R = ${c.reward}`)}</div>`).join("")}<h3 class="panel-title more-space">五层检查</h3>${t.gates.map(g=>`<div class="source-row"><span>${g.passed?"✓":"○"} ${g.name}</span><span class="hint">${esc(g.reason)}</span></div>`).join("")}`:`<pre class="code">${esc(JSON.stringify(t.artifact,null,2))}</pre><div class="notice warning">这是待审核生成产物，未进入训练导出。</div>`)+evidence);
}
function exportModal() {
  showModal(modalHead("导出训练数据")+`<p class="hint">仅导出通过五层检查的数值任务。封闭基准永不导出，原始来源信息随数据保留。</p><label for="export-split">数据划分</label><select id="export-split"><option value="train">train</option><option value="validation">validation</option></select><label><input type="checkbox" id="export-demo">包含原创演示样本（仅用于联调）</label><div id="export-links"></div><div class="notice">RL 导出提供 prompt + ground_truth + reward_spec。训练器在生成时计算奖励。DPO 仅导出同时存在正确、错误候选的任务。</div>`);
  updateExport();
}
function updateExport() {
  const split=$("#export-split").value,demo=$("#export-demo").checked;
  const counts={rl:0,sft:0,dpo:0};
  state.tasks.filter(t=>t.status==="accepted"&&t.split===split&&(demo||!t.is_demo)&&t.type==="numeric_qa").forEach(t=>{counts.rl++;counts.sft++;if(t.candidates.some(c=>c.reward===0))counts.dpo++;});
  $("#export-links").innerHTML=`<div class="export-options">${[["rl","可验证奖励任务"],["sft","监督微调样本"],["dpo","成对偏好样本"]].map(([format,label])=>`<a href="/api/export?format=${format}&split=${split}&demo=${demo}" download><strong>${format.toUpperCase()} ↓</strong><small>${label} · ${counts[format]} 条</small></a>`).join("")}</div>`;
}
function feedbackForm() {
  const tasks=state.tasks.filter(t=>t.type==="numeric_qa");
  if(!tasks.length){toast("请先运行飞轮构造数值任务");return;}
  showModal(modalHead("记录一次模型评测")+`<form id="feedback-form"><label for="feedback-task">任务</label><select id="feedback-task" style="width:100%">${tasks.map(t=>`<option value="${t.id}">${esc(t.title)} / ${t.op} / ${t.split}</option>`).join("")}</select><pre id="feedback-prompt" class="code"></pre><label for="feedback-model">模型 / 评测运行名</label><input id="feedback-model" value="manual-evaluation" required maxlength="160"><label for="prediction">模型原始输出（JSON）</label><textarea id="prediction" placeholder='{"answer": 0, "unit": "Pa"}' required></textarea><div class="form-actions"><button class="primary" type="submit">验证并记录 ↗</button></div></form>`);
  updateFeedbackPrompt();
}
function updateFeedbackPrompt() {const t=state.tasks.find(t=>t.id===$("#feedback-task").value);$("#feedback-prompt").textContent=t?.prompt||"";}
async function handleAction(button) {
  const action=button.dataset.action,id=button.dataset.id;
  if(action==="close")return $("#modal").close();
  if(action==="seed"){button.disabled=true;const r=await api("/api/demo",{});await refresh();toast(`已载入 ${r.created} 条原创演示标注`);return;}
  if(action==="run")return startJob("/api/run",{limit:24,provider:"demo"},"数值 QA 构造");
  if(action==="asset")return assetDetail(id);
  if(action==="task")return taskDetail(id);
  if(action==="export")return exportModal();
  if(action==="feedback-form")return feedbackForm();
  if(action==="task-filter"){taskFilter=id;render();return;}
  if(action==="discover")return showModal(modalHead("接入开放科学来源")+`<form id="discover-form"><p class="hint">从官方 API 检索并保存元数据。单条全文、图像及附件的许可需另行核对。</p><label for="connector">数据来源</label><select id="connector"><option value="arxiv">arXiv</option><option value="crossref">Crossref</option></select><label for="query">检索主题</label><input id="query" value="scientific machine learning" required maxlength="240" style="width:100%"><label for="discover-limit">记录上限</label><input id="discover-limit" type="number" min="1" max="20" value="5"><div class="form-actions"><button class="primary">检索并保存 ↗</button></div></form>`);
  if(action==="import")return showModal(modalHead("导入资产清单")+`<form id="import-form"><p class="hint">粘贴 JSON 数组。网页只导入元数据；保存原文件请使用 CLI 的 import --download 或 local_file。</p><textarea id="manifest" rows="12" required placeholder='[{"title":"资产标题","source_id":"doi-or-id","source_url":"https://…","modality":"cad","license":"CC-BY-4.0","text":"来源证据"}]'></textarea><div class="form-actions"><button class="primary">导入清单 ＋</button></div></form>`);
  if(action==="synthesize"){
    const provider=$("#provider").value,kind=$("#kind").value;
    if(kind==="numeric")return startJob("/api/run",{provider,limit:Number($("#batch").value)},"数值 QA 构造");
    return startJob("/api/synthesize",{provider,kind,asset_id:$("#synth-asset").value},"科研产物构造");
  }
}
document.addEventListener("click",async e=>{const b=e.target.closest("[data-action]");if(!b)return;try{await handleAction(b);}catch(error){b.disabled=false;toast(error.message);}});
document.addEventListener("input",e=>{if(e.target.id==="asset-search"){filters.query=e.target.value;$("#asset-results").innerHTML=assetCards();}});
document.addEventListener("change",e=>{
  if(e.target.id==="modality-filter"){filters.modality=e.target.value;$("#asset-results").innerHTML=assetCards();}
  if(e.target.id==="split-filter"){filters.split=e.target.value;$("#asset-results").innerHTML=assetCards();}
  if(["export-split","export-demo"].includes(e.target.id))updateExport();
  if(e.target.id==="feedback-task")updateFeedbackPrompt();
});
document.addEventListener("submit",async e=>{
  e.preventDefault();const form=e.target;
  const button=form.querySelector('button[type="submit"],button.primary');if(button)button.disabled=true;
  try{
    if(form.id==="discover-form"){const body={connector:$("#connector").value,query:$("#query").value,limit:Number($("#discover-limit").value)};await startJob("/api/discover",body,"开放来源检索");$("#modal").close();}
    if(form.id==="import-form"){const result=await api("/api/import",{assets:JSON.parse($("#manifest").value)});$("#modal").close();await refresh();toast(`新增 ${result.created} 条 · 重复 ${result.duplicates} 条 · 错误 ${result.errors.length} 条`);if(result.errors.length)showModal(modalHead("导入结果")+`<pre class="code">${esc(JSON.stringify(result,null,2))}</pre>`);}
    if(form.id==="feedback-form"){const prediction=$("#prediction").value;JSON.parse(prediction);const r=await api("/api/feedback",{task_id:$("#feedback-task").value,model:$("#feedback-model").value,prediction});$("#modal").close();await refresh();toast(`评测已记录 · 奖励 ${r.reward.toFixed(1)} · 优先级已更新`);}
  }catch(error){toast(error.message);if(button)button.disabled=false;}
});
window.addEventListener("hashchange",()=>{render();window.scrollTo(0,0);});
async function boot(){try{token=(await api("/api/session")).token;await refresh();const jobs=await api("/api/jobs");const pending=jobs.find(j=>j.status==="running");if(pending){activeJob={id:pending.id,label:pending.action};render();watchJob();}}catch(error){$("#app").innerHTML=`<div class="empty"><h3>尚未连接本地引擎</h3><p>请在项目目录运行 <code>python3 -m helix serve</code>，再访问 http://127.0.0.1:8765。</p><p>${esc(error.message)}</p></div>`;}}
boot();
