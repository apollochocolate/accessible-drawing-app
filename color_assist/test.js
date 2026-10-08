const AXES = {
  protan:{
    label:'적색계열',
    baseH:28,
    altDir:1,
    L:.63,
    C:.15
  },

  deutan:{
    label:'녹색계열',
    baseH:142,
    altDir:-1,
    L:.63,
    C:.14
  },

  tritan:{
    label:'청황계열',
    baseH:252,
    altDir:-1,
    L:.64,
    C:.13
  }
};


// 난이도 0(쉬움) ~ 6(매우 어려움)
const DIFFS = [
  52,
  38,
  27,
  19,
  13,
  8,
  5
];


const TOTAL_ADAPTIVE_PER_AXIS = 8;
const TOTAL_PAIR_PER_AXIS = 2;

const TOTAL_TRIALS =
  3 * (
    TOTAL_ADAPTIVE_PER_AXIS +
    TOTAL_PAIR_PER_AXIS
  );


let state;


// ============================================================
// 색각 유형 직접 선택
// ============================================================

let selectedPreset = null;


function selectPreset(axis){

  selectedPreset = axis;


  document
    .querySelectorAll('.profileOption')
    .forEach(button => {

      button.classList.toggle(
        'selected',
        button.dataset.profile === axis
      );

    });


  const selectedProfile =
    document.getElementById(
      'selectedProfile'
    );


  const applyPresetBtn =
    document.getElementById(
      'applyPresetBtn'
    );


  selectedProfile.classList.remove(
    'hidden'
  );


  selectedProfile.innerHTML =
    `선택한 유형: <b>${AXES[axis].label}</b>`;


  applyPresetBtn.classList.remove(
    'hidden'
  );

}


document
  .querySelectorAll('.profileOption')
  .forEach(button => {

    button.addEventListener(
      'click',
      () => {

        selectPreset(
          button.dataset.profile
        );

      }
    );

  });


// ============================================================
// 직접 선택한 색각 유형으로 프로필 생성
// ============================================================

function createPresetProfile(axis){

  return {

    version:5,

    testType:'preset',

    medicalDiagnosis:false,

    createdAt:
      new Date().toISOString(),

    dominantAxis:axis,

    // 직접 선택 프로필의 초기 보정 강도
    correctionStrength:50,

    metrics:{

      protan:{

        confusion:
          axis === 'protan'
            ? 100
            : 0,

        accuracy:null,

        thresholdHueDifference:null,

        avgResponseMs:null,

        pairAccuracy:null,

        uncertainResponses:null

      },


      deutan:{

        confusion:
          axis === 'deutan'
            ? 100
            : 0,

        accuracy:null,

        thresholdHueDifference:null,

        avgResponseMs:null,

        pairAccuracy:null,

        uncertainResponses:null

      },


      tritan:{

        confusion:
          axis === 'tritan'
            ? 100
            : 0,

        accuracy:null,

        thresholdHueDifference:null,

        avgResponseMs:null,

        pairAccuracy:null,

        uncertainResponses:null

      }

    },


    totalTrials:0,

    totalDurationSec:0

  };

}


// ============================================================
// 직접 선택한 프로필 저장
// ============================================================

async function savePresetProfile(){

  if(!selectedPreset){

    alert(
      '먼저 색각 유형을 선택해 주세요.'
    );

    return;

  }


  try{

    const profile =
      createPresetProfile(
        selectedPreset
      );


    await chrome.storage.local.set({

      colorVisionProfile:
        profile,

      enabled:true,

      imageCorrection:true,

      visualCues:true,

      manualStrength:null

    });


    alert(

      `${AXES[selectedPreset].label} 프로필이 적용되었습니다.\n\n` +

      '이제 웹페이지에서 선택한 색각 유형에 맞는 보정을 사용할 수 있습니다.'

    );


  }catch(error){

    console.error(
      '프로필 저장 실패:',
      error
    );


    alert(
      '프로필 저장에 실패했습니다.\n' +
      '확장 프로그램 페이지에서 실행하고 있는지 확인해 주세요.'
    );

  }

}


document
  .getElementById('applyPresetBtn')
  .addEventListener(
    'click',
    savePresetProfile
  );


// ============================================================
// 정밀 테스트 모드
// ============================================================

