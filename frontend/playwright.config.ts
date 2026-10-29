import { defineConfig } from '@playwright/test'
import path from 'node:path'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  workers: 1,
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8011',
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 1100 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      '"..\\.venv\\Scripts\\python.exe" -m uvicorn app.main:app --app-dir ..\\backend --host 127.0.0.1 --port 8011',
    url: 'http://127.0.0.1:8011/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
    env: { DATA_CLEAN_HOME: path.resolve('artifacts', `e2e-data-${Date.now()}`) },
  },
})
