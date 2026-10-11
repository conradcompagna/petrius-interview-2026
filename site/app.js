"use strict";

const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const colors = {text:"#218450", summarium:"#a038a0", inscriptio:"#ca8007", other:"#657588", main_text:"#218450", gloss:"#3d82bd", marginalia:"#795ac0", header:"#b56d42", footer:"#b56d42", initial:"#d14a50", mixed:"#168e94", uncertain:"#949080", unknown:"#929a90", reject:"#b55243", non_main:"#b55243"};
const color = label => colors[label] || "#7d8790";
Object.assign(colors, {source_text:"#218450", heading:"#b56d42", noise:"#b55243", ungrouped:"#e02035", outside:"#8a8f95", text_region:"#168e94", text_line:"#397caf", unassigned:"#cf4553", main_text_block:"#218450", joined_heading:"#ca8007", not_selected:"#8a8f95", cross_region:"#397caf", low_lexicon:"#397caf", ocr_row:"#397caf", mdz_paragraph:"#168e94", annotated_region:"#168e94"});
const nice = str => str === "ocr" ? "OCR text" : String(str || "").replaceAll("_", " ");
const text = (tag, value, cls) => { const n = document.createElement(tag); n.textContent = value; if (cls) n.className = cls; return n; };
const svgNode = (tag, attrs = {}) => { const n = document.createElementNS(NS, tag); for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v); return n; };
const staticSite = document.documentElement.dataset.static === "true";
function apiURL(route, collection, key) {
  if(!staticSite)return `${route}?${new URLSearchParams({dataset:collection,key})}`;
  const page=dataset(collection)?.pages.find(p=>p.key===key);
  if(!page)throw new Error("This page is not in the published collection");
  return route==="/image"?page.image_url:route==="/text"?page.text_url:page.annotation;
}
async function readJSON(url) {
  const response=await fetch(url,{cache:"no-cache"});
  if(!response.ok)throw new Error(`Could not load ${url} (${response.status})`);
  if(!url.endsWith(".gz"))return response.json();
  const bytes=new Uint8Array(await response.arrayBuffer());
  const body=bytes[0]===31&&bytes[1]===139?await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text():new TextDecoder().decode(bytes);
  return JSON.parse(body);
}
const state = {index:null, mode:"finished", dataset:"finished-interview", key:"", ref:"auto", pageView:"single", role:null, overlays:true, active:"a", selected:null, serial:0, filtered:[]};
const panes = {};
let toastTimer;
function toast(message) { $("toast").textContent = message; $("toast").style.display = "block"; clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").style.display = "none", 2600); }
function dataset(id = state.dataset) { return state.index.datasets.find(d => d.id === id); }
function displayNote(value) {
  if(typeof value!=="string")return "";
  return value.split(/(?<=[.!?])\s+|\s*·\s*/).filter(s=>!/(?:AI.reviewed|\bsilver\b|human.gold|independent human|LLM annotations|model.drafted|not calibrated|not measured accuracy)/i.test(s)).join(" · ");
}
function collectionNote() {}
function allowedDatasets() { return state.index.datasets.filter(d => d.pages.length); }
function outputName(d) { return d.name; }
function visibleObject(o) { return state.overlays && $("layer-" + o.kind)?.checked && (!state.role || o.label === state.role); }
function saveURL() { history.replaceState(null, "", "#" + new URLSearchParams({mode:state.mode, dataset:state.dataset, page:state.key, reference:state.ref, view:state.pageView})); }
function isComparison() { return false; }
function isSplitView() { return isComparison() && state.pageView === "split"; }
function updatePageView() {
  const comparison=isComparison(),split=isSplitView();
  document.body.classList.toggle("compare",split);
  document.body.classList.toggle("segmentation-view",state.mode==="segmentation");
  state.active="a";
}
function setPageView(value) {
  state.pageView=value==="single"?"single":"split";
  try { localStorage.setItem("annotation-page-view",state.pageView); } catch(e) { /* URL still preserves the choice. */ }
  updatePageView();state.role=null;clearSelection();activate(state.active);
  const p=panes[state.active];if(isSplitView()&&p.box)p.setBox(p.box);
  saveURL();
}

class PagePane {
  constructor(id) { this.id=id; this.host=$("view-"+id); this.page=null; this.svg=null; this.box=null; }
  empty(title, explanation) {
    if(this.jsonURL){URL.revokeObjectURL(this.jsonURL);this.jsonURL=null;}
    this.page=null; this.svg=null; this.box=null; this.host.replaceChildren(); this.host.classList.remove("loading");
    const el=text("div", "", "empty"); el.append(text("strong",title),text("small",explanation)); this.host.append(el);
    $("status-"+this.id).textContent="";
  }
  show(page) {
    this.page=page; this.host.replaceChildren(); this.host.classList.add("loading");
    $("name-"+this.id).textContent=dataset(page.dataset)?.name||page.dataset_name;
    const counts = {};
    for (const o of page.objects) if (o.kind !== "draft") counts[o.kind]=(counts[o.kind]||0)+1;
    $("status-"+this.id).textContent=page.pending?"Processing pending — source scan available":Object.entries(counts).map(([k,n])=>`${n} ${k}${n===1?"":"s"}`).join(" · ") || (["ocr","segmentation"].includes(page.kind)?"No text detections":"No saved annotations");
    $("status-"+this.id).title="";
    this.svg=svgNode("svg", {role:"img", "aria-label":`${page.dataset_name}, ${page.book}, scan ${page.scan}`, preserveAspectRatio:"xMidYMid meet"});
    const img=svgNode("image", {href:apiURL("/image",page.dataset,page.key),width:page.image.width,height:page.image.height});
    img.addEventListener("load",()=>this.host.classList.remove("loading"));
    img.addEventListener("error",()=> {this.host.classList.remove("loading"); toast("The source scan could not be loaded.");});
    this.svg.append(img); this.layers=svgNode("g"); this.svg.append(this.layers); this.host.append(this.svg);
    this.fit(false); this.draw(); updateMistakes();
    this.svg.addEventListener("wheel", e=>{e.preventDefault(); activate(this.id); this.zoom(Math.exp(-Math.max(-160,Math.min(160,e.deltaY))*.0035),this.point(e));}, {passive:false});
    this.svg.addEventListener("pointerdown",e=>{
      if(e.button!==0)return;
      activate(this.id); const target=e.target.closest("[data-object]");
      this.drag={x:e.clientX,y:e.clientY,point:this.point(e),box:[...this.box],target:target?.getAttribute("data-object"),moved:false};
      this.svg.setPointerCapture(e.pointerId);
    });
    this.svg.addEventListener("pointermove",e=>{
      if(!this.drag)return;
      const d=this.drag;
      if(Math.hypot(e.clientX-d.x,e.clientY-d.y)>4)d.moved=true;
      if(!d.moved)return;
      const p=this.point(e); this.setBox([this.box[0]+d.point.x-p.x,this.box[1]+d.point.y-p.y,d.box[2],d.box[3]]);
    });
    this.svg.addEventListener("pointerup",()=>{
      const d=this.drag; this.drag=null; if(d&&!d.moved&&d.target)select(this.id,d.target,false);
    });
    this.svg.addEventListener("pointercancel",()=>this.drag=null);
    this.svg.addEventListener("dblclick",e=>{e.preventDefault();this.zoom(1.8,this.point(e));});
  }
  point(event) { const p=this.svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(this.svg.getScreenCTM().inverse()); }
  fit(sync=true) { if(this.page)this.setBox([0,0,this.page.image.width,this.page.image.height],sync); }
  setBox(box,sync=true) {
    if(!this.svg)return; this.box=box;this.svg.setAttribute("viewBox",box.join(" "));
    if(this.id===state.active)$("zoom-value").textContent=Math.round(this.page.image.width/box[2]*100)+"%";
    if(sync&&isSplitView()&&$("sync").checked){
      const other=panes[this.id==="a"?"b":"a"];
      if(other.page){const sx=other.page.image.width/this.page.image.width,sy=other.page.image.height/this.page.image.height;other.setBox([box[0]*sx,box[1]*sy,box[2]*sx,box[3]*sy],false);}
    }
  }
  zoom(factor,point=null) {
    if(!this.box)return;
    const [x,y,w,h]=this.box, current=this.page.image.width/w;
    factor=Math.max(.5,Math.min(30,current*factor))/current;
    const p=point||{x:x+w/2,y:y+h/2};
    this.setBox([p.x-(p.x-x)/factor,p.y-(p.y-y)/factor,w/factor,h/factor]);
  }
  focus(o) {
    if(!this.page)return;
    const [x,y,x2,y2]=o.bbox, bw=Math.max(x2-x,80), bh=Math.max(y2-y,30);
    const aspect=this.host.clientWidth/Math.max(1,this.host.clientHeight);
    const w=Math.max(bw*1.45,bh*3*aspect,Math.min(this.page.image.width*.22,450));
    const h=w/aspect;this.setBox([(x+x2-w)/2,(y+y2-h)/2,w,h]);
  }
  draw() {
    if(!this.layers)return;
    this.layers.replaceChildren();
    if(!this.page)return;
    const opacity=Number($("opacity").value)/100;
    // Keep spans and initials above rows. Within each layer, draw excluded
    // detections first: overlapping outside duplicates must not intercept clicks
    // on the retained, labelled annotation visible underneath them.
    const rank={region:0,paragraph:1,draft:1,row:2,span:3,object:4};
    const excluded=o=>o.label==="outside"||o.label==="not_selected";
    for(const o of [...this.page.objects].sort((a,b)=>rank[a.kind]-rank[b.kind]||Number(excluded(b))-Number(excluded(a)))) {
      if(!visibleObject(o))continue;
      const baselineOnly=o.geometry_type==="baseline";
      const rings=baselineOnly ? [o.baseline] : o.components?.length ? o.components.flatMap(c=>[c.polygon,...(c.holes||[])]) : [o.polygon,...(o.holes||[])];
      const d=rings.filter(r=>r?.length).map(r=>"M"+r.map(p=>p.join(",")).join("L")+(baselineOnly?"":"Z")).join(" ");
      const path=svgNode("path",{d,fill:baselineOnly?"none":color(o.label),"fill-opacity":o.draft ? .035 : opacity,stroke:color(o.label),"stroke-opacity":o.draft ? .45 : 1,"stroke-width":baselineOnly?1.7:o.kind==="region"?1.7:1.15,"fill-rule":"evenodd","data-object":o.id,class:"geometry"});
      if(baselineOnly){path.setAttribute("vector-effect","non-scaling-stroke");path.setAttribute("pointer-events","stroke");}
      if(o.draft)path.setAttribute("stroke-dasharray","4 3");
      if(state.selected?.pane===this.id&&(state.selected.id===o.id||state.selected.id==="region:"+o.parent))path.classList.add("selected");
      if(o.text){const title=svgNode("title");title.textContent=o.text;path.append(title);}this.layers.append(path);
      if(o.mistake&&state.mistakes!==false){this.layers.append(svgNode("path",{d,fill:"#e01b24","fill-opacity":.28,stroke:"#e01b24","stroke-width":3,"vector-effect":"non-scaling-stroke","fill-rule":"evenodd","pointer-events":"none",class:"mistake"}));}
      if(!baselineOnly&&false&&o.baseline?.length)this.layers.append(svgNode("polyline",{points:o.baseline.map(p=>p.join(",")).join(" "),fill:"none",stroke:color(o.label),"stroke-width":1.2,"vector-effect":"non-scaling-stroke","pointer-events":"none"}));
      if(false&&o.reading_order!==null&&o.reading_order!==undefined){
        const order=svgNode("text",{x:o.bbox[0],y:o.bbox[1]-4,fill:color(o.label),"font-size":19,"font-weight":700,stroke:"white","stroke-width":3,"paint-order":"stroke","pointer-events":"none"});order.textContent=o.reading_order;this.layers.append(order);
      }
    }
  }
}

function activate(id) {
  if(!panes[id].page)return;
  state.active=id;
  for(const [key,p] of Object.entries(panes))$("pane-"+key).classList.toggle("active-pane",key===id);
  $("zoom-value").textContent=panes[id].box?Math.round(panes[id].page.image.width/panes[id].box[2]*100)+"%":"100%";
  renderObjectList();
}
function renderLegend() {
  const labels=new Map();
  for(const p of Object.values(panes))if(p.page&&!$("pane-"+p.id).hidden)for(const o of p.page.objects)if($("layer-"+o.kind)?.checked)labels.set(o.label,(labels.get(o.label)||0)+1);
  $("legend").replaceChildren();
  if(state.role&&!labels.has(state.role))state.role=null;
  for(const [label,count] of [...labels].sort((a,b)=> (Object.keys(colors).indexOf(a[0])+1||99)-(Object.keys(colors).indexOf(b[0])+1||99))){
    const b=text("button","",state.role===label?"active":"");b.style.setProperty("--role",color(label));b.append(document.createElement("i"),text("span",`${nice(label)} ${count}`));b.title=`Show only ${nice(label)}; click again to show all`;
    b.setAttribute("aria-pressed",state.role===label?"true":"false");b.onclick=()=>{state.role=state.role===label?null:label;redraw();};$("legend").append(b);
  }
  if(!labels.size)$("legend").append(text("span","No annotations in the enabled layers", "legend-empty"));
}
function redraw() {renderLegend();Object.values(panes).forEach(p=>p.draw());renderObjectList();updateMistakes();}
function updateMistakes() {
  const objs=Object.values(panes).flatMap(p=>p.page?.objects||[]),flagged=objs.filter(o=>o.mistake!==null&&o.mistake!==undefined),n=flagged.filter(o=>o.mistake).length,nr=flagged.filter(o=>o.mistake&&o.kind==="region").length,b=$("mistakes");
  if(!b)return;b.hidden=!flagged.length;b.textContent=(state.mistakes===false?"Show mistakes":"Hide mistakes")+" ("+(n-nr)+" lines, "+nr+" regions)";b.style.color=n?"#e01b24":"";
}
function renderObjectList() {}
function clearSelection() {
  state.selected=null;$("selection-detail").replaceChildren();$("inspect-title").textContent="";
  document.querySelector(".inspector").classList.remove("has-selection");redraw();
}
function select(pane,id,focus) {
  const p=panes[pane],o=p.page.objects.find(item=>item.id===id);if(!o)return;
  activate(pane);state.selected={pane,id};document.querySelector(".inspector").classList.add("has-selection");
  $("inspect-title").textContent=nice(o.label);
  const detail=$("selection-detail");detail.replaceChildren();
  const field=(k,v)=>{const line=text("div","","detail-meta");line.append(text("strong",k+": "),document.createTextNode(v));detail.append(line);};
  const badge=text("span",`${nice(o.label)} · ${o.kind}`,"badge");badge.style.setProperty("--role",color(o.label));detail.append(badge);
  if(o.source_id)field("ID",o.source_id);
  if(o.subtype)field("Subtype",nice(o.subtype));
  if(o.parent)field("Parent annotation",o.parent);
  if(o.bbox)field("Position",o.bbox.map(n=>Math.round(n)).join(", "));
  const m=/^network (\S+)(?: \(([\d.]+)\))? \| reference (\S+)/.exec(o.note||"");
  if(m){field("Predicted",nice(m[1])+(m[2]?` (confidence ${m[2]})`:""));field("Reference",nice(m[3]));}
  if(o.kind==="row"&&/runs across regions/.test(o.note||""))field("Crosses regions",o.note.replace(/^.*regions /,""));
  if(o.lex_words?.length){
    const n=o.lex_words.filter(w=>w[1]===true).length,t=o.lex_words.filter(w=>w[1]!==null).length;field("Words in lexicon",`${n} of ${t}`);
    const box=text("div","","detail-text");
    o.lex_words.forEach(([w,found],i)=>{if(i)box.append(" ");const s=text("span",w);if(found===false){s.style.background="#f6c8c8";s.style.color="#9b1c1c";}else if(found===true){s.style.background="#d3eedc";}box.append(s);});
    detail.append(box);
  }else if(o.text)detail.append(text("div",o.text,"detail-text"));
  if(typeof o.ocr_confidence==="number")field("OCR score",o.ocr_confidence.toFixed(3));
  if(typeof o.classification_score==="number")field("Classifier score",o.classification_score.toFixed(3));
  if(typeof o.detection_score==="number")field("Detector score",o.detection_score.toFixed(3));
  if(o.probabilities&&Object.keys(o.probabilities).length)for(const [label,score] of Object.entries(o.probabilities))field(nice(label),typeof score==="number"?score.toFixed(3):String(score));
  if(o.input_line_refs?.length)field("Source detections",o.input_line_refs.map(r=>`${r.set}:${r.id}`).join(", "));
  if(focus)p.focus(o);Object.values(panes).forEach(p=>p.draw());renderObjectList();
}

function renderCollection() {
  const available=allowedDatasets();
  if(!available.length)throw new Error("No collections are available in this view");
  if(!available.some(d=>d.id===state.dataset))state.dataset=available[0].id;
  const group=(label,ds)=>{const g=document.createElement("optgroup");g.label=label;g.append(...ds.map(d=>new Option(`${outputName(d)} · ${d.pages.length}`,d.id)));return g;};
  const fin=available.filter(d=>d.group==="finished"),old=available.filter(d=>d.group!=="finished");
  $("dataset").replaceChildren(...available.map(d=>new Option(`${outputName(d)} · ${d.pages.length}`,d.id)));
  $("dataset").value=state.dataset;state.mode=dataset().group==="finished"?"finished":"archive";
  renderPages();
}
async function selectOutput(id) {
  if(!allowedDatasets().some(d=>d.id===id))return;
  const previous=panes[state.active],key=state.key,box=previous.box?[...previous.box]:null,image=previous.page?.image;
  state.dataset=id;renderCollection();
  await loadPage(dataset().pages.some(p=>p.key===key)?key:dataset().pages[0].key);
  const current=panes[state.active];
  if(state.dataset===id&&state.key===key&&box&&current.page?.image.width===image?.width&&current.page?.image.height===image?.height)current.setBox(box);
}
function renderPages() {
  state.filtered=dataset().pages;
  const bookCount=new Set(state.filtered.map(p=>p.book)).size;
  $("page-count").textContent=`${state.filtered.length} scans · ${bookCount} ${bookCount===1?"book":"books"}`;
  const fragment=document.createDocumentFragment();
  for(const p of state.filtered){
    const b=text("button","","page-card"+(p.key===state.key?" active":""));b.dataset.key=p.key;
    const head=text("span","","scan");head.append(text("span",`${p.display_id?p.display_id+" · ":""}Scan ${String(p.scan).padStart(5,"0")}`),text("span",["ocr","segmentation"].includes(dataset().kind)?"":p.semantic_units?`${p.semantic_units} units`:p.split,"dot-count"));
    b.append(head,text("span",p.book,"book-id"),text("span",p.title,"book-title"));b.title=p.title;b.onclick=()=>loadPage(p.key);fragment.append(b);
  }
  $("page-list").replaceChildren(fragment);
  if(!state.filtered.length)$("page-list").append(text("div","No scans match this search.","hint-box"));
  updatePosition();
}
function updatePosition() {
  const position=state.filtered.findIndex(p=>p.key===state.key);
  $("position").textContent=position>=0?`${position+1} / ${state.filtered.length}`:"—";
  $("prev").disabled=position<=0;$("next").disabled=position<0||position>=state.filtered.length-1;
  for(const card of $("page-list").children)card.classList.toggle("active",card.dataset.key===state.key);
}
function navigate(delta) { const i=state.filtered.findIndex(p=>p.key===state.key);const next=state.filtered[i+delta];if(i>=0&&next)loadPage(next.key); }
async function fetchPage(ds,key) {return readJSON(apiURL("/api/page",ds,key));}
async function loadPage(key) {
  const serial=++state.serial;state.key=key;state.role=null;state.active=isComparison()?"b":"a";state.selected=null;
  $("selection-detail").replaceChildren();document.querySelector(".inspector").classList.remove("has-selection");
  $("inspect-title").textContent="";
  const descriptor=dataset().pages.find(p=>p.key===key);if(!descriptor)return;
  $("page-title").textContent=`${descriptor.display_id?descriptor.display_id+" · ":""}Scan ${String(descriptor.scan).padStart(5,"0")}`;
  $("page-subtitle").textContent=`${descriptor.book} · ${descriptor.split}`;$("page-title").title=descriptor.title;
  updatePosition();saveURL();
  const selectedCard=Array.from($("page-list").children).find(c=>c.dataset.key===key);selectedCard?.scrollIntoView({block:"nearest"});
  const compare=isComparison();updatePageView();
  panes.a.empty("Loading scan…","");
  let reference=null;
  if(compare){
    const choices=state.index.datasets.filter(d=>(dataset().group!=="finished"||d.group==="finished")&&d.id!==state.dataset&&d.pages.some(p=>p.key===key));
    $("reference").replaceChildren(new Option("Reference: automatic","auto"),...choices.map(d=>new Option(outputName(d),d.id)));
    if(state.ref!=="auto"&&!choices.some(d=>d.id===state.ref))state.ref="auto";
    $("reference").value=state.ref;
    reference=state.ref!=="auto"?state.ref:choices.find(d=>d.id===dataset().reference_dataset)?.id||choices.find(d=>d.kind==="reference")?.id||choices[0]?.id;
    $("name-a").textContent="Reference annotations";
  }
  const mainID=compare?"b":"a";
  const jobs=[fetchPage(state.dataset,key).then(p=>{if(serial===state.serial)panes[mainID].show(p);}).catch(e=>{if(serial===state.serial)panes[mainID].empty("Page unavailable",e.message);})];
  if(compare&&reference)jobs.push(fetchPage(reference,key).then(p=>{if(serial===state.serial)panes.a.show(p);}).catch(e=>{if(serial===state.serial)panes.a.empty("Reference unavailable",e.message);}));
  else if(compare)panes.a.empty("No matching collection", "Choose a page included in both an annotation collection and a model output.");
  await Promise.all(jobs);if(serial!==state.serial)return;
  activate(panes[mainID].page?mainID:isSplitView()?"a":mainID);redraw();saveURL();
}
function setMode(mode) {
  state.mode=mode;state.ref="auto";
  if(mode==="finished")$("experiment-archive").open=false;
  if(mode==="compare")state.pageView="split";
  for(const b of document.querySelectorAll("[data-mode]"))b.classList.toggle("active",b.dataset.mode===mode);
  renderCollection();const pages=dataset().pages;loadPage(pages.some(p=>p.key===state.key)?state.key:pages[0].key);
}

async function init() {
  panes.a=new PagePane("a");
  try {
    state.index=await readJSON(staticSite?"data/index.json":"/api/index");
    if(staticSite){}
    const hash=new URLSearchParams(location.hash.slice(1));
    let savedPageView;try { savedPageView=localStorage.getItem("annotation-page-view"); } catch(e) { /* Storage is optional. */ }
    state.pageView=(hash.get("view")||savedPageView)==="split"?"split":"single";
    state.mode="finished";
    state.dataset=hash.get("dataset")||"finished-task1-min";state.ref=hash.get("reference")||"auto";
    const requested=state.index.datasets.find(d=>d.id===state.dataset);
    if(requested&&requested.group!=="finished"&&state.mode!=="compare")state.mode="archive";
    state.key=hash.get("page")||"bsb10144443/00040";
    renderCollection();
    $("dataset").onchange=()=>selectOutput($("dataset").value);
    $("prev").onclick=()=>navigate(-1);$("next").onclick=()=>navigate(1);
    for(const input of document.querySelectorAll(".layer-controls input"))input.onchange=redraw;
    $("opacity").oninput=()=>Object.values(panes).forEach(p=>p.draw());
    $("overlays").onclick=()=>{state.overlays=!state.overlays;$("overlays").textContent=state.overlays?"Hide overlays":"Show overlays";redraw();};
    $("mistakes").onclick=()=>{state.mistakes=state.mistakes===false;redraw();};
    $("fit").onclick=()=>panes[state.active].fit();$("zoom-in").onclick=()=>panes[state.active].zoom(1.4);$("zoom-out").onclick=()=>panes[state.active].zoom(1/1.4);
    $("expand").onclick=()=>{const expanded=document.body.classList.toggle("focus-view");$("expand").textContent=expanded?"Restore panels":"Expand";};
    document.addEventListener("keydown",e=>{
      if(["INPUT","SELECT","TEXTAREA"].includes(e.target.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;
      if(e.key==="ArrowLeft"){e.preventDefault();navigate(-1);}if(e.key==="ArrowRight"){e.preventDefault();navigate(1);}
      if(e.key.toLowerCase()==="f")$("fit").click();if(e.key.toLowerCase()==="o")$("overlays").click();if(e.key.toLowerCase()==="m"&&!$("mistakes").hidden)$("mistakes").click();if(e.key==="Escape")clearSelection();
    });
    await loadPage(dataset().pages.some(p=>p.key===state.key)?state.key:dataset().pages[0].key);
    setInterval(async()=>{
      if(!["ocr","segmentation"].includes(state.mode))return;
      try {
        const requested=state.dataset,response=await fetch("/api/ocr-status?"+new URLSearchParams({dataset:requested}));if(!response.ok)return;
        const status=await response.json();if(!["ocr","segmentation"].includes(state.mode)||state.dataset!==requested)return;
        const ready=new Set(status.ready),d=dataset();
        if(d.completed_pages===ready.size)return;
        d.completed_pages=ready.size;d.pages.forEach(p=>p.ocr_ready=ready.has(p.key));collectionNote();renderPages();
        if((state.mode==="segmentation"?panes.b:panes.a).page?.pending&&ready.has(state.key))loadPage(state.key);
      }catch(e){ /* Keep the source scan available if the local server restarts. */ }
    },20000);
    if(state.index.warnings.length)toast(`${state.index.warnings.length} source examples were unavailable; see /api/index for details.`);
  }catch(e){panes.a.empty("Could not open the annotation desk",e.message+(staticSite?"":". Check that the local Python server is running."));$("page-count").textContent="Connection unavailable";}
}
init();
