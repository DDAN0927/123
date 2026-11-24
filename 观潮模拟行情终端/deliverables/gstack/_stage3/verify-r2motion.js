// verify-r2motion.js — 设计审计 Round 2(动效与交互)探针
// 覆盖:时长 4 档收口 / intel-row 去 padding 位移 / dot-live 脉冲合成层化 /
// reduced-motion 全量兜底 / :focus-visible 与 disabled 三态 / 抽屉 .24s 回归
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
let pass = 0, fail = 0;
const ok = (name, cond, detail) => {
  if (cond) { pass++; console.log('PASS', name, detail || ''); }
  else { fail++; console.log('FAIL', name, detail || ''); }
};
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const url = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

  // —— 正常动画上下文 ——
  const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await p.goto(url, { waitUntil: 'load' });
  await p.waitForTimeout(1200);

  // 1. 全表 transition-duration 收口 4 档
  const census = await p.evaluate(() => {
    const found = new Set();
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list) => {
        for (const r of list) {
          if (r.cssRules) { walk(r.cssRules); continue; }
          if (r.style && r.style.transitionDuration && r.style.transitionDuration !== '') {
            r.style.transitionDuration.split(',').forEach((d) => found.add(d.trim()));
          }
        }
      };
      walk(rules);
    }
    return [...found];
  });
  const bad = census.filter((d) => !['0.12s', '0.2s', '0.24s', '0.56s'].includes(d));
  ok('时长收口 4 档', bad.length === 0, `违规: ${bad.join(',') || '无'} / 全集: ${census.join(',')}`);

  // 2. 时长令牌生效
  const tok = await p.evaluate(() => {
    const cs = getComputedStyle(document.documentElement);
    return { fast: cs.getPropertyValue('--t-fast').trim(), state: cs.getPropertyValue('--t-state').trim(), panel: cs.getPropertyValue('--t-panel').trim(), enter: cs.getPropertyValue('--t-enter').trim() };
  });
  ok('时长令牌 4 个', tok.fast === '.12s' && tok.state === '.2s' && tok.panel === '.24s' && tok.enter === '.56s', JSON.stringify(tok));

  // 3. .rv 入场 0.56s
  const rvDur = await p.evaluate(() => {
    const el = document.querySelector('.rv');
    return el ? getComputedStyle(el).transitionDuration : 'missing';
  });
  ok('.rv 入场 560ms', rvDur.split(',')[0].trim() === '0.56s', rvDur);

  // 4. intel-row:hover 不再触发 layout(padding 位移)
  const intel = await p.evaluate(() => {
    const row = document.querySelector('.intel-row');
    if (!row) return { missing: true };
    const before = row.getBoundingClientRect();
    const props = getComputedStyle(row).transitionProperty;
    row.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    const after = row.getBoundingClientRect();
    return { props, stable: Math.abs(after.left - before.left) < 0.5 && Math.abs(after.width - before.width) < 0.5 };
  });
  ok('intel-row 过渡不含 padding', !intel.missing && !/padding/.test(intel.props), intel.props);
  ok('intel-row hover 无位移', !intel.missing && intel.stable, '');

  // 5. dot-live 脉冲:本体静止,::after 走 transform
  const dot = await p.evaluate(() => {
    const el = document.querySelector('.dot-live');
    if (!el) return { missing: true };
    const kf = [...document.styleSheets].flatMap((s) => { try { return [...s.cssRules]; } catch { return []; } })
      .filter((r) => r.cssRules && r.name === 'pulse')
      .map((r) => r.cssText).join('');
    return {
      selfAnim: getComputedStyle(el).animationName,
      afterAnim: getComputedStyle(el, '::after').animationName,
      kfTransform: /transform/.test(kf), kfShadow: /box-shadow/.test(kf),
    };
  });
  ok('dot-live 本体无动画', !dot.missing && dot.selfAnim === 'none', dot.selfAnim);
  ok('脉冲环在 ::after', !dot.missing && dot.afterAnim === 'pulse', dot.afterAnim);
  ok('pulse 关键帧走 transform 弃 box-shadow', !dot.missing && dot.kfTransform && !dot.kfShadow, '');

  // 6. 抽屉时长保持 .24s(C6 决策不回退)
  const drawerDur = await p.evaluate(() => getComputedStyle(document.getElementById('drawer')).transitionDuration);
  ok('抽屉 240ms 保持', drawerDur === '0.24s', drawerDur);

  // 7. focus-visible 全局描边
  await p.keyboard.press('Tab');
  await p.keyboard.press('Tab');
  const fv = await p.evaluate(() => {
    const el = document.activeElement;
    const cs = getComputedStyle(el);
    return { tag: el.tagName + '.' + (el.className || '').toString().slice(0, 16), style: cs.outlineStyle, width: cs.outlineWidth };
  });
  ok('Tab 聚焦有可见描边', fv.style !== 'none' && parseFloat(fv.width) >= 1, `${fv.tag} ${fv.style} ${fv.width}`);

  // 8. disabled 三态
  const dis = await p.evaluate(() => {
    const btn = document.querySelector('button.btn') || document.querySelector('button:not([disabled])');
    if (!btn) return { missing: true };
    btn.disabled = true;
    const o = parseFloat(getComputedStyle(btn).opacity);
    const c = getComputedStyle(btn).cursor;
    btn.disabled = false;
    return { opacity: o, cursor: c };
  });
  ok('disabled 降透明 + not-allowed', !dis.missing && dis.opacity < 0.9 && /not-allowed/.test(dis.cursor), `op=${dis.opacity} cur=${dis.cursor}`);

  // —— reduced-motion 上下文 ——
  const p2 = await (await b.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })).newPage();
  await p2.goto(url, { waitUntil: 'load' });
  await p2.waitForTimeout(800);
  const rm = await p2.evaluate(() => {
    let animating = 0;
    document.querySelectorAll('*').forEach((el) => {
      const a = getComputedStyle(el).animationName;
      if (a && a !== 'none') {
        const d = parseFloat(getComputedStyle(el).animationDuration);
        if (d > 0.05) animating++;
      }
    });
    const drawer = getComputedStyle(document.getElementById('drawer'));
    const dot = document.querySelector('.dot-live');
    return {
      animating,
      drawerDur: parseFloat(drawer.transitionDuration),
      dotAnim: dot ? getComputedStyle(dot, '::after').animationDuration : 'missing',
      rvOpacity: getComputedStyle(document.querySelector('.rv')).opacity,
    };
  });
  ok('reduced-motion 动画元素 ≤2', rm.animating <= 2, `仍在动: ${rm.animating}`);
  ok('reduced-motion 过渡时长 ≈0', rm.drawerDur < 0.05, `${rm.drawerDur}s`);
  ok('reduced-motion 脉冲环停摆', rm.dotAnim !== 'missing' && parseFloat(rm.dotAnim) < 0.05, `${rm.dotAnim}s`);
  ok('reduced-motion 入场直接可见', rm.rvOpacity === '1', rm.rvOpacity);

  await b.close();
  console.log(`\n${pass + fail} 项: ${pass} PASS, ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})();