document
  .getElementById('testModeBtn')
  .addEventListener(
    'click',
    () => {

      document
        .getElementById('profileSelect')
        .classList.add('hidden');


      document
        .getElementById('intro')
        .classList.remove('hidden');

    }
  );


// ============================================================
// 프로필 초기화
// ============================================================

document
  .getElementById('resetProfileBtn')
  .addEventListener(
    'click',
    async () => {

      const confirmed =
        confirm(
          '저장된 색각 프로필을 초기화할까요?\n\n' +
          '색각 프로필만 삭제되며 다른 확장 프로그램 설정은 유지됩니다.'
        );


      if(!confirmed){

        return;

      }


      try{

        await chrome.storage.local.remove(
          'colorVisionProfile'
        );


        selectedPreset = null;


        document
          .querySelectorAll('.profileOption')
          .forEach(button => {

            button.classList.remove(
              'selected'
            );

          });


        document
          .getElementById('selectedProfile')
          .classList.add('hidden');


        document
          .getElementById('applyPresetBtn')
          .classList.add('hidden');


        const resetStatus =
          document.getElementById(
            'resetStatus'
          );


        resetStatus.textContent =
          '저장된 색각 프로필이 초기화되었습니다.';


        resetStatus.style.color =
          '#18864b';


        alert(
          '프로필이 초기화되었습니다.\n\n' +
          '새로운 색각 유형을 선택하거나 정밀 테스트를 진행하세요.'
        );


      }catch(error){

        console.error(
          '프로필 초기화 실패:',
          error
        );


        const resetStatus =
          document.getElementById(
            'resetStatus'
          );


        resetStatus.textContent =
          '프로필 초기화에 실패했습니다.';


        resetStatus.style.color =
          '#c93b3b';


        alert(
          '프로필 초기화에 실패했습니다.\n' +
          '확장 프로그램 페이지에서 실행하고 있는지 확인해 주세요.'
        );

      }

    }
  );


// ============================================================
// 기존 정밀 테스트
// ============================================================

function resetState(){

  state = {

    phase:'adaptive',

    axisOrder:
      shuffle([
        'protan',
        'deutan',
        'tritan'
      ]),

    axisIndex:0,


    adaptiveDone:{

      protan:0,
      deutan:0,
      tritan:0

    },


    pairDone:{

      protan:0,
      deutan:0,
      tritan:0

    },


    level:{

      protan:2,
      deutan:2,
      tritan:2

    },


    correctStreak:{

      protan:0,
      deutan:0,
      tritan:0

    },


    records:[],

    startedAt:
      Date.now(),

    trialStart:0,

    current:null

  };

}


function shuffle(a){

  return [
    ...a
  ].sort(
    () => Math.random() - .5
  );

}


function clamp(v,a,b){

  return Math.max(
    a,
    Math.min(b,v)
  );

}


function color(
  axis,
  hShift=0,
  cShift=0,
  lShift=0
){

  const x =
    AXES[axis];


  return `oklch(${
    clamp(
      x.L + lShift,
      .35,
      .85
    )
  } ${
    clamp(
      x.C + cShift,
      .035,
      .22
    )
  } ${
    ((x.baseH + hShift) % 360 + 360) % 360
  })`;

}


function getTotalDone(){

  return state.records.length;

}


function updateProgress(){

  const p =
    Math.min(
      100,
      getTotalDone() /
      TOTAL_TRIALS *
      100
    );


  document
    .getElementById(
      'progressFill'
    )
    .style.width =
      p + '%';


  document
    .getElementById(
      'phaseLabel'
    )
    .textContent =
      `${getTotalDone() + 1} / ${TOTAL_TRIALS}`;

}


// ============================================================
// Adaptive 다음 축
// ============================================================

function nextAdaptiveAxis(){

  for(
    let i = 0;
    i < state.axisOrder.length;
    i++
  ){

    const ax =
      state.axisOrder[
        (state.axisIndex + i) % 3
      ];


    if(
      state.adaptiveDone[ax] <
      TOTAL_ADAPTIVE_PER_AXIS
    ){

      state.axisIndex =
        (
          state.axisOrder.indexOf(ax) +
          1
        ) % 3;


      return ax;

    }

  }


  return null;

}


// ============================================================
// Pair 다음 축
// ============================================================

