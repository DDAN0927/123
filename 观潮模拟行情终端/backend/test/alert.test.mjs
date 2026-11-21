// 提醒判定回归测试(SEC-01)
// 运行: node --test backend/test/
// 覆盖四种方向 × 高价股/低价股,证明 pct_up / pct_down 不再被当成 below。
import test from 'node:test';
import assert from 'node:assert/strict';
import { alertHit, alertLine } from '../worker.js';

const q = (price, chgPct) => ({ price, chgPct });

test('above / below 仍按最新价判定', () => {
  assert.equal(alertHit({ dir: 'above', price: 100 }, q(101, 1.2)), true);
  assert.equal(alertHit({ dir: 'above', price: 100 }, q(99, -1.2)), false);
  assert.equal(alertHit({ dir: 'below', price: 100 }, q(99, -1.2)), true);
  assert.equal(alertHit({ dir: 'below', price: 100 }, q(101, 1.2)), false);
});

test('pct_up 比涨跌幅,与股价高低无关(高价股不再静默失效)', () => {
  // 贵州茅台 1680 元,涨幅 6% ≥ 阈值 5% —— 旧逻辑 price<=5 恒 false,永不触发
  assert.equal(alertHit({ dir: 'pct_up', price: 5 }, q(1680, 6)), true);
  // 涨幅 4% 未达阈值
  assert.equal(alertHit({ dir: 'pct_up', price: 5 }, q(1680, 4)), false);
});

test('pct_down 比跌幅,低价股不再被误触发', () => {
  // 3 元低价股,当日涨 2% —— 旧逻辑 price<=5 为 true,会误发"跌破"
  assert.equal(alertHit({ dir: 'pct_down', price: 5 }, q(3, 2)), false);
  // 跌 6% ≥ 阈值 5%
  assert.equal(alertHit({ dir: 'pct_down', price: 5 }, q(3, -6)), true);
});

test('涨跌幅缺失或非数值时不触发,避免 NaN 比较漏判', () => {
  assert.equal(alertHit({ dir: 'pct_up', price: 5 }, q(100, NaN)), false);
  assert.equal(alertHit({ dir: 'pct_down', price: 5 }, q(100, NaN)), false);
  assert.equal(alertHit({ dir: 'pct_up', price: NaN }, q(100, 9)), false);
});

test('未知方向一律不触发,不再默认按 below 处理', () => {
  assert.equal(alertHit({ dir: 'cross', price: 5 }, q(1, 0)), false);
  assert.equal(alertHit({ dir: undefined, price: 5 }, q(1, 0)), false);
});

test('文案按方向区分,不再把百分比写成价格', () => {
  assert.equal(alertLine({ code: '600519', dir: 'pct_up', price: 5 }, q(1680, 6.2)), '600519 涨幅 6.20% ≥ 5%');
  assert.equal(alertLine({ code: '600519', dir: 'pct_down', price: 5 }, q(1680, -6.2)), '600519 跌幅 6.20% ≥ 5%');
  assert.equal(alertLine({ code: '600519', dir: 'above', price: 1700 }, q(1701, 1)), '600519 突破 1700(现价 1701)');
  assert.equal(alertLine({ code: '600519', dir: 'below', price: 1700 }, q(1699, -1)), '600519 跌破 1700(现价 1699)');
});
