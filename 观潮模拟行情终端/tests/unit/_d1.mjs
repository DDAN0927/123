/**
 * 测试用 D1 适配层:用 node:sqlite 跑真实 SQL,而不是手写 SQL 语义的 mock。
 *
 * 为什么用真库:本轮要验的是「单条 UPSERT 在并发下仍然逐次 +1」和「窗口 CASE 的语义」,
 * 手工 mock 只能验证 mock 自己。用真 SQLite 时,把每次调用前插一个 setImmediate,
 * 就能复现两个请求在 await 边界交错执行的情形——这正是原来"先读后写"被击穿的条件。
 *
 * 对外形状对齐 Workers D1:prepare(sql) → { bind(...).first()/.all()/.run() }
 */
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import worker from '../../backend/worker.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEMA = readFileSync(join(HERE, '..', '..', 'backend', 'schema.sql'), 'utf8');

// 让出一次事件循环,制造并发交错点
const tick = () => new Promise((r) => setImmediate(r));

export function makeDB() {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);

  const DB = {
    // 直连辅助(测试准备/断言用,worker 不会调)
    one: (sql, ...args) => {
      const row = db.prepare(sql).get(...args);
      return row === undefined ? null : row;
    },
    many: (sql, ...args) => db.prepare(sql).all(...args),
    run: (sql, ...args) => db.prepare(sql).run(...args),
    raw: db,

    prepare(sql) {
      const stmt = db.prepare(sql); // SQL 写错在这里就会抛,不会被 mock 吃掉
      let args = [];
      const api = {
        bind(...a) { args = a; return api; },
        async first() {
          await tick();
          const row = stmt.get(...args);
          return row === undefined ? null : row;
        },
        async all() {
          await tick();
          return { results: stmt.all(...args) };
        },
        async run() {
          await tick();
          const r = stmt.run(...args);
          return { success: true, meta: { changes: Number(r.changes) } };
        },
      };
      return api;
    },
  };
  return DB;
}

export function makeEnv(extra = {}) {
  return {
    DB: makeDB(),
    ALLOWED_ORIGIN: 'https://app.test',
    RESEND_API_KEY: 'test-key',
    ALERT_FROM: 'alerts@test.dev',
    ...extra,
  };
}

export function makeRequest(path, { method = 'GET', body, ip = '10.0.0.1', token } = {}) {
  const headers = { 'CF-Connecting-IP': ip };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = 'Bearer ' + token;
  return new Request('https://worker.test' + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function call(env, path, opts) {
  const res = await worker.fetch(makeRequest(path, opts), env, {});
  let data = null;
  try { data = await res.json(); } catch (e) {}
  return { status: res.status, data, res };
}

// scheduled 把工作交给 ctx.waitUntil,这里捕获并 await;新实现内部已 try/catch,不会 reject
export async function runCron(env) {
  let pending = null;
  await worker.scheduled({ cron: '*/5 * * * *' }, env, { waitUntil: (p) => { pending = p; } });
  if (!pending) throw new Error('scheduled 未调用 ctx.waitUntil');
  return await pending;
}

// 静音并收集日志
export function captureLogs() {
  const logs = { log: [], warn: [], error: [] };
  const orig = { log: console.log, warn: console.warn, error: console.error };
  for (const k of ['log', 'warn', 'error']) {
    console[k] = (...a) => logs[k].push(a.map(String).join(' '));
  }
  logs.restore = () => { console.log = orig.log; console.warn = orig.warn; console.error = orig.error; };
  return logs;
}
