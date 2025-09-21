(() => {
  const introScreen = document.getElementById('intro-screen');
  const mainMenu = document.getElementById('main-menu');
  const continueBtn = document.getElementById('continue-btn');
  const panelOverlay = document.getElementById('panel-container');
  const panelShade = panelOverlay.querySelector('.panel-shade');
  const panelWrapper = panelOverlay.querySelector('.panel-wrapper');
  const panels = Array.from(panelWrapper.querySelectorAll('.panel'));
  const menuButtons = Array.from(document.querySelectorAll('[data-open]'));
  const closeTriggers = Array.from(panelOverlay.querySelectorAll('[data-close]'));
  const scanlinesLayer = document.querySelector('.scanlines');
  const scanlinesToggle = panelOverlay.querySelector(
    '[data-panel="settings"] input[type="checkbox"]'
  );

  let activeButton = null;

  function showMainMenu() {
    if (!introScreen.classList.contains('active')) return;
    introScreen.classList.remove('active');
    mainMenu.classList.add('active');
  }

  function openPanel(name, trigger) {
    const panelToShow = panels.find((panel) => panel.dataset.panel === name);
    if (!panelToShow) return;

    panels.forEach((panel) => {
      panel.classList.toggle('active', panel === panelToShow);
    });

    panelOverlay.classList.add('visible');
    panelOverlay.setAttribute('aria-hidden', 'false');

    if (trigger) {
      if (activeButton) {
        activeButton.classList.remove('selected');
      }
      trigger.classList.add('selected');
      activeButton = trigger;
    }

    window.setTimeout(() => {
      const focusTarget =
        panelToShow.querySelector('[data-focus]') ||
        panelToShow.querySelector('button, select, input, a');
      if (focusTarget) {
        focusTarget.focus({ preventScroll: true });
      }
    }, 40);
  }

  function closePanel() {
    if (!panelOverlay.classList.contains('visible')) return;
    panelOverlay.classList.remove('visible');
    panelOverlay.setAttribute('aria-hidden', 'true');
    panels.forEach((panel) => panel.classList.remove('active'));
    if (activeButton) {
      activeButton.classList.remove('selected');
      activeButton = null;
    }
  }

  continueBtn?.addEventListener('click', showMainMenu);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      if (introScreen.classList.contains('active')) {
        event.preventDefault();
        showMainMenu();
        return;
      }
    }

    if (event.key === 'Escape') {
      closePanel();
    }
  });

  menuButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const panelName = button.dataset.open;
      openPanel(panelName, button);
    });
  });

  closeTriggers.forEach((trigger) => {
    trigger.addEventListener('click', () => {
      closePanel();
    });
  });

  panelShade.addEventListener('click', closePanel);

  panelOverlay.addEventListener('transitionend', (event) => {
    if (event.target === panelOverlay && !panelOverlay.classList.contains('visible')) {
      panels.forEach((panel) => panel.classList.remove('active'));
    }
  });

  if (scanlinesToggle) {
    scanlinesToggle.addEventListener('change', () => {
      if (!scanlinesLayer) return;
      scanlinesLayer.style.display = scanlinesToggle.checked ? 'block' : 'none';
    });
  }
})();
