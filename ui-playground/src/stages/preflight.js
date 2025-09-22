export default function wirePreflight(settings, goto) {
  const preflightFill = document.querySelector('[data-preflight-fill]');
  const preflightVal = document.querySelector('[data-preflight-val]');
  const preflightCopy = document.querySelector('[data-preflight-copy]');
  const skipPreflightBtn = document.querySelector('[data-skip-preflight]');
  const blipsRoot = document.querySelector('[data-pf-blips]');
  let preflightProgress = 0;
  const copyLines = [
    'Calibrating orbital sweep…',
    'Thermal lens focusing…',
    'Attitude control stable…',
    'Telemetry link nominal…',
    'Inertial reference aligned…'
  ];
  let copyIdx = 0;
  function setProgressRing(pct) {
    const deg = Math.max(0, Math.min(360, (pct / 100) * 360));
    const ring = document.querySelector('.preflight .orbit .progress-ring');
    if (ring) ring.style.background = `conic-gradient(var(--accent2) 0 ${deg}deg, rgba(255,255,255,.08) ${deg}deg 360deg)`;
  }
  function spawnBlip(pct) {
    if (settings.reducedMotion || !blipsRoot) return;
    // Map progress percent to angle on the orbit
    const theta = (pct / 100) * 360 - 90; // start at top
    const rad = (theta * Math.PI) / 180;
    const r = 45; // percent of half-size
    const left = 50 + r * Math.cos(rad);
    const top = 50 + r * Math.sin(rad);
    const el = document.createElement('div');
    el.className = 'blip';
    el.style.left = `${left}%`;
    el.style.top = `${top}%`;
    blipsRoot.appendChild(el);
    window.setTimeout(() => el.remove(), 1200);
  }
  function tickPreflight() {
    if (settings.reducedMotion) {
      preflightProgress = 100;
    } else {
      preflightProgress = Math.min(100, preflightProgress + (Math.random() * 8 + 6));
    }
    preflightFill.style.width = `${preflightProgress}%`;
    preflightVal.textContent = `${Math.floor(preflightProgress)}%`;
    setProgressRing(preflightProgress);
    if (!settings.reducedMotion && Math.random() > 0.45) spawnBlip(preflightProgress);
    if (!settings.reducedMotion && Math.random() > 0.6) {
      copyIdx = (copyIdx + 1) % copyLines.length;
      if (preflightCopy) preflightCopy.textContent = copyLines[copyIdx];
    }
    if (preflightProgress >= 100) {
      goto('uplink');
      return;
    }
    window.setTimeout(tickPreflight, settings.reducedMotion ? 80 : 280);
  }
  skipPreflightBtn?.addEventListener('click', () => {
    preflightProgress = 100;
    tickPreflight();
  });
  window.setTimeout(tickPreflight, 350);
}
