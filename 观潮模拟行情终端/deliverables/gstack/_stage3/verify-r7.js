const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(900);
  const r = await p.evaluate(() => {
    const box = document.querySelector('#mktStatus');
    const txt = box.querySelector('.txt').textContent;
    const dotOff = box.querySelector('.dot-live').classList.contains('dot-off');
    // 用假日期直接驱动 tickMktStatus:周六 10:00 应收盘;周三 10:00 应交易中
    const sat = new Date(2026, 10, 28, 10, 0, 0); // 2026-11-28 是周六
    const wed = new Date(2026, 10, 25, 10, 0, 0); // 周三
    window.tickMktStatus(sat);
    const satTxt = box.querySelector('.txt').textContent + '/' + box.querySelector('.dot-live').classList.contains('dot-off');
    window.tickMktStatus(wed);
    const wedTxt = box.querySelector('.txt').textContent + '/' + box.querySelector('.dot-live').classList.contains('dot-off');
    window.tickMktStatus(new Date());
    return {
      nowTxt: txt, nowDotOff: dotOff, satTxt, wedTxt,
      termMeta: document.querySelector('#termMeta').textContent,
      hstat: [...document.querySelectorAll('.hstat span')].map((x) => x.textContent).find((t) => t.includes('准确率')),
    };
  });
  /* 时段无关:开盘(9:30-11:30/13:00-15:00 工作日)必须「交易中」,否则「已收盘」,
     且圆点状态必须与文案一致——不能假设探针运行时刻在盘中 */
  const intraday = (() => {
    const d = new Date(), day = d.getDay(), m = d.getHours() * 60 + d.getMinutes();
    if (day === 0 || day === 6) return false;
    return (m >= 570 && m <= 690) || (m >= 780 && m <= 900);
  })();
  ok('当前时段状态正确', r.nowTxt === (intraday ? '沪深交易中' : '沪深已收盘') && r.nowDotOff === !intraday,
    `${r.nowTxt} dotOff=${r.nowDotOff} intraday=${intraday}`);
  ok('周六判定收盘', r.satTxt.startsWith('沪深已收盘') && r.satTxt.endsWith('true'), r.satTxt);
  ok('周三上午判定交易中', r.wedTxt.startsWith('沪深交易中') && r.wedTxt.endsWith('false'), r.wedTxt);
  ok('termMeta 无编造延迟', r.termMeta.includes('模拟行情 · 本地生成') && !r.termMeta.includes('行情延迟'), r.termMeta.slice(-20));
  ok('68.4% 带演示标注', (r.hstat || '').includes('演示'), r.hstat);
  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
