/**
 * 云端状态校验与 cron 资源闸回归测试（SEC-03a / SEC-03b）
 * 运行: node --test "tests/unit/*.test.mjs"
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeEnv, call, runCron, captureLogs } from './_d1.mjs';

const PW = 'password123';

async function newUser(env, email = 's@x.com', ip = '10.0.0.1') {
  const r = await call(env, '/api/register', { method: 'POST', ip, body: { email, password: PW } });
  assert.equal(r.status, 200, '测试前置:注册应成功');
  return r.data.token;
}

const put = (env, token, state) => call(env, '/api/state', { method: 'PUT', token, body: { state } });

function stored(env, email = 's@x.com') {
  const row = env.DB.one('SELECT data FROM states WHERE user_id=(SELECT id FROM users WHERE email=?)', email);
  return row ? JSON.parse(row.data) : null;
}

const mkAlerts = (n, fn = (i) => ({ id: String(i), code: '600519', dir: 'above', price: 10 + i })) =>
  Array.from({ length: n }, (_, i) => fn(i));

/* ---------------- SEC-03a:入库结构校验 ---------------- */

test('SEC-03a:提交 300 条提醒 → 入库不超过 200 条', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const r = await put(env, token, { alerts: mkAlerts(300) });
  assert.equal(r.status, 200);
  const s = stored(env);
  assert.equal(s.alerts.length, 200, `应截断到 200,实际 ${s.alerts.length}`);
  assert.equal(s.alerts[0].id, '0');
  assert.equal(s.alerts[199].id, '199', '保留的是前 200 条');
});

test('SEC-03a:非法方向/非法代码/非法阈值被逐条丢弃,合法条目保留', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const alerts = [
    { id: '1', code: '600519', dir: 'above', price: 1700 },      // 保留
    { id: '2', code: '600519', dir: 'evil', price: 1700 },       // 方向非法
    { id: '3', code: '<script>', dir: 'above', price: 10 },      // 代码非法
    { id: '4', code: '000001', dir: 'pct_up', price: 150 },      // 百分比阈值 >100
    { id: '5', code: '000001', dir: 'pct_down', price: 5 },      // 保留
    { id: '6', code: '600000', dir: 'below', price: -1 },        // 阈值非正
    { id: '7', code: '600000', dir: 'below', price: 'abc' },     // 阈值非数
    null,                                                         // 非对象
    'x',                                                          // 非对象
  ];
  const r = await put(env, token, { alerts });
  assert.equal(r.status, 200, '不应整体 400');
  const s = stored(env);
  assert.deepEqual(s.alerts.map((a) => a.id), ['1', '5'], `实际保留 ${JSON.stringify(s.alerts.map((a) => a.id))}`);
});

test('SEC-03a:alerts 不是数组时按空处理,请求不失败', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const r = await put(env, token, { alerts: 'not-an-array', favorites: ['600519'] });
  assert.equal(r.status, 200);
  const s = stored(env);
  assert.deepEqual(s.alerts, []);
  assert.deepEqual(s.favorites, ['600519'], '其它字段不应被牵连');
});

test('SEC-03a:state 本身是数组时按坏请求拒绝', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const r = await put(env, token, [1, 2, 3]);
  assert.equal(r.status, 400);
});

test('SEC-03a:未带 alerts 字段时保持"不存在",不被写成空数组(否则拉取会清空本地提醒)', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const r = await put(env, token, { favorites: ['600519'] });
  assert.equal(r.status, 200);
  const s = stored(env);
  assert.equal('alerts' in s, false, 'alerts 不应被凭空创建');
  assert.equal('favGroups' in s, false, 'favGroups 不应被凭空创建');
  assert.deepEqual(s.favorites, ['600519']);
});

test('SEC-03a:favGroups 组数 ≤20、每组代码 ≤500,非法代码被剔除', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const groups = Array.from({ length: 25 }, (_, g) => ({
    name: 'g' + g,
    codes: Array.from({ length: 600 }, (_, i) => (i === 0 ? '<bad>' : String(600000 + i))),
  }));
  const r = await put(env, token, { favGroups: groups });
  assert.equal(r.status, 200);
  const s = stored(env);
  assert.equal(s.favGroups.length, 20, '组数应截断到 20');
  assert.equal(s.favGroups[0].codes.length, 500, '每组代码应截断到 500');
  assert.ok(!s.favGroups[0].codes.includes('<bad>'), '非法代码应被剔除');
  assert.equal(s.favGroups[0].name, 'g0');
});

