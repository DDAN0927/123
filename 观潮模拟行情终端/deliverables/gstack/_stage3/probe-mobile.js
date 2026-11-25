const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  for (const w of [375, 414, 560, 768]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 800 } });
    const p = await ctx.newPage();
    await p.goto(FILE, { waitUntil: 'load' });
    await p.waitForTimeout(700);
    const r = await p.evaluate(() => {
      const wrap = document.querySelector('.nav .wrap');
      const cs = getComputedStyle(wrap);
      const kids = [...wrap.children].map(el => {
        const r = el.getBoundingClientRect();
        return { cls: el.className || el.tagName, w: Math.round(r.width), l: Math.round(r.left), r: Math.round(r.right) };
      });
      const nr = document.querySelector('.nav-right');
      const nrKids = [...nr.children].map(el => {
        const r = el.getBoundingClientRect();
        const d = getComputedStyle(el).display;
        return { id: el.id || el.className, w: Math.round(r.width), r: Math.round(r.right), d };
      });
      const term = document.querySelector('.term');
      const tl = document.querySelector('.term-layout');
      const tbar = document.querySelector('.term-bar');
      const tsearch = document.querySelector('.term-search');
      const tinput = document.getElementById('termSearch');
      const seg = document.getElementById('marketSeg');
      return {
        vw: innerWidth, wrapPad: cs.paddingLeft + '|' + cs.paddingRight, wrapGap: cs.gap,
        wrapW: Math.round(wrap.getBoundingClientRect().width), kids,
        navRightKids: nrKids,
        term: { w: Math.round(term.getBoundingClientRect().width), scrollW: term.scrollWidth, minW: getComputedStyle(term).minWidth },
        termLayout: { w: Math.round(tl.getBoundingClientRect().width), cols: getComputedStyle(tl).gridTemplateColumns },
        tbar: { w: Math.round(tbar.getBoundingClientRect().width) },
        tsearch: { w: Math.round(tsearch.getBoundingClientRect().width), minW: getComputedStyle(tsearch).minWidth, basis: getComputedStyle(tsearch).flexBasis },
        tinput: { w: Math.round(tinput.getBoundingClientRect().width), minW: getComputedStyle(tinput).minWidth },
        seg: seg ? { w: Math.round(seg.getBoundingClientRect().width) } : null,
        hDoc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        bodyScrollW: document.body.scrollWidth,
      };
    });
    console.log(w, JSON.stringify(r, null, 0));
    await ctx.close();
  }
  await b.close();
})();
