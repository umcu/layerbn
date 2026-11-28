"""The interactive network explorer.

One self-contained HTML file (no server, no internet, no Python needed to open
it) that shows the learned network with the probability distribution of every
variable inside its node. Click a state to enter it as evidence: all other
distributions update at once to their posterior, and the prior is kept as a
tick mark so the change is visible. Click a variable's name to see its
conditional probability table (CPT).

The inference runs in the page (exact variable elimination on the network's
own CPTs), so the file can be e-mailed or put next to the report.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from layerbn.discretisation import MISSING, pretty_labels


def explorer_model(study: Any, network: str | None = None, *,
                   stability: bool = False) -> dict[str, Any]:
    """Everything the page needs, as plain data."""
    definition = study.project.network(network)
    bn = study.network(definition.name)
    design = study.design
    targets = set(study.project.default_targets(definition))

    frequencies = study.edge_frequencies(definition.name) if stability else {}
    strengths = study.arc_strengths(definition.name)

    layers = [{"name": layer.name, "title": layer.title, "time": layer.time,
               "colour": layer.colour}
              for layer in design.layers if layer.name in definition.layer_map]
    layer_of = {c: layer.name for layer in design.layers for c in layer.variables}

    nodes = []
    for column in definition.columns:
        if column not in bn.names():
            continue
        var = bn.variable(column)
        labels = list(var.labels())
        pretty = pretty_labels(labels)
        parents = [bn.variable(i).name() for i in sorted(bn.parents(column))]
        cpt = bn.cpt(column)
        names = list(cpt.names)
        array = cpt.toarray()                    # pyAgrum stores the axes reversed
        axes = [array.ndim - 1 - names.index(n) for n in [*parents, column]]
        table = np.transpose(array, axes)
        v = design.variable(column)
        nodes.append({
            "id": column, "label": v.label, "short": v.short_label,
            "layer": layer_of[column], "target": column in targets,
            "states": [pretty[s] for s in labels],
            "missing": [s == MISSING for s in labels],
            "parents": parents,
            "cpt": [round(float(x), 6) for x in table.ravel()],
        })
    arcs = [{"from": p, "to": c, "strength": strengths.get((p, c)),
             "freq": frequencies.get((p, c))}
            for p, c in study.arcs(definition.name)]
    return {"title": study.project.name, "network": definition.name,
            "subtitle": f"{len(nodes)} variables, {len(arcs)} arcs, {study.n} participants",
            "layers": layers, "nodes": nodes, "arcs": arcs}


def explorer_html(model: Mapping[str, Any],
                  evidence: Mapping[str, Sequence[str]] | None = None) -> str:
    """The page for one model. `evidence` maps variable id to the states to start with."""
    payload = dict(model)
    payload["evidence"] = {k: list(v) if isinstance(v, (list, tuple)) else [v]
                           for k, v in (evidence or {}).items()}
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      default=lambda o: None).replace("</", "<\\/")
    return _PAGE.replace("__TITLE__", _escape(str(model.get("title", "Network"))))\
                .replace("__DATA__", text)


class Explorer:
    """An explorer page that shows itself in a notebook and can be saved."""

    def __init__(self, html: str) -> None:
        self.html = html

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.html, encoding="utf-8")
        return path

    def _repr_html_(self) -> str:
        from html import escape
        return (f'<iframe srcdoc="{escape(self.html, quote=True)}" width="100%" height="820" '
                'style="border:1px solid #e6e8eb;border-radius:8px"></iframe>')


def write_explorer(study: Any, path: str | Path, network: str | None = None, *,
                   stability: bool = False,
                   evidence: Mapping[str, Sequence[str]] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(explorer_html(explorer_model(study, network, stability=stability),
                                  evidence), encoding="utf-8")
    return path


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · network explorer</title>
<style>
:root{--ink:#1f2328;--ink2:#57606a;--ink3:#8c959f;--line:#e6e8eb;--bg:#f6f7f9;--card:#fff;--acc:#1f2328;--miss:#b8bfc7}
*{box-sizing:border-box}
html,body{margin:0;height:100%;font:13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg)}
#app{display:grid;grid-template-columns:1fr 340px;grid-template-rows:auto 1fr;height:100%}
header{grid-column:1/3;display:flex;align-items:center;gap:14px;padding:10px 18px;background:var(--card);border-bottom:1px solid var(--line)}
header h1{font-size:15px;margin:0;font-weight:650}
header .sub{color:var(--ink2);font-size:12px}
header .sp{flex:1}
button,input[type=search]{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:5px 10px}
button{cursor:pointer}button:hover{background:var(--bg)}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
label.t{display:flex;gap:5px;align-items:center;color:var(--ink2);cursor:pointer;user-select:none}
#canvas{overflow:auto;position:relative;background:var(--bg)}
#stage{transform-origin:0 0;position:relative}
svg{display:block}
aside{background:var(--card);border-left:1px solid var(--line);overflow:auto;padding:14px 16px}
aside h2{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:18px 0 8px;font-weight:600}
aside h2:first-child{margin-top:0}
@media (max-width:900px){
  #app{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr) auto}
  header{grid-column:1;flex-wrap:wrap;gap:8px 12px}
  aside{border-left:0;border-top:1px solid var(--line);max-height:38vh}
}
.band{fill-opacity:.07}
.bandt{font-size:12px;font-weight:650;fill:var(--ink)}
.timet{font-size:12px;font-weight:700;fill:var(--ink2)}
.card{fill:#fff}
.card.sel{stroke:var(--ink);stroke-width:1.6}
.title{font-size:11.5px;font-weight:650;fill:var(--ink);cursor:pointer}
.title:hover{text-decoration:underline}
.sl{font-size:10.5px;fill:var(--ink2)}
.pc{font-size:10.5px;fill:var(--ink);font-variant-numeric:tabular-nums}
.track{fill:#eef0f3}
.row{cursor:pointer}
.row:hover .hit{fill:#00000008}
.hit{fill:transparent}
.arc{fill:none;stroke-linecap:round;marker-end:url(#head)}
.arc.dim{opacity:.10}
.arc.hl{stroke:var(--ink);opacity:1}
.delta{font-size:9.5px;font-variant-numeric:tabular-nums}
.chip{display:inline-flex;align-items:center;gap:6px;background:var(--bg);border:1px solid var(--line);border-radius:99px;padding:3px 6px 3px 10px;margin:0 6px 6px 0;font-size:12px}
.chip b{font-weight:650}.chip i{cursor:pointer;font-style:normal;color:var(--ink3);padding:0 3px}.chip i:hover{color:var(--ink)}
.tgt{margin-bottom:12px}.tgt .n{font-weight:650;margin-bottom:4px}
.tgt .r{display:grid;grid-template-columns:90px 1fr 70px;gap:6px;align-items:center;margin:2px 0;font-size:12px}
.bar{height:8px;background:#eef0f3;border-radius:4px;position:relative}.bar>div{height:100%;border-radius:4px}
.bar>u{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--ink);opacity:.55}
table.cpt{border-collapse:collapse;width:100%;font-size:11.5px;font-variant-numeric:tabular-nums}
table.cpt th,table.cpt td{padding:3px 6px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
table.cpt th:first-child,table.cpt td:first-child{text-align:left}
table.cpt th{color:var(--ink2);font-weight:600;position:sticky;top:0;background:#fff}
table.cpt tr.m td:first-child{font-weight:650}
.muted{color:var(--ink3);font-size:12px}
.hint{color:var(--ink2);font-size:12px;line-height:1.5}
.pe{font-size:12px;color:var(--ink2)}
.cptwrap{max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:6px}
</style></head>
<body><div id="app">
<header>
  <div><h1 id="ttl"></h1><div class="sub" id="sub"></div></div><div class="sp"></div>
  <input type="search" id="q" placeholder="Find variable…" size="18">
  <label class="t"><input type="checkbox" id="arcs" checked> Arcs</label>
  <label class="t"><input type="checkbox" id="chg" checked> Change vs prior</label>
  <button id="zo">−</button><button id="zi">+</button>
  <button id="clr" class="primary">Clear evidence</button>
</header>
<div id="canvas"><div id="stage"><svg id="svg"></svg></div></div>
<aside id="side"></aside>
</div>
<script>
const M = __DATA__;
const MISS = "#b8bfc7";
const byId = Object.fromEntries(M.nodes.map(n => [n.id, n]));
const layerBy = Object.fromEntries(M.layers.map(l => [l.name, l]));
M.nodes.forEach(n => { n.card = n.states.length; n.pc = n.parents.map(p => byId[p].states.length); });
let evidence = {};            // id -> Set of state indexes
for (const [k, v] of Object.entries(M.evidence || {})) if (byId[k]) {
  const s = new Set(v.map(x => byId[k].states.indexOf(x)).filter(i => i >= 0)); if (s.size) evidence[k] = s; }
let selected = null, scale = 1, prior = null, post = null, pEvidence = 1;

// ---------- exact inference: variable elimination ----------------------------
function strides(card){const s=new Array(card.length);let a=1;for(let i=card.length-1;i>=0;i--){s[i]=a;a*=card[i];}return s;}
function mult(a,b){
  const vars=[...a.vars];for(const v of b.vars)if(!vars.includes(v))vars.push(v);
  const card=vars.map(v=>byId[v].card),size=card.reduce((x,y)=>x*y,1);
  const sa=strideIn(a,vars),sb=strideIn(b,vars),out=new Float64Array(size),asg=new Array(vars.length).fill(0);
  let oa=0,ob=0;
  for(let i=0;i<size;i++){
    out[i]=a.data[oa]*b.data[ob];
    for(let k=vars.length-1;k>=0;k--){asg[k]++;oa+=sa[k];ob+=sb[k];
      if(asg[k]<card[k])break;oa-=sa[k]*card[k];ob-=sb[k]*card[k];asg[k]=0;}
  }
  return {vars,data:out};
}
function strideIn(f,vars){const st=strides(f.vars.map(v=>byId[v].card));return vars.map(v=>{const i=f.vars.indexOf(v);return i<0?0:st[i];});}
function sumOut(f,v){
  const keep=f.vars.filter(x=>x!==v),card=f.vars.map(x=>byId[x].card),size=card.reduce((x,y)=>x*y,1);
  const kc=keep.map(x=>byId[x].card),ks=strides(kc);
  const so=f.vars.map(x=>{const i=keep.indexOf(x);return i<0?0:ks[i];});
  const out=new Float64Array(kc.reduce((x,y)=>x*y,1)),asg=new Array(card.length).fill(0);let o=0;
  for(let i=0;i<size;i++){
    out[o]+=f.data[i];
    for(let k=card.length-1;k>=0;k--){asg[k]++;o+=so[k];if(asg[k]<card[k])break;o-=so[k]*card[k];asg[k]=0;}
  }
  return {vars:keep,data:out};
}
function ancestors(ids){const seen=new Set(),st=[...ids];while(st.length){const x=st.pop();if(seen.has(x))continue;seen.add(x);byId[x].parents.forEach(p=>st.push(p));}return seen;}
function query(q,ev){
  const rel=ancestors([q,...Object.keys(ev)]);
  let fs=[];
  for(const id of rel){const n=byId[id];fs.push({vars:[...n.parents,id],data:Float64Array.from(n.cpt)});
    if(ev[id]){const d=new Float64Array(n.card);ev[id].forEach(i=>d[i]=1);fs.push({vars:[id],data:d});}}
  const elim=[...rel].filter(x=>x!==q);
  while(elim.length){
    let best=-1,cost=Infinity;
    elim.forEach((v,i)=>{const sc=new Set();fs.forEach(f=>{if(f.vars.includes(v))f.vars.forEach(x=>sc.add(x));});
      let c=1;sc.forEach(x=>c*=byId[x].card);if(c<cost){cost=c;best=i;}});
    const v=elim.splice(best,1)[0],inn=fs.filter(f=>f.vars.includes(v));fs=fs.filter(f=>!f.vars.includes(v));
    let p=inn[0];for(let i=1;i<inn.length;i++)p=mult(p,inn[i]);fs.push(sumOut(p,v));
  }
  let r=fs[0];for(let i=1;i<fs.length;i++)r=mult(r,fs[i]);
  const z=r.data.reduce((a,b)=>a+b,0);return {p:Array.from(r.data,x=>x/z),z};
}
function compute(){
  const ev={};for(const k in evidence)ev[k]=evidence[k];
  if(!prior){prior={};M.nodes.forEach(n=>prior[n.id]=query(n.id,{}).p);}
  post={};pEvidence=1;
  M.nodes.forEach(n=>{const r=query(n.id,ev);post[n.id]=r.p;pEvidence=r.z;});
  if(!Object.keys(ev).length)pEvidence=1;
}

// ---------- layout: layers as rows, from the top down ------------------------------
const W=232,ROW=16,HEAD=26,PADY=8,GAPX=30,ROWGAP=78,INNER=40,GUTTER=170,TOP=26,PER_ROW=6;
const pos={};let rows=[],totalW=0,totalH=0;
function cardH(n){return HEAD+n.card*ROW+PADY;}
function layout(){
  rows=[];
  const inner=new Set(M.arcs.filter(a=>byId[a.from]&&byId[a.to]&&byId[a.from].layer===byId[a.to].layer)
                       .map(a=>byId[a.from].layer));
  for(const l of M.layers){
    const ns=M.nodes.filter(n=>n.layer===l.name);
    for(let i=0;i<ns.length;i+=PER_ROW)rows.push({l,ns:ns.slice(i,i+PER_ROW),first:i===0});
  }
  const widest=Math.max(1,...rows.map(r=>r.ns.length));
  const contentW=widest*W+(widest-1)*GAPX;
  let y=TOP;
  rows.forEach((r,i)=>{
    if(i)y+=r.first?ROWGAP:22;
    if(r.first&&inner.has(r.l.name))y+=INNER;
    r.top=y;r.h=Math.max(...r.ns.map(cardH));
    let x=GUTTER+(contentW-(r.ns.length*W+(r.ns.length-1)*GAPX))/2;
    for(const n of r.ns){pos[n.id]={x,y,h:cardH(n),row:i};x+=W+GAPX;}
    y+=r.h;
  });
  totalW=GUTTER+contentW+30;totalH=y+30;
}

// ---------- drawing -------------------------------------------------------------
const NS="http://www.w3.org/2000/svg";
function el(tag,attrs,parent,text){const e=document.createElementNS(NS,tag);for(const k in attrs)if(attrs[k]!=null)e.setAttribute(k,attrs[k]);if(text!=null)e.textContent=text;if(parent)parent.appendChild(e);return e;}
const pct=x=>x<0.005?"<1%":x>0.995?">99%":Math.round(x*100)+"%";
const trunc=(s,n)=>s.length>n?s.slice(0,n-1)+"…":s;
const showChg=()=>document.getElementById("chg").checked;
const hasEv=()=>Object.keys(evidence).length>0;

function draw(){
  const svg=document.getElementById("svg");svg.innerHTML="";
  svg.setAttribute("width",totalW);svg.setAttribute("height",totalH);
  const q=document.getElementById("q").value.trim().toLowerCase();
  const seen=new Set();
  rows.forEach(r=>{
    if(!r.first)return;
    const last=rows.filter(o=>o.l===r.l).pop();
    el("rect",{x:18,y:r.top,width:4,height:last.top+last.h-r.top,rx:2,fill:r.l.colour},svg);
    const title=r.l.title+(r.l.time?" · "+r.l.time:"");
    el("text",{x:32,y:r.top+14,class:"bandt"},svg,trunc(title,22));
    seen.add(r.l.name);
  });
  const defs=el("defs",{},svg),mk=el("marker",{id:"head",viewBox:"0 0 10 10",refX:9,refY:5,
    markerWidth:5,markerHeight:5,orient:"auto-start-reverse",markerUnits:"strokeWidth"},defs);
  el("path",{d:"M0,1 L10,5 L0,9 z",fill:"#32475e"},mk);
  const gA=el("g",{},svg);
  if(document.getElementById("arcs").checked)drawArcs(gA);
  for(const n of M.nodes)drawNode(svg,n,q);
}
// Arc colour: the blue side of RdBu, light (rarely found) to dark (always found).
function arcColour(f){if(f==null)return "#56606d";const lo=[0xb4,0xd4,0xe8],hi=[0x05,0x30,0x61];
  return "rgb("+lo.map((v,i)=>Math.round(v+(hi[i]-v)*Math.min(1,Math.max(0,f)))).join(",")+")";}
function drawArcs(g){
  const max=Math.max(1e-9,...M.arcs.map(a=>a.strength||0));
  // spread the arcs at one edge of a card, ordered by where their other end is
  const ends={};
  for(const a of M.arcs){const p=pos[a.from],c=pos[a.to];if(!p||!c)continue;
    const same=p.row===c.row;
    (ends[a.from+(same?"|t":"|b")]??=[]).push([c.x,a,"out"]);
    (ends[a.to+"|t"]??=[]).push([p.x,a,"in"]);}
  const port=new Map();
  for(const k in ends){const [id,edge]=k.split("|"),p=pos[id],list=ends[k].sort((u,v)=>u[0]-v[0]);
    const n=list.length,step=Math.min(22,(W-60)/Math.max(n-1,1));
    list.forEach(([,a,end],i)=>port.set(a.from+">"+a.to+end,{x:p.x+W/2+(i-(n-1)/2)*step,y:edge==="t"?p.y:p.y+p.h}));}
  for(const a of M.arcs){
    const p=pos[a.from],c=pos[a.to];if(!p||!c)continue;
    const A=port.get(a.from+">"+a.to+"out"),B=port.get(a.from+">"+a.to+"in");
    let d;
    if(p.row===c.row){const lift=Math.min(INNER+ROWGAP*0.55,26+Math.abs(B.x-A.x)*0.09);
      d=`M${A.x},${A.y} C${A.x},${A.y-lift} ${B.x},${B.y-lift} ${B.x},${B.y}`;}
    else{const r=Math.max(30,(B.y-A.y)*0.45);d=`M${A.x},${A.y} C${A.x},${A.y+r} ${B.x},${B.y-r} ${B.x},${B.y}`;}
    const w=a.strength?0.8+2.0*Math.sqrt(a.strength/max):1.2;
    const hl=selected&&(a.from===selected||a.to===selected);
    const e=el("path",{d,class:"arc"+(selected&&!hl?" dim":"")+(hl?" hl":""),"stroke-width":w,
                       stroke:hl?null:arcColour(a.freq)},g);
    if(a.freq!=null&&a.freq<0.5)e.setAttribute("stroke-dasharray","5 4");
    el("title",{},e,`${byId[a.from].label} → ${byId[a.to].label}`+(a.freq!=null?` · in ${Math.round(a.freq*100)}% of resamples`:"")+(a.strength?` · MI ${a.strength.toFixed(2)} bits`:""));
  }
}
function lum(hex){const v=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255);return .2126*v[0]+.7152*v[1]+.0722*v[2];}
function mix(hex,share){const v=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
  return "rgb("+v.map(c=>Math.round(c+(255-c)*share)).join(",")+")";}
function drawNode(svg,n,q){
  const p=pos[n.id],col=layerBy[n.layer].colour,ev=evidence[n.id];
  const dim=q&&!n.label.toLowerCase().includes(q);
  const g=el("g",{opacity:dim?0.25:1},svg);
  const clip="c"+n.id.replace(/[^A-Za-z0-9_-]/g,"_");
  const cp=el("clipPath",{id:clip},g);el("rect",{x:p.x,y:p.y,width:W,height:p.h,rx:7},cp);
  el("rect",{x:p.x,y:p.y,width:W,height:p.h,rx:7,class:"card"+(selected===n.id?" sel":""),
             stroke:n.target?col:mix(col,.45),"stroke-width":n.target?1.6:1},g);
  el("rect",{x:p.x,y:p.y,width:W,height:HEAD-4,fill:n.target?col:mix(col,.8),"clip-path":`url(#${clip})`},g);
  const ink=n.target&&lum(col)<.55?"#ffffff":"#1f2328";
  const t=el("text",{x:p.x+10,y:p.y+15.5,class:"title",style:`fill:${ink}`},g,trunc(n.layer&&layerBy[n.layer].time?n.short:n.label,30));
  t.addEventListener("click",()=>{selected=selected===n.id?null:n.id;draw();side();});
  el("title",{},t,n.label+" — click for the CPT");
  if(ev)el("text",{x:p.x+W-8,y:p.y+15.5,"text-anchor":"end",class:"sl",style:`fill:${ink}`},g,"evidence ✕").addEventListener("click",()=>{delete evidence[n.id];update();});
  const lab=96,bx=p.x+12+lab,bw=W-12-lab-48;
  const barCol=lum(col)<.85?col:"#8c959f";
  n.states.forEach((s,i)=>{
    const y=p.y+HEAD+i*ROW,v=post[n.id][i],pr=prior[n.id][i],on=ev&&ev.has(i);
    const r=el("g",{class:"row"},g);
    el("rect",{x:p.x+6,y:y,width:W-12,height:ROW,class:"hit",rx:4},r);
    if(on)el("rect",{x:p.x+6,y:y,width:W-12,height:ROW,rx:4,fill:"#1f232812"},r);
    el("text",{x:p.x+12,y:y+11.5,class:"sl","font-weight":on?700:400,fill:on?"#1f2328":null},r,trunc(s,16));
    el("rect",{x:bx,y:y+3.5,width:bw,height:9,rx:2,class:"track"},r);
    const fill=n.missing[i]?MISS:barCol;
    el("rect",{x:bx,y:y+3.5,width:Math.max(1.5,bw*v),height:9,rx:2,fill:on?"#1f2328":fill,opacity:hasEv()&&ev&&!on?0.35:1},r);
    if(hasEv()&&showChg()&&Math.abs(v-pr)>0.0005)el("rect",{x:bx+bw*pr-1,y:y+1.5,width:2,height:13,rx:1,fill:"#1f2328",opacity:.55},r);
    el("text",{x:p.x+W-8,y:y+11.5,"text-anchor":"end",class:"pc","font-weight":on?700:400},r,pct(v));
    r.addEventListener("click",e=>{toggle(n.id,i,e.shiftKey||e.metaKey||e.ctrlKey);});
    el("title",{},r,`${n.label}: ${s}\nposterior ${(v*100).toFixed(1)}%  ·  prior ${(pr*100).toFixed(1)}%\nclick: set as evidence · shift-click: allow several states`);
  });
}
function toggle(id,i,multi){
  const s=evidence[id];
  if(s&&s.has(i)){s.delete(i);if(!s.size)delete evidence[id];}
  else if(multi&&s)s.add(i);else evidence[id]=new Set([i]);
  update();
}

// ---------- side panel ---------------------------------------------------------------
function side(){
  const a=document.getElementById("side");let h="";
  h+=`<h2>Evidence</h2>`;
  const ks=Object.keys(evidence);
  if(!ks.length)h+=`<div class="hint">Click a state in any variable to enter evidence. Every distribution updates to its posterior; the tick marks show the prior. Shift-click adds a second state (“either of these”). Click a variable name to see its CPT.</div>`;
  else{h+=ks.map(k=>`<span class="chip"><span>${esc(byId[k].short&&layerBy[byId[k].layer].time?byId[k].label:byId[k].label)}: <b>${[...evidence[k]].map(i=>esc(byId[k].states[i])).join(" or ")}</b></span><i data-k="${k}">✕</i></span>`).join("");
    h+=`<div class="pe">P(evidence) = ${(pEvidence*100).toPrecision(pEvidence<0.1?2:3)}%</div>`;}
  const tg=M.nodes.filter(n=>n.target);
  if(tg.length){h+=`<h2>Targets</h2>`;
    for(const n of tg){h+=`<div class="tgt"><div class="n">${esc(n.label)}</div>`;
      n.states.forEach((s,i)=>{const v=post[n.id][i],pr=prior[n.id][i],c=layerBy[n.layer].colour,d=Math.round((v-pr)*100);
        h+=`<div class="r"><span>${esc(trunc(s,14))}</span><div class="bar"><div style="width:${v*100}%;background:${n.missing[i]?MISS:c}"></div>${hasEv()?`<u style="left:${pr*100}%"></u>`:""}</div><span>${pct(v)}${hasEv()&&d?` <span class="muted">${d>0?"+":""}${d}</span>`:""}</span></div>`;});
      h+=`</div>`;}}
  if(selected)h+=cptHtml(byId[selected]);
  a.innerHTML=h;
  a.querySelectorAll(".chip i").forEach(e=>e.addEventListener("click",()=>{delete evidence[e.dataset.k];update();}));
}
const esc=s=>String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function cptHtml(n){
  let h=`<h2>CPT · ${esc(n.label)}</h2>`;
  if(!n.parents.length)return h+`<div class="hint">No parents: this is the prior distribution of ${esc(n.label)}.</div>`;
  const rows=n.pc.reduce((a,b)=>a*b,1),limit=600;
  h+=`<div class="hint" style="margin-bottom:6px">P(${esc(n.short||n.label)} | ${n.parents.map(p=>esc(byId[p].short||byId[p].label)).join(", ")}). Rows that match the current evidence are in bold.</div>`;
  h+=`<div class="cptwrap"><table class="cpt"><thead><tr><th>${n.parents.map(p=>esc(trunc(byId[p].short||byId[p].label,10))).join(" · ")}</th>${n.states.map(s=>`<th>${esc(trunc(s,9))}</th>`).join("")}</tr></thead><tbody>`;
  const st=strides(n.pc);
  for(let r=0;r<Math.min(rows,limit);r++){
    const idx=n.pc.map((c,k)=>Math.floor(r/st[k])%c);
    const match=idx.every((i,k)=>!evidence[n.parents[k]]||evidence[n.parents[k]].has(i))&&n.parents.some(p=>evidence[p]);
    h+=`<tr class="${match?"m":""}"><td>${idx.map((i,k)=>esc(trunc(byId[n.parents[k]].states[i],10))).join(" · ")}</td>`;
    for(let s=0;s<n.card;s++){const v=n.cpt[r*n.card+s];
      h+=`<td style="background:${n.missing[s]?"#b8bfc7":layerBy[n.layer].colour}${Math.round(v*60+3).toString(16).padStart(2,"0")}">${(v*100).toFixed(0)}</td>`;}
    h+=`</tr>`;
  }
  h+=`</tbody></table></div>`;
  if(rows>limit)h+=`<div class="muted">First ${limit} of ${rows} rows.</div>`;
  return h;
}

function update(){compute();draw();side();}
function zoom(f){scale=Math.min(2,Math.max(.3,scale*f));const s=document.getElementById("stage");s.style.transform=`scale(${scale})`;s.style.width=totalW*scale+"px";s.style.height=totalH*scale+"px";}
document.getElementById("ttl").textContent=M.title+" · "+M.network;
document.getElementById("sub").textContent=M.subtitle+" · click a state to set evidence";
document.getElementById("clr").onclick=()=>{evidence={};update();};
document.getElementById("q").oninput=draw;
document.getElementById("arcs").onchange=draw;document.getElementById("chg").onchange=draw;
document.getElementById("zi").onclick=()=>zoom(1.15);document.getElementById("zo").onclick=()=>zoom(1/1.15);
// Fit the network to the width of the window on load, so a narrow window
// (or a page embedded in documentation) shows the whole network at once.
function fit(){const c=document.getElementById("canvas");if(!c.clientWidth||!totalW)return;
  scale=1;zoom(Math.min(1,Math.max(.3,(c.clientWidth-8)/totalW)));}
layout();update();fit();
</script></body></html>
"""