test('SEC-03a:未涉及的字段原样保留(不破坏账户/自选同步)', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const state = {
    v: 1,
    favorites: ['600519', '000001'],
    compare: ['600519'],
    account: { cash: 12345.67, positions: { '600519': { qty: 100, cost: 1600 } }, trades: [], realized: 0 },
    alerts: [{ id: 'a', code: '600519', dir: 'above', price: 1700 }],
    favGroups: [{ name: '默认', codes: ['600519'] }],
    updatedAt: 1,
  };
  const r = await put(env, token, state);
  assert.equal(r.status, 200);
  const s = stored(env);
  assert.deepEqual(s.favorites, state.favorites);
  assert.deepEqual(s.compare, state.compare);
  assert.deepEqual(s.account, state.account);
  assert.equal(s.v, 1);
  assert.equal(s.alerts.length, 1);
  assert.equal(s.alerts[0].price, 1700);
});

test('SEC-03a:超过 400KB 仍返回 413', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  const r = await put(env, token, { alerts: [], note: 'x'.repeat(410000) });
  assert.equal(r.status, 413);
});

/* ---------------- SEC-03b:cron 总量闸与错误兜底 ---------------- */

function seedBigState(env, n) {
  const now = Date.now();
  env.DB.run('INSERT INTO users (id,email,salt,pass_hash,iterations,created_at) VALUES (?,?,?,?,?,?)',
    'u-big', 'big@x.com', 'salt', 'hash', 100000, now);
  const alerts = mkAlerts(n, (i) => ({ id: String(i), code: String(600000 + i), dir: 'above', price: 1 }));
  env.DB.run('INSERT INTO states (user_id,data,updated_at) VALUES (?,?,?)',
    'u-big', JSON.stringify({ alerts }), now);
}

test('SEC-03b:6000 个提醒代码 → 单轮最多 20 次 fetch,并记录 warn', async () => {
  const env = makeEnv();
  seedBigState(env, 6000);

  const logs = captureLogs();
  const realFetch = globalThis.fetch;
  let fetchCount = 0;
  globalThis.fetch = async () => {
    fetchCount++;
    return { ok: true, json: async () => ({ data: { diff: [] } }) };
  };
  try {
    const r = await runCron(env);
    assert.equal(r.checked, 1);
  } finally {
    globalThis.fetch = realFetch;
    logs.restore();
  }

  assert.ok(fetchCount <= 20, `子请求应 ≤20,实际 ${fetchCount}`);
  assert.equal(fetchCount, 20, '800 个代码 / 每批 40 = 20 次');
  assert.equal(logs.warn.length, 1, '应有一条 warn');
  assert.match(logs.warn[0], /超过单轮上限 800/);
  assert.match(logs.warn[0], /跳过 5200/);
});

test('SEC-03b:上游 fetch 抛错时 cron 仍正常结束,不抛给平台', async () => {
  const env = makeEnv();
  const token = await newUser(env);
  await put(env, token, { alerts: [{ id: '1', code: '600519', dir: 'above', price: 1 }] });

  const logs = captureLogs();
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('eastmoney down'); };
  try {
    const r = await runCron(env);
    assert.equal(r.hit, 0, '上游失败时不应误判命中');
  } finally {
    globalThis.fetch = realFetch;
    logs.restore();
  }
});

test('SEC-03b:handleAlerts 内部抛错 → scheduled 不 reject,并记录 console.error', async () => {
  const env = makeEnv();
  env.DB.prepare = () => { throw new Error('d1 unavailable'); };

  const logs = captureLogs();
  let threw = null;
  try {
    await runCron(env);
  } catch (e) {
    threw = e;
  } finally {
    logs.restore();
  }

  assert.equal(threw, null, 'scheduled 的 waitUntil promise 不得 reject');
  assert.equal(logs.error.length, 1, '应记录一条 error');
  assert.match(logs.error[0], /handleAlerts failed/);
  assert.match(logs.error[0], /d1 unavailable/);
});
