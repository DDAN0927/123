/**
 * 认证与限流回归测试（SEC-02 / SEC-04 / SEC-05）
 * 运行: node --test "tests/unit/*.test.mjs"
 *
 * 用真 SQLite 跑 worker 里的真实 SQL,因此断言的是「SQL 的语义」而不是 mock 的行为。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeEnv, call } from './_d1.mjs';

const PW = 'correct-horse';

const reg = (env, email, ip, password = PW) => call(env, '/api/register', { method: 'POST', ip, body: { email, password } });
const log = (env, email, password, ip) => call(env, '/api/login', { method: 'POST', ip, body: { email, password } });

/* ---------------- SEC-04:邮箱维度不再硬锁 ---------------- */

test('SEC-04:同邮箱连错 5 次后,正确密码仍能登录(邮箱维度不得硬锁)', async () => {
  const env = makeEnv();
  const r = await reg(env, 'v@x.com', '10.0.0.1');
  assert.equal(r.status, 200);

  // 5 次失败刻意来自 5 个不同 IP,确保 i: 维度不会先锁,只考察邮箱维度
  for (let i = 0; i < 5; i++) {
    const bad = await log(env, 'v@x.com', 'wrong-pass-' + i, '10.0.0.' + (10 + i));
    assert.equal(bad.status, 401, `第 ${i + 1} 次错误密码应 401`);
  }

  const emailRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'e:v@x.com');
  assert.equal(emailRow.fails, 5, '邮箱维度应累计 5 次失败');

  const ok = await log(env, 'v@x.com', PW, '10.0.0.99');
  assert.equal(ok.status, 200, '知道邮箱的攻击者不得把受害者锁在门外');
  assert.ok(ok.data && ok.data.token, '应返回令牌');
});

test('SEC-04:邮箱维度只延迟不拒绝——第 6 次仍返回 200 而不是 429', async () => {
  const env = makeEnv();
  await reg(env, 'delay@x.com', '10.0.5.1');
  for (let i = 0; i < 4; i++) await log(env, 'delay@x.com', 'bad' + i, '10.0.5.' + (10 + i));

  const t0 = Date.now();
  const ok = await log(env, 'delay@x.com', PW, '10.0.5.99');
  const cost = Date.now() - t0;

  assert.equal(ok.status, 200);
  // 4 次失败 → backoff = 200 * 2^(4-3) = 400ms
  assert.ok(cost >= 350, `应至少有约 400ms 延迟,实际 ${cost}ms`);
});

test('SEC-04:同 IP 连错 5 次后第 6 次仍返回 429(IP 维度保留硬锁)', async () => {
  const env = makeEnv();
  await reg(env, 'w@x.com', '10.9.9.9');
  const ip = '10.1.1.1';
  for (let i = 0; i < 5; i++) {
    const bad = await log(env, 'w@x.com', 'bad' + i, ip);
    assert.equal(bad.status, 401);
  }
  const r6 = await log(env, 'w@x.com', 'bad6', ip);
  assert.equal(r6.status, 429);
  assert.match(String(r6.data.error), /过多/);
  assert.ok(r6.res.headers.get('Retry-After'), '429 应带 Retry-After');
});

/* ---------------- SEC-02:原子计数 / 只清邮箱键 ---------------- */

test('SEC-02:两次并发失败后计数为 2(单条 UPSERT,不是先读后写)', async () => {
  const env = makeEnv();
  await reg(env, 'c@x.com', '10.2.0.1');
  const ip = '10.2.2.2';

  // 两个请求在 await 边界交错执行;先读后写的实现会让两者都读到 0、都写回 1
  await Promise.all([
    log(env, 'c@x.com', 'bad-a', ip),
    log(env, 'c@x.com', 'bad-b', ip),
  ]);

  const ipRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip);
  const emailRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'e:c@x.com');
  assert.equal(ipRow.fails, 2, `并发两次失败应计 2 次,实际 ${ipRow.fails}`);
  assert.equal(emailRow.fails, 2, `邮箱维度也应计 2 次,实际 ${emailRow.fails}`);
});

