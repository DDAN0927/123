const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const vp of [{ width: 375, height: 812 }, { width: 414, height: 896 }]) {
    const ctx = await b.newContext({ viewport: vp });
    const p = await ctx.newPage();
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(900);
    // kbd-btn 与导航图标对齐(48)
    const kb = await p.evaluate(() => {
      const el = document.querySelector('#openPalette');
      if (!el || getComputedStyle(el).display === 'none') return { missing: true };
      const r = el.getBoundingClientRect();
      return { h: Math.round(r.height), w: Math.round(r.width) };
    });
    ok(`${vp.width} kbd-btn 48px 触控`, !kb.missing && kb.h === 48, `h=${kb.h} w=${kb.w}`);
    // 打开移动菜单,断言分组样式
    const m = await p.evaluate(() => {
      document.querySelector('#mobileMenu').click();
      const links = [...document.querySelectorAll('.nav-links.is-open a')];
      const pages = links.filter((a) => !a.classList.contains('nav-m'));
      const more = links.filter((a) => a.classList.contains('nav-m'));
      const csOf = (a) => {
        const c = getComputedStyle(a);
        return { fs: c.fontSize, color: c.color, bt: c.borderTopWidth, mt: c.marginTop };
      };
      return {
        open: !!document.querySelector('.nav-links.is-open'),
        pages: pages.map(csOf), more: more.map(csOf),
        nMore: more.length,
      };
    });
    ok(`${vp.width} 菜单展开且 10 项齐全`, m.open && m.pages.length === 6 && m.nMore === 4,
      `pages=${m.pages.length} more=${m.nMore}`);
    ok(`${vp.width} 次级组 13px`, m.more.every((x) => x.fs === '13px'), JSON.stringify(m.more.map((x) => x.fs)));
    const alerts = m.more[0];
    ok(`${vp.width} 组间分隔线`, parseFloat(alerts.bt) > 0 && parseFloat(alerts.mt) > 0,
      `bt=${alerts.bt} mt=${alerts.mt}`);
    // 分层:次级组颜色须不同于页面导航(取解析后的 rgb 对比)
    const diffColor = m.pages.length && m.more.length &&
      m.pages[0].color !== m.more[1].color;
    ok(`${vp.width} 次级色分层`, diffColor, `page=${m.pages[0] && m.pages[0].color} more=${m.more[1] && m.more[1].color}`);
    const ovX = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(`${vp.width} 菜单展开不溢出`, ovX <= 0, `ovX=${ovX}`);
    await ctx.close();
  }
  // 桌面宽度不受影响:nav-m 默认隐藏
  const d = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await d.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(600);
  const r = await p.evaluate(() => getComputedStyle(document.querySelector('a.nav-m')).display);
  ok('1440 nav-m 仍隐藏', r === 'none', `display=${r}`);
  await b.close();
  console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})();
