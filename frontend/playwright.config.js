import { defineConfig, devices } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const API_PORT = 8765
const WEB_PORT = 5180

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: '../.venv/bin/python run.py',
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        PORT: String(API_PORT),
        RELOAD: '0',
        DOCULENS_DATA_DIR: mkdtempSync(join(tmpdir(), 'doculens-e2e-')),
        DISABLE_NEURAL_EMBEDDINGS: '1',
        LLM_PROVIDER: 'none',
        AUTH_MODE: 'test',
        ADMIN_EMAILS: 'admin@example.com',
        STORAGE_BACKEND: 'local',
        CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}`,
      },
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: { VITE_API_PROXY: `http://127.0.0.1:${API_PORT}`, VITE_AUTH_MODE: 'test' },
    },
  ],
})
