/**
 * 观潮 · 提醒判定单元测试
 * 覆盖 SEC-01(pct_up/pct_down 被当成 below)与 SEC-12(邮件 HTML 转义)的回归。
 * 运行:node --test tests/unit/
 */
import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import worker, { esc } from '../../backend/worker.js';

const REAL_FETCH = globalThis.fetch;

afterEach(() => { globalThis.fetch = REAL_FETCH; });

/* ---------- mock 基础设施 ---------- */

// env.DB:prepare(sql) → { bind() → self, all(), first(), run() }
function makeEnv(rows, { mail = true } = {}) {
  const calls = { updates: [] };
  const DB = {
    prepare(sql) {
      const stmt = {
        args: [],
        bind(...args) { stmt.args = args; return stmt; },
        async all() {
          if (/FROM\s+states/i.test(sql)) return { results: rows };
          return { results: [] };
        },
        async first() { return null; },
        async run() {
          if (/UPDATE\s+states/i.test(sql)) calls.updates.push(stmt.args);
          return { success: true };
        },
      };
      return stmt;
    },
  };
  const env = { DB };
  if (mail) { env.RESEND_API_KEY = 'test-key'; env.ALERT_FROM = 'alerts@test.dev'; }
  return { env, calls };
}

// 拦截东财 ulist 与 Resend;quotes: { '600519': { price, chg } }
function stubNet(quotes, mails) {
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    if (u.startsWith('https://push2.eastmoney.com/api/qt/ulist.np/get')) {
      const secids = new URL(u).searchParams.get('secids').split(',');
      const diff = secids.map((sid) => {
        const code = sid.slice(sid.indexOf('.') + 1); // '1.600519' → '600519'
        const q = quotes[code];
        if (!q) return { f12: code, f2: '-', f3: '-' };
        return { f12: code, f2: String(q.price), f3: String(q.chg) };
      });
      return { ok: true, json: async () => ({ data: { diff } }) };
    }
    if (u === 'https://api.resend.com/emails') {
      mails.push(JSON.parse(init.body));
      return { ok: true, json: async () => ({ id: 'test-mail' }) };
    }
    throw new Error('unexpected fetch: ' + u);
  };
}

// scheduled 把 handleAlerts 交给 ctx.waitUntil,这里捕获并 await 它
async function runCron(env) {
  let pending = null;
  await worker.scheduled({ cron: '*/5 * * * *' }, env, { waitUntil: (p) => { pending = p; } });
  assert.ok(pending, 'scheduled 必须通过 ctx.waitUntil 交出 handleAlerts 的 promise');
  return await pending;
}

function rowsOf(alerts) {
  return [{ user_id: 'u1', email: 'u1@test.dev', data: JSON.stringify({ alerts }) }];
}

// 取邮件正文段落(第一个 line-height:1.7 的 <p>)
function mailBody(html) {
  const m = /<p style="color:#555;line-height:1\.7">([\s\S]*?)<\/p>/.exec(html);
  assert.ok(m, '邮件里应存在正文段落');
  return m[1];
}

/* ---------- 1. pct_up ---------- */

test('pct_up 阈值 5:chg=6 命中且文案带 %', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '600519', dir: 'pct_up', price: 5 }]));
  const mails = [];
  stubNet({ '600519': { price: 1680, chg: 6 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 1);
  assert.equal(calls.updates.length, 1, '命中后应回写 states');
  assert.equal(mails.length, 1, '命中后应发一封邮件');
  const body = mailBody(mails[0].html);
  assert.match(body, /涨幅 6\.00% ≥ 5%/);
  assert.doesNotMatch(body, /跌破/, '百分比提醒不得渲染成"跌破"');
});

test('pct_up 阈值 5:chg=3 不命中', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '600519', dir: 'pct_up', price: 5 }]));
  const mails = [];
  stubNet({ '600519': { price: 1680, chg: 3 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 0);
  assert.equal(calls.updates.length, 0);
  assert.equal(mails.length, 0);
});

/* ---------- 2. pct_down ---------- */

test('pct_down 阈值 5:chg=-6 命中且文案带 %', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '000001', dir: 'pct_down', price: 5 }]));
  const mails = [];
  stubNet({ '000001': { price: 11, chg: -6 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 1);
  assert.equal(calls.updates.length, 1);
  assert.equal(mails.length, 1);
  const body = mailBody(mails[0].html);
  assert.match(body, /跌幅 6\.00% ≥ 5%/);
  assert.match(body, /%/, '跌幅阈值必须以百分比呈现');
});

