const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const rows = [];
  for (const w of [1920,1600,1512,1500,1470,1440,1400,1366,1280,1181,1140,1024]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 800 } });
    const p = await ctx.newPage();
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(500);
    const r = await p.evaluate(() => {
      const wrap = document.querySelector('.nav .wrap');
      const links = document.querySelector('.nav-links');
      const right = document.querySelector('.nav-right');
      const cs = getComputedStyle(wrap);
      const a0 = document.querySelector('.nav-links a');
      const linkA = [...document.querySelectorAll('.nav-links a')].map(a => Math.round(a.getBoundingClientRect().height));
      const chip = document.getElementById('acctChip').getBoundingClientRect();
      const kbd = document.getElementById('openPalette').getBoundingClientRect();
      return {
        wrapW: Math.round(wrap.getBoundingClientRect().width),
        pad: cs.paddingLeft + '/' + cs.paddingRight,
        linksW: links ? Math.round(links.getBoundingClientRect().width) : 0,
        linksScrollW: links ? links.scrollWidth : 0,
        rightW: Math.round(right.getBoundingClientRect().width),
        linkHeights: linkA,
        fs: a0 ? getComputedStyle(a0).fontSize : '',
        chip: { w: Math.round(chip.width), r: Math.round(chip.right) },
        kbd: { w: Math.round(kbd.width), r: Math.round(kbd.right) },
        menuVisible: getComputedStyle(document.getElementById('mobileMenu')).display,
        hScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    rows.push({ w, ...r });
    console.log(JSON.stringify({ w, ...r }));
    await ctx.close();
  }
  require('fs').writeFileSync('layout/nav-metrics.json', JSON.stringify(rows, null, 2));
  await b.close();
})();
