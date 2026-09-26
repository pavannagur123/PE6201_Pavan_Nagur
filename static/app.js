const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let meta = null;
let cases = [];
let currentPair = null;
let evalIndex = 0;
let judgments = JSON.parse(localStorage.getItem("macrofit-eval") || "[]");

async function api(path, options = {}) {
  const res = await fetch(path, {headers: {"Content-Type":"application/json"}, ...options});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}
function toast(message) { const el=$("#toast"); el.textContent=message; el.classList.remove("hidden"); setTimeout(()=>el.classList.add("hidden"),3200); }
function money(v){return `S$${Number(v).toFixed(2)}`}
function itemNames(plan){return plan.items.map(x=>x.item).join(" + ")}
function nutrition(plan){return `<div class="macro-strip"><div><strong>${money(plan.totals.price_sgd)}</strong><span>cost</span></div><div><strong>${plan.totals.protein_g}g</strong><span>protein</span></div><div><strong>${plan.totals.carbs_g}g</strong><span>carbs</span></div><div><strong>${plan.totals.kcal}</strong><span>kcal</span></div></div>`}
function planMarkup(plan, blind=false, letter=""){
  const rows=plan.items.map((x,i)=>`<div class="meal-row"><span class="meal-num">${i+1}</span><div><h3>${x.item}</h3><p>${x.shop} · ${x.location_name} · ${x.distance_km} km · ${money(x.price_sgd)}</p></div></div>`).join("");
  if(blind)return `<span class="letter">${letter}</span>${rows}${nutrition(plan)}<span class="choose-label">I would eat this →</span>`;
  return `${rows}${nutrition(plan)}`;
}

async function init(){
  try{
    [meta,cases]=await Promise.all([api("/api/meta"),api("/api/eval-cases")]);
    $("#model-status").innerHTML=`<span></span>${meta.openrouter_ready?`OpenRouter · ${meta.model}`:"Demo mode"}`;
    $("#model-status").classList.toggle("ready",meta.openrouter_ready);
    $("#model-toggle").disabled=!meta.openrouter_ready;
    $("#item-count").textContent=meta.menu_count;
    renderMenu(meta.menu); updateEval();
  }catch(e){toast(e.message)}
}

$$('.nav-link').forEach(btn=>btn.addEventListener('click',()=>{
  $$('.nav-link').forEach(x=>x.classList.remove('active')); btn.classList.add('active');
  $$('.view').forEach(x=>x.classList.remove('active')); $(`#${btn.dataset.view}-view`).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}));
$("#budget").addEventListener("input",e=>$("#budget-output").textContent=`S$${e.target.value}`);
$("#model-toggle").addEventListener("change",e=>$("#mode-hint").textContent=e.target.checked?"OpenRouter ranks the same shortlist":"Demo heuristic — not LLM evidence");

$("#planner-form").addEventListener("submit",async e=>{
  e.preventDefault(); const button=e.submitter; button.disabled=true; button.firstElementChild.textContent="Searching all plans…";
  const body={budget:+$("#budget").value,protein_g:+$("#protein").value,carbs_g:+$("#carbs").value,preferences:$("#preferences").value,mode:$("#model-toggle").checked?"openrouter":"demo"};
  try{
    const data=await api("/api/rank",{method:"POST",body:JSON.stringify(body)}); renderResults(data); $("#results").classList.remove("hidden"); $("#results").scrollIntoView({behavior:"smooth"});
  }catch(err){toast(err.message)}finally{button.disabled=false;button.firstElementChild.textContent="Build my shortlist"}
});
function renderResults(data){
  const p=data.model_pick; $("#pick-card").innerHTML=planMarkup(p); $("#model-reason").textContent=data.ranking.reason;
  $("#ranker-label").textContent=data.ranking.mode==="openrouter"?`OpenRouter · ${data.ranking.model}`:"Demo preference heuristic";
  $("#result-title").textContent=data.ranking.mode==="openrouter"?"Model pick from the shortlist":"Demo pick from the shortlist";
  $("#feasible-badge").textContent=p.feasible?"Constraints met":"Closest available";
  $("#search-summary").textContent=`${data.solution.evaluated_count.toLocaleString()} plans checked · ${data.solution.feasible_count.toLocaleString()} feasible`;
  $("#shortlist").innerHTML=data.solution.shortlist.map((x,i)=>`<article class="mini-plan"><span class="rank">SOLVER RANK ${i+1}</span><h4>${itemNames(x)}</h4><p>${money(x.totals.price_sgd)} · ${x.totals.protein_g}g P</p><p>${x.totals.carbs_g}g carbs · score ${x.score}</p></article>`).join("");
}

function renderMenu(rows){
  $("#menu-table").innerHTML=rows.map(x=>`<tr><td>${x.item}</td><td>${x.shop}</td><td>${x.location_name}</td><td>${x.distance_km} km · ${x.walk_min} min</td><td>${money(x.price_sgd)}</td><td>${x.protein_g}g</td><td>${x.carbs_g}g</td><td title="${x.mapping_method}">${x.source_match}</td><td><span class="confidence ${x.confidence}">${x.confidence}</span></td></tr>`).join("");
}
$("#menu-search").addEventListener("input",e=>{const q=e.target.value.toLowerCase();renderMenu(meta.menu.filter(x=>`${x.item} ${x.shop} ${x.cuisine} ${x.location_name}`.toLowerCase().includes(q)))});

