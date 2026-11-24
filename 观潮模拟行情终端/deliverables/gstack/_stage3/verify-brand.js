const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(800);
  await p.click('#alertsBtn');
  await p.waitForTimeout(900);
  const info = await p.evaluate(() => {
    const btn = document.querySelector('.alert-form button');
    if (!btn) return { found: false };
    const cs = getComputedStyle(btn);
    const r = btn.getBoundingClientRect();
    return { found: true, text: btn.textContent.trim(), bg: cs.backgroundColor, color: cs.color, border: cs.borderColor, w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) };
  });
  console.log(JSON.stringify(info));
  if (info.found) await p.screenshot({ path: 'layout/alert-add-btn-2x.png', clip: { x: info.x - 10, y: info.y - 40, width: Math.min(info.w + 20, 400), height: info.h + 60 } });
  await b.close();
})();
