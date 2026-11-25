/* 阶段三 布局探针:多视口扫描横向溢出、溢出元素、触摸目标、控制台错误 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const fs = require('fs');

const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
const OUT = path.join(__dirname, 'layout');
fs.mkdirSync(OUT, { recursive: true });

const VPS = [
  { name: 'desktop-1920', w: 1920, h: 1080 },
  { name: 'desktop-1440', w: 1440, h: 900 },
  { name: 'desktop-1366', w: 1366, h: 768 },
  { name: 'tablet-1024', w: 1024, h: 768 },
  { name: 'tablet-768', w: 768, h: 1024 },
  { name: 'mobile-414', w: 414, h: 896 },
  { name: 'mobile-375', w: 375, h: 667 },
];

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const report = [];
  for (const vp of VPS) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)); });
    page.on('pageerror', (e) => errs.push('pageerror: ' + String(e.message).slice(0, 200)));
    await page.goto(FILE, { waitUntil: 'load' });
    await page.waitForTimeout(1200);

    const res = await page.evaluate(() => {
      const de = document.documentElement;
      const vw = window.innerWidth;
      const overflowX = de.scrollWidth - de.clientWidth;
      // 找出超出视口右边界的元素(排除被 overflow 容器裁剪的)
      const offenders = [];
      const clippedBy = (el) => {
        let p = el.parentElement;
        while (p && p !== document.body) {
          const cs = getComputedStyle(p);
          if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') return p;
          p = p.parentElement;
        }
        return null;
      };
      const all = document.querySelectorAll('body *');
      for (const el of all) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed' && cs.opacity === '0') continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > vw + 1 && !clippedBy(el)) {
          offenders.push({
            sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
            right: Math.round(r.right), width: Math.round(r.width),
          });
        }
      }
      // 触摸目标 <48px 的可交互元素(仅移动端统计使用)
      const interactives = [...document.querySelectorAll('button, a, [role="button"], input, select, summary, .chip, .tab')];
      const smallTargets = [];
      for (const el of interactives) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.width < 48 || r.height < 48) {
          smallTargets.push({
            sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : ''),
            w: Math.round(r.width), h: Math.round(r.height),
            text: (el.textContent || '').trim().slice(0, 12),
          });
        }
      }
      // 字体基准
      const bodyFont = getComputedStyle(document.body).fontSize;
      return {
        vw, overflowX, offenders: offenders.slice(0, 12), offenderCount: offenders.length,
        smallTargets: smallTargets.slice(0, 20), smallCount: smallTargets.length,
        bodyFont,
        docHeight: Math.round(de.scrollHeight),
        h1: (document.querySelector('h1') || {}).textContent?.trim().slice(0, 40) || '',
      };
    });

    await page.screenshot({ path: path.join(OUT, vp.name + '-fold.png') });
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT, vp.name + '-foot.png') });
    await page.evaluate(() => window.scrollTo(0, 0));

    report.push({ vp: vp.name, ...res, errors: errs });
    console.log(`[${vp.name}] overflowX=${res.overflowX}px offenders=${res.offenderCount} smallTargets=${res.smallCount} errors=${errs.length}`);
    if (res.offenderCount) console.log('   ->', JSON.stringify(res.offenders.slice(0, 6)));
    if (errs.length) console.log('   ERR', errs.slice(0, 3));
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, 'layout.json'), JSON.stringify(report, null, 2));
  await browser.close();
})();
