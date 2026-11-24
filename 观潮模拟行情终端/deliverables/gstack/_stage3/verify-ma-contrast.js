/* MA 三色图形件对比度专项(WCAG 2.1 SC 1.4.11 非文本对比度 ≥3:1)
   对象:K 线 MA5/10/20 折线 + 图例色块(同源:--ma5/--ma10/--ma20)
   背景:K 线画布逐层 alpha 合成后的实际底色(亮/暗两主题各测一次)
   用法:node verify-ma-contrast.js  → 任一不达 3:1 退出码 1 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

const SLOTS = [['MA5', '--ma5'], ['MA10', '--ma10'], ['MA20', '--ma20']];
const THRESHOLD = 3.0;
const hex2rgb = (h) => {
  const s = h.trim();
  const m = s.match(/^#([0-9a-f]{6})$/i);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
};
const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
const L = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };

let pass = 0, fail = 0;
const ok = (name, cond, extra) => { if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); } else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); } };

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);

  /* 打开抽屉,让 #detailChart 参与布局;背景取画布逐层合成后的实际底色 */
  await p.evaluate(() => { if (typeof openDrawer === 'function') openDrawer('AAPL'); });
  await p.waitForTimeout(900);

  for (const theme of ['light', 'dark']) {
    await p.evaluate((t) => setTheme(t), theme);
    await p.waitForTimeout(700);
    const snap = await p.evaluate(() => {
      const parse = (c) => {
        const s = String(c); const m = s.match(/[\d.]+/g); if (!m) return null;
        const n = m.map(Number);
        /* color-mix() 计算值是 color(srgb 0.937 … / .7):三通道 0–1 浮点,不能按 0–255 解 */
        if (/^color\(srgb/i.test(s)) return { r: n[0] * 255, g: n[1] * 255, b: n[2] * 255, a: s.includes('/') ? n[3] : 1 };
        return { r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1 };
      };
      const over = (fg, bgc) => ({ r: fg.r * fg.a + bgc.r * (1 - fg.a), g: fg.g * fg.a + bgc.g * (1 - fg.a), b: fg.b * fg.a + bgc.b * (1 - fg.a), a: 1 });
      const effBg = (el) => {
        const stack = []; let n = el;
        while (n && n.nodeType === 1) {
          const c = parse(getComputedStyle(n).backgroundColor);
          if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
          n = n.parentElement;
        }
        let base = { r: 255, g: 255, b: 255, a: 1 };
        for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
        return base;
      };
      const pick = (c) => c && { r: Math.round(c.r), g: Math.round(c.g), b: Math.round(c.b) };
      const rootCS = getComputedStyle(document.documentElement);
      const vars = ['--ma5', '--ma10', '--ma20'].map((v) => rootCS.getPropertyValue(v).trim());
      /* 图例色块的实际背景(应等于同名变量) */
      const swatches = ['ma5', 'ma10', 'ma20'].map((cls) => {
        const el = document.querySelector('.synth-line .legend i.' + cls);
        return el ? getComputedStyle(el).backgroundColor : null;
      });
      return {
        themeAttr: document.documentElement.getAttribute('data-theme'),
        detail: pick(effBg(document.getElementById('detailChart'))),
        hero: pick(effBg(document.getElementById('heroChart'))),
        vars, swatches,
      };
    });

    ok(`[${theme}] 主题切换生效`, snap.themeAttr === theme, `data-theme=${snap.themeAttr}`);
    console.log(`  画布底色 detail=${JSON.stringify(snap.detail)} hero=${JSON.stringify(snap.hero)}`);
    console.log(`  变量 ${snap.vars.join(' / ')}  图例 ${snap.swatches.join(' / ')}`);

    snap.vars.forEach((raw, i) => {
      const [name] = SLOTS[i];
      const fg = hex2rgb(raw);
      ok(`[${theme}] ${name} 变量可解析为 6 位 hex`, !!fg, raw);
      if (!fg) return;
      ok(`[${theme}] ${name} ${raw} vs K线画布 ≥${THRESHOLD}:1`, ratio(fg, snap.detail) >= THRESHOLD, `${ratio(fg, snap.detail).toFixed(2)}:1`);
      ok(`[${theme}] ${name} vs hero 画布 ≥${THRESHOLD}:1`, ratio(fg, snap.hero) >= THRESHOLD, `${ratio(fg, snap.hero).toFixed(2)}:1`);
      /* 图例与折线必须同源同色,否则「图例说这是 MA5 的线」不成立 */
      const sw = snap.swatches[i];
      const rgbStr = `rgb(${fg.r}, ${fg.g}, ${fg.b})`;
      ok(`[${theme}] ${name} 图例色块与变量同色`, sw === rgbStr, `${sw} vs ${rgbStr}`);
    });
  }

  ok('零 pageerror', errs.length === 0, errs.slice(0, 2).join(' | '));
  console.log(`\n结果: ${pass} PASS, ${fail} FAIL`);
  await b.close();
  process.exit(fail ? 1 : 0);
})();
