export default function wireGlobe(settings, goto) {
  const detail = document.querySelector('[data-globe-detail]');
  const map = document.querySelector('.globe .map');
  const aus = document.querySelector('.globe .map .aus');
  const vic = document.querySelector('.globe .map .vic');
  const melb = document.querySelector('.globe .map .melb');
  const beacon = document.querySelector('[data-beacon]');
  const markersRoot = document.querySelector('[data-markers]');

  // Places: name with approximate polar coordinates relative to radar center (r in %, theta in degrees from +x clockwise)
  const places = [
    { name: '47 Claremont St', r: 36, theta: 210 },
    { name: '8 Murphy St', r: 28, theta: 250 },
    { name: 'Neds Bakery', r: 40, theta: 190 },
    { name: 'France-Soir', r: 34, theta: 230 },
    { name: '101 Collins', r: 46, theta: 320 },
    { name: 'Mt Erica Hotel', r: 52, theta: 170 },
  ];

  function polarToPercent(rPct, thetaDeg) {
    // Percentage-based positioning within markersRoot (0-100%).
    // Center is at 50%/50%, radius is 50% of the container.
    const rad = (thetaDeg * Math.PI) / 180;
    const r = (rPct / 100) * 50; // percent of half-size
    const left = 50 + r * Math.cos(-rad);
    const top = 50 + r * Math.sin(-rad);
    return { left, top };
  }

  function spawnMarkers() {
    markersRoot.innerHTML = '';
    for (const p of places) {
      const { left, top } = polarToPercent(p.r, p.theta);
      const m = document.createElement('div');
      m.className = 'marker';
      m.style.left = `${left}%`;
      m.style.top = `${top}%`;
      m.dataset.theta = String(p.theta);
      m.innerHTML = `<div class="dot"></div><div class="label">${p.name}</div>`;
      // Make interactive: click/keyboard moves the beacon focus
      m.setAttribute('role', 'button');
      m.setAttribute('tabindex', '0');
      const activate = () => {
        if (window.WorldSim && typeof window.WorldSim.setFocus === 'function') {
          window.WorldSim.setFocus({ x: left, y: top, ripple: true });
        }
        const caption = document.querySelector('.globe .caption .detail');
        if (caption) caption.textContent = `Target locked: ${p.name}`;
        m.classList.add('active');
      };
      m.addEventListener('click', activate);
      m.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          activate();
        }
      });
      markersRoot.appendChild(m);
    }
  }
  spawnMarkers();

  // Richer rotating detail copy
  const lines = [
    'Thermal sweep over Melbourne grid…',
    'Rail, water, arterial overlays…',
    'South Yarra corridor resolved…',
    'City lights telemetry stabilized…',
    'Tram clusters stabilized on 78/72 lines…',
    'Yarra bend thermal signatures rising…'
  ];
  let i = 0;
  const run = () => {
    detail.textContent = lines[i % lines.length];
    i += 1;
    if (i > (settings.reducedMotion ? 2 : 5)) {
      goto('arrival');
      return;
    }
    window.setTimeout(run, settings.reducedMotion ? 200 : 700);
  };
  run();

  // Parallax (disabled for reduced motion)
  if (!settings.reducedMotion) {
    const center = () => {
      const rect = map.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    };
    const onMove = (e) => {
      const c = center();
      const dx = (e.clientX - c.x) / window.innerWidth;
      const dy = (e.clientY - c.y) / window.innerHeight;
      aus.style.transform = `translate(${dx * 6}px, ${dy * 6}px)`;
      vic.style.transform = `translate(${dx * 10}px, ${dy * 10}px)`;
      melb.style.transform = `translate(${dx * 14}px, ${dy * 14}px)`;
    };
    window.addEventListener('mousemove', onMove, { passive: true });
  }

  // Expose a simple focus setter with smooth move and ripple
  window.WorldSim = window.WorldSim || {};
  window.WorldSim.setFocus = ({ x = '52%', y = '58%', ripple = true } = {}) => {
    if (!beacon) return;
    beacon.style.transition = settings.reducedMotion ? 'none' : 'left .35s ease, top .35s ease';
    beacon.style.left = typeof x === 'number' ? `${x}%` : x;
    beacon.style.top = typeof y === 'number' ? `${y}%` : y;
    if (ripple && !settings.reducedMotion) {
      beacon.style.animation = 'none';
      // trigger reflow to restart animation
      // eslint-disable-next-line no-unused-expressions
      beacon.offsetHeight;
      beacon.style.animation = 'pulse 2.4s ease-out infinite';
    }
  };

  // Reveal markers when the sweep passes near their angle
  if (!settings.reducedMotion) {
    const sweepEl = document.querySelector('.globe .sweep');
    let lastAngle = 0;
    const revealThreshold = 10; // degrees
    function readAngle() {
      // Use computed transform to estimate rotation angle (fallback: time-based)
      // Since direct read is complex, we simulate by time delta
      const t = Date.now() / 1000; // seconds
      const angle = (t * 360 / 3.2) % 360; // matches 3.2s per rotation
      const markers = Array.from(markersRoot.querySelectorAll('.marker'));
      for (const m of markers) {
        const theta = Number(m.dataset.theta);
        // Compute shortest distance around circle
        let d = Math.abs(((theta - angle + 540) % 360) - 180);
        if (d < revealThreshold) {
          m.classList.add('active');
        }
      }
      lastAngle = angle;
      requestAnimationFrame(readAngle);
    }
    requestAnimationFrame(readAngle);
  }
}
