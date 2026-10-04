#!/usr/bin/env node
/* Capture the real Falsify UI without starting experiments or changing app data.
 * Run with a Node installation containing Playwright (or set NODE_PATH).
 * Screenshots are production inputs, not proof of a new scientific run.
 */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const SOURCES = {
  flawed: '06f519544cd443a194a44965a1246164',
  control: '83faf266dc944354b43b5b8ffc22bbd6',
};
const SHOTS = [
  { id: 'claim', source: 'flawed', selector: '#experiment' },
  { id: 'orchestration', source: 'flawed', selector: '.lab-grid' },
  { id: 'choices', source: 'flawed', selector: '#evidence-E012', event: 'E012' },
  { id: 'audit', source: 'flawed', selector: '#evidence-E026', event: 'E026' },
  { id: 'corrected', source: 'flawed', selector: '.results-section' },
  { id: 'control', source: 'control', selector: '.results-section' },
  { id: 'measured', source: 'flawed', selector: '.results-section' },
  { id: 'closing', source: 'flawed', selector: '#method' },
];

function options() {
  const out = { url: 'http://127.0.0.1:8765', output: path.join(ROOT, 'output/demo-video/captures'), record: false, plan: path.join(ROOT, 'video/demo-plan.json') };
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (key === '--record') out.record = true;
    else if (key === '--help') {
      console.log('Usage: node scripts/capture_demo.cjs [--url URL | --access-file PRIVATE_JSON] [--output DIR] [--plan JSON] [--record] [--only scene_id,...]');
      process.exit(0);
    } else if (['--url', '--output', '--access-file', '--plan', '--only'].includes(key)) {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Missing value for ${key}`);
      out[key.slice(2).replace('-file', 'File')] = args[++i];
    } else throw new Error(`Unknown option: ${key}`);
  }
  return out;
}

async function main() {
  const opts = options();
  let credentials;
  if (opts.accessFile) {
    const access = JSON.parse(await fs.readFile(opts.accessFile, 'utf8'));
    opts.url = access.url;
    credentials = { username: access.username, password: access.password };
  }
  const base = new URL(opts.url);
  if (base.username || base.password) throw new Error('Do not embed credentials in a URL. Use --access-file.');
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(base.hostname);
  if (base.protocol !== 'https:' && !(base.protocol === 'http:' && loopback)) throw new Error('Use HTTPS except for loopback capture.');
  const plan = JSON.parse(await fs.readFile(opts.plan, 'utf8'));
  const selectedIds = opts.only?.split(',');
  if (selectedIds?.some(id => !SHOTS.some(shot => shot.id === id))) throw new Error('Unknown scene id in --only');
  await fs.mkdir(opts.output, { recursive: true });
  // Use installed Chrome in an isolated temporary profile. This avoids depending
  // on the bundled Playwright package and browser cache having matching versions.
  const browser = await chromium.launch({ channel: process.env.FALSIFY_VIDEO_BROWSER_CHANNEL || 'chrome', headless: true });
  const report = { created_at: new Date().toISOString(), base_url: base.origin, source_label: 'Recorded replay of actual Omnigent investigations', fresh_inference: false, screenshots: [], videos: [], verified_sources: [] };
  try {
    // Check actual HTTP responses against the exact reviewed records. No API mocking.
    const preflight = await browser.newContext({ httpCredentials: credentials });
    try {
      for (const [name, id] of Object.entries(SOURCES)) {
        const original = await fs.readFile(path.join(ROOT, 'demo/runs', id, 'run.json'));
        const expected = JSON.parse(original);
        const response = await preflight.request.get(new URL(`/api/runs/${id}/export`, base).href);
        if (!response.ok()) throw new Error(`Could not fetch reviewed ${name} record: HTTP ${response.status()}`);
        const actual = await response.json();
        // JSON property order has no scientific meaning.
        const canonical = (value) => JSON.stringify(value, (key, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(k => [k, item[k]])) : item);
        if (canonical(actual) !== canonical(expected)) throw new Error(`Displayed ${name} record differs from the reviewed source`);
        if (actual.mode !== 'omnigent' || actual.status !== 'completed' || !actual.validation?.protocol_verified || actual.validation?.agrees_with_split_rule !== true) throw new Error(`Unverified ${name} record`);
        report.verified_sources.push({ id, case_id: actual.case_id, file_sha256: crypto.createHash('sha256').update(original).digest('hex') });
      }
    } finally { await preflight.close(); }

    for (const shot of SHOTS.filter(shot => !selectedIds || selectedIds.includes(shot.id))) {
      const scene = plan.scenes.find(s => s.id === shot.id);
      if (!scene) throw new Error(`Plan has no scene ${shot.id}`);
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5,
        reducedMotion: 'reduce', httpCredentials: credentials,
        ...(opts.record ? { recordVideo: { dir: path.join(opts.output, 'raw-video'), size: { width: 1440, height: 900 } } } : {}),
      });
      try {
        // A capture may read evidence but must never launch or cancel an investigation.
        await context.route('**/*', async route => {
          const request = route.request();
          if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) return route.abort('blockedbyclient');
          return route.continue();
        });
        const page = await context.newPage();
        const pageErrors = [];
        page.on('pageerror', error => pageErrors.push(error.message));
        const runId = SOURCES[shot.source];
        await page.goto(new URL(`/?run=${runId}`, base).href, { waitUntil: 'networkidle' });
        await page.locator('#context-label').filter({ hasText: 'Recorded replay' }).waitFor();
        if ((await page.locator('#error-message').isVisible())) throw new Error(`App reported an error while capturing ${shot.id}`);
        if (!(await page.locator('#export-link').getAttribute('href')).includes(runId)) throw new Error('UI selected an unexpected run');
        if (shot.event) {
          const event = page.locator(`#evidence-${shot.event}`);
          await event.waitFor();
          if (shot.expand) await event.locator('summary').click();
          await event.evaluate(el => el.scrollIntoView({ block: 'start', behavior: 'instant' }));
        }
        const region = page.locator(shot.selector);
        await region.evaluate(el => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
        // Wait for layout and score-bar transitions, not for scientific execution.
        await page.waitForTimeout(750);
        const imageFile = path.resolve(opts.output, `${shot.id}.png`);
        await region.screenshot({ path: imageFile, animations: 'disabled' });
        const imageBytes = await fs.readFile(imageFile);
        report.screenshots.push({ scene_id: shot.id, file: imageFile, sha256: crypto.createHash('sha256').update(imageBytes).digest('hex'), run_id: runId, selector: shot.selector, event_id: shot.event || null });
        console.log(`Captured ${shot.id}: recorded ${shot.source} case`);
        if (opts.record) {
          const duration = Number(scene.duration_seconds);
          if (!Number.isFinite(duration) || duration <= 0 || duration > 120) throw new Error(`Invalid scene duration: ${shot.id}`);
          const clipStart = await page.evaluate(() => performance.now() / 1000);
          const video = page.video();
          await page.waitForTimeout(duration * 1000 + 500);
          await context.close();
          const videoFile = path.resolve(opts.output, `${shot.id}.webm`);
          await video.saveAs(videoFile);
          report.videos.push({ scene_id: shot.id, file: videoFile, content_start_seconds_approx: clipStart, requested_hold_seconds: duration, note: 'Raw recording includes page load. Select the stable held view before editing; all scientific results are recorded replay.' });
        }
        if (pageErrors.length) throw new Error(`Browser errors: ${pageErrors.join('; ')}`);
      } finally { await context.close(); }
    }
  } finally { await browser.close(); }
  await fs.writeFile(path.join(opts.output, 'capture-report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(`Saved ${report.screenshots.length} real UI captures. No experiments were started.`);
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
