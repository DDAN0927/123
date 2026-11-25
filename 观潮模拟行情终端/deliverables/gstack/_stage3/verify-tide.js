// verify-tide.js — 潮位图探针:结构 / 最新行真实数据 / 语义标注 / 布局无溢出
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

  for (const width of [1440, 1180, 1024, 760, 560, 414, 375]) {
    const p = await (await b.newContext({ viewport: { width, height: 900 } })).newPage();
    p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
    await p.goto(url, { waitUntil: 'load' });
    await p.waitForTimeout(width <= 760 ? 1400 : 1000);
    const r = await p.evaluate(() => {
      const cells = document.querySelector('.breadth-cells');
      const items = cells ? cells.children.length : 0;
      const grid = cells ? getComputedStyle(cells) : null;
      const overflowX = document.documentElement.scrollWidth - document.documentElement.clientWidth;
      const breadthRect = document.getElementById('breadth')?.getBoundingClientRect();
      const moversRect = document.querySelector('.movers')?.getBoundingClientRect();
      return {
        items,
        rows: grid ? grid.gridTemplateRows.split(' ').length : 0,
        overflowX,
        noOverlap: !breadthRect || !moversRect || moversRect.top >= breadthRect.bottom - 1,
      };
    });
    ok(`${width} 潮位图单元格存在(=板块数×10)`, r.items > 0 && r.items % 10 === 0, `${r.items} 格`);
    ok(`${width} 行数=10(纵向时间)`, r.rows === 10, `${r.rows} 行`);
    ok(`${width} 无横向溢出`, r.overflowX <= 0, `溢出 ${r.overflowX}px`);
    ok(`${width} 潮位图与涨幅榜不重叠`, r.noOverlap, '');
    await p.close();
  }

  // 数据语义:最新一行 = 真实板块上涨占比;历史行 title 带「回放」
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto(url, { waitUntil: 'load' });
  await p.waitForTimeout(1000);
  const sem = await p.evaluate(() => {
    renderBreadth(); /* 同步重渲染,避开 liveTick 竞态 */
    const cells = [...document.querySelectorAll('.breadth-cells i')];
    const cols = cells.length / 10;
    const upC = getComputedStyle(document.documentElement).getPropertyValue('--up').trim();
    const downC = getComputedStyle(document.documentElement).getPropertyValue('--down').trim();
    // 每列最后一行(DOM 序:r=9 → index r*cols+c? 不,column flow: index = r + c*10)
    let lastReal = 0, lastMismatch = 0, replayTitles = 0, realTitles = 0;
    const boards = industryBoards().filter((x) => x.kind === 'group').sort((a, b) => (b.up / (b.count || 1)) - (a.up / (a.count || 1)));
    for (let c = 0; c < cols; c++) {
      const lastCell = cells[c * 10 + 9];
      const expectUp = (boards[c].up / (boards[c].count || 1)) * 100 >= 50;
      const isUp = lastCell.style.background.includes('up');
      if (expectUp === isUp) lastReal++; else lastMismatch++;
      if (/回放/.test(lastCell.title)) replayTitles++;
      const firstCell = cells[c * 10];
      if (/回放/.test(firstCell.title)) realTitles++;
    }
    return { cols, lastReal, lastMismatch, replayTitles, realTitles, upC, downC, sub: document.querySelector('.breadth .sub').textContent };
  });
  ok(`列数=一级行业数(${sem.cols})`, sem.cols >= 10 && sem.cols <= 30, `${sem.cols} 列`);
  ok('最新一行颜色 = 真实板块占比', sem.lastMismatch === 0, `一致 ${sem.lastReal}/${sem.lastReal + sem.lastMismatch}`);
  ok('最新一行 title 不带「回放」', sem.replayTitles === 0, `带回放 ${sem.replayTitles}/${sem.cols}(应为 0)`);
  ok('历史行 title 带「回放」', sem.realTitles === sem.cols, `带回放 ${sem.realTitles}/${sem.cols}`);
  ok('副标注披露模拟回放', /回放为模拟/.test(sem.sub), sem.sub.slice(-24));

  await b.close();
  console.log(`\n${pass + fail} 项: ${pass} PASS, ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})();