function nextPairAxis(){

  for(
    let i = 0;
    i < state.axisOrder.length;
    i++
  ){

    const ax =
      state.axisOrder[
        (state.axisIndex + i) % 3
      ];


    if(
      state.pairDone[ax] <
      TOTAL_PAIR_PER_AXIS
    ){

      state.axisIndex =
        (
          state.axisOrder.indexOf(ax) +
          1
        ) % 3;


      return ax;

    }

  }


  return null;

}


// ============================================================
// Adaptive 문제 생성
// ============================================================

function makeAdaptiveTrial(axis){

  const level =
    state.level[axis];


  const diff =
    DIFFS[level];


  const target =
    Math.floor(
      Math.random() * 4
    );


  const baseJ =
    (Math.random() - .5) * 2.4;


  const colors = [];


  for(
    let i = 0;
    i < 4;
    i++
  ){

    const lj =
      (Math.random() - .5) *
      .006;


    colors.push(

      i === target

        ? color(
            axis,
            AXES[axis].altDir *
            diff +
            baseJ,
            0,
            lj
          )

        : color(
            axis,
            baseJ,
            0,
            lj
          )

    );

  }


  return {

    type:'adaptive',

    axis,

    level,

    diff,

    target,

    colors

  };

}


// ============================================================
// Pair 문제 생성
// ============================================================

function makePairTrial(axis){

  const level =
    state.level[axis];


  const diff =
    DIFFS[
      clamp(
        level +
        Math.floor(
          Math.random() * 3
        ) -
        1,
        0,
        6
      )
    ];


  const isSame =
    Math.random() < .36;


  const baseJ =
    (Math.random() - .5) * 3;


  return {

    type:'pair',

    axis,

    level,

    diff,

    isSame,

    a:
      color(
        axis,
        baseJ
      ),

    b:
      isSame

        ? color(
            axis,
            baseJ
          )

        : color(
            axis,
            AXES[axis].altDir *
            diff +
            baseJ
          )

  };

}


// ============================================================
// 문제 출력
// ============================================================

function renderTrial(){

  updateProgress();


  let axis;


  if(
    state.phase ===
    'adaptive'
  ){

    axis =
      nextAdaptiveAxis();


    if(!axis){

      state.phase =
        'pair';


      state.axisIndex =
        0;


      return renderTrial();

    }


    state.current =
      makeAdaptiveTrial(
        axis
      );

  }else{

    axis =
      nextPairAxis();


    if(!axis){

      return finish();

    }


    state.current =
      makePairTrial(
        axis
      );

  }


  const x =
    state.current;


  state.trialStart =
    performance.now();


  const oddArea =
    document.getElementById(
      'oddArea'
    );


  const pairArea =
    document.getElementById(
      'pairArea'
    );


  const pairButtons =
    document.getElementById(
      'pairButtons'
    );


  if(
    x.type ===
    'adaptive'
  ){

    document
      .getElementById(
        'questionTitle'
      )
      .textContent =
        '다르게 보이는 색 하나를 선택하세요';


    document
      .getElementById(
        'questionDesc'
      )
      .textContent =
        `${AXES[axis].label} 구별 · 현재 난이도 ${x.level + 1}/7`;


    oddArea.innerHTML = '';


    oddArea
      .classList
      .remove('hidden');


    pairArea
      .classList
      .add('hidden');


    pairButtons
      .classList
      .add('hidden');


    x.colors.forEach(
      (c,i) => {

        const b =
          document.createElement(
            'button'
          );


        b.className =
          'choice';


        b.style.background =
          c;


        b.setAttribute(
          'aria-label',
          `${i + 1}번 색`
        );


        b.onclick =
          () => answerAdaptive(i);


        oddArea.appendChild(b);

      }
    );

  }else{

    document
      .getElementById(
        'questionTitle'
      )
      .textContent =
        '두 색이 같아 보이나요, 다르게 보이나요?';


    document
      .getElementById(
        'questionDesc'
      )
      .textContent =
        `${AXES[axis].label} 확인 문항`;


    oddArea
      .classList
      .add('hidden');


    pairArea
      .classList
      .remove('hidden');


    pairButtons
      .classList
      .remove('hidden');


    document
      .getElementById(
        'pairA'
      )
      .style.background =
        x.a;


    document
      .getElementById(
        'pairB'
      )
      .style.background =
        x.b;

  }


  document
    .getElementById(
      'trialMeta'
    )
    .textContent =
      `측정 축: ${AXES[axis].label}`;

}