test('pct_down 阈值 5:chg=-3 不命中', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '000001', dir: 'pct_down', price: 5 }]));
  const mails = [];
  stubNet({ '000001': { price: 11, chg: -3 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 0);
  assert.equal(calls.updates.length, 0);
  assert.equal(mails.length, 0);
});

/* ---------- 3. above / below 仍然正常 ---------- */

test('above 10 / price 11 命中,below 10 / price 11 不命中', async () => {
  const up = makeEnv(rowsOf([{ id: 'a1', code: '600000', dir: 'above', price: 10 }]));
  const upMails = [];
  stubNet({ '600000': { price: 11, chg: 1 } }, upMails);
  const rUp = await runCron(up.env);
  assert.equal(rUp.hit, 1, 'above 应命中');
  assert.equal(upMails.length, 1);
  assert.match(mailBody(upMails[0].html), /突破 10\(现价 11\)/);

  const down = makeEnv(rowsOf([{ id: 'a1', code: '600000', dir: 'below', price: 10 }]));
  const downMails = [];
  stubNet({ '600000': { price: 11, chg: 1 } }, downMails);
  const rDown = await runCron(down.env);
  assert.equal(rDown.hit, 0, 'below 不应命中');
  assert.equal(downMails.length, 0);
});

/* ---------- 4/5. 回归守卫:旧代码的两类误判 ---------- */

test('回归守卫:高价股 1680 挂 pct_up 5、chg=1 → 不命中(旧代码恒 false 静默失效)', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '600519', dir: 'pct_up', price: 5 }]));
  const mails = [];
  stubNet({ '600519': { price: 1680, chg: 1 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 0);
  assert.equal(calls.updates.length, 0);
  assert.equal(mails.length, 0);
});

test('回归守卫:低价股 3 挂 pct_up 5、chg=0 → 不命中(旧代码因 price<=5 立即误触发)', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '000002', dir: 'pct_up', price: 5 }]));
  const mails = [];
  stubNet({ '000002': { price: 3, chg: 0 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 0, '价格低于阈值但涨幅为 0,不得触发');
  assert.equal(calls.updates.length, 0, '不得把 hit 写回');
  assert.equal(mails.length, 0, '不得发邮件');
});

test('回归守卫:低价股 3 挂 pct_down 5、chg=0 → 不命中(旧代码因 price<=5 立即误触发)', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '000003', dir: 'pct_down', price: 5 }]));
  const mails = [];
  stubNet({ '000003': { price: 3, chg: 0 } }, mails);

  const r = await runCron(env);

  assert.equal(r.hit, 0);
  assert.equal(calls.updates.length, 0);
  assert.equal(mails.length, 0);
});

/* ---------- 6. 未知方向 ---------- */

test('未知方向 foo → 不命中,不得回退成 below', async () => {
  const { env, calls } = makeEnv(rowsOf([{ id: 'a1', code: '600000', dir: 'foo', price: 100 }]));
  const mails = [];
  stubNet({ '600000': { price: 11, chg: 0 } }, mails); // 若回退成 below,11<=100 会命中

  const r = await runCron(env);

  assert.equal(r.hit, 0);
  assert.equal(calls.updates.length, 0);
  assert.equal(mails.length, 0);
});

/* ---------- 7. 邮件 HTML 转义 ---------- */

test('esc 转义 & < > " \'', () => {
  assert.equal(esc('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  assert.equal(esc(`&"'`), '&amp;&quot;&#39;');
  assert.equal(esc(123), '123');
  assert.equal(esc(null), 'null');
});

test('邮件正文只允许 <br> 标签,动态片段不得产生裸标签', async () => {
  const { env } = makeEnv(rowsOf([{ id: 'a1', code: '600519', dir: 'pct_up', price: 5 }]));
  const mails = [];
  stubNet({ '600519': { price: 1680, chg: 6 } }, mails);

  await runCron(env);

  const body = mailBody(mails[0].html);
  const withoutBr = body.replace(/<br>/g, '');
  assert.ok(!/[<>]/.test(withoutBr), `正文不得含裸标签,实际:${body}`);
});
