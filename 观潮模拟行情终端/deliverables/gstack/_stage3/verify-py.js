const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1500);
  // 1) 单元级:边界法抽查
  const unit = await p.evaluate(() => ({
    gzmt: pyInitialsOf({ name: '贵州茅台' }),
    ndsd: pyInitialsOf({ name: '宁德时代' }),
    hq: pyInitialsOf({ name: '沪深300' }),
    eng: pyInitialsOf({ name: 'NVDA' }),
  }));
  console.log('unit:', JSON.stringify(unit));
  ok('贵州茅台 → gzmt', unit.gzmt === 'gzmt', unit.gzmt);
  ok('宁德时代 → ndsd', unit.ndsd === 'ndsd', unit.ndsd);
  ok('混合串(沪深300 → hs300)', unit.hq === 'hs300', unit.hq);
  // 2) palette 拼音检索
  await p.click('#openPalette');
  await p.waitForTimeout(300);
  await p.fill('#palInput', 'gzmt');
  await p.waitForTimeout(500);
  const pal = await p.evaluate(() => ({ n: palResults.length, names: palResults.slice(0, 3).map((s) => s.name) }));
  ok('palette 搜 gzmt 出茅台', pal.n > 0 && pal.names.some((x) => x.includes('茅台')), JSON.stringify(pal));
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  // 3) 终端搜索
  await p.fill('#termSearch', 'ndsd');
  await p.waitForTimeout(700);
  const term = await p.evaluate(() => {
    const rows = [...document.querySelectorAll('#hotBody tr')];
    return { n: rows.length, first: (rows[0] || { innerText: '' }).innerText.replace(/\s+/g, ' ').slice(0, 40) };
  });
  ok('终端搜 ndsd 命中宁德时代', term.n >= 1 && term.first.includes('宁德时代'), JSON.stringify(term));
  // 4) 回归
  await p.fill('#termSearch', '茅台');
  await p.waitForTimeout(700);
  const cn = await p.evaluate(() => [...document.querySelectorAll('#hotBody tr')].map((r) => r.innerText.replace(/\s+/g, ' ')).join('|').slice(0, 60));
  ok('中文子串搜索仍可用', cn.includes('茅台'), cn);
  await p.fill('#termSearch', '600519');
  await p.waitForTimeout(700);
  const code = await p.evaluate(() => document.querySelectorAll('#hotBody tr').length);
  ok('代码搜索仍可用', code >= 1, `rows=${code}`);
  await ctx.close();
  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
