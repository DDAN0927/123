"""生成攻略库覆盖报告（docs/kb-coverage.html）。

用法
----
    .venv/Scripts/python.exe scripts/kb_report.py

为什么要有这份报告
------------------
「攻略库覆盖 355 城」这句话现在有两种含义：6 城有门票和开放时间，其余 349 城
只有景点名。数字上「全覆盖」听起来一样，实际差别很大。这份报告把两档摊开，
一城一行，谁有精编攻略、谁只有清单，一眼能数清 —— 答辩时被追问也不用心虚。
"""

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rag import coverage

OUT = ROOT / "docs" / "kb-coverage.html"


def main() -> int:
    full = set(coverage.full_cities())
    guided = set(coverage.guided_cities())
    listed = set(coverage.list_cities())
    spots = {name: [s[0] for s in items] for name, items in _parse_spots().items()}
    cities = sorted(full | guided | listed)

    rows = []
    for city in cities:
        names = spots.get(city, [])
        if city in full:
            tier, badge = "full", "精编攻略"
        elif city in guided:
            tier, badge = "guided", "景点导览"
        else:
            tier, badge = "list", "景点清单"
        preview = "、".join(names[:5]) + ("…" if len(names) > 5 else "")
        rows.append(
            f'<tr class="{tier}" data-city="{html.escape(city)}" data-spots="{html.escape(preview)}">'
            f"<td class=city>{html.escape(city)}</td>"
            f"<td><span class='badge {tier}'>{badge}</span></td>"
            f"<td class=num>{len(names)}</td>"
            f"<td class=spots>{html.escape(preview) or '—'}</td>"
            "</tr>"
        )

    total_spots = sum(len(v) for v in spots.values())
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>攻略库覆盖报告</title>
<style>
  :root {{ --ink:#1b1b25; --muted:#6b6b7b; --line:#e8e8f0; --bg:#fbfbfd;
          --full:#0E9E94; --guided:#5b6ee1; --list:#8a8aa0; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:32px 20px 64px; background:var(--bg); color:var(--ink);
          font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  h1 {{ font-size:26px; margin:0 0 6px; }}
  .sub {{ color:var(--muted); margin:0 0 24px; font-size:14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:24px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:14px 16px; }}
  .card .k {{ font-size:12px; color:var(--muted); letter-spacing:.04em; }}
  .card .v {{ font-size:24px; font-weight:700; margin-top:2px; }}
  .card.full .v {{ color:var(--full); }}
  .card.guided .v {{ color:var(--guided); }}
  .bar {{ height:8px; border-radius:99px; background:#ececf3; overflow:hidden; display:flex; margin-bottom:22px; }}
  .bar i {{ display:block; height:100%; }}
  .bar .a {{ background:var(--full); }}
  .bar .c {{ background:var(--guided); }}
  .bar .b {{ background:var(--list); }}
  input {{ width:100%; padding:11px 14px; border:1px solid var(--line); border-radius:10px;
           font-size:14px; background:#fff; margin-bottom:14px; }}
  input:focus {{ outline:2px solid #d8d2ff; border-color:#b9a9ff; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line);
           border-radius:12px; overflow:hidden; }}
  th {{ text-align:left; font-size:12px; color:var(--muted); font-weight:600; letter-spacing:.05em;
        padding:10px 14px; background:#f6f6fb; border-bottom:1px solid var(--line); }}
  td {{ padding:9px 14px; border-bottom:1px solid #f2f2f8; vertical-align:top; }}
  tr:last-child td {{ border-bottom:none; }}
  tr.full {{ background:#f4fbfa; }}
  .city {{ font-weight:600; white-space:nowrap; }}
  .num {{ color:var(--muted); text-align:right; width:64px; }}
  .spots {{ color:var(--muted); font-size:13px; }}
  .badge {{ display:inline-block; padding:1px 8px; border-radius:99px; font-size:12px; white-space:nowrap; }}
  .badge.full {{ background:#dff4f1; color:#0a7b73; }}
  .badge.guided {{ background:#e6e9fb; color:#3c4bb8; }}
  .badge.list {{ background:#efeff5; color:#6b6b7b; }}
  .empty {{ padding:24px; text-align:center; color:var(--muted); }}
  footer {{ margin-top:22px; color:var(--muted); font-size:13px; }}
  code {{ background:#f2f2f8; padding:1px 5px; border-radius:4px; font-size:12.5px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>攻略库覆盖报告</h1>
  <p class="sub">数据源：<code>knowledge_base/</code>（人工精编）+ <code>knowledge_base/guides/</code>（景点导览，
    由 <code>scripts/gen_city_guides.py</code> 从中文维基导游与高德生成）+ <code>knowledge_base/spots/</code>（景点清单，
    由 <code>scripts/gen_city_spots.py</code> 从地图数据生成）</p>

  <div class="cards">
    <div class="card"><div class="k">覆盖城市</div><div class="v">{len(cities)}</div></div>
    <div class="card full"><div class="k">精编攻略（门票/时间/交通）</div><div class="v">{len(full)}</div></div>
    <div class="card guided"><div class="k">景点导览（介绍 + 部分门票）</div><div class="v">{len(guided)}</div></div>
    <div class="card"><div class="k">景点清单（仅景点名与类型）</div><div class="v">{len(listed)}</div></div>
    <div class="card"><div class="k">收录景点</div><div class="v">{total_spots}</div></div>
  </div>

  <div class="bar">
    <i class="a" style="width:{len(full) / max(len(cities), 1) * 100:.2f}%"></i>
    <i class="c" style="width:{len(guided) / max(len(cities), 1) * 100:.2f}%"></i>
    <i class="b" style="width:{len(listed) / max(len(cities), 1) * 100:.2f}%"></i>
  </div>

  <input id="q" placeholder="搜索城市名或景点名，例如「哈尔滨」「布达拉宫」">
  <table>
    <thead><tr><th>城市</th><th>资料档位</th><th class=num>景点</th><th>代表景点</th></tr></thead>
    <tbody id="tb">
      {"".join(rows)}
    </tbody>
  </table>
  <p class="empty" id="empty" hidden>没有匹配的城市</p>

  <footer>
    升档方式：把 <code>哈尔滨.md</code> 放进 <code>knowledge_base/</code> 并重建索引，
    该城市即升为「精编攻略」（同名导览档与清单档会被自动忽略）。<br>
    导览档与清单档请勿手改 —— 它们是数据源的派生物，重跑生成脚本会覆盖。
  </footer>
</div>
<script>
  var q = document.getElementById("q"), tb = document.getElementById("tb");
  var rows = Array.prototype.slice.call(tb.rows), empty = document.getElementById("empty");
  q.addEventListener("input", function () {{
    var v = q.value.trim().toLowerCase(), n = 0;
    rows.forEach(function (r) {{
      var hit = !v || r.dataset.city.toLowerCase().indexOf(v) >= 0
                     || r.dataset.spots.toLowerCase().indexOf(v) >= 0;
      r.hidden = !hit;
      if (hit) n++;
    }});
    empty.hidden = n > 0;
  }});
</script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8", newline="\n")
    print(
        f"已生成 {OUT.relative_to(ROOT)}：{len(cities)} 城"
        f"（精编 {len(full)} / 导览 {len(guided)} / 清单 {len(listed)}），景点 {total_spots}"
    )
    return 0


def _parse_spots() -> dict[str, list[tuple[str, str]]]:
    """复用生成脚本的解析，避免两处各写一份 geo-data.js 解析器。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_city_spots", ROOT / "scripts" / "gen_city_spots.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_geo()


if __name__ == "__main__":
    raise SystemExit(main())
