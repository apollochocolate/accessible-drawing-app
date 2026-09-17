const AXES = {
  protan:{label:'적색계열', baseH:28, altDir:1, L:.63, C:.15},
  deutan:{label:'녹색계열', baseH:142, altDir:-1, L:.63, C:.14},
  tritan:{label:'청황계열', baseH:252, altDir:-1, L:.64, C:.13}
};
// 난이도 0(쉬움) ~ 6(매우 어려움): hue difference를 점차 축소
const DIFFS=[52,38,27,19,13,8,5];
const TOTAL_ADAPTIVE_PER_AXIS=8;
const TOTAL_PAIR_PER_AXIS=2;
const TOTAL_TRIALS=3*(TOTAL_ADAPTIVE_PER_AXIS+TOTAL_PAIR_PER_AXIS);
let state;

function resetState(){
  state={phase:'adaptive', axisOrder:shuffle(['protan','deutan','tritan']), axisIndex:0,
    adaptiveDone:{protan:0,deutan:0,tritan:0}, pairDone:{protan:0,deutan:0,tritan:0},
    level:{protan:2,deutan:2,tritan:2}, correctStreak:{protan:0,deutan:0,tritan:0},
    records:[], startedAt:Date.now(), trialStart:0, current:null};
}
function shuffle(a){return [...a].sort(()=>Math.random()-.5)}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function color(axis,hShift=0,cShift=0,lShift=0){const x=AXES[axis]; return `oklch(${clamp(x.L+lShift,.35,.85)} ${clamp(x.C+cShift,.035,.22)} ${((x.baseH+hShift)%360+360)%360})`;}
function getTotalDone(){return state.records.length}
function updateProgress(){const p=Math.min(100,getTotalDone()/TOTAL_TRIALS*100);document.getElementById('progressFill').style.width=p+'%';document.getElementById('phaseLabel').textContent=`${getTotalDone()+1} / ${TOTAL_TRIALS}`}

function nextAdaptiveAxis(){
  for(let i=0;i<state.axisOrder.length;i++){const ax=state.axisOrder[(state.axisIndex+i)%3]; if(state.adaptiveDone[ax]<TOTAL_ADAPTIVE_PER_AXIS){state.axisIndex=(state.axisOrder.indexOf(ax)+1)%3;return ax}}
  return null;
}
function nextPairAxis(){
  for(let i=0;i<state.axisOrder.length;i++){const ax=state.axisOrder[(state.axisIndex+i)%3]; if(state.pairDone[ax]<TOTAL_PAIR_PER_AXIS){state.axisIndex=(state.axisOrder.indexOf(ax)+1)%3;return ax}}
  return null;
}

function makeAdaptiveTrial(axis){
  const level=state.level[axis], diff=DIFFS[level];
  const target=Math.floor(Math.random()*4);
  const baseJ=(Math.random()-.5)*2.4;
  const colors=[];
  for(let i=0;i<4;i++){
    // same-lightness jitter를 아주 작게 넣되 타깃의 밝기 단서는 최소화
    const lj=(Math.random()-.5)*.006;
    colors.push(i===target ? color(axis, AXES[axis].altDir*diff+baseJ, 0, lj) : color(axis, baseJ,0,lj));
  }
  return {type:'adaptive',axis,level,diff,target,colors};
}
function makePairTrial(axis){
  const level=state.level[axis];
  const diff=DIFFS[clamp(level+Math.floor(Math.random()*3)-1,0,6)];
  const isSame=Math.random()<.36;
  const baseJ=(Math.random()-.5)*3;
  return {type:'pair',axis,level,diff,isSame,a:color(axis,baseJ),b:isSame?color(axis,baseJ):color(axis,AXES[axis].altDir*diff+baseJ)};
}

function renderTrial(){
  updateProgress();
  let axis;
  if(state.phase==='adaptive'){
    axis=nextAdaptiveAxis();
    if(!axis){state.phase='pair';state.axisIndex=0;return renderTrial()}
    state.current=makeAdaptiveTrial(axis);
  }else{
    axis=nextPairAxis();
    if(!axis)return finish();
    state.current=makePairTrial(axis);
  }
  const x=state.current; state.trialStart=performance.now();
  const oddArea=document.getElementById('oddArea'), pairArea=document.getElementById('pairArea'), pairButtons=document.getElementById('pairButtons');
  if(x.type==='adaptive'){
    document.getElementById('questionTitle').textContent='다르게 보이는 색 하나를 선택하세요';
    document.getElementById('questionDesc').textContent=`${AXES[axis].label} 구별 · 현재 난이도 ${x.level+1}/7`;
    oddArea.innerHTML=''; oddArea.classList.remove('hidden'); pairArea.classList.add('hidden'); pairButtons.classList.add('hidden');
    x.colors.forEach((c,i)=>{const b=document.createElement('button');b.className='choice';b.style.background=c;b.setAttribute('aria-label',`${i+1}번 색`);b.onclick=()=>answerAdaptive(i);oddArea.appendChild(b)});
  }else{
    document.getElementById('questionTitle').textContent='두 색이 같아 보이나요, 다르게 보이나요?';
    document.getElementById('questionDesc').textContent=`${AXES[axis].label} 확인 문항`;
    oddArea.classList.add('hidden');pairArea.classList.remove('hidden');pairButtons.classList.remove('hidden');
    document.getElementById('pairA').style.background=x.a;document.getElementById('pairB').style.background=x.b;
  }
  document.getElementById('trialMeta').textContent=`측정 축: ${AXES[axis].label}`;
}
function record(correct,unsure=false){
  const x=state.current, rt=Math.round(performance.now()-state.trialStart);
  state.records.push({type:x.type,axis:x.axis,level:x.level,diff:x.diff,correct,unsure,responseMs:rt});
  if(x.type==='adaptive'){
    state.adaptiveDone[x.axis]++;
    if(unsure || !correct){state.correctStreak[x.axis]=0;state.level[x.axis]=clamp(state.level[x.axis]-1,0,6)}
    else{state.correctStreak[x.axis]++;if(state.correctStreak[x.axis]>=2){state.level[x.axis]=clamp(state.level[x.axis]+1,0,6);state.correctStreak[x.axis]=0}}
  }else state.pairDone[x.axis]++;
  renderTrial();
}
function answerAdaptive(i){record(i===state.current.target,false)}
function answerPair(ans){const correct=(ans==='same')===state.current.isSame;record(correct,false)}