test('SEC-02:三次并发失败后计数为 3', async () => {
  const env = makeEnv();
  await reg(env, 'c3@x.com', '10.2.0.3');
  const ip = '10.2.2.3';
  await Promise.all([
    log(env, 'c3@x.com', 'bad-a', ip),
    log(env, 'c3@x.com', 'bad-b', ip),
    log(env, 'c3@x.com', 'bad-c', ip),
  ]);
  const row = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip);
  assert.equal(row.fails, 3);
});

test('SEC-02:成功登录只清 e: 键,i: 键的失败计数必须保留', async () => {
  const env = makeEnv();
  await reg(env, 'd@x.com', '10.3.0.1');
  const ip = '10.3.3.3';

  await log(env, 'd@x.com', 'bad-1', ip);
  await log(env, 'd@x.com', 'bad-2', ip);
  assert.equal(env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip).fails, 2);

  const ok = await log(env, 'd@x.com', PW, ip);
  assert.equal(ok.status, 200);

  const ipRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip);
  assert.ok(ipRow, 'i: 键不得被成功登录删除');
  assert.equal(ipRow.fails, 2, 'i: 计数不得被成功登录重置——否则攻击者登录自己的账号就能清零');
  assert.equal(env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'e:d@x.com'), null, 'e: 键应被清除');
});

test('SEC-02:窗口过期后计数从 1 重新开始', async () => {
  const env = makeEnv();
  await reg(env, 'w2@x.com', '10.3.5.1');
  const ip = '10.3.5.5';
  await log(env, 'w2@x.com', 'bad-1', ip);
  await log(env, 'w2@x.com', 'bad-2', ip);

  // 把窗口起点挪到 20 分钟前
  env.DB.run('UPDATE login_attempts SET first_at=? WHERE key=?', Date.now() - 20 * 60 * 1000, 'i:' + ip);

  await log(env, 'w2@x.com', 'bad-3', ip);
  const row = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip);
  assert.equal(row.fails, 1, '超出窗口应重置为 1');
});

/* ---------------- SEC-05:注册限流 ---------------- */

test('SEC-05:同 IP 连续注册 6 次,第 6 次返回 429', async () => {
  const env = makeEnv();
  const ip = '10.4.4.4';
  for (let i = 0; i < 5; i++) {
    const r = await reg(env, `z${i}@x.com`, ip, 'password123');
    assert.equal(r.status, 200, `第 ${i + 1} 次注册应成功,实际 ${r.status}`);
  }
  const r6 = await reg(env, 'z9@x.com', ip, 'password123');
  assert.equal(r6.status, 429);
  assert.match(String(r6.data.error), /频繁/);

  // 另一个 IP 不受影响
  const other = await reg(env, 'other@x.com', '10.4.5.5', 'password123');
  assert.equal(other.status, 200, '限流必须按 IP 隔离');
});

test('SEC-05:非法邮箱的注册尝试同样计入配额(否则可用垃圾请求绕过)', async () => {
  const env = makeEnv();
  const ip = '10.4.6.6';
  for (let i = 0; i < 5; i++) {
    const r = await reg(env, 'not-an-email', ip, 'password123');
    assert.equal(r.status, 400);
  }
  const r6 = await reg(env, 'ok@x.com', ip, 'password123');
  assert.equal(r6.status, 429);
});

test('SEC-05:注册键与登录键分开命名,互不影响', async () => {
  const env = makeEnv();
  const ip = '10.4.7.7';
  await reg(env, 'sep@x.com', ip);
  // 注册已用掉 1 次 r: 配额,但登录的 i: 计数应为 1(本次登录失败)而不是 2
  await log(env, 'sep@x.com', 'bad', ip);
  const ipRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'i:' + ip);
  const regRow = env.DB.one('SELECT fails FROM login_attempts WHERE key=?', 'r:' + ip);
  assert.equal(ipRow.fails, 1);
  assert.equal(regRow.fails, 1);
});
