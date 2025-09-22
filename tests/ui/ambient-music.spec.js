const path = require('path');
const { pathToFileURL } = require('url');
const { test, expect } = require('@playwright/test');

const indexPath = path.resolve(__dirname, '../../index.html');
const indexUrl = pathToFileURL(indexPath).href;

async function setSliderValue(page, value) {
  await page.locator('[data-setting="music-volume"]').evaluate((element, newValue) => {
    element.value = newValue;
    element.dispatchEvent(new Event('input', { bubbles: true }));
  }, value.toString());
}

test.describe('Ambient music loop', () => {
  test('starts after activation, reacts to slider, and persists volume', async ({ page }) => {
    await page.goto(indexUrl);
    await page.waitForSelector('#continue-btn');

    const initialContextState = await page.evaluate(() => window.__worldSimMusic?.contextState ?? null);
    expect(initialContextState).toBeNull();

    await page.click('#continue-btn');

    await page.waitForFunction(() => window.__worldSimMusic?.contextState === 'running');

    await page.waitForFunction(() => {
      const gain = window.__worldSimMusic?.masterGainValue;
      return typeof gain === 'number' && gain > 0.01;
    });

    await setSliderValue(page, 0);

    await page.waitForFunction(() => {
      const gain = window.__worldSimMusic?.masterGainValue;
      return typeof gain === 'number' && gain >= 0 && gain <= 0.001;
    });

    await setSliderValue(page, 58);

    await page.waitForFunction(() => {
      const music = window.__worldSimMusic;
      if (!music) return false;
      const gain = music.masterGainValue;
      const target = music.targetVolume;
      return (
        typeof gain === 'number' &&
        typeof target === 'number' &&
        Math.abs(target - 0.58) < 0.001 &&
        Math.abs(gain - target) < 0.02
      );
    });

    await page.reload();
    await page.waitForSelector('#continue-btn');

    const persistedSliderValue = await page
      .locator('[data-setting="music-volume"]')
      .evaluate((element) => element.value);
    expect(persistedSliderValue).toBe('58');

    const storedVolume = await page.evaluate(() => window.localStorage.getItem('worldsim:music-volume'));
    expect(parseFloat(storedVolume)).toBeCloseTo(0.58, 2);
  });
});
