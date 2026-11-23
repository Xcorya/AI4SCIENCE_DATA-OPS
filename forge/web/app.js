"use strict";
const $ = (s) => document.querySelector(s);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = (v, currency="CNY") => new Intl.NumberFormat("zh-CN",{style:"currency",currency,maximumFractionDigits:2}).format(v/100);
const pretty = (v) => JSON.stringify(v,null,2);
const stateLabel = {draft:"采购草案",ordered:"待交付",delivered:"待验收",accepted:"验收通过",review:"待复核",rejected:"已拒收"};
const badge = (v) => `<span class="tag ${v==="accepted"?"good":v==="rejected"?"bad":"warn"}">${esc(stateLabel[v]||v)}</span>`;
let state, selected, view="workbench", editorAction, busy=false, generation=0, fileReadGeneration=0;
async function api(path,data,raw=false) {
  const response = await fetch(path, data===undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:raw?data:JSON.stringify(data)});
  const value = await response.json();
  if(!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}
let toastTimer;
function toast(message) {$("#toast").textContent=message;$("#toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("#toast").hidden=true,4500);}
function download(value,name,raw=false) {const u=URL.createObjectURL(new Blob([raw?value:pretty(value)],{type:"application/json"}));const a=document.createElement("a");a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function rawInput() {const raw=$("#json-input").value;const value=JSON.parse(raw);if(!value||Array.isArray(value)||typeof value!=="object")throw new Error("JSON 必须是对象");return raw;}
async function exportArtifact(kind,id) {const response=await fetch(`/api/export/${kind}/${encodeURIComponent(id)}`);if(!response.ok)throw new Error((await response.json()).error);download(await response.text(),id+".json",true);}
function metric(label,value,foot,unit="") {return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${esc(value)}<small>${unit}</small></div><div class="metric-foot">${foot}</div></div>`;}
async function refresh() {
  state=await api("/api/state"); if(!state.demands.some(d=>d.id===selected)) selected=state.demands[0]?.id;
  $("#mode").textContent=state.demo ? "SYNTHETIC / 合成演示数据" : "LOCAL / 私有签名模式";
  await render();
}
async function render() {
  const token=++generation;
  document.querySelectorAll(".nav").forEach(n=>n.classList.toggle("active",n.dataset.view===view));
  const ranking=selected?await api("/api/rank/"+encodeURIComponent(selected)):[];
  if(token!==generation)return;
  const eligible=ranking.filter(r=>r.eligible);
  $("#metrics").innerHTML=metric("已定义需求",state.demands.length,"规格已固定，可追踪每次交付","份")+metric("当前可采购报价",eligible.length,"预算 / 交期 / 权限全部满足","家")+metric("采购订单",state.orders.length,"从草案到验收的完整记录","笔")+metric("已通过验收",state.orders.filter(o=>o.state==="accepted").length,"来自 AEGIS 的签名验收报告","批");
  if(view==="orders")return renderOrders();
  if(view==="audit")return renderAudit();
  const demand=state.demands.find(d=>d.id===selected), spec=demand?.spec;
  $("#content").innerHTML=`<div class="section-head"><h2>采购工作台<small>DEMAND / SUPPLIER FIT</small></h2><button class="primary small" data-act="new-demand">＋ 新建需求</button></div>
  <div class="workspace-grid"><div class="panel demand-list"><div class="panel-pad"><p class="panel-label">需求池 / ${state.demands.length}</p></div>${state.demands.map(d=>`<button class="demand ${d.id===selected?"active":""}" data-act="select" data-id="${esc(d.id)}"><small class="mono">${esc(d.id)}</small><strong>${esc(d.spec.title)}</strong><small>${d.spec.quantity} 条 · ${money(d.spec.budget_cents,d.spec.currency)}</small><span class="tag">${esc(d.spec.purpose)}</span></button>`).join("")||'<div class="empty">建立第一份数据需求。</div>'}</div>
  <div class="panel">${spec?`<div class="panel-pad"><div class="section-head"><div><p class="panel-label">LOCKED SPECIFICATION</p><h3 class="spec-title">${esc(spec.title)}</h3><div class="mono muted">SHA256 / ${esc(demand.spec_hash.slice(0,24))}…</div></div><button class="small" data-act="new-quote">＋ 录入报价</button></div><div class="spec-details"><span class="tag">${spec.quantity} 条记录</span><span class="tag">≤ ${money(spec.budget_cents,spec.currency)}</span><span class="tag">≤ ${spec.max_days} 天</span><span class="tag">${esc(spec.region)} / ${esc(spec.purpose)}</span><span class="tag">缺陷率 ≤ ${(spec.max_defect_rate*100).toFixed(1)}%</span></div></div>
  <div class="table-wrap"><table><thead><tr><th>供应商 / 授权声明</th><th>含费用总价</th><th>交付 / 声明质量</th><th>采购判断</th><th></th></tr></thead><tbody>${ranking.map(q=>`<tr class="${q.eligible?"":"quote-ineligible"}"><td><strong>${esc(q.vendor)}</strong><small>${q.rights_verified?"已记录权限核验":"权限证据待核验"} ${q.pareto?" · PARETO":""}</small></td><td><strong>${money(q.total_cents,q.currency)}</strong><small>${q.cost_per_expected_usable===null?"不可估算":money(q.cost_per_expected_usable,q.currency)} / 预计可用条</small></td><td><strong>${q.lead_days} 天</strong><small>${(q.declared_quality*100).toFixed(1)}% · 供应商声明</small></td><td><span class="tag ${q.eligible?"good":"bad"}">${q.eligible?"可采购":"已拦截"}</span>${q.reasons.map(r=>`<small>${esc(r)}</small>`).join("")}</td><td>${q.eligible?`<button class="small" data-act="draft" data-id="${esc(q.id)}">生成草案 ↗</button>`:"—"}</td></tr>`).join("")||'<tr><td colspan="5">暂无报价，录入后自动比较。</td></tr>'}</tbody></table></div><p class="note">排序依据：总成本 ÷ 预计可用条数。质量为供应商声明，实际交付由 AEGIS 检查。PARETO 表示成本、交期、声明质量三项中未被其他合格报价同时优于。</p>`:'<div class="empty">先定义数量、预算、交期和使用权限。</div>'}</div></div>`;
}
function renderOrders() {
  $("#content").innerHTML=`<div class="section-head"><h2>订单与交付<small>COMMIT / SHIP / ACCEPT</small></h2><button class="small" data-act="import-report">导入 AEGIS 报告 ↓</button></div><div class="card-list">${state.orders.map(o=>`<article class="panel order-card"><div><div class="mono muted">${esc(o.id)} / ${esc(o.quote.vendor)}</div><h3>${esc(o.spec.title)}</h3><p>${o.spec.quantity} 条 · ${money(o.quote.total_cents,o.spec.currency)} · ${esc(o.spec.region)} / ${esc(o.spec.purpose)}</p><div class="state-line">${["draft","ordered","delivered","accepted"].map(s=>`<span class="${s===o.state?"current":""}">${stateLabel[s]}</span>`).join("")}</div><div><div class="actions">${badge(o.state)}${o.state==="draft"?`<button class="primary small" data-act="release" data-id="${esc(o.id)}">确认本地采购单</button>`:""}${["ordered","review","rejected"].includes(o.state)?`<button class="primary small" data-act="deliver" data-id="${esc(o.id)}">登记${o.delivery_id?"新批次":"交付"}</button>`:""}${o.delivery_id?`<button class="small" data-act="export-delivery" data-id="${esc(o.delivery_id)}">导出交付包 ↗</button>`:""}</div>${o.report_id?`<p class="status-caption mono">AEGIS / ${esc(o.report_id)}</p>`:""}</div></article>`).join("")||'<div class="panel empty">从合格报价生成第一笔采购草案。</div>'}</div>`;
}
function renderAudit() {
  $("#content").innerHTML=`<div class="section-head"><h2>操作留痕<small>LOCAL EVENT JOURNAL</small></h2><button class="small" data-act="export-audit">导出事件</button></div><div class="panel table-wrap"><table><thead><tr><th>序号 / 时间</th><th>动作</th><th>对象</th><th>依据</th></tr></thead><tbody>${state.events.map(e=>`<tr><td>${e.seq}<small>${esc(e.at.slice(0,19))} UTC</small></td><td>${esc(e.action)}</td><td class="mono">${esc(e.entity)}</td><td class="mono">${esc(e.detail)}</td></tr>`).join("")}</tbody></table><p class="note">展示最近 40 条。完整历史保存在本地 SQLite。此日志用于追踪操作，不提供防数据库管理员篡改保证。</p></div>`;
}
function editor(title,fields,action,submit="保存") {fileReadGeneration++;editorAction=action;$("#editor-title").textContent=title;$("#editor-fields").innerHTML=fields;$("#editor-error").textContent="";$("#editor-submit").textContent=submit;$("#editor").showModal();}
const jsonField=(label,value)=>`<label>${label}<textarea id="json-input" spellcheck="false" required>${esc(pretty(value))}</textarea></label>`;
const field=(name,label,value,type="text")=>`<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" required></label>`;
document.addEventListener("click",async(event)=>{
  const nav=event.target.closest("[data-view]");
  if(nav){view=nav.dataset.view;return render().catch(e=>toast(e.message));}
  const button=event.target.closest("[data-act]");if(!button||busy)return;
  const {act,id}=button.dataset;
  try {
    if(act==="select"){selected=id;return await render();}
    if(act==="new-demand") {
      const spec=state.demands.find(d=>d.id===selected)?.spec||{title:"新数据需求",quantity:100,budget_cents:100000,currency:"CNY",max_days:14,purpose:"model_training",region:"CN",max_defect_rate:.05,allow_derivatives:true,allow_pii:false,schema:{id:"string",text:"string"},unique_key:"id"};
      return editor("定义数据需求",jsonField("需求规格 · 金额使用最小货币单位，例如 100 分 = ¥1",spec),async()=>api("/api/demands",rawInput(),true));
    }
    if(act==="new-quote"){const demandId=selected;return editor("录入供应商报价",jsonField("报价与权限范围",{vendor:"New supplier",unit_cents:3000,fee_cents:0,capacity:100,lead_days:10,currency:state.demands.find(d=>d.id===demandId).spec.currency,declared_quality:.95,evidence:"填写实际合同或核验记录编号",purposes:["model_training"],regions:["CN"],derivatives:true,rights_verified:false}),async()=>api("/api/quotes",`{"demand_id":${JSON.stringify(demandId)},"quote":${rawInput()}}`,true));}
    if(act==="draft"){busy=true;await api("/api/orders",{demand_id:selected,quote_id:id});view="orders";toast("采购草案已生成");await refresh();}
    if(act==="release"){busy=true;await api("/api/orders/release",{order_id:id});toast("本地采购单已确认，等待交付");await refresh();}
    if(act==="deliver")return editor("登记数据交付",`<p class="muted">上传完整记录与许可声明，交付后规格和内容将绑定签名。</p><label>载入交付 JSON 文件<input type="file" id="input-file" accept=".json,application/json"></label>${jsonField(state.demo?"合成示例 · 请替换为实际交付":"交付内容 · 请填写 manifest 和 records",state.demo?state.demo_input:{manifest:{coverage:"full",record_count:1,source:"",license:"",evidence:"",rights_verified:false,purposes:[],regions:[],derivatives:false,valid_until:"",prohibited_source:false},records:[{id:"record-1",text:""}]})}`,async()=>api("/api/deliveries",`{"order_id":${JSON.stringify(id)},"delivery":${rawInput()}}`,true),"登记并签名");
    if(act==="export-delivery"){await exportArtifact("deliveries",id);toast("交付包已导出，可在 AEGIS 导入");}
    if(act==="import-report")return editor("导入 AEGIS 验收报告",`<label>载入签名报告文件<input type="file" id="input-file" accept=".json,application/json"></label>${jsonField("AEGIS 签名报告",{})}`,async()=>api("/api/reports/import",`{"report":${rawInput()}}`,true),"校验并应用");
    if(act==="export-audit")download(state.events,"forge-recent-events.json");
  } catch(e){toast(e.message);}finally{busy=false;}
});
$("#close-editor").addEventListener("click",()=>$("#editor").close());
$("#editor").addEventListener("close",()=>fileReadGeneration++);
$("#editor-fields").addEventListener("input",event=>{if(event.target.id==="json-input")fileReadGeneration++;});
$("#editor-fields").addEventListener("change",async(event)=>{if(event.target.id!=="input-file")return;const token=++fileReadGeneration;try{const file=event.target.files[0];if(file){if(file.size>8*1024*1024)throw new Error("文件超过 8 MiB");const raw=await file.text();JSON.parse(raw);if(token===fileReadGeneration&&$("#editor").open){$("#json-input").value=raw;$("#editor-error").textContent="";}}}catch(e){if(token===fileReadGeneration)$("#editor-error").textContent=e.message;}});
$("#editor-form").addEventListener("submit",async(event)=>{event.preventDefault();if(busy)return;busy=true;$("#editor-submit").disabled=true;try{await editorAction();$("#editor-error").textContent="";$("#editor").close();toast("已保存，记录已更新");await refresh();}catch(e){$("#editor-error").textContent=e.message;}finally{busy=false;$("#editor-submit").disabled=false;}});
refresh().catch(e=>{$("#content").innerHTML=`<div class="error-panel">服务暂不可用：${esc(e.message)}。请检查本地运行终端并刷新页面。</div>`;});
