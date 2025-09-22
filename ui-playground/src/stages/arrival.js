export default function wireArrival(settings, goto) {
  const modeButtons = Array.from(document.querySelectorAll('.modes [data-mode]'));
  let launchMode = 'narrative';
  modeButtons.forEach(b => b.addEventListener('click', () => {
    modeButtons.forEach(x => x.classList.toggle('active', x === b));
    launchMode = b.dataset.mode;
    const modeLabel = document.querySelector('[data-arrival-mode]');
    if (modeLabel) modeLabel.textContent = launchMode;
  }));
  // Optional gentle shimmer on hero horizon
  if (!settings.reducedMotion) {
    const horizon = document.querySelector('.arrival .hero .horizon');
    if (horizon) {
      horizon.animate([
        { opacity: .4 },
        { opacity: .7 },
        { opacity: .4 }
      ], { duration: 6000, iterations: Infinity, easing: 'ease-in-out' });
    }
    // Slow tram animation guard
    const tram = document.querySelector('.arrival .hero .tram');
    if (tram) {
      tram.style.animationDuration = '10s';
    }
  }
  const enterBtn = document.querySelector('[data-enter-hub]');
  enterBtn?.addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/simulations/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenarioId: 'prime-timeline',
          mode: launchMode,
          start: '2025-09-20',
          until: '2025-09-27',
          step: 'day',
          seed: 1337,
          interactive: false
        })
      });
      const data = await resp.json();
      if (data?.id) pollStatus(data.id);
    } catch (err) {
      console.warn('Launch failed', err);
    }
  });
  // Small helper to add feed lines
  function addFeed(line) {
    const ul = document.querySelector('[data-activity-feed]');
    if (!ul) return;
    const li = document.createElement('li');
    const t = new Date();
    const hh = String(t.getHours()).padStart(2,'0');
    const mm = String(t.getMinutes()).padStart(2,'0');
    li.innerHTML = `<span class="time">${hh}:${mm}</span> ${line}`;
    ul.prepend(li);
  }
  // Interactivity: hover nodes to glow, click to pin
  const nodes = Array.from(document.querySelectorAll('.arrival .hero .map .node'));
  nodes.forEach(n => {
    n.addEventListener('mouseenter', () => n.classList.add('active'));
    n.addEventListener('mouseleave', () => n.classList.remove('active'));
    n.addEventListener('click', () => {
      nodes.forEach(x => x.classList.remove('pinned'));
      n.classList.add('pinned');
      addFeed(`${n.dataset.node || n.textContent} highlighted.`);
    });
  });

  // KPI card: sparkline + live toggle
  const kpiCard = document.querySelector('[data-kpis]');
  const sparkRoot = document.querySelector('[data-kpi-spark]');
  const liveBtn = document.querySelector('[data-kpi-live]');
  let sparkValues = Array.from({length: 16}, () => 20 + Math.random()*60);
  function renderSpark() {
    if (!sparkRoot) return;
    sparkRoot.innerHTML = '';
    const max = 100;
    sparkValues.forEach(v => {
      const bar = document.createElement('span');
      bar.style.position = 'absolute';
      bar.style.bottom = '0';
      bar.style.width = `${100/sparkValues.length}%`;
      bar.style.left = `${(sparkRoot.children.length)*(100/sparkValues.length)}%`;
      bar.style.height = `${(v/max)*100}%`;
      bar.style.background = 'var(--accent2)';
      bar.style.opacity = '.85';
      sparkRoot.appendChild(bar);
    });
  }
  renderSpark();
  let live = false; let sparkTimer;
  liveBtn?.addEventListener('click', () => {
    live = !live; if (kpiCard) kpiCard.dataset.live = String(live);
    if (live) {
      sparkTimer = setInterval(() => {
        sparkValues.push(20 + Math.random()*60);
        sparkValues = sparkValues.slice(-16);
        renderSpark();
        // gently vary KPIs
        const bump = (sel, delta=1) => {
          const el = document.querySelector(sel); if (!el) return;
          const num = parseFloat(el.textContent.replace(/[^0-9.-]/g,''));
          const next = Math.max(0, num + (Math.random()-.5)*delta);
          el.textContent = isNaN(next) ? el.textContent : next.toFixed(1);
        };
        bump('[data-kpi-tram]', .3);
        bump('[data-kpi-sent]', .2);
        bump('[data-kpi-pop]', 2);
        bump('[data-kpi-foot]', 40);
      }, 1000);
    } else {
      clearInterval(sparkTimer);
    }
  });

  // Neighborhood Signals: chips drive mini bars
  const chipsRoot = document.querySelector('[data-signal-chips]');
  const barsRoot = document.querySelector('[data-signal-bars]');
  function renderBars(values) {
    if (!barsRoot) return;
    barsRoot.innerHTML = '';
    values.forEach(v => {
      const s = document.createElement('span');
      s.style.height = `${v}%`;
      barsRoot.appendChild(s);
    });
  }
  const signalPresets = {
    'chapel-footfall': Array.from({length:8}, () => 40+Math.random()*50),
    'yarra-traffic': Array.from({length:8}, () => 20+Math.random()*60),
    'retail-sentiment': Array.from({length:8}, () => 30+Math.random()*40),
    'cafe-occupancy': Array.from({length:8}, () => 25+Math.random()*55)
  };
  renderBars(signalPresets['chapel-footfall']);
  chipsRoot?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-signal]');
    if (!btn) return;
    chipsRoot.querySelectorAll('.chip').forEach(c => c.classList.toggle('active', c===btn));
    const key = btn.dataset.signal;
    renderBars(signalPresets[key] || []);
  });
  async function pollStatus(id) {
    let done = false;
    while (!done) {
      try {
        const s = await fetch(`/api/simulations/${id}`).then(r => r.json());
        const pct = Math.round(((s.progress || 0) * 100));
        document.querySelector('[data-sync-badge]').textContent = `Sim: ${s.status} ${pct}%`;
        if (s.status === 'running' && Math.random() > .7) addFeed('Background processing step completed.');
        if (s.status === 'completed' || s.status === 'failed') done = true;
      } catch {
        document.querySelector('[data-sync-badge]').textContent = 'Sim: error';
        done = true;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  }
}
