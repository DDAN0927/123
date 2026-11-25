const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'index.html').replace(/\\/g, '/');
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}  ${d}`); if (!c) fail++; };
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => { fail++; console.log('FAIL  pageerror', e.message); });
  await p.goto(FILE, { waitUntil: 'load' });
  await p.waitForTimeout(1200);
  // 定位到终端表格
  await p.evaluate(() => document.querySelector('#hotBody').scrollIntoView());
  await p.waitForTimeout(300);

  // j:第一次按下 → 第一行获得光标
  await p.keyboard.press('j');
  let r = await p.evaluate(() => {
    const cur = document.querySelector('#hotBody tr.kb-cursor');
    return { idx: cur ? [...document.querySelectorAll('#hotBody tr')].indexOf(cur) : -1, code: cur && cur.dataset.code };
  });
  ok('j 选中第 1 行', r.idx === 0, `idx=${r.idx} code=${r.code}`);
  const code0 = r.code;
  await p.keyboard.press('j');
  await p.keyboard.press('j');
  r = await p.evaluate(() => document.querySelector('#hotBody tr.kb-cursor')?.dataset.code);
  ok('j 连按向下移动', r && r !== code0, `cur=${r}`);
  await p.keyboard.press('k');
  r = await p.evaluate(() => document.querySelector('#hotBody tr.kb-cursor')?.dataset.code);
  ok('k 向上回移(光标未丢)', !!r, `cur=${r}`);

  // Enter 打开抽屉(动态读当前光标行,tick 重渲染会导致行序重排,不做硬编码断言)
  const curCode = await p.evaluate(() => document.querySelector('#hotBody tr.kb-cursor')?.dataset.code);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(350);
  let dr = await p.evaluate(() => {
    const d = document.getElementById('drawer');
    return { on: d.classList.contains('is-on'), code: document.querySelector('#drawerSub').textContent.slice(0, 8) };
  });
  ok('Enter 打开抽屉', dr.on, `sub=${dr.code}`);
  ok('打开的是光标行', dr.code.startsWith(curCode), `${dr.code} vs ${curCode}`);

  // j/k 抽屉开着时直接切标的
  await p.keyboard.press('j');
  await p.waitForTimeout(250);
  const dr2 = await p.evaluate(() => document.querySelector('#drawerSub').textContent.slice(0, 8));
  ok('抽屉开着 j 直接切标的', dr2 !== dr.code, `${dr.code} → ${dr2}`);

  // 1-4 切抽屉页
  for (const [key, pane] of [['1', 'chart'], ['2', 'diag'], ['3', 'fund'], ['4', 'trade']]) {
    await p.keyboard.press(key);
    await p.waitForTimeout(120);
    const st = await p.evaluate((pn) => {
      const btn = document.querySelector(`.dh-tabs button[data-pane="${pn}"]`);
      const paneEl = document.getElementById('pane-' + pn);
      return btn.classList.contains('is-on') && !paneEl.hidden;
    }, pane);
    ok(`${key} 切到 ${pane} 页`, st, '');
  }

  // Esc 逐层:先关抽屉
  await p.keyboard.press('Escape');
  await p.waitForTimeout(250);
  const l1 = await p.evaluate(() => ({
    drawer: document.getElementById('drawer').classList.contains('is-on'),
  }));
  ok('Esc 第 1 层:抽屉关', !l1.drawer, '');
  // 此时无其他层 → 再按 Esc 不误关(无层可关)
  // 打开提醒抽屉再按 Esc 只关它,不影响导航
  await p.evaluate(() => document.getElementById('alertsBtn').click());
  await p.waitForTimeout(250);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(250);
  const l2 = await p.evaluate(() => document.getElementById('alertDrawer').classList.contains('is-on'));
  ok('Esc 关提醒抽屉', !l2, '');
  // 应用弹层互斥(openSettings/openDrawer 均先关其他层),逐层语义对 palette 生效
  await p.evaluate(() => document.getElementById('settingsBtn').click());
  await p.waitForTimeout(300);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(250);
  const l3 = await p.evaluate(() => ({
    set: document.getElementById('settingsModal').classList.contains('is-on'),
    pal: document.getElementById('palette').classList.contains('is-on'),
  }));
  ok('Esc 关设置弹层', !l3.set && !l3.pal, `set=${l3.set}`);

  // / 聚焦搜索(palette)
  await p.keyboard.press('/');
  await p.waitForTimeout(400);
  const pal = await p.evaluate(() => {
    const el = document.getElementById('palette');
    return { on: el.classList.contains('is-on'), focused: document.activeElement === document.getElementById('palInput') };
  });
  ok('/ 打开并聚焦搜索', pal.on && pal.focused, '');
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  const palOff = await p.evaluate(() => !document.getElementById('palette').classList.contains('is-on'));
  ok('Esc 关搜索', palOff, '');

  // 输入框聚焦时不劫持 j/k
  await p.evaluate(() => document.querySelector('#smartQuery').focus());
  await p.keyboard.type('jjkk');
  const typing = await p.evaluate(() => document.querySelector('#smartQuery').value);
  ok('输入框聚焦不劫持按键', typing === 'jjkk', `value=${typing}`);

  // 翻页后光标清除(renderTable 重渲染)
  await p.evaluate(() => document.querySelector('#smartQuery').blur());
  await p.keyboard.press('j');
  await p.keyboard.press('j');
  await p.evaluate(() => { [...document.querySelectorAll('#pager button')].pop().click(); });
  await p.waitForTimeout(300);
  const cleared = await p.evaluate(() => document.querySelectorAll('#hotBody tr.kb-cursor').length);
  ok('翻页后光标清除', cleared === 0, `n=${cleared}`);

  await b.close();
  console.log(fail ? `\n${fail} FAILED` : '\nALL PASS');
  process.exit(fail ? 1 : 0);
})();
