
const $ = (id) => document.getElementById(id);

const defaults = {
  enabled: true,
  visualCues: true,
  imageCorrection: true,
  manualStrength: null,
  colorVisionProfile: null
};

function profileLabel(profile) {
  if (!profile) return "테스트 필요";
  const axis = profile.dominantAxis;
  if (axis === "protan") return "적색계열 혼동 경향";
  if (axis === "deutan") return "녹색계열 혼동 경향";
  if (axis === "tritan") return "청황계열 혼동 경향";
  if (axis === "mixed") return "복합 혼동 경향";
  return "뚜렷한 단일 혼동 경향 없음";
}

function profileDetail(profile) {
  if (!profile?.metrics) return "색 구별 테스트를 먼저 진행해 주세요.";
  const p = profile.metrics.protan?.confusion ?? 0;
  const d = profile.metrics.deutan?.confusion ?? 0;
  const t = profile.metrics.tritan?.confusion ?? 0;
  return `적색 ${p} · 녹색 ${d} · 청황 ${t}`;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  return tabs[0];
}

async function send(message) {
  const tab = await getActiveTab();
  if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
  try { await chrome.tabs.sendMessage(tab.id, message); } catch (_) {}
}

async function load() {
  const data = await chrome.storage.local.get(defaults);
  $("enabled").checked = data.enabled;
  $("visualCues").checked = data.visualCues;
  $("imageCorrection").checked = data.imageCorrection;

  const profile = data.colorVisionProfile;
  $("profileName").textContent = profileLabel(profile);
  $("profileDetail").textContent = profileDetail(profile);

  const strength = data.manualStrength ?? profile?.correctionStrength ?? 0;
  $("strength").value = strength;
  $("strengthValue").textContent = `${strength}%`;

  if (!profile) {
    $("enabled").checked = false;
    $("enabled").disabled = true;
    $("strength").disabled = true;
    $("visualCues").disabled = true;
    $("imageCorrection").disabled = true;
  }
}

$("openTest").addEventListener("click", () => chrome.runtime.openOptionsPage());

$("enabled").addEventListener("change", async (e) => {
  await chrome.storage.local.set({enabled: e.target.checked});
  await send({type: "SET_ENABLED", value: e.target.checked});
});

$("imageCorrection").addEventListener("change", async (e) => {
  await chrome.storage.local.set({imageCorrection: e.target.checked});
  await send({type: "SET_IMAGE_CORRECTION", value: e.target.checked});
});

$("visualCues").addEventListener("change", async (e) => {
  await chrome.storage.local.set({visualCues: e.target.checked});
  await send({type: "SET_VISUAL_CUES", value: e.target.checked});
});

$("strength").addEventListener("input", (e) => {
  $("strengthValue").textContent = `${e.target.value}%`;
});

$("strength").addEventListener("change", async (e) => {
  const value = Number(e.target.value);
  await chrome.storage.local.set({manualStrength: value});
  await send({type: "SET_STRENGTH", value});
});

$("reanalyze").addEventListener("click", () => send({type: "REANALYZE"}));
$("resetPage").addEventListener("click", () => send({type: "RESTORE"}));

load();
