(async function(){
"use strict";
const $=id=>document.getElementById(id), core=window.DanangDefense, params=new URLSearchParams(location.search);
const initialTime=Math.max(0,Math.min(3600,Number(params.get("t"))||1800));
const initialScenario=params.get("scenario")==="normal"?"normal":"pm_peak";
const state={playing:false,time:initialTime,speed:10,last:0,data:{}};
const [manifest,network,summary]=await Promise.all([fetch("manifest.json").then(r=>r.json()),fetch("network.json").then(r=>r.json()),fetch("aggregate-summary.json").then(r=>r.json())]);
async function loadScenario(scenario){
  const caseId=scenario==="pm_peak"?"test_pm_peak_demand103":"test_normal_demand103";
  const runs=manifest.runs.filter(r=>r.case_id===caseId);
  const fixed=runs.find(r=>r.controller_id==="published_fixed"), dqn=runs.find(r=>r.controller_id==="dueling_n3");
  const [left,right]=await Promise.all([fetch(fixed.replay_path).then(r=>r.json()),fetch(dqn.replay_path).then(r=>r.json())]);
  state.data={left,right,fixed,dqn,scenario}; state.time=initialTime; $("seek").value=state.time;
  const label=scenario==="pm_peak"?"PM peak, 17:00–18:00":"Normal traffic, 13:00–14:00";
  $("provenance").textContent=`${label} · observed digitized partial coverage · demand seed 103 · simulator seed 203`;
  const agg=summary.dqn_minus_published_fixed[scenario], pct=Math.abs(agg.relative_change_percent).toFixed(1);
  $("aggregate").textContent=scenario==="pm_peak"?`DDQN ${pct}% lower than published fixed time`:`DDQN ${pct}% higher than published fixed time`;
  $("details").textContent=JSON.stringify({selection_rule:fixed.selection_rule,simulator:fixed.simulator,fixed_replay_sha256:fixed.replay_sha256,dqn_replay_sha256:dqn.replay_sha256,aggregate_sha256:manifest.aggregate_results.sha256},null,2);
  render();
}
function draw(canvas,replay){
 const ctx=canvas.getContext("2d"),T=core.transform(network.bounds,canvas.width,canvas.height,34),frame=replay.frames[core.frameIndexAt(replay.frames,state.time)];
 ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle="#e8e5dc";ctx.fillRect(0,0,canvas.width,canvas.height);
 ctx.lineCap="round";for(const e of network.edges){ctx.beginPath();e.shape.forEach((p,i)=>(i?ctx.lineTo(T.x(p[0]),T.y(p[1])):ctx.moveTo(T.x(p[0]),T.y(p[1]))));ctx.strokeStyle="#58646d";ctx.lineWidth=24;ctx.stroke();ctx.strokeStyle="#d9d5c9";ctx.lineWidth=1;ctx.setLineDash([7,7]);ctx.stroke();ctx.setLineDash([])}
 for(const v of frame.vehicles){const [id,x,y,a,type]=v;ctx.save();ctx.translate(T.x(x),T.y(y));ctx.rotate((a-90)*Math.PI/180);ctx.fillStyle=type==="motorcycle"?"#e76f51":type==="car"?"#2a9d8f":type==="truck"?"#e9c46a":"#7a6fa6";ctx.fillRect(-2,-4,type==="motorcycle"?4:6,type==="motorcycle"?8:12);ctx.restore()}
 ctx.fillStyle=frame.p%2?"#e9c46a":"#24a67a";ctx.beginPath();ctx.arc(canvas.width/2,canvas.height/2,11,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#17324d";ctx.lineWidth=3;ctx.stroke();
 ctx.fillStyle="#17324d";ctx.font="bold 15px system-ui";ctx.fillText(core.phaseLabel(frame.p),16,24);
 return frame;
}
function metrics(el,frame,replay){const m=replay.metrics;el.innerHTML=[["Current queue",Math.round(frame.q)+" veh"],["Pending",frame.pending+" veh"],["Arrived",frame.arrived],["Whole episode",m.queue_integral_vehicle_hours.toFixed(1)+" veh-h"]].map(x=>`<div class="metric"><strong>${x[1]}</strong><span>${x[0]}</span></div>`).join("")}
function render(){if(!state.data.left)return;const l=draw($("left"),state.data.left),r=draw($("right"),state.data.right);metrics($("leftMetrics"),l,state.data.left);metrics($("rightMetrics"),r,state.data.right);$("clock").textContent=`${String(Math.floor(state.time/60)).padStart(2,"0")}:${String(Math.floor(state.time%60)).padStart(2,"0")}`;const f=state.data.left.metrics.queue_integral_vehicle_hours,d=state.data.right.metrics.queue_integral_vehicle_hours,c=core.representativeChange(f,d);$("episode").textContent=`Representative case: DDQN ${Math.abs(c).toFixed(1)}% ${c<0?"lower":"higher"} queue integral (${d.toFixed(1)} vs ${f.toFixed(1)} veh-h).`;}
function tick(ts){if(state.playing){if(state.last)state.time=Math.min(3600,state.time+(ts-state.last)/1000*state.speed);state.last=ts;$("seek").value=state.time;render();if(state.time>=3600){state.playing=false;$("play").textContent="▶ Play"}}requestAnimationFrame(tick)}
$("play").onclick=()=>{state.playing=!state.playing;state.last=0;$("play").textContent=state.playing?"❚❚ Pause":"▶ Play"};$("reset").onclick=()=>{state.time=1800;$("seek").value=1800;render()};$("speed").onchange=e=>state.speed=+e.target.value;$("seek").oninput=e=>{state.time=+e.target.value;render()};$("scenario").onchange=e=>loadScenario(e.target.value);
$("scenario").value=initialScenario;await loadScenario(initialScenario);$("status").textContent="Verified bundle loaded";requestAnimationFrame(tick);
})().catch(error=>{document.getElementById("status").textContent="Bundle error: "+error.message;console.error(error)});
