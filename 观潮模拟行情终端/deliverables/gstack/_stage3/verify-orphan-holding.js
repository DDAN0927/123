/* 持仓「无法定价」专项:标的掉出股票池后,持仓不能从总资产里静默蒸发。
   触发路径(都是真实 UI 路径,不是构造):
    1) 东财/新浪真实快照同步 -> resetUniverseTo(仅 CN)
    2) CSV 快照导入 -> applyImportedUniverse(整体替换)
    3) 刷新时加载缓存快照 -> loadSnapshotIntoUniverse
   三者都会整体替换 STOCKS/BY_CODE。持有美股再同步 A 股 = NVDA 立刻变孤儿。
   断言的期望:可定价的照常算,不可定价的**显式计数并给出成本**,不编造价格。
   用法:node verify-orphan-holding.js  → 任一不满足退出码 1 */
const { chromium } = require('../_baseline/node_modules/playwright');
const path = require('path');
const FILE = 'file:///' + path.resolve(__dirname, '../../..', 'index.html').replace(/\\/g, '/');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log(`  PASS ${name}${extra ? ' — ' + extra : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${extra ? ' — ' + extra : ''}`); }
};
const head = (s) => console.log(`\n===== ${s} =====`);

/* 一次性读取面板所有可见结论 */
const readPf = (p) => p.evaluate(() => {
  const t = (sel) => (document.querySelector(sel) || {}).textContent || '';
  const m = accountMetrics();
  return {
    total: document.getElementById('pfTotal').textContent,
    totalNum: m.total,
    mv: m.mv,
    rowCount: document.querySelectorAll('#pfHoldBody tr').length,
    rowCodes: Array.from(document.querySelectorAll('#pfHoldBody tr')).map((tr) => tr.dataset.code),
    holdMeta: t('#pfHoldMeta'),
    orphanText: t('[data-dq="orphan"]'),
    diverDq: t('[data-dq="diver"]'),
    discDq: t('[data-dq="disc"]'),
    discMeta: t('#pfDiscMeta'),
    discChips: Array.from(document.querySelectorAll('#pfDisc .disc-chip')).map((c) => c.textContent),
    diverKpis: t('#pfDivers .diver-kpis'),
    diverNote: t('#pfDivers .disc-note'),
  };
});

