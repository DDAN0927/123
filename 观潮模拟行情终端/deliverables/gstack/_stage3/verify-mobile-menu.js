const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 375, height: 667 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(800);
  const navRight = await p.evaluate(() => {
    const r = document.querySelector('.nav-right').getBoundingClientRect();
    const m = document.getElementById('mobileMenu').getBoundingClientRect();
    return { right: Math.round(r.right), menuRight: Math.round(m.right), menuW: Math.round(m.width), vw: document.documentElement.clientWidth };
  });
  console.log('navRight', JSON.stringify(navRight));
  await p.click('#mobileMenu');
  await p.waitForTimeout(400);
  await p.screenshot({ path: 'layout/mobile-menu-open.png' });
  const items = await p.evaluate(() => [...document.querySelectorAll('.nav-links a')].filter(a => a.offsetHeight > 0).map(a => ({ t: a.textContent.trim(), h: Math.round(a.getBoundingClientRect().height) })));
  console.log('menu items', JSON.stringify(items));
  // 点「明暗主题」
  await p.click('.nav-links a[data-mact="theme"]');
  await p.waitForTimeout(500);
  const theme = await p.evaluate(() => document.documentElement.getAttribute('data-theme'));
  const open = await p.evaluate(() => document.querySelector('.nav-links').classList.contains('is-open'));
  console.log('after theme click: theme=', theme, 'panelOpen=', open);
  // 再开菜单点「设置」
  await p.click('#mobileMenu'); await p.waitForTimeout(300);
  await p.click('.nav-links a[data-mact="settings"]');
  await p.waitForTimeout(600);
  const st = await p.evaluate(() => {
    const m = document.getElementById('settingsModal');
    const cs = getComputedStyle(m);
    return { open: m.classList.contains('is-open') || cs.opacity === '1' || m.getAttribute('aria-hidden') === 'false', w: Math.round(m.getBoundingClientRect().width) };
  });
  console.log('settings open', JSON.stringify(st));
  await p.screenshot({ path: 'layout/mobile-settings-from-menu.png' });
  console.log('errors', errs.length, errs.slice(0, 3));
  await b.close();
})();