document.querySelectorAll('[data-pair]').forEach(b=>b.onclick=()=>answerPair(b.dataset.pair));
document.getElementById('unsureBtn').onclick=()=>record(false,true);

document.getElementById('startBtn').onclick=()=>{
  if(!document.getElementById('calibCheck').checked){alert('먼저 회색 5단계가 구분되는지 확인해 주세요.');return}
  resetState();document.getElementById('intro').classList.add('hidden');document.getElementById('testScreen').classList.remove('hidden');renderTrial();
};

function axisMetrics(axis){
  const rows=state.records.filter(r=>r.axis===axis), adapt=rows.filter(r=>r.type==='adaptive'), pair=rows.filter(r=>r.type==='pair');
  const acc=rows.length?rows.filter(r=>r.correct).length/rows.length:0;
  const unsure=rows.filter(r=>r.unsure).length;
  // 가장 어려운 최근 6개 adaptive의 평균 level을 threshold proxy로 사용
  const tail=adapt.slice(-6); const avgLevel=tail.length?tail.reduce((s,r)=>s+r.level,0)/tail.length:0;
  const thresholdDiff=DIFFS[Math.round(clamp(avgLevel,0,6))];
  // confusion score: 낮은 정확도 + 낮은 달성 level(큰 색차 필요) + unsure 가중
  const levelPenalty=(6-avgLevel)/6;
  const confusion=Math.round(clamp(((1-acc)*.56 + levelPenalty*.36 + (unsure/Math.max(rows.length,1))*.08)*100,0,100));
  const avgRt=Math.round(rows.reduce((s,r)=>s+r.responseMs,0)/Math.max(rows.length,1));
  const pairAcc=pair.length?Math.round(pair.filter(r=>r.correct).length/pair.length*100):0;
  return {confusion,accuracy:Math.round(acc*100),thresholdHueDifference:thresholdDiff,avgResponseMs:avgRt,pairAccuracy:pairAcc,uncertainResponses:unsure};
}
function finish(){
  document.getElementById('testScreen').classList.add('hidden');document.getElementById('resultScreen').classList.remove('hidden');
  const metrics={protan:axisMetrics('protan'),deutan:axisMetrics('deutan'),tritan:axisMetrics('tritan')};
  const entries=Object.entries(metrics).sort((a,b)=>b[1].confusion-a[1].confusion);
  const top=entries[0], second=entries[1];
  const dominant=top[1].confusion>=35 && top[1].confusion-second[1].confusion>=8 ? top[0] : (top[1].confusion>=35?'mixed':'mild');
  const avgConf=Math.round((metrics.protan.confusion+metrics.deutan.confusion+metrics.tritan.confusion)/3);
  const profile={version:5,testType:'color-discrimination-profile',medicalDiagnosis:false,createdAt:new Date().toISOString(),dominantAxis:dominant,
    correctionStrength:Math.round(clamp(top[1].confusion*.9+avgConf*.1,10,90)),metrics,totalTrials:state.records.length,totalDurationSec:Math.round((Date.now()-state.startedAt)/1000)};
  state.profile=profile;
  const rg=document.getElementById('resultGrid');rg.innerHTML='';
  ['protan','deutan','tritan'].forEach(ax=>{const m=metrics[ax];const c=document.createElement('div');c.className='resultCard';c.innerHTML=`<strong>${AXES[ax].label}</strong><div class="score">${m.confusion}</div><div class="meter"><span style="width:${m.confusion}%"></span></div><div class="small" style="margin-top:10px">정답률 ${m.accuracy}% · 최소 구별 단계 약 ${m.thresholdHueDifference}° · 평균 반응 ${m.avgResponseMs}ms</div>`;rg.appendChild(c)});
  const label=dominant==='mixed'?'복합 혼동 경향':dominant==='mild'?'뚜렷한 단일 혼동 경향 없음':AXES[dominant].label+' 혼동 경향';
  document.getElementById('summary').innerHTML=`<b>프로필:</b> ${label}<br><b>권장 초기 보정 강도:</b> ${profile.correctionStrength}%<br><span class="small">이 값은 확장 프로그램의 초기 보정값으로 사용할 수 있으며, 실제 사용 중 사용자가 강도를 미세조정하도록 설계하는 것이 좋습니다.</span>`;
}

document.getElementById('saveBtn').onclick=async()=>{
  if(!state.profile) return;
  await chrome.storage.local.set({
    colorVisionProfile: state.profile,
    enabled: true,
    imageCorrection: true,
    visualCues: true,
    manualStrength: null
  });
  alert('프로필이 적용되었습니다. 이제 웹페이지에서 확장 프로그램 보정을 사용할 수 있습니다.');
};
document.getElementById('restartBtn').onclick=()=>location.reload();
