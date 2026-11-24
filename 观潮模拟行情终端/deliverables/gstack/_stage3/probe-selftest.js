const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0,150)); });
  p.on('pageerror', e => errs.push('PE:' + e.message.slice(0,150)));
  await p.goto(FILE + '?selftest', { waitUntil: 'load' });
  await p.waitForTimeout(2500);
  const r = await p.evaluate(() => {
    /* 面板 id 是 selfTestPanel(驼峰),早前写成 selftestPanel 会静默落回 body 取数 */
    const panel = document.getElementById('selfTestPanel');
    const bt = panel && panel.querySelector('b');
    const title = bt ? bt.textContent.trim() : '';
    const mm = title.match(/(\d+)\s*\/\s*(\d+)/);
    const txt = panel ? panel.innerText : document.body.innerText;
    const failLines = (txt.match(/^.*FAIL.*$/gm) || []).slice(0, 5);
    return {
      found: !!panel,
      title,
      pass: mm ? Number(mm[1]) : (txt.match(/PASS/g) || []).length,
      fail: mm ? Number(mm[2]) - Number(mm[1]) : (txt.match(/FAIL/g) || []).length,
      failLines,
      head: txt.slice(0, 120),
    };
  });
  console.log(JSON.stringify(r, null, 1));
  console.log('errors:', errs.length, errs.slice(0,3));
  await b.close();
})();
