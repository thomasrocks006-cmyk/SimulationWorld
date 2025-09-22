const root = document.documentElement;
const stageContainer = document.getElementById('stage-container');
const syncBadge = document.querySelector('[data-sync-badge]');
const lastRunEl = document.querySelector('[data-last-run]');

const STAGES = ['preflight','uplink','globe','arrival'];

async function loadStage(name) {
  const html = await fetch(`/src/stages/${name}.html`).then(r=>r.text());
  stageContainer.innerHTML = html;
}

function setStage(name) {
  // Toggle classes/aria in current DOM
  document.querySelectorAll('.stage').forEach(el => {
    const active = el.getAttribute('data-stage') === name;
    el.classList.toggle('active', active);
    el.setAttribute('aria-hidden', active ? 'false' : 'true');
  });
}

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const SETTINGS_KEY = 'worldsim:settings:v1';
const defaultSettings = { displayMode: 'windowed', aspectRatio: 'auto', uiScale: 1, letterbox: true, audio: { musicVolume: 0.7, sfxVolume: 0.8, muted: false }, reducedMotion: prefersReduced };
function loadSettings(){ try{ const raw=localStorage.getItem(SETTINGS_KEY); return raw? { ...defaultSettings, ...JSON.parse(raw)} : { ...defaultSettings }; }catch{return { ...defaultSettings };}}
function saveSettings(s){ try{ localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)); }catch{} }
function applySettings(s){ root.style.setProperty('--ui-scale', String(s.uiScale)); root.style.setProperty('--aspect', s.aspectRatio === 'auto' ? 'auto' : s.aspectRatio.replace(':',' / ')); document.body.classList.toggle('letterbox', !!s.letterbox); if (s.reducedMotion) document.body.classList.add('reduced-motion'); else document.body.classList.remove('reduced-motion'); }

let settings = loadSettings();
applySettings(settings);

// Modal wiring
const settingsBtn = document.querySelector('[data-open-settings]');
const modal = document.querySelector('.modal[data-modal]');
const dialog = document.querySelector('.modal .dialog');
function openModal(){ modal.setAttribute('aria-hidden','false'); trapFocus(dialog); document.querySelectorAll('[data-setting]').forEach(inp=>{ const path=inp.name.split('.'); let v=settings; for(const p of path) v=v?.[p]; if (typeof v === 'boolean') inp.checked=v; else inp.value=v; }); }
function closeModal(){ modal.setAttribute('aria-hidden','true'); }
settingsBtn?.addEventListener('click', openModal);
document.querySelectorAll('[data-close]').forEach(el=> el.addEventListener('click', closeModal));
modal.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
document.querySelectorAll('[data-setting]').forEach(inp=>{
  inp.addEventListener('input', ()=>{
    const path = inp.name.split('.'); let ref=settings; for(let i=0;i<path.length-1;i++) ref=ref[path[i]]; const key=path[path.length-1];
    ref[key] = (inp.type==='checkbox') ? inp.checked : (inp.type==='range' ? Number(inp.value) : inp.value);
    saveSettings(settings); applySettings(settings);
  });
});

