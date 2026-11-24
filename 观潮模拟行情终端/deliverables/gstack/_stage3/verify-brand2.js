const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const theme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(700);
    if (theme === 'dark') { await p.click('#themeToggle'); await p.waitForTimeout(700); }
    await p.click('#alertsBtn');
    await p.waitForTimeout(900);
    const r = await p.evaluate(() => {
      const btns = [...document.querySelectorAll('.alert-form button, .btn-sync.primary, .cmp-add button')].filter(b => b.offsetWidth > 0);
      return btns.map(b => { const cs = getComputedStyle(b); const x = b.getBoundingClientRect(); return { t: b.textContent.trim().slice(0, 10), bg: cs.backgroundColor, color: cs.color, bc: cs.borderColor, w: Math.round(x.width), y: Math.round(x.y) }; });
    });
    console.log(theme, JSON.stringify(r));
    const first = await p.locator('.alert-form button').boundingBox();
    if (first) await p.screenshot({ path: `layout/btn-${theme}-fixed.png`, clip: { x: first.x - 8, y: first.y - 46, width: Math.min(first.width + 16, 420), height: first.height + 60 } });
    await ctx.close();
  }
  await b.close();
})();
