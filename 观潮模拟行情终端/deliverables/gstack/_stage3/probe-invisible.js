const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(600);
  const dump = async (label) => {
    const r = await p.evaluate(() => [...document.querySelectorAll('button')].filter(el => {
      const t = el.textContent.trim();
      return t && t.length < 12;
    }).map(el => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return { t: el.textContent.trim(), cls: el.className, color: cs.color, bg: cs.backgroundColor, visible: r.width > 0 };
    }).filter(x => x.visible && x.color === x.bg));
    console.log(label, JSON.stringify(r));
  };
  await dump('light');
  await p.click('#themeToggle'); await p.waitForTimeout(700);
  await dump('dark');
  await b.close();
})();