// ============================================================
// 답변 기록
// ============================================================

function record(
  correct,
  unsure=false
){

  const x =
    state.current;


  const rt =
    Math.round(
      performance.now() -
      state.trialStart
    );


  state.records.push({

    type:x.type,

    axis:x.axis,

    level:x.level,

    diff:x.diff,

    correct,

    unsure,

    responseMs:rt

  });


  if(
    x.type ===
    'adaptive'
  ){

    state.adaptiveDone[
      x.axis
    ]++;


    if(
      unsure ||
      !correct
    ){

      state.correctStreak[
        x.axis
      ] = 0;


      state.level[
        x.axis
      ] =
        clamp(
          state.level[x.axis] - 1,
          0,
          6
        );

    }else{

      state.correctStreak[
        x.axis
      ]++;


      if(
        state.correctStreak[
          x.axis
        ] >= 2
      ){

        state.level[
          x.axis
        ] =
          clamp(
            state.level[x.axis] + 1,
            0,
            6
          );


        state.correctStreak[
          x.axis
        ] = 0;

      }

    }

  }else{

    state.pairDone[
      x.axis
    ]++;

  }


  renderTrial();

}


function answerAdaptive(i){

  record(
    i ===
    state.current.target,
    false
  );

}


function answerPair(ans){

  const correct =
    (ans === 'same') ===
    state.current.isSame;


  record(
    correct,
    false
  );

}


// Pair 버튼
document
  .querySelectorAll('[data-pair]')
  .forEach(
    b => {

      b.onclick =
        () =>
          answerPair(
            b.dataset.pair
          );

    }
  );


// 잘 모르겠음
document
  .getElementById(
    'unsureBtn'
  )
  .onclick =
    () =>
      record(
        false,
        true
      );


// ============================================================
// 정밀 테스트 시작
// ============================================================

document
  .getElementById(
    'startBtn'
  )
  .onclick =
    () => {


      if(
        !document
          .getElementById(
            'calibCheck'
          )
          .checked
      ){

        alert(
          '먼저 회색 5단계가 구분되는지 확인해 주세요.'
        );


        return;

      }


      resetState();


      document
        .getElementById(
          'intro'
        )
        .classList
        .add('hidden');


      document
        .getElementById(
          'profileSelect'
        )
        .classList
        .add('hidden');


      document
        .getElementById(
          'testScreen'
        )
        .classList
        .remove('hidden');


      renderTrial();

    };


// ============================================================
// 축별 결과 계산
// ============================================================

function axisMetrics(axis){

  const rows =
    state.records.filter(
      r =>
        r.axis === axis
    );


  const adapt =
    rows.filter(
      r =>
        r.type === 'adaptive'
    );


  const pair =
    rows.filter(
      r =>
        r.type === 'pair'
    );


  const acc =
    rows.length

      ? rows.filter(
          r =>
            r.correct
        ).length /
        rows.length

      : 0;


  const unsure =
    rows.filter(
      r =>
        r.unsure
    ).length;


  const tail =
    adapt.slice(-6);


  const avgLevel =
    tail.length

      ? tail.reduce(
          (s,r) =>
            s + r.level,
          0
        ) /
        tail.length

      : 0;


  const thresholdDiff =
    DIFFS[
      Math.round(
        clamp(
          avgLevel,
          0,
          6
        )
      )
    ];


  const levelPenalty =
    (6 - avgLevel) /
    6;


  const confusion =
    Math.round(

      clamp(

        (
          (1 - acc) * .56 +

          levelPenalty * .36 +

          (
            unsure /
            Math.max(
              rows.length,
              1
            )
          ) * .08

        ) * 100,

        0,
        100

      )

    );


  const avgRt =
    Math.round(

      rows.reduce(
        (s,r) =>
          s + r.responseMs,
        0
      ) /

      Math.max(
        rows.length,
        1
      )

    );


  const pairAcc =
    pair.length

      ? Math.round(

          pair.filter(
            r =>
              r.correct
          ).length /

          pair.length *

          100

        )

      : 0;


  return {

    confusion,

    accuracy:
      Math.round(
        acc * 100
      ),

    thresholdHueDifference:
      thresholdDiff,

    avgResponseMs:
      avgRt,

    pairAccuracy:
      pairAcc,

    uncertainResponses:
      unsure

  };

}


