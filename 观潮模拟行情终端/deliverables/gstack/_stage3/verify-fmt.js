const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(900);
  const r = await p.evaluate(() => {
    const out = { fmtCases: [] };
    for (const v of [20.6393, -20.6393, 0.7659, -0.7659, 0, 0.005, -0.005, 1234.5678, -1234.5678]) {
      out.fmtCases.push({ v, s: fmt.px(v) , px2: fmt.px(v, 2) });
    }
    // 实际渲染的涨跌额单元格
    const cells = [...document.querySelectorAll('table.hot tbody tr')].slice(0, 6).map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent.trim()));
    out.rows = cells;
    return out;
  });
  console.log(JSON.stringify(r, null, 1));
  await b.close();
})();
