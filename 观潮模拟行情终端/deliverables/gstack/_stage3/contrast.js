/* WCAG 2.1 对比度实测:对 alpha 做逐层合成(朴素脚本忽略 alpha 会误报)。
   用法:node contrast.js  → 输出 light/dark 两份 <4.5:1 文本节点清单 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(700);

  const audit = () => {
    const parse = (c) => {
      const s = String(c);
      const m = s.match(/[\d.]+/g);
      if (!m) return null;
      const n = m.map(Number);
      // color-mix() 的计算值是 `color(srgb 0.937 0.937 0.918 / 0.7)`,三通道是 0–1 浮点;
      // 若按 0–255 解析,浅色会被算成近黑,产生大量假阴性(<4.5:1 误报)。
      if (/^color\(srgb/i.test(s)) {
        return { r: n[0] * 255, g: n[1] * 255, b: n[2] * 255, a: s.includes('/') ? n[3] : 1 };
      }
      return { r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1 };
    };
    const over = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
    const effBg = (el) => {
      const stack = [];
      let n = el;
      while (n && n.nodeType === 1) {
        const c = parse(getComputedStyle(n).backgroundColor);
        if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
        n = n.parentElement;
      }
      let base = { r: 255, g: 255, b: 255, a: 1 };
      for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
      return base;
    };
    const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
    const out = [];
    for (const el of document.querySelectorAll('body *')) {
      const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim().length > 1);
      if (!own.length) continue;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 4 || rect.height < 4) continue;
      const fg0 = parse(cs.color);
      if (!fg0 || fg0.a === 0) continue;
      const bg = effBg(el);
      const fg = fg0.a < 1 ? over(fg0, bg) : fg0;
      const L1 = lum(fg), L2 = lum(bg);
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      const size = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 700;
      const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
      if (ratio < need) {
        out.push({
          text: own.map(n => n.textContent.trim()).join(' ').slice(0, 20),
          sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : ''),
          ratio: +ratio.toFixed(2), need, size, color: cs.color,
        });
      }
    }
    return out;
  };

  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') { await p.click('#themeToggle'); await p.waitForTimeout(800); }
    const res = await p.evaluate(audit);
    console.log(`\n=== ${theme} === 不达标 ${res.length} 处`);
    res.slice(0, 40).forEach(r => console.log(`  ${r.ratio.toFixed(2)} (需${r.need}) ${r.size}px ${r.sel}「${r.text}」 ${r.color}`));
  }
  await b.close();
})();
