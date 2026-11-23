const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'docs/site/index.html'), 'utf8');
const nodes = new Map();
const groups = {mode:[],panel:[],axis:[]};
let focused = null, downloads = [], urls = new Map(), revoked = [], timers = [];
class Element {
  constructor(attrs={}) { Object.assign(this, {value:'',textContent:'',innerHTML:'',hidden:false,dataset:{},listeners:{},attrs:{},children:[],tabIndex:0}); for(const [k,v] of Object.entries(attrs))this.setAttribute(k,v); }
  setAttribute(k,v){this.attrs[k]=v;if(k==='id')this.id=v;if(k==='value')this.value=v;if(k.startsWith('data-'))this.dataset[k.slice(5)]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  fire(k,event={}){return this.listeners[k]?.(event);}
  focus(){focused=this;}
  querySelectorAll(selector){ if(selector==='button'){return [...this.innerHTML.matchAll(/<button\b([^>]*)>/g)].map(m=>new Element(attrs(m[1])));} return [];}
  querySelector(selector){const id=/data-sample="([^"]+)"/.exec(selector)?.[1];return this.querySelectorAll('button').find(e=>e.dataset.sample===id);}
  appendChild(el){this.children.push(el);}
  click(){if(this.download)downloads.push({name:this.download,url:this.href,attached:body.children.includes(this)});return this.fire('click');}
  remove(){const i=body.children.indexOf(this);if(i>=0)body.children.splice(i,1);}
}
function attrs(str){return Object.fromEntries([...str.matchAll(/([\w-]+)="([^"]*)"/g)].map(m=>[m[1],m[2]]));}
for(const match of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*)>/g)){
 const at=attrs(match[2]);let el=new Element(at);if(at.id)nodes.set('#'+at.id,el);for(const group of Object.keys(groups))if(at['data-'+group])groups[group].push(el);
}
const body = new Element();
const doc={body,querySelector:s=>nodes.get(s),querySelectorAll:s=>groups[/\[data-(\w+)\]/.exec(s)?.[1]]||[],createElement:()=>new Element()};
const context = vm.createContext({document:doc,Blob,URL:{createObjectURL(blob){const id='blob:check-'+urls.size;urls.set(id,blob);return id;},revokeObjectURL(url){revoked.push(url);}},setTimeout:(f,t)=>timers.push([f,t]),console});
vm.runInContext(fs.readFileSync(path.join(root,'docs/site/app.js'),'utf8'),context);
const get=expr=>JSON.parse(vm.runInContext('JSON.stringify('+expr+')',context));
let checks=0;
function check(name,fn){fn();checks++;console.log('PASS '+name);}
check('all fixture IDs remain synthetic; no training release',()=>{assert.ok(get('fixtures.every(f=>f.id.startsWith("SYN-"))'));assert.ok(get('fixtures.map(assess)').every(x=>x.release_allowed===false));});
check('default fixture paths',()=>assert.deepEqual(get('fixtures.map(f=>assess(f).status)'),['provisional','review','quarantine','provisional','review']));
check('whole-video coverage blocks each label, not only record',()=>assert.ok(get('assess(fixtures[4]).labels').every(x=>x.state==='review')));
check('overlapping inspected spans use union',()=>{assert.equal(get('intervalCoverage([[0,65],[0,65]],120)'),65/120);assert.equal(get('intervalCoverage([[0,4],[2,6],[6,10]],10)'),1);});
check('invalid inspected intervals fail closed',()=>{for(const expr of ['intervalCoverage([[0,121]],120)','intervalCoverage([[-1,2]],120)','intervalCoverage([[2,2]],120)','intervalCoverage([[0,1]],0)'])assert.equal(get(expr),null);});
check('duplicated half-video cannot qualify full-video claim',()=>{assert.equal(get('assess({...fixtures[4],temporal:{...fixtures[4].temporal,inspected:[[0,65],[0,65]]}}).status'),'review');});
check('unordered event blocks each candidate',()=>assert.ok(get('assess({...fixtures[3],temporal:{...fixtures[3].temporal,ordered:false}}).labels').every(x=>x.state==='review')));
check('raising quality forces review',()=>{nodes.get('#quality-threshold').value='.99';nodes.get('#quality-threshold').fire('input');assert.equal(nodes.get('#decision-status').textContent,'进入人工复核');nodes.get('#quality-threshold').value='.86';nodes.get('#quality-threshold').fire('input');});
check('correlated evidence cannot acquire extra family',()=>assert.equal(get('assess(fixtures[1]).labels[0].supporting_family_count'),1));
check('candidate preview requires its target label',()=>{vm.runInContext('current=fixtures[0]',context);const decision=get('assess(current)');decision.labels.find(x=>x.label_id==='appearance.plot.line').state='review';context.injectedDecision=decision;assert.equal(get('taskFor(injectedDecision).target'),null);});
check('mode button switches sample and media state',()=>{const video=groups.mode.find(e=>e.dataset.mode==='video');video.click();assert.match(nodes.get('#sample-id').textContent,/VIDEO/);assert.equal(video.attrs['aria-pressed'],'true');});
check('keyboard tab navigation selects requested panel',()=>{const tab=groups.panel[0];tab.fire('keydown',{key:'End',preventDefault(){}});assert.equal(nodes.get('#panel-task').hidden,false);assert.equal(groups.panel.find(e=>e.dataset.panel==='task').attrs['aria-selected'],'true');});
check('taxonomy filtering and empty state',()=>{nodes.get('#taxonomy-search').value='TEM';nodes.get('#taxonomy-search').fire('input');assert.match(nodes.get('#taxonomy-summary').textContent,/3 \/ 19/);nodes.get('#taxonomy-search').value='NO_SUCH_LABEL_123';nodes.get('#taxonomy-search').fire('input');assert.match(nodes.get('#taxonomy-rows').innerHTML,/没有匹配标签/);});
(async()=>{
 nodes.get('#download-sample').click();
 check('download anchor attached before click and removed afterward',()=>{assert.equal(downloads.length,1);assert.equal(downloads[0].attached,true);assert.equal(body.children.length,0);});
 const downloaded=JSON.parse(await urls.get(downloads[0].url).text());
 check('download JSON represents active fixture and blocked training',()=>{assert.equal(downloaded.fixture.id,'SYN-VID-001');assert.equal(downloaded.demo_only,true);assert.equal(downloaded.training_task.export_to_training,false);assert.equal(downloaded.decision.release_allowed,false);});
 check('download status describes correct format and safe cleanup',()=>{assert.match(nodes.get('#download-status').textContent,/不能直接作为后端观测输入/);assert.equal(timers.at(-1)[1],30000);timers.at(-1)[0]();assert.deepEqual(revoked,[downloads[0].url]);});
 console.log(JSON.stringify({passed:checks,browser_integration:false,note:'DOM harness checks JS logic and event wiring. Browser checks are recorded separately in VALIDATION.md.'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
