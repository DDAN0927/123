const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });

  // —— R7 补漏:hero 无虚假宣称 ——
  let ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  let p = await ctx.newPage();
  p.on('pageerror', (e) => { fail++; console.log('FAIL  pageerror', e.message); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1500);
  let r = await p.evaluate(() => {
    const live = document.querySelector('.hero-live').textContent;
    return {
      live,
      noStream: !/数据流在线/.test(live) && !/延迟/.test(live),
      honest: /模拟行情 · 本地生成 · 非实时/.test(live),
      latencyGone: !document.getElementById('latency'),
      tickCount: document.getElementById('tickCount').textContent,
    };
  });
  ok('hero 无「数据流在线/延迟」宣称', r.noStream && r.honest, r.live.trim().slice(0, 30));
  ok('随机延迟写入器已删', r.latencyGone, '');
  ok('tick 计数如实从 0 起', parseInt(r.tickCount.replace(/,/g, ''), 10) < 100, `count=${r.tickCount}`);

  // —— 快览条:375 可见、可滑、内容齐全 ——
  r = await p.evaluate(() => {
    const strip = document.getElementById('quickStrip');
    const cs = getComputedStyle(strip);
    return {
      shown: cs.display === 'flex',
      idxChips: strip.querySelectorAll('[data-qs-idx]').length,
      tail: /去行情终端/.test(strip.textContent),
    };
  });
  ok('375 快览条显示', r.shown, '');
  ok('6 个指数 chip + 去终端', r.idxChips === 6 && r.tail, `idx=${r.idxChips}`);
  // 加自选后出现自选 chip
  r = await p.evaluate(() => {
    toggleFav('NVDA'); toggleFav('300750'); toggleFav('0700'); toggleFav('AAPL');
    renderTable();
    const strip = document.getElementById('quickStrip');
    return { favChips: strip.querySelectorAll('[data-qs]').length };
  });
  ok('自选 chip 进入快览条', r.favChips === 4, `fav=${r.favChips}`);
  r = await p.evaluate(() => {
    const strip = document.getElementById('quickStrip');
    const chips = [...strip.querySelectorAll('.qs-chip')];
    const h = Math.min(...chips.map((c) => c.getBoundingClientRect().height));
    return {
      scrollable: strip.scrollWidth > strip.clientWidth,
      ovX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      minH: Math.round(h),
    };
  });
  ok('横向可滑且不撑破页面', r.scrollable && r.ovX <= 0, `sw=${r.scrollable} ovX=${r.ovX}`);
  ok('chip 触控 ≥44px', r.minH >= 44, `minH=${r.minH}`);
  // 点自选 chip 回抽屉
  await p.evaluate(() => document.querySelector('[data-qs="300750"]').click());
  await p.waitForTimeout(300);
  r = await p.evaluate(() => ({
    on: document.getElementById('drawer').classList.contains('is-on'),
    code: document.querySelector('#drawerSub').textContent.slice(0, 6),
  }));
  ok('点自选 chip 打开抽屉', r.on && r.code.startsWith('300750'), r.code);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  // 点指数 chip 切市场过滤
  await p.evaluate(() => document.querySelector('[data-qs-idx="HSI"]').click());
  await p.waitForTimeout(1100);
  r = await p.evaluate(() => ({
    mkt: document.querySelector('#marketSeg button.is-on')?.dataset.market,
    termInView: (() => { const t = document.getElementById('terminal').getBoundingClientRect(); return t.top < window.innerHeight && t.bottom > 0; })(),
  }));
  ok('点指数 chip 切市场过滤并跳终端', r.mkt === 'HK' && r.termInView, `mkt=${r.mkt}`);
  // 原地更新:改价后文本变、滚动位置与节点身份不变
  // 原地更新:改价后文本变、滚动位置与节点身份不变
  // (html 全局 scroll-behavior:smooth,scrollLeft 赋值是动画——先滚、等到位、再断言)
  await p.evaluate(() => {
    const strip = document.getElementById('quickStrip');
    strip.scrollLeft = strip.children[1].offsetLeft;
  });
  await p.waitForTimeout(600);
  r = await p.evaluate(() => {
    const strip = document.getElementById('quickStrip');
    const target = strip.scrollLeft;
    if (target <= 0) return { changed: false, sameNode: false, scrollKept: false, note: 'scroll target=0' };
    const chip = document.querySelector('[data-qs="NVDA"]');
    const before = chip.querySelector('[data-qs-px="NVDA"]').textContent;
    const nodeBefore = chip.querySelector('[data-qs-px="NVDA"]');
    const s = BY_CODE['NVDA'];
    s.last = s.last * 1.05;
    s.chgPct = ((s.last - s.prevClose) / s.prevClose) * 100;
    qsTickUpdate(s);
    const el = chip.querySelector('[data-qs-px="NVDA"]');
    return {
      changed: el.textContent !== before,
      sameNode: el === nodeBefore,
      scrollKept: Math.abs(strip.scrollLeft - target) < 2,
    };
  });
  ok('tick 原地更新(文本变/节点同/滚动不丢)', r.changed && r.sameNode && r.scrollKept, JSON.stringify(r));
  await ctx.close();

  // —— 桌面隐藏 ——
  ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  r = await p.evaluate(() => getComputedStyle(document.getElementById('quickStrip')).display);
  ok('桌面(1280)快览条隐藏', r === 'none', `display=${r}`);
  await ctx.close();

  await b.close();
  console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})();
