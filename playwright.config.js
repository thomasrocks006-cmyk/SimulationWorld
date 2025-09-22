const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/ui',
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
  },
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
});
