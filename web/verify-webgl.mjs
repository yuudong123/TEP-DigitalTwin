import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const base = process.argv[2] ?? 'http://127.0.0.1:8000'
const seconds = Number(process.argv[3] ?? 90)
const output = path.resolve(process.argv[4] ?? '../reports/26-final/webgl-2026-10-15.json')
const screenshot = path.resolve(process.argv[5] ?? '../reports/26-final/unity-live-2026-10-15.png')
await mkdir(path.dirname(output), { recursive: true })
await mkdir(path.dirname(screenshot), { recursive: true })
const browser = await chromium.launch({ channel: process.env.TEP_BROWSER_CHANNEL ?? 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1 })
// Test-only loader wrapper captures the public instance; WASM/data and API stay real.
await page.route('**/unity/Build/unity.loader.js', async route => {
  const response = await route.fetch()
  const body = await response.text()
  await route.fulfill({ response, body: body + `
const __tepOriginalUnityFactory = window.createUnityInstance;
window.createUnityInstance = async (...args) => {
  const instance = await __tepOriginalUnityFactory(...args);
  window.__tepTestUnityInstance = instance;
  return instance;
};` })
})
const errors = []
const responses = new Map()
let matching = 0
let fresh = 0
let stale = 0
const samples = []
const started = Date.now()
page.on('pageerror', error => errors.push(String(error)))
page.on('response', async response => {
  if (response.url().includes('/api/predictions/latest') && response.status() === 200) {
    try {
      const received = Date.parse(response.headers()['x-prediction-received-at'])
      responses.set(received, await response.json())
      if (responses.size > 200) responses.delete(responses.keys().next().value)
    } catch { /* Aborted response while deliberately testing connectivity. */ }
  }
})
await page.addInitScript(() => {
  window.__tepUnityAck = null
  window.__tepUnityAckCount = 0
  window.addEventListener('tep-unity-prediction', event => {
    window.__tepUnityAck = event.detail
    window.__tepUnityAckCount++
  })
})
function near(a, b) { return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= 1e-4 }
async function readAndMatch() {
  const ack = await page.evaluate(() => window.__tepUnityAck)
  if (!ack) throw new Error('Unity has not acknowledged a prediction')
  const source = responses.get(ack.received_at_unix_ms)
  if (!source) return null
  const actual = ack.prediction
  if (source.trajectory_key !== actual.trajectory_key || source.model_version !== actual.model_version || source.status !== actual.status
    || !near(source.timestamp_hours, actual.timestamp_hours) || !near(source.rul.hours, actual.rul.hours)) throw new Error('API and Unity prediction differ')
  for (const key of ['failure_within_4h', 'failure_within_2h', 'failure_within_1h']) {
    if (!near(source.risk[key].score, actual.risk[key].score) || !near(source.risk[key].threshold, actual.risk[key].threshold)
      || source.risk[key].alert !== actual.risk[key].alert) throw new Error('API and Unity risk differ')
  }
  matching++
  if (ack.connection_state === 'connected') fresh++
  if (ack.connection_state === 'stale') stale++
  return ack
}
const report = { source: 'actual_compiled_unity_webgl_and_live_api', base, errors, passed: false }
try {
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  const unity = page.locator('.unity-card')
  await unity.waitFor({ timeout: 30000 })
  await page.waitForFunction(() => document.querySelector('.unity-card')?.dataset.unityState === 'ready', null, { timeout: 150000 })
  await page.waitForFunction(() => window.__tepUnityAck !== null, null, { timeout: 15000 })
  const initial = await readAndMatch()
  report.initial = initial
  await page.locator('.stream-controls').first().getByRole('button', { name: '일시정지', exact: true }).click()
  await page.waitForFunction(() => window.__tepUnityAck?.connection_state === 'paused', null, { timeout: 15000 })
  report.pause_propagates_to_unity = true
  const rejection = await page.evaluate(async () => {
    const accepted = structuredClone(window.__tepUnityAck)
    for (const kind of ['numeric_status', 'invalid_risk', 'missing_receipt']) {
      const invalid = structuredClone(accepted)
      if (kind === 'numeric_status') invalid.prediction.status = '1'
      if (kind === 'invalid_risk') invalid.prediction.risk.failure_within_1h.score = 1.5
      if (kind === 'missing_receipt') delete invalid.received_at_unix_ms
      const prior = window.__tepUnityAckCount
      window.__tepTestUnityInstance.SendMessage('DigitalTwinRuntime', 'ApplyPredictionEnvelope', JSON.stringify(invalid))
      await new Promise(resolve => setTimeout(resolve, 600))
      if (window.__tepUnityAckCount !== prior) return false
    }
    window.__tepTestUnityInstance.SendMessage('DigitalTwinRuntime', 'ApplyPredictionEnvelope', JSON.stringify(accepted))
    return true
  })
  if (!rejection) throw new Error('Compiled Unity accepted an invalid prediction envelope')
  report.invalid_predictions_rejected_by_compiled_unity = true
  await page.locator('.stream-controls').first().getByRole('button', { name: '재생', exact: true }).click()
  await page.route('**/api/predictions/latest', route => route.abort())
  await page.waitForFunction(() => window.__tepUnityAck?.connection_state === 'error', null, { timeout: 15000 })
  report.connection_error_propagates_to_unity = true
  await page.unroute('**/api/predictions/latest')
  await page.waitForFunction(() => ['connected', 'stale'].includes(window.__tepUnityAck?.connection_state), null, { timeout: 15000 })
  report.connection_restored = true
  for (const viewport of [{ width: 1280, height: 900 }, { width: 1920, height: 1200 }]) {
    await page.setViewportSize(viewport)
    await page.waitForFunction(() => {
      const canvas = document.querySelector('#unity-canvas')
      const rect = canvas?.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      return rect && Math.abs(canvas.width - rect.width * dpr) <= 2 && Math.abs(canvas.height - rect.height * dpr) <= 2
    }, null, { timeout: 15000 })
  }
  report.resized_canvas_matches_viewport = true
  const deadline = Date.now() + seconds * 1000
  let captured = false
  while (Date.now() < deadline) {
    const ack = await readAndMatch()
    const memory = await page.evaluate(() => performance.memory ? performance.memory.usedJSHeapSize : null)
    samples.push({ elapsed_seconds: Math.round((Date.now() - started) / 1000), trajectory: ack?.prediction.trajectory_key,
      timestamp: ack?.prediction.timestamp_hours, state: ack?.connection_state, js_heap_bytes: memory })
    if (ack?.connection_state === 'connected' && !captured) {
      await unity.screenshot({ path: screenshot })
      captured = true
    }
    if (errors.length) throw new Error('Browser runtime error: ' + errors.join('; '))
    console.log(JSON.stringify(samples.at(-1)))
    await page.waitForTimeout(Math.min(15000, Math.max(1, deadline - Date.now())))
  }
  if (!captured) await unity.screenshot({ path: screenshot })
  report.final = await readAndMatch()
  report.matching_samples = matching
  report.fresh_samples = fresh
  report.stale_samples = stale
  report.samples = samples
  report.elapsed_seconds = Math.round((Date.now() - started) / 1000)
  report.passed = matching > 0 && errors.length === 0
} catch (error) {
  report.failure = String(error)
  await page.screenshot({ path: screenshot }).catch(() => {})
  process.exitCode = 1
} finally {
  await writeFile(output, JSON.stringify(report, null, 2))
  await browser.close()
}
console.log(JSON.stringify({ passed: report.passed, failure: report.failure, matching, fresh, stale, output }))