function updateEval(){
  evalIndex=Math.min(judgments.length,cases.length-1); const done=judgments.length; $("#eval-count").textContent=`${done}/20`; $("#progress-label").textContent=`${done} of 20 judged`; $("#progress-bar").style.width=`${done/20*100}%`;
  if(!cases.length)return; const c=cases[evalIndex]; $("#case-id").textContent=`Case ${String(evalIndex+1).padStart(2,"0")}`; $("#case-target").textContent=`S$${c.budget} · ${c.protein_g}g protein · ${c.carbs_g}g carbs`; $("#case-pref").textContent=`“${c.preferences}”`;
  $("#eval-mode-note").textContent=meta?.openrouter_ready?`OpenRouter is connected · ${meta.model}`:"Demo heuristic only — do not report as LLM evidence"; $("#blind-grid").classList.add("hidden"); $("#tie-row").classList.add("hidden"); $("#eval-actions").classList.remove("hidden"); currentPair=null; renderSummary();
}
$("#generate-pair").addEventListener("click",async e=>{
  const b=e.currentTarget;b.disabled=true;b.textContent="Generating…";const c=cases[evalIndex];
  try{const d=await api("/api/eval-pair",{method:"POST",body:JSON.stringify({...c,mode:meta.openrouter_ready?"openrouter":"demo"})});
    if(d.model_pick.plan_id===d.solution.optimizer_pick.plan_id){
      judgments.push({case_id:c.id,winner:"tie",mode:d.ranking.mode,optimizer_plan:d.solution.optimizer_pick.plan_id,model_plan:d.model_pick.plan_id,model_reason:d.ranking.reason});localStorage.setItem("macrofit-eval",JSON.stringify(judgments));toast("Both systems chose the same plan — recorded as a tie");updateEval();return;
    }
    const flip=Math.random()<.5;const a=flip?d.model_pick:d.solution.optimizer_pick;const bp=flip?d.solution.optimizer_pick:d.model_pick;currentPair={data:d,leftRole:flip?"model":"optimizer",rightRole:flip?"optimizer":"model",left:a,right:bp,case:c};
    $("#blind-grid").innerHTML=`<button class="blind-option" data-choice="left">${planMarkup(a,true,"A")}</button><button class="blind-option" data-choice="right">${planMarkup(bp,true,"B")}</button>`;$("#blind-grid").classList.remove("hidden");$("#tie-row").classList.remove("hidden");$("#eval-actions").classList.add("hidden");
    $$("[data-choice]").forEach(x=>x.onclick=()=>recordChoice(x.dataset.choice));
  }catch(err){toast(err.message)}finally{b.disabled=false;b.textContent="Generate blind pair"}
});
function recordChoice(choice){
  if(!currentPair)return;let winner=choice==="tie"?"tie":choice==="left"?currentPair.leftRole:currentPair.rightRole;
  judgments.push({case_id:currentPair.case.id,winner,mode:currentPair.data.ranking.mode,optimizer_plan:currentPair.data.solution.optimizer_pick.plan_id,model_plan:currentPair.data.model_pick.plan_id,model_reason:currentPair.data.ranking.reason});localStorage.setItem("macrofit-eval",JSON.stringify(judgments));toast(`Recorded: ${choice==="tie"?"tie":`option ${choice==="left"?"A":"B"}`}`);updateEval();
}
$("#skip-case").addEventListener("click",()=>{const c=cases[evalIndex];judgments.push({case_id:c.id,winner:"skipped",mode:meta.openrouter_ready?"openrouter":"demo",optimizer_plan:"",model_plan:"",model_reason:""});localStorage.setItem("macrofit-eval",JSON.stringify(judgments));updateEval()});
$("#reset-eval").addEventListener("click",()=>{if(confirm("Clear all blind-evaluation judgments?")){judgments=[];localStorage.removeItem("macrofit-eval");updateEval()}});
function renderSummary(){
  const counts={model:0,optimizer:0,tie:0,skipped:0};judgments.forEach(x=>counts[x.winner]++);const decisive=counts.model+counts.optimizer;const valid=decisive+counts.tie;const rate=decisive?Math.round(counts.model/decisive*100):0;
  $("#metric-grid").innerHTML=`<div class="metric"><strong>${rate}%</strong><span>model win rate</span></div><div class="metric"><strong>${counts.model}</strong><span>model wins</span></div><div class="metric"><strong>${counts.optimizer}</strong><span>optimizer wins</span></div><div class="metric"><strong>${counts.tie}</strong><span>ties</span></div>`;
  $("#eval-caveat").textContent=(judgments.some(x=>x.mode!=="openrouter")?"Contains demo-heuristic judgments. These are UI tests, not evidence of LLM value. ":"All recorded comparisons used the configured OpenRouter model. ")+`Valid n=${valid}; skipped=${counts.skipped}. With this small sample, interpret the result as directional evidence.`;
  $("#eval-summary").classList.toggle("hidden",judgments.length===0);
}
$("#export-results").addEventListener("click",()=>{
  const cols=["case_id","winner","mode","optimizer_plan","model_plan","model_reason"];const escape=v=>`"${String(v??"").replaceAll('"','""')}"`;const csv=[cols.join(','),...judgments.map(x=>cols.map(k=>escape(x[k])).join(','))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='macrofit_blind_evaluation.csv';a.click();URL.revokeObjectURL(a.href);
});
init();