function trapFocus(container){ const focusables=()=> Array.from(container.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')).filter(el=>!el.hasAttribute('disabled')); const first=()=>focusables()[0]; const last=()=>focusables()[focusables().length-1]; first()?.focus(); container.addEventListener('keydown', e=>{ if(e.key!=='Tab') return; const f=focusables(); if(!f.length) return; const i=f.indexOf(document.activeElement); if(e.shiftKey && (i<=0)){ e.preventDefault(); last().focus(); } else if(!e.shiftKey && (i===f.length-1)){ e.preventDefault(); first().focus(); } }); }

async function safeFetch(url, opts={}){ try { const merged = { headers: { 'Content-Type': 'application/json', ...(opts.headers||{}) }, ...opts }; if (merged.body && typeof merged.body !== 'string') merged.body = JSON.stringify(merged.body); const res = await fetch(url, merged); if (!res.ok) throw new Error('HTTP '+res.status); const ct = res.headers.get('content-type')||''; return ct.includes('application/json') ? await res.json() : await res.text(); } catch (e) { throw e; } }

async function hydrateTelemetry(){
  try { const data = await safeFetch('/api/scenarios'); syncBadge.textContent='API: Connected'; if (data?.lastRun?.startedAt){ const d=new Date(data.lastRun.startedAt); lastRunEl.textContent = `Last run: ${d.toLocaleString()}`; } else { lastRunEl.textContent='Last run: —'; } }
  catch { syncBadge.textContent='API: Disconnected'; lastRunEl.textContent='Last run: —'; }
}

function wirePreflight(){
  const preflightFill = document.querySelector('[data-preflight-fill]'); const preflightVal = document.querySelector('[data-preflight-val]'); const skipPreflightBtn = document.querySelector('[data-skip-preflight]');
  let preflightProgress = 0;
  function tickPreflight(){ if (settings.reducedMotion){ preflightProgress=100; } else { preflightProgress = Math.min(100, preflightProgress + (Math.random()*8 + 6)); } preflightFill.style.width = `${preflightProgress}%`; preflightVal.textContent = `${Math.floor(preflightProgress)}%`; if (preflightProgress >= 100){ goto('uplink'); return; } window.setTimeout(tickPreflight, settings.reducedMotion ? 80 : 280); }
  skipPreflightBtn?.addEventListener('click', ()=>{ preflightProgress=100; tickPreflight(); });
  window.setTimeout(tickPreflight, 350);
}

function wireUplink(){
  const uplinkFill = document.querySelector('[data-uplink-fill]'); const uplinkVal = document.querySelector('[data-uplink-val]'); const uplinkStatus = document.querySelector('[data-uplink-status]');
  let uplinkProgress = 0;
  const step = () => {
    uplinkProgress = Math.min(100, uplinkProgress + (Math.random()*6 + 5));
    uplinkFill.style.width = `${uplinkProgress}%`;
    uplinkVal.textContent = `${Math.floor(uplinkProgress)}%`;
    if (uplinkProgress < 50) uplinkStatus.textContent = 'Locking population grid…';
    else if (uplinkProgress < 85) uplinkStatus.textContent = 'Deploying ground telemetry…';
    else uplinkStatus.textContent = 'Uplink established.';
    if (uplinkProgress >= 100){ goto('globe'); return; }
    window.setTimeout(step, settings.reducedMotion ? 90 : 320);
  };
  step();
}

function wireGlobe(){
  const detail = document.querySelector('[data-globe-detail]');
  const lines = [ 'Thermal sweep over Melbourne grid…', 'Rail, water, arterial overlays…', 'South Yarra corridor resolved…' ];
  let i=0;
  const run = () => { detail.textContent = lines[i % lines.length]; i += 1; if (i > (settings.reducedMotion ? 2 : 5)) { goto('arrival'); return; } window.setTimeout(run, settings.reducedMotion ? 200 : 700); };
  run();
}

function wireArrival(){
  const modeButtons = Array.from(document.querySelectorAll('.modes [data-mode]'));
  let launchMode='narrative';
  modeButtons.forEach(b=> b.addEventListener('click', ()=>{ modeButtons.forEach(x=>x.classList.toggle('active', x===b)); launchMode=b.dataset.mode; }));
  const enterBtn = document.querySelector('[data-enter-hub]');
  enterBtn?.addEventListener('click', async () => {
    try { const resp = await safeFetch('/api/simulations/launch', { method:'POST', body: { scenarioId:'prime-timeline', mode:launchMode, start:'2025-09-20', until:'2025-09-27', step:'day', seed:1337, interactive:false } }); if (resp?.id){ pollStatus(resp.id); } }
    catch (err) { console.warn('Launch failed', err); }
  });
}

async function pollStatus(id){ let done=false; while(!done){ try { const s = await safeFetch(`/api/simulations/${id}`); const pct = Math.round(((s.progress||0)*100)); document.querySelector('[data-sync-badge]').textContent = `Sim: ${s.status} ${pct}%`; if (s.status==='completed' || s.status==='failed') done=true; } catch { document.querySelector('[data-sync-badge]').textContent='Sim: error'; done=true; } await new Promise(r=> setTimeout(r, 1000)); } }

async function goto(name){
  await loadStage(name);
  setStage(name);
  // Dynamically import and run the stage logic
  try {
    const mod = await import(`./stages/${name}.js`);
    if (typeof mod.default === 'function') {
      mod.default(settings, goto);
    }
  } catch (e) {
    console.warn(`No JS module for stage ${name}`, e);
  }
}

// init
hydrateTelemetry();
goto('preflight');