// ============================================================
// 테스트 종료
// ============================================================

function finish(){

  document
    .getElementById(
      'testScreen'
    )
    .classList
    .add('hidden');


  document
    .getElementById(
      'resultScreen'
    )
    .classList
    .remove('hidden');


  const metrics = {

    protan:
      axisMetrics(
        'protan'
      ),

    deutan:
      axisMetrics(
        'deutan'
      ),

    tritan:
      axisMetrics(
        'tritan'
      )

  };


  const entries =
    Object.entries(
      metrics
    ).sort(
      (a,b) =>
        b[1].confusion -
        a[1].confusion
    );


  const top =
    entries[0];


  const second =
    entries[1];


  const dominant =

    top[1].confusion >= 35 &&

    top[1].confusion -
    second[1].confusion >= 8

      ? top[0]

      :

        (
          top[1].confusion >= 35
            ? 'mixed'
            : 'mild'
        );


  const avgConf =
    Math.round(

      (
        metrics.protan.confusion +

        metrics.deutan.confusion +

        metrics.tritan.confusion

      ) / 3

    );


  const profile = {

    version:5,

    testType:
      'color-discrimination-profile',

    medicalDiagnosis:false,

    createdAt:
      new Date().toISOString(),

    dominantAxis:
      dominant,

    correctionStrength:
      Math.round(

        clamp(

          top[1].confusion * .9 +

          avgConf * .1,

          10,
          90

        )

      ),

    metrics,

    totalTrials:
      state.records.length,

    totalDurationSec:
      Math.round(

        (
          Date.now() -
          state.startedAt
        ) / 1000

      )

  };


  state.profile =
    profile;


  const rg =
    document.getElementById(
      'resultGrid'
    );


  rg.innerHTML = '';


  [
    'protan',
    'deutan',
    'tritan'
  ]
  .forEach(
    ax => {

      const m =
        metrics[ax];


      const c =
        document.createElement(
          'div'
        );


      c.className =
        'resultCard';


      c.innerHTML = `

        <strong>
          ${AXES[ax].label}
        </strong>

        <div class="score">
          ${m.confusion}
        </div>

        <div class="meter">

          <span
            style="width:${m.confusion}%">
          </span>

        </div>

        <div
          class="small"
          style="margin-top:10px">

          정답률 ${m.accuracy}%

          · 최소 구별 단계 약
          ${m.thresholdHueDifference}°

          · 평균 반응
          ${m.avgResponseMs}ms

        </div>

      `;


      rg.appendChild(c);

    }
  );


  const label =

    dominant === 'mixed'

      ? '복합 혼동 경향'

      :

        dominant === 'mild'

          ? '뚜렷한 단일 혼동 경향 없음'

          :

            AXES[dominant].label +
            ' 혼동 경향';


  document
    .getElementById(
      'summary'
    )
    .innerHTML = `

      <b>프로필:</b>
      ${label}

      <br>

      <b>권장 초기 보정 강도:</b>
      ${profile.correctionStrength}%

      <br>

      <span class="small">

        이 값은 확장 프로그램의 초기 보정값으로
        사용할 수 있으며,
        실제 사용 중 사용자가 강도를
        미세조정하도록 설계하는 것이 좋습니다.

      </span>

    `;

}


// ============================================================
// 테스트 결과 저장
// ============================================================

document
  .getElementById(
    'saveBtn'
  )
  .onclick =
    async () => {


      if(
        !state.profile
      ){

        return;

      }


      try{

        await chrome.storage.local.set({

          colorVisionProfile:
            state.profile,

          enabled:true,

          imageCorrection:true,

          visualCues:true,

          manualStrength:null

        });


        alert(

          '프로필이 적용되었습니다. ' +

          '이제 웹페이지에서 확장 프로그램 보정을 사용할 수 있습니다.'

        );


      }catch(error){

        console.error(
          '프로필 저장 실패:',
          error
        );


        alert(
          '프로필 저장에 실패했습니다. ' +
          '확장 프로그램 페이지에서 실행하고 있는지 확인해 주세요.'
        );

      }

    };


// 다시 테스트
document
  .getElementById(
    'restartBtn'
  )
  .onclick =
    () =>
      location.reload();