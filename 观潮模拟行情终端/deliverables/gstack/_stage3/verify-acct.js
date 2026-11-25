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
    const r = await p.evaluate(() => {
      const chip = document.querySelector('#acctChip');
      const cs = getComputedStyle(chip);
      const cr = chip.getBoundingClientRect();
      const nr = document.querySelector('.nav-right').getBoundingClientRect();
      const total = chip.querySelector('#acctTotal');
      const tr = total.getBoundingClientRect();
      return {
        shown: cs.display !== 'none', chipW: Math.round(cr.width), chipRight: Math.round(cr.right),
        navRight: Math.round(nr.right), vw: document.documentElement.clientWidth,
        totalTxt: total.textContent, totalVisible: tr.width > 0 && getComputedStyle(total).visibility !== 'hidden',
        icoHidden: getComputedStyle(chip.querySelector('.acct-ico')).display === 'none',
        lblHidden: getComputedStyle(chip.querySelector('.acct-txt i')).display === 'none',
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    ok(`${vp.width} 资产 chip 可见`, r.shown && r.totalVisible, `total=${r.totalTxt} w=${r.chipW} right=${r.chipRight}`);
    ok(`${vp.width} 紧凑单行(图标/标签隐藏)`, r.icoHidden && r.lblHidden, '');
    ok(`${vp.width} 不溢出`, r.overflowX <= 0 && r.navRight <= r.vw, `navRight=${r.navRight}/${r.vw} ovX=${r.overflowX}`);
    await ctx.close();
  }
  // 移动菜单:提醒入口打开提醒抽屉
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 } });
  const p = await ctx.newPage();
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(800);
  const m = await p.evaluate(() => {
    document.querySelector('#mobileMenu').click();
    return new Promise((res) => setTimeout(() => {
      const link = [...document.querySelectorAll('.nav-links a[data-mact]')].find((a) => a.dataset.mact === 'alerts');
      const visible = link && getComputedStyle(link).display !== 'none';
      if (link) link.click();
      setTimeout(() => res({
        linkVisible: visible,
        alertOpen: document.querySelector('#alertDrawer').classList.contains('is-on'),
        menuClosed: !document.querySelector('.nav-links').classList.contains('is-on'),
      }), 500);
    }, 400));
  });
  ok('菜单提醒入口可用', m.linkVisible && m.alertOpen && m.menuClosed, JSON.stringify(m));
  await b.close();
  console.log(fail ? `\n*** ${fail} FAILED ***` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
