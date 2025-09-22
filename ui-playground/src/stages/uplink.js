export default function wireUplink(settings, goto) {
  const uplinkFill = document.querySelector('[data-uplink-fill]');
  const uplinkVal = document.querySelector('[data-uplink-val]');
  const uplinkStatus = document.querySelector('[data-uplink-status]');
  const packetsRoot = document.querySelector('[data-uplink-packets]');
  let uplinkProgress = 0;
  const statuses = [
    'Triangulating orbital vector…',
    'Locking population grid…',
    'Deploying ground telemetry…',
    'Normalizing signal…',
    'Uplink established.'
  ];
  let statusIdx = 0;
  function spawnPacket() {
    if (settings.reducedMotion || !packetsRoot) return;
    const y = 20 + Math.random() * 60; // percent
    const x = -10 + Math.random() * 10; // start near left
    const el = document.createElement('div');
    el.className = 'packet';
    el.style.left = `${x}%`;
    el.style.top = `${y}%`;
    packetsRoot.appendChild(el);
    window.setTimeout(() => el.remove(), 1600);
  }
  function pulseBars(progress) {
    const bars = document.querySelectorAll('.uplink .comms .bars span');
    const level = Math.floor(1 + (progress / 100) * 3);
    bars.forEach((b, i) => {
      b.style.background = i < level ? 'var(--accent2)' : 'rgba(255,255,255,.14)';
      b.style.boxShadow = i < level ? '0 0 8px rgba(123,212,99,.4)' : 'none';
    });
  }
  const step = () => {
    uplinkProgress = Math.min(100, uplinkProgress + (Math.random() * 6 + 5));
    uplinkFill.style.width = `${uplinkProgress}%`;
    uplinkVal.textContent = `${Math.floor(uplinkProgress)}%`;
    if (!settings.reducedMotion && Math.random() > 0.5) spawnPacket();
    pulseBars(uplinkProgress);
    // Occasionally rotate status line for a livelier feel
    if (!settings.reducedMotion && Math.random() > 0.65) {
      statusIdx = Math.min(statuses.length - 1, statusIdx + 1);
      uplinkStatus.textContent = statuses[statusIdx];
    } else {
      // Ensure logical status progression as a fallback
      if (uplinkProgress < 50) uplinkStatus.textContent = 'Locking population grid…';
      else if (uplinkProgress < 85) uplinkStatus.textContent = 'Deploying ground telemetry…';
      else uplinkStatus.textContent = 'Uplink established.';
    }
    if (uplinkProgress >= 100) {
      goto('globe');
      return;
    }
    window.setTimeout(step, settings.reducedMotion ? 90 : 320);
  };
  step();
}