(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(FILE + '?api=off', { waitUntil: 'load' });
  await p.waitForTimeout(900);
  await p.evaluate(() => { if (typeof liveTimer !== 'undefined' && liveTimer) clearInterval(liveTimer); });

  /* ---------- 构造:持有 1 只美股 + 1 只 A 股,现金 50 万 ---------- */
  const setup = await p.evaluate(() => {
    const us = BY_CODE['NVDA'] || STOCKS.find((s) => s.market === 'US');
    const cn = BY_CODE['600519'] || STOCKS.find((s) => s.market === 'CN');
    if (!us || !cn) return { ok: false };
    const cash = 500000;
    const pos = {};
    pos[us.code] = { qty: 100, cost: us.last };
    pos[cn.code] = { qty: 100, cost: cn.last };
    window.__us = us.code;
    window.__cn = cn.code;
    account = { cash, positions: pos, trades: [], realized: 0, dayRealized: 0, dayStamp: dayStamp() };
    saveAccount();
    openPortfolio();
    return { ok: true, us: us.code, usLast: us.last, cn: cn.code, cnLast: cn.last, cash };
  });
  if (!setup.ok) { console.log('无法构造测试持仓(缺 US/CN 标的)'); process.exit(1); }
  await p.waitForTimeout(300);
  const before = await readPf(p);

  head('A. 基线:两只持仓都可见');
  ok('两只持仓都在表里', before.rowCount === 2, before.rowCodes.join(','));
  const mvExpect = setup.usLast * 100 + setup.cnLast * 100;
  ok('总资产 = 现金 + 两只有市值', Math.abs(before.totalNum - (setup.cash + mvExpect)) < 1, `${before.totalNum.toFixed(2)}`);
  ok('无「无法定价」提示(dq 行不存在或为空)', !before.orphanText.trim(), before.orphanText);

  /* ---------- B. 真实路径:同步 A 股快照(整体替换股票池,美股掉出) ---------- */
  head('B. 同步 A 股快照后,美股持仓变成「无法定价」');
  const after = await p.evaluate(() => {
    const cnOnly = STOCKS.filter((s) => s.market === 'CN');
    resetUniverseTo(cnOnly, true);      /* 与 syncEastmoney 成功后走的是同一个函数 */
    renderPortfolio();
    const m = accountMetrics();
    const p = account.positions;
    return { cnPool: cnOnly.length, hasNvda: !!BY_CODE['NVDA'], keptPos: Object.keys(p), totalNum: m.total, mv: m.mv };
  });
  await p.waitForTimeout(200);
  const b2 = await readPf(p);
  ok('股票池已被替换(美股不在池内)', after.cnPool > 0 && !after.hasNvda, `CN ${after.cnPool} 只, BY_CODE['NVDA']=${after.hasNvda}`);
  ok('持仓记录本身没丢(账户状态仍持有 2 只)', after.keptPos.length === 2, after.keptPos.join(','));

  head('C. 核心:不可定价的持仓必须被数出来,不能静默蒸发');
  ok('持仓表仍列出 2 行(或在孤儿区列出)', b2.rowCount === 2, `实际 ${b2.rowCount} 行:${b2.rowCodes.join(',')}`);
  ok('界面出现「无法定价」质量提示', /无法定价|未计入/.test(b2.orphanText), `dq 行=${JSON.stringify(b2.orphanText)}`);
  ok('提示里带具体只数', /1\s*只/.test(b2.orphanText) || /1 只/.test(b2.holdMeta), `meta=${b2.holdMeta}`);
  ok('总资产不再包含不可定价市值(不编造价格)', b2.totalNum < before.totalNum - 1, `${before.totalNum.toFixed(0)} -> ${b2.totalNum.toFixed(0)}`);
  ok('不可定价持仓的成本被披露(用户能自己算)', /成本/.test(b2.orphanText), b2.orphanText);

  head('D. 分散度:权重只覆盖可定价部分,必须在面板上说清');
  ok('分散度面板出现数据质量行', !!b2.diverDq.trim(), b2.diverDq);
  ok('质量行说明有持仓未计入', /未计入|无法定价|可定价/.test(b2.diverDq), b2.diverDq);

  head('E. 纪律:止损检查覆盖不到不可定价持仓,不能算「通过」');
  ok('纪律面板出现数据质量行', !!b2.discDq.trim(), b2.discDq);
  ok('止损规则不是干净的 ✓(不可判定须标注)', !/止损在位 · 全部在位/.test(b2.discChips.join(' ')) || /缺失|未计/.test(b2.discDq), b2.discChips.join(' | '));

  /* ---------- F. 恢复股票池后回到基线(降级是暂时的,不是一次性污染) ---------- */
  head('F. 恢复股票池后回到基线');
  const back = await p.evaluate(() => {
    resetUniverseTo(CURATED.concat(STOCKS), true);
    renderPortfolio();
    return accountMetrics();
  });
  await p.waitForTimeout(200);
  const b3 = await readPf(p);
  ok('恢复后不再报「无法定价」', !/无法定价|未计入/.test(b3.orphanText), b3.orphanText);
  ok('恢复后总资产回到基线', Math.abs(back.total - before.totalNum) < 1, `${back.total.toFixed(0)} vs ${before.totalNum.toFixed(0)}`);
  ok('恢复后持仓表 2 行', b3.rowCount === 2, b3.rowCodes.join(','));

  head('G. 新增文字的可读性(亮/暗各测一次,WCAG 4.5:1)');
  /* F 段已把股票池恢复,孤儿行随之消失 —— 要测这些文字必须先把降级态重新造出来。
     (第一版漏了这一步,量到的是「元素不存在」,属于探针自身的顺序错误) */
  await p.evaluate(() => { resetUniverseTo(STOCKS.filter((s) => s.market === 'CN'), true); renderPortfolio(); });
  await p.waitForTimeout(300);
  /* contrast.js 只扫当前渲染出的文本,而孤儿行与质量行要「有孤儿」才存在,
     不在这里单测就等于没测。alpha 逐层合成后再算,朴素比较会误报。 */
  const ratioOf = (p, sels) => p.evaluate((map) => {
    const parse = (c) => {
      const m = String(c).match(/[\d.]+/g);
      if (!m) return null;
      const n = m.map(Number);
      if (/^color\(srgb/i.test(String(c))) return { r: n[0] * 255, g: n[1] * 255, b: n[2] * 255, a: String(c).includes('/') ? n[3] : 1 };
      return { r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1 };
    };
    const over = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
    const effBg = (el) => {
      const st = []; let n = el;
      while (n && n.nodeType === 1) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { st.push(c); if (c.a >= 1) break; } n = n.parentElement; }
      let base = { r: 255, g: 255, b: 255, a: 1 };
      for (let i = st.length - 1; i >= 0; i--) base = over(st[i], base);
      return base;
    };
    const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
    const one = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      const bg = effBg(el);
      const fg0 = parse(cs.color);
      const fg = fg0.a < 1 ? over(fg0, bg) : fg0;
      const L1 = lum(fg), L2 = lum(bg);
      return { r: +(((Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05)).toFixed(2)), size: cs.fontSize, color: cs.color };
    };
    const out = {};
    Object.keys(map).forEach((k) => { out[k] = one(map[k]); });
    return out;
  }, sels);
  const ORPH_SELS = {
    dqText: '[data-dq="orphan"] span:not(.dq-tag)',
    dqTag: '[data-dq="orphan"] .dq-tag',
    orphName: '#pfHoldBody tr.is-orphan .nm',
    orphCd: '#pfHoldBody tr.is-orphan .cd',
    orphCell: '#pfHoldBody tr.is-orphan td',
    /* 注销按钮是本轮新增的可点元素:它自己带 color:var(--accent),不跟随 td 的 --mute */
    orphBtn: '#pfHoldBody tr.is-orphan .pf-orphan-act',
  };
  const contrast = async (label) => {
    const r = await ratioOf(p, ORPH_SELS);
    Object.keys(r).forEach((k) => {
      const v = r[k];
      if (!v) { ok(`${label} ${k} 元素存在`, false, '未找到'); return; }
      ok(`${label} ${k} ≥4.5:1`, v.r >= 4.5, `${v.r}:1 (${v.size}, ${v.color})`);
    });
  };
  /* 两套主题都要显式切:页面初始主题取决于系统偏好,不能拿「当前算什么」
     当第一份样本 —— 第一版就是这么量的,两次都是亮色,却标成了「暗色/亮色」。
     下面另加一条断言:两次取色必须不同,否则说明切主题没生效,量了同一套。 */
  await p.evaluate(() => setTheme('dark'));
  await p.waitForTimeout(700);
  const darkSample = await ratioOf(p, ORPH_SELS);
  const darkVals = Object.keys(darkSample).map((k) => darkSample[k] && darkSample[k].color);
  await p.evaluate(() => setTheme('light'));
  await p.waitForTimeout(700);
  const lightSample = await ratioOf(p, ORPH_SELS);
  const lightVals = Object.keys(lightSample).map((k) => lightSample[k] && lightSample[k].color);
  ok('两次取色不同(证明确实切过主题)', JSON.stringify(darkVals) !== JSON.stringify(lightVals), `${darkVals[0]} vs ${lightVals[0]}`);
  const check = (label, r) => Object.keys(r).forEach((k) => {
    const v = r[k];
    if (!v) { ok(`${label} ${k} 元素存在`, false, '未找到'); return; }
    ok(`${label} ${k} ≥4.5:1`, v.r >= 4.5, `${v.r}:1 (${v.size}, ${v.color})`);
  });
  check('暗色', darkSample);
  check('亮色', lightSample);
  await p.evaluate(() => setTheme('dark'));
  await p.waitForTimeout(400);

  /* ---------- I. 孤儿持仓的退出通道:二次确认 + 按成本退回 + 留痕 ----------
     这些断言全部跑在真实 DOM 上(点真按钮),因为要防的正是「点一下就没了」。
     注意:此时主题已被 G 段切回 dark,BY_CODE 只有 A 股,孤儿仍在。 */
  head('I. 孤儿持仓的退出通道:二次确认 / 按成本退回 / 留痕');
  const pre = await p.evaluate(() => {
    const m = accountMetrics();
    const btn = document.querySelector('#pfHoldBody tr.is-orphan [data-close-orphan]');
    return {
      cash: account.cash, total: m.total, orphan: m.orphan.length, rows: document.querySelectorAll('#pfHoldBody tr').length,
      btn: !!btn, btnTxt: btn ? btn.textContent.trim() : '',
      costAmt: m.orphan.reduce((a, o) => a + o.costAmt, 0), realized: account.realized,
    };
  });
  ok('孤儿行有注销按钮', pre.btn, pre.btnTxt);
  ok('文案是「按成本注销」而非「卖出」', /按成本注销/.test(pre.btnTxt) && !/卖出/.test(pre.btnTxt), pre.btnTxt);

  /* 孤儿行空白处:不能关抽屉。旧实现把孤儿当普通行处理 —— closePortfolio 之后
     openDrawer(一个 BY_CODE 查不到的代码),结果就是「点一下抽屉没了,什么也没发生」。 */
  await p.click('#pfHoldBody tr.is-orphan .nm');
  await p.waitForTimeout(350);
  const rowClick = await p.evaluate(() => ({
    on: document.querySelector('#portfolio').classList.contains('is-on'),
    cash: account.cash,
  }));
  ok('点孤儿行空白处不关抽屉', rowClick.on === true, `is-on=${rowClick.on}`);
  ok('点孤儿行空白处不动账', Math.abs(rowClick.cash - pre.cash) < 1e-9, rowClick.cash.toFixed(2));

  /* 先验「手滑防护」:点一次进入待确认,4 秒不点自动撤回,期间账面一分不动。
     这条要真等 4 秒 —— 用假时钟测不到 setTimeout 与 DOM 文本的真实联动。 */
  await p.click('#pfHoldBody tr.is-orphan [data-close-orphan]');
  await p.waitForTimeout(250);
  const armedState = await p.evaluate(() => ({
    armed: !!document.querySelector('#pfHoldBody [data-armed="1"]'),
    txt: (document.querySelector('#pfHoldBody [data-close-orphan]') || {}).textContent || '',
    cash: account.cash,
  }));
  ok('点一次进入待确认', armedState.armed && /再点一次/.test(armedState.txt), armedState.txt.trim());
  const armC = await ratioOf(p, { arm: '#pfHoldBody [data-close-orphan].is-arming' });
  ok('待确认态文字仍 ≥4.5:1', !!(armC.arm && armC.arm.r >= 4.5), armC.arm ? `${armC.arm.r}:1 (${armC.arm.color})` : '未找到');
  await p.waitForTimeout(4300);
  const disarmed = await p.evaluate(() => ({
    armed: !!document.querySelector('#pfHoldBody [data-armed="1"]'),
    txt: (document.querySelector('#pfHoldBody [data-close-orphan]') || {}).textContent || '',
    cash: account.cash,
    orphan: accountMetrics().orphan.length,
  }));
  ok('4 秒不操作自动撤回', !disarmed.armed && /^按成本注销$/.test(disarmed.txt.trim()), `armed=${disarmed.armed} txt=${disarmed.txt.trim()}`);
  ok('撤回后账面仍未动', Math.abs(disarmed.cash - pre.cash) < 1e-9 && disarmed.orphan === pre.orphan, `cash=${disarmed.cash.toFixed(2)} orphan=${disarmed.orphan}`);

  /* 正式走一遍:点两次 */
  await p.click('#pfHoldBody tr.is-orphan [data-close-orphan]');
  await p.waitForTimeout(250);
  const mid = await p.evaluate(() => ({
    cash: account.cash, rows: document.querySelectorAll('#pfHoldBody tr').length,
    orphan: accountMetrics().orphan.length,
    armed: !!document.querySelector('#pfHoldBody [data-armed="1"]'),
    btnTxt: (document.querySelector('#pfHoldBody [data-close-orphan]') || {}).textContent || '',
  }));
  ok('第一次点击不动账', Math.abs(mid.cash - pre.cash) < 1e-9, `${pre.cash.toFixed(2)} -> ${mid.cash.toFixed(2)}`);
  ok('第一次点击不删持仓', mid.orphan === pre.orphan && mid.rows === pre.rows, `orphan=${mid.orphan} rows=${mid.rows}`);
  ok('第一次点击进入待确认态', mid.armed && /再点一次/.test(mid.btnTxt), mid.btnTxt.trim());

  /* 第二次点击:执行 */
  await p.click('#pfHoldBody tr.is-orphan [data-close-orphan]');
  await p.waitForTimeout(350);
  const post = await p.evaluate(() => {
    const m = accountMetrics();
    return {
      cash: account.cash, total: m.total, orphan: m.orphan.length,
      rows: document.querySelectorAll('#pfHoldBody tr').length,
      dq: (document.querySelector('[data-dq="orphan"]') || {}).textContent || '',
      tradeTxt: (document.querySelector('#pfTradeList') || {}).textContent || '',
      realized: account.realized, rec: account.trades[0] || null,
    };
  });
  ok('注销后持仓表只剩 1 行', post.rows === 1, `rows=${post.rows}`);
  ok('现金按成本退回', Math.abs(post.cash - (pre.cash + pre.costAmt)) < 1e-6, `${pre.cash.toFixed(2)} -> ${post.cash.toFixed(2)}(成本 ${pre.costAmt.toFixed(2)})`);
  ok('总资产补回原先悬在账外的成本', Math.abs(post.total - (pre.total + pre.costAmt)) < 1e-6, `${pre.total.toFixed(2)} -> ${post.total.toFixed(2)}`);
  ok('注销不计盈亏(realized 不动)', post.realized === pre.realized, `${pre.realized} -> ${post.realized}`);
  ok('「无法定价」质量行随之消失', !post.dq.trim(), post.dq);
  ok('成交记录写明「注销 · 按成本」', /注销/.test(post.tradeTxt) && /按成本/.test(post.tradeTxt), post.tradeTxt.replace(/\s+/g, ' ').trim().slice(0, 70));
  ok('留痕是 side=close 且零费用', !!post.rec && post.rec.side === 'close' && post.rec.fee === 0, JSON.stringify(post.rec));

  /* 刷新:close 记录必须活着。记录丢了而现金变了,就是「反向静默」 */
  await p.reload({ waitUntil: 'load' });
  await p.waitForTimeout(900);
  await p.evaluate(() => { if (typeof liveTimer !== 'undefined' && liveTimer) clearInterval(liveTimer); openPortfolio(); });
  await p.waitForTimeout(300);
  const afterReload = await p.evaluate(() => ({
    hasClose: account.trades.some((t) => t.side === 'close'),
    tradeTxt: (document.querySelector('#pfTradeList') || {}).textContent || '',
    cash: account.cash,
  }));
  ok('刷新后注销记录仍在(持久化放行了 close)', afterReload.hasClose, `现金 ${afterReload.cash.toFixed(2)}`);
  ok('刷新后成交列表仍显示「注销」', /注销/.test(afterReload.tradeTxt), afterReload.tradeTxt.replace(/\s+/g, ' ').trim().slice(0, 60));
  ok('刷新后现金没有回退', Math.abs(afterReload.cash - post.cash) < 1e-6, `${post.cash.toFixed(2)} vs ${afterReload.cash.toFixed(2)}`);

  head('H. 运行期零异常');
  ok('零 pageerror', errs.length === 0, errs.slice(0, 3).join(' | '));

  console.log('\n实测数值:', JSON.stringify({
    before: { total: +before.totalNum.toFixed(2), rows: before.rowCount },
    after: { total: +b2.totalNum.toFixed(2), rows: b2.rowCount },
    orphan: b2.orphanText,
  }));
  console.log(`\n结果: ${pass} 通过 / ${fail} 失败`);
  await b.close();
  process.exit(fail ? 1 : 0);
})();
