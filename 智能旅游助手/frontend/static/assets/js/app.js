/* ==========================================================================
   旅游智能助手 · 应用核心（API / 登录态 / 地图 / 功能页渲染）
   所有功能页共用此文件；调用本站同源 /api/* 接口
   ========================================================================== */
(function () {
  "use strict";

  const API_BASE = "";
  const TOKEN_KEY = "tc_token";
  const USER_KEY = "tc_user";

  // 构建标记：HTML 里的资源引用都带 ?v=<同一串>，线上排查「是不是旧版」用。
  // 改前端静态资源时务必同步 bump（scripts/stamp_assets.py --stamp 会一起改 HTML）。
  const BUILD = "2026-11-25a";
  window.__TC_BUILD__ = BUILD;
  try { console.info("[travel-copilot] build " + BUILD); } catch (e) { /* 老浏览器忽略 */ }

  // 高德地图 Web 端(JS API) Key 与安全密钥 —— 由后端 GET /api/config 下发，前端不硬编码。
  // 注意：JS API 2.0 必须在加载 amap 脚本「之前」注入 window._AMapSecurityConfig，
  // 否则地图会加载失败（INVALID_USER_SCODE），页面表现为一片空白。
  // 这两个值本来就是公开的（要发给浏览器），访问控制靠高德控制台的域名白名单；
  // 做成运行时配置是为了让自部署者能换成自己的 Key。
  let AMAP_KEY = "";
  let AMAP_JS_CODE = "";
  let _cfgPromise = null;
  function loadPublicConfig() {
    if (!_cfgPromise) {
      _cfgPromise = fetch(API_BASE + "/api/config")
        .then((r) => (r.ok ? r.json() : {}))
        .then((c) => {
          AMAP_KEY = c.amap_key || "";
          AMAP_JS_CODE = c.amap_security_js_code || "";
          return c;
        })
        .catch(() => ({}));
    }
    return _cfgPromise;
  }
  // 地图加载失败时展示的排查提示（放在 iframe 内，避免出现「莫名其妙一片空白」）
  const AMAP_FAIL_HTML = '<div class="am-fail"><b>⚠️ 地图加载失败</b>'
    + '<span>高德 JS API 未能初始化，常见原因：</span>'
    + '<span>① 未配置 AMAP_KEY（在 .env 里填入自己的高德 Key 与安全密钥）</span>'
    + '<span>② Key 未把当前访问域名加入白名单（部署到新域名后必须补上）</span>'
    + '<span>③ 安全密钥 jscode 与 Key 不匹配</span>'
    + '<span>④ 网络无法访问 webapi.amap.com</span></div>';

  /* ---------- 网络 ---------- */
  /** 下载类请求（导出 .ics / 打印版）需要自己 fetch，这里复用同一套头。 */
  function authHeaders() {
    const t = localStorage.getItem(TOKEN_KEY);
    return t ? { "X-Auth-Token": t } : {};
  }

  /**
   * 非 JSON 响应的兜底文案。
   * 后端没起、或请求被静态服务器（python -m http.server 之类）接管时，响应体是整段
   * HTML —— 例如 `<!DOCTYPE HTML>…<p>Error code: 501</p>`，因为静态服务器不支持 POST。
   * 以前直接把前 200 字塞进登录框，界面上就是一屏标签。这里只保留「人写的纯文本」，
   * HTML 一律换成人话，原文丢给 console 排障。
   */
  function humanizeNonJson(r, text) {
    const body = String(text || "").trim();
    const looksHtml = /^<(!doctype|html|head|body)/i.test(body) || /<html[\s>]/i.test(body);
    if (body && !looksHtml) return body.length > 200 ? body.slice(0, 200) + "…" : body;
    console.warn("[api] 非 JSON 响应", r.status, r.url, body.slice(0, 500));
    if (r.status === 501) return "后端未启动（501）：请求被静态文件服务器接管了";
    if (r.status === 404) return "接口不存在（404），请确认后端已启动";
    if (r.status >= 502 && r.status <= 504) return `后端服务暂不可用（${r.status}），请稍后重试`;
    return `服务返回 ${r.status}，响应格式异常`;
  }

  async function api(method, path, body) {
    const url = API_BASE + path;
    const opts = { method, headers: {} };
    const t = localStorage.getItem(TOKEN_KEY);
    // 用 X-Auth-Token 而不是 Authorization: Bearer ——
    // 魔搭创空间（*.ms.show）的边缘 WAF 会把任何带 Authorization: Bearer 的请求
    // 当成「SDK Token 直连」直接 403（与 token 内容无关，应用层根本收不到）。
    // 后端两种头都认，所以统一用前者，换平台也不用改回来。
    if (t) opts.headers["X-Auth-Token"] = t;
    if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let r;
    try {
      r = await fetch(url, opts);
    } catch (e) {
      return { ok: false, status: 0, data: { detail: "网络异常，请稍后重试" } };
    }
    const text = await r.text();
    let data = {};
    if (text) {
      try { data = JSON.parse(text); }
      catch (e) { data = { detail: humanizeNonJson(r, text) }; }
    }
    // FastAPI 的 422 校验错误里 detail 是一个数组（Pydantic 逐字段报错），
    // 直接丢给 textContent / toast 会渲染成 "[object Object]"。在这里统一压成一句人话，
    // 否则每个调用点都得自己判断一次。
    if (data && Array.isArray(data.detail)) {
      data.detail = data.detail
        .map((d) => (d && (d.msg || d.message)) || String(d))
        .filter(Boolean)
        .join("；") || "请求参数不合法";
    } else if (data && data.detail && typeof data.detail === "object") {
      data.detail = data.detail.message || data.detail.msg || "请求失败";
    }
    // headers 一并返回：内容库列表把分页总数放在 X-Total-Count 响应头里，
    // 这样返回体仍是数组，接口保持向后兼容。
    return { ok: r.ok, status: r.status, data, headers: r.headers };
  }
  const apiGet = (path) => api("GET", path);
  const apiPost = (path, body) => api("POST", path, body);
  const apiPut = (path, body) => api("PUT", path, body);

  /* 断网时浏览器给的是 "Failed to fetch" / "NetworkError..." / "Load failed"，
     用户读不懂也没法行动。统一压成一句人话；后端 detail 已经是人话，原样透出。 */
  function netErrText(e) {
    const m = String((e && e.message) || "");
    if (!m) return "服务暂不可用，请稍后重试";
    if (/Failed to fetch|NetworkError|Load failed|net::ERR_|network error/i.test(m)) {
      return "网络异常，请稍后重试";
    }
    return m;
  }

  /* ---------- 文本与 Markdown 渲染（自带 HTML 转义，防 XSS） ---------- */
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function mdInline(s) {
    let t = escapeHtml(s);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return t;
  }

  /* 轻量 Markdown 渲染：标题 / 列表 / 表格 / 引用 / 代码块 / 分隔线 / 行内样式 */
  function renderMarkdown(md) {
    if (!md) return "";
    const lines = String(md).replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let i = 0;
    let list = null, listBuf = [], quoteBuf = [], tableBuf = [], codeBuf = [], inCode = false;

    const flushList = () => {
      if (!list) return;
      out.push(`<${list}>${listBuf.join("")}</${list}>`);
      list = null; listBuf = [];
    };
    const flushQuote = () => {
      if (!quoteBuf.length) return;
      out.push(`<blockquote>${quoteBuf.join("<br>")}</blockquote>`);
      quoteBuf = [];
    };
    // 表格行的判定不能要求「以 | 结尾」——模型输出的表格经常省略最后一列的收尾竖线：
    //   | 住宿 | 900 |
    //   | 餐饮（3天） | 300      ← 少了结尾的 |
    // 旧实现用 /^\s*\|.*\|\s*$/ 判定，这一行会被当成普通段落，页面上直接露出裸管道符。
    // 现在以「以 | 开头」为准；已进入表格时，还兼容 GFM 那种不带外侧竖线的写法。
    const isTableRow = (l) => {
      const t = l.trim();
      if (t.length < 2) return false;
      if (t.startsWith("|")) return true;
      return tableBuf.length > 0 && (t.match(/\|/g) || []).length >= 2;
    };
    const isSepRow = (l) => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes("-");
    const flushTable = () => {
      if (!tableBuf.length) return;
      const rows = tableBuf.slice();
      tableBuf = [];
      let head = null, body = rows;
      if (rows.length >= 2 && isSepRow(rows[1])) { head = rows[0]; body = rows.slice(2); }
      const cells = (row, tag) => row.replace(/^\s*\|/, "").replace(/\|\s*$/, "")
        .split("|").map((c) => `<${tag}>${mdInline(c.trim())}</${tag}>`).join("");
      let html = "<table>";
      if (head) html += `<thead><tr>${cells(head, "th")}</tr></thead>`;
      html += "<tbody>" + body.filter((r) => !isSepRow(r))
        .map((r) => `<tr>${cells(r, "td")}</tr>`).join("") + "</tbody></table>";
      out.push(html);
    };
    const flushAll = () => { flushList(); flushQuote(); flushTable(); };

    while (i < lines.length) {
      const raw = lines[i];
      const line = raw.trim();

      // 代码块
      if (/^```/.test(line)) {
        if (!inCode) { flushAll(); inCode = true; codeBuf = []; }
        else { out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`); inCode = false; }
        i++; continue;
      }
      if (inCode) { codeBuf.push(raw); i++; continue; }

      // 表格
      if (isTableRow(line)) { flushList(); flushQuote(); tableBuf.push(line); i++; continue; }
      flushTable();

      if (!line) { flushAll(); i++; continue; }

      // 分隔线
      if (/^([-*_])\1{2,}$/.test(line)) { flushAll(); out.push("<hr>"); i++; continue; }

      // 标题
      const h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) { flushAll(); const lv = h[1].length; out.push(`<h${lv}>${mdInline(h[2])}</h${lv}>`); i++; continue; }

      // 引用
      if (/^>\s?/.test(line)) { flushList(); quoteBuf.push(mdInline(line.replace(/^>\s?/, ""))); i++; continue; }
      flushQuote();

      // 列表
      const ul = line.match(/^[-*•]\s+(.*)$/);
      const ol = line.match(/^(\d+)[.、)]\s+(.*)$/);
      if (ul || ol) {
        const type = ul ? "ul" : "ol";
        if (list && list !== type) flushList();
        list = type;
        listBuf.push(`<li>${mdInline(ul ? ul[1] : ol[2])}</li>`);
        i++; continue;
      }
      flushList();

      // 段落
      out.push(`<p>${mdInline(line)}</p>`);
      i++;
    }
    if (inCode && codeBuf.length) out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
    flushAll();
    return out.join("");
  }

  /* ---------- 打字机逐字显示（总时长约 4 秒，长文自适应加速） ---------- */
  function typewrite(el, text, opts) {
    const o = opts || {};
    const speed = o.speed || 16;
    const totalSteps = 240;
    const chunk = Math.max(1, Math.ceil(text.length / totalSteps));
    let n = 0;
    let stopped = false;
    const timer = setInterval(() => {
      if (stopped) return;
      n = Math.min(text.length, n + chunk);
      el.innerHTML = renderMarkdown(text.slice(0, n)) + (n < text.length ? '<span class="tw-caret"></span>' : "");
      if (o.onTick) o.onTick();
      if (n >= text.length) { clearInterval(timer); if (o.onDone) o.onDone(); }
    }, speed);
    return () => { stopped = true; clearInterval(timer); };
  }

  /* ---------- 轻提示 ---------- */
  function toast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2200);
  }

  /* ---------- 文件下载 ---------- */
  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  /* ---------- 登录态 ---------- */
  function authState() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  }
  function setAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
  async function logout() {
    await apiPost("/api/auth/logout", {});
    clearAuth();
    location.reload();
  }

  /* ---------- 导航栏注入（所有功能页共用） ---------- */
  function injectAppNav() {
    const header = document.querySelector(".site-header");
    if (!header) return;
    const links = header.querySelector(".nav-links");
    const user = authState();
    const isAdmin = user && user.role === "admin";
    const adminLinks = isAdmin
      ? '<a href="admin.html">运营管理</a><a href="kb.html">知识库</a>'
      : "";
    // 应用页（含 .app-main）使用应用导航；营销页保留原有导航，仅补充入口与高亮
    const isAppPage = !!document.querySelector(".app-main");

    if (links) {
      if (isAppPage) {
        // 应用页导航项多，标记出来让 CSS 在窄桌面下收进汉堡菜单
        links.classList.add("nav-links--app");
        document.body.classList.add("app-page");
        links.innerHTML = `
          <a href="index.html">首页</a>
          <a href="chat.html">AI旅行咨询</a>
          <a href="map.html">城市地图</a>
          <a href="spots.html">景点库</a>
          <a href="transit.html">交通路线</a>
          <a href="trips.html">我的行程</a>
          <a href="favorites.html">我的收藏</a>
          ${adminLinks}
          <a href="about.html">关于我们</a>
          <a href="contact.html">联系我们</a>`;
      } else if (isAdmin && !links.querySelector('a[href="admin.html"]')) {
        links.insertAdjacentHTML("beforeend", adminLinks);
      }
      const cur = location.pathname.split("/").pop() || "index.html";
      links.querySelectorAll("a").forEach((a) => {
        const h = (a.getAttribute("href") || "").split("#")[0];
        a.classList.toggle("active", !!h && h === cur);
      });
    }

    const cta = header.querySelector(".nav-cta");
    if (cta) {
      if (user) {
        // 账号区一律「平铺按钮」，不做下拉菜单。
        // 演进史：①「👤 用户名」死胶囊（点了没反应，根本没有改密入口）
        //        ②「用户名 ▾」下拉（要多点一步，还有人反馈菜单点不出来）
        //        ③ 现在：点用户名/钥匙 = 直接开改密弹窗；退出单独一颗按钮。
        // 没有展开状态，就不存在「点开又立刻被关掉」「菜单被裁掉」这类失败。
        // ≥1201px 额外给一颗带文字的「修改密码」，窄屏靠长按/悬停提示与弹窗标题自解释。
        cta.innerHTML = `
          <div class="nav-account">
            <button type="button" class="nav-account-btn" id="app-account"
                    aria-haspopup="dialog" title="修改密码（当前账号 ${escapeHtml(user.username)}）"
                    aria-label="修改密码，当前账号 ${escapeHtml(user.username)}">
              <span class="nav-account-avatar" aria-hidden="true">👤</span>
              <span class="nav-account-name">${escapeHtml(user.username)}</span>
              <span class="nav-account-key" aria-hidden="true">🔑</span>
            </button>
            <button type="button" class="btn btn-ghost nav-pwd-btn" id="app-change-pwd">修改密码</button>
            <a href="#" class="btn btn-primary nav-logout-btn" id="app-logout">退出 <span class="fill"></span></a>
          </div>
          <button class="nav-burger" aria-label="菜单" aria-expanded="false"><span></span><span></span><span></span></button>`;
        bindAccountActions();
      } else {
        cta.innerHTML = `
          <a href="index.html#login" class="btn btn-primary">登录 <span class="fill"></span></a>
          <button class="nav-burger" aria-label="菜单" aria-expanded="false"><span></span><span></span><span></span></button>`;
      }
    }
  }

  /* ---------- 账号区动作绑定（改密 / 退出） ---------- */
  function bindAccountActions() {
    ["app-account", "app-change-pwd"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("click", (e) => { e.preventDefault(); openPasswordModal(); });
    });
    const out = document.getElementById("app-logout");
    if (out) out.addEventListener("click", (e) => { e.preventDefault(); logout(); });
  }

  /* ---------- 修改密码弹窗 ---------- */
  // 后端 @NotBlank 的报错会带 Java 字段名（oldPassword 不能为空），对用户没意义。
  // 这里翻成中文；万一又出现字段名对不上的情况，界面上至少读得懂。
  function pwdErrText(raw) {
    const s = String(raw == null ? "" : raw).trim();
    if (!s) return "修改失败，请稍后重试";
    const zh = s
      .replace(/oldPassword/g, "原密码")
      .replace(/newPassword/g, "新密码")
      .replace(/username/g, "用户名");
    return zh;
  }
  // 后端 /api/auth/change-password 会返回一枚新 token（旧 token 因会话世代 +1 全部失效），
  // 所以成功后必须把本地 token 换成新的，否则用户一改完密码就把自己踢下线。
  function openPasswordModal() {
    const user = authState();
    if (!user) { toast("登录状态已失效，请重新登录"); return; }
    let modal = document.getElementById("pwd-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "pwd-modal";
      modal.className = "modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.setAttribute("aria-labelledby", "pwd-title");
      modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-card">
          <h3 id="pwd-title">修改密码</h3>
          <p class="modal-sub">当前账号：<strong id="pwd-who"></strong></p>
          <input id="pwd-old" class="app-input" type="password" placeholder="原密码"
                 autocomplete="current-password" aria-label="原密码" />
          <input id="pwd-new" class="app-input" type="password" placeholder="新密码（6~64 位）"
                 autocomplete="new-password" aria-label="新密码" />
          <input id="pwd-new2" class="app-input" type="password" placeholder="确认新密码"
                 autocomplete="new-password" aria-label="确认新密码" />
          <div class="modal-err" id="pwd-err" role="alert" aria-live="polite"></div>
          <div class="modal-actions">
            <button class="btn btn-primary" id="pwd-submit" type="button"><span id="pwd-submit-label">保存</span> <span class="fill"></span></button>
            <button class="btn btn-ghost" id="pwd-cancel" type="button">取消</button>
          </div>
          <p class="modal-hint">改完后其他设备上的登录会全部失效，当前设备自动续登；忘记密码请找管理员重置。
            <span class="modal-ver">v${BUILD}</span></p>
          <button class="modal-close" type="button" aria-label="关闭">&times;</button>
        </div>`;
      document.body.appendChild(modal);

      const err = modal.querySelector("#pwd-err");
      const btn = modal.querySelector("#pwd-submit");
      const btnLabel = modal.querySelector("#pwd-submit-label");
      const oldEl = modal.querySelector("#pwd-old");
      const newEl = modal.querySelector("#pwd-new");
      const newEl2 = modal.querySelector("#pwd-new2");

      const close = () => {
        modal.classList.remove("open");
        err.textContent = "";
        [oldEl, newEl, newEl2].forEach((el) => { el.value = ""; });
        btn.disabled = false;
        btnLabel.textContent = "保存";
        const back = document.getElementById("app-account");
        if (back) back.focus();
      };
      modal.querySelector(".modal-backdrop").addEventListener("click", close);
      modal.querySelector(".modal-close").addEventListener("click", close);
      modal.querySelector("#pwd-cancel").addEventListener("click", close);
      modal.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { e.stopPropagation(); close(); }
      });

      const submit = async () => {
        err.textContent = "";
        const oldPw = oldEl.value;
        const np = newEl.value;
        const np2 = newEl2.value;
        if (!oldPw) { err.textContent = "请填写原密码"; oldEl.focus(); return; }
        if (np.length < 6) { err.textContent = "新密码至少 6 位"; newEl.focus(); return; }
        if (np.length > 64) { err.textContent = "新密码最多 64 位"; newEl.focus(); return; }
        if (np !== np2) { err.textContent = "两次输入的新密码不一致"; newEl2.focus(); return; }
        if (np === oldPw) { err.textContent = "新密码不能与原密码相同"; newEl.focus(); return; }
        btn.disabled = true;
        btnLabel.textContent = "保存中…";
        // 字段名必须是 snake_case：后端 application.yml 里
        // spring.jackson.property-naming-strategy = SNAKE_CASE，全站契约都是 snake_case
        // （day_index / start_date / session_id 同理）。写成 oldPassword 时 Jackson 解不出来，
        // 服务端只会回「oldPassword 不能为空」，看起来像校验问题，其实是字段名对不上。
        const r = await apiPost("/api/auth/change-password", { old_password: oldPw, new_password: np });
        if (!r.ok) {
          btn.disabled = false;
          btnLabel.textContent = "保存";
          err.textContent = pwdErrText(r.data.detail || r.data.message);
          return;
        }
        setAuth(r.data.token, { username: r.data.username, role: r.data.role });
        close();
        toast("密码已修改，其他设备需重新登录");
      };
      btn.addEventListener("click", submit);
      [oldEl, newEl, newEl2].forEach((el) => {
        el.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } });
      });
    }
    modal.querySelector("#pwd-who").textContent = user.username;
    const errBox = modal.querySelector("#pwd-err");
    if (errBox) errBox.textContent = "";
    const submitBtn = modal.querySelector("#pwd-submit");
    if (submitBtn) submitBtn.disabled = false;
    const submitLabel = modal.querySelector("#pwd-submit-label");
    if (submitLabel) submitLabel.textContent = "保存";
    modal.classList.add("open");
    const first = modal.querySelector("#pwd-old");
    if (first) first.focus();
  }

  /* ---------- 高德坐标转换（WGS-84 → GCJ-02） ---------- */
  function wgs84ToGcj02(lng, lat) {
    let tLng = lng - 105, tLat = lat - 35;
    let dLat = (-100 + 2 * tLng + 3 * tLat + 0.2 * tLat * tLat
      + 0.1 * tLng * tLat + 0.2 * Math.sqrt(Math.abs(tLng))
      + (20 * Math.sin(6 * tLng * Math.PI) + 20 * Math.sin(2 * tLng * Math.PI)) * 2 / 3
      + (20 * Math.sin(tLat * Math.PI) + 40 * Math.sin(tLat / 3 * Math.PI)) * 2 / 3
      + (160 * Math.sin(tLat / 12 * Math.PI) + 320 * Math.sin(tLat * Math.PI / 30)) * 2 / 3);
    let dLng = (300 + tLng + 2 * tLat + 0.1 * tLng * tLng
      + 0.1 * tLng * tLat + 0.1 * Math.sqrt(Math.abs(tLng))
      + (20 * Math.sin(6 * tLng * Math.PI) + 20 * Math.sin(2 * tLng * Math.PI)) * 2 / 3
      + (20 * Math.sin(tLng * Math.PI) + 40 * Math.sin(tLng / 3 * Math.PI)) * 2 / 3
      + (150 * Math.sin(tLng / 12 * Math.PI) + 300 * Math.sin(tLng / 30 * Math.PI)) * 2 / 3);
    let radLat = lat / 180 * Math.PI;
    let ee = 0.00669342162296594323;
    let magic = 1 - ee * Math.sin(radLat) * Math.sin(radLat);
    let sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180) / ((6378245 * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
    dLng = (dLng * 180) / (6378245 / sqrtMagic * Math.cos(radLat) * Math.PI);
    return [lng + dLng, lat + dLat];
  }

  /* ---------- 高德地图模板（城市景点） ---------- */
  async function renderAmapCity(containerId, city, info) {
    await loadPublicConfig();
    const el0 = document.getElementById(containerId);
    if (!AMAP_KEY) { if (el0) el0.innerHTML = AMAP_FAIL_HTML; return; }
    const clat = info.center[0], clng = info.center[1];
    const [cLng, cLat] = wgs84ToGcj02(clng, clat);
    const spots = info.spots.map(s => {
      const [gLng, gLat] = wgs84ToGcj02(s[2], s[1]);
      return { name: s[0], lng: gLng.toFixed(6), lat: gLat.toFixed(6), cat: s[3] };
    });
    // 景点名可能来自用户输入（自定义景点）。JSON.stringify 不会转义 < >，
    // 一个叫「</script>」的景点就能把 iframe 里的脚本块提前截断 —— 必须转成 \u003c 形式。
    const payload = JSON.stringify({ city, center: { lng: +cLng.toFixed(6), lat: +cLat.toFixed(6) }, spots })
      .replace(/</g, "\\u003c").replace(/>/g, "\\u003e");
    const html = `
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{height:100%;margin:0;padding:0;font-family:"Yuanti SC","Microsoft YaHei",sans-serif}
body{display:flex;flex-direction:column}
#am-tools{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;flex:0 0 auto}
.amt{border:2px solid #2b2b2b;border-radius:10px;background:#fff;color:#2b1d0e;font-weight: var(--fw-strong);font-size:.82rem;padding:7px 14px;cursor:pointer;box-shadow:3px 3px 0 #2b2b2b;transition:all .12s}
.amt:hover{background:#ffd21e;transform:translate(-1px,-1px);box-shadow:4px 4px 0 #2b2b2b}
.amt:active{transform:translate(2px,2px);box-shadow:1px 1px 0 #2b2b2b}
.amt.on{background:#ff4d4d;color:#fff}
#am-map{width:100%;flex:1 1 auto;min-height:0;border:2.5px solid #2b2b2b;border-radius:16px;box-shadow:4px 4px 0 rgba(43,43,43,.9)}
.am-tip{font-size:.75rem;color:#8a6a3b;margin-top:7px;font-weight: var(--fw-medium);flex:0 0 auto}
.amap-marker-label{border:2px solid #2b2b2b!important;border-radius:8px!important;padding:2px 7px!important;background:#fff9e0!important;color:#2b1d0e!important;font-weight: var(--fw-strong)!important;font-size:12px!important;box-shadow:2px 2px 0 rgba(43,43,43,.55)!important}
.am-fail{margin:16px;padding:18px 20px;background:#fff9e0;border:2px solid #2b2b2b;border-radius:14px;box-shadow:4px 4px 0 rgba(43,43,43,.55);color:#7a2b0e;font-size:13px;line-height:2;font-weight: var(--fw-medium)}
.am-fail b{display:block;font-size:15px;margin-bottom:6px;color:#c0392b}
.am-fail span{display:block}
</style></head><body>
<div id="am-tools">
  <button class="amt on" data-m="marks">📍 景点标记</button>
  <button class="amt" data-m="driving">🚗 驾车路线</button>
  <button class="amt" data-m="walking">🚶 步行路线</button>
  <button class="amt" data-m="transit">🚌 公交路线</button>
</div>
<div id="am-map"></div>
<div class="am-tip">路线按推荐游玩顺序串联各景点 · 点击地图标记查看详情 · 滚轮缩放</div>
<script>window._AMapSecurityConfig={securityJsCode:"${AMAP_JS_CODE}"};</script>
<script src="https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}"></script>
<script>
if(typeof AMap==="undefined"){document.body.innerHTML=${JSON.stringify(AMAP_FAIL_HTML)};throw new Error("AMap JS API 加载失败");}
const DATA = ${payload};
const map = new AMap.Map("am-map", {center:[DATA.center.lng,DATA.center.lat],zoom:12});
map.setStatus({scrollWheel:true});
AMap.plugin(["AMap.Scale","AMap.ToolBar"],function(){try{map.addControl(new AMap.Scale());map.addControl(new AMap.ToolBar({position:"RT"}));}catch(e){}});
const CAT_ICON={"地标":"\ud83c\udfdb\ufe0f","古迹":"\ud83c\udfdf\ufe0f","公园":"\ud83c\udf33","街区":"\ud83c\udf92\ufe0f","商圈":"\ud83d\udecd\ufe0f","自然":"\ud83c\udf04","乐园":"\ud83c\udfa1","亲子":"\ud83d\udc3c","体验":"\ud83d\udea1","场馆":"\ud83c\udfa8","美食":"\ud83c\udf5c"};
function esc(t){return String(t==null?"":t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
DATA.spots.forEach(function(s,i){
  const mk=new AMap.Marker({position:[s.lng,s.lat],label:{content:(i+1)+"."+esc(s.name),direction:"right",offset:new AMap.Pixel(12,-6)}});
  mk.on("click",function(){
    const iw=new AMap.InfoWindow({content:'<div style="font-weight: var(--fw-strong);font-size:14px">'+(i+1)+'. '+esc(s.name)+'</div><div style="color:#8a6a3b;font-size:12px;margin-top:3px">'+(CAT_ICON[s.cat]||"📍")+' '+esc(s.cat)+' · 推荐顺序第 '+(i+1)+' 站</div>',offset:new AMap.Pixel(0,-32)});
    iw.open(map,[s.lng,s.lat]);
  });
  map.add(mk);
});
let planners=[];
function clearRoutes(){planners.forEach(function(p){try{p.clear();}catch(e){}});planners=[];}
function planRoute(mode){clearRoutes();if(mode==="marks")return;const plugin=mode==="driving"?"AMap.Driving":mode==="walking"?"AMap.Walking":"AMap.Transfer";AMap.plugin(plugin,function(){let idx=0;const next=function(){if(idx>=DATA.spots.length-1)return;const a=DATA.spots[idx],b=DATA.spots[idx+1];let planner;if(mode==="transit")planner=new AMap.Transfer({map:map,city:DATA.city,hideMarkers:true});else if(mode==="driving")planner=new AMap.Driving({map:map,hideMarkers:true});else planner=new AMap.Walking({map:map,hideMarkers:true});planners.push(planner);planner.search(new AMap.LngLat(a.lng,a.lat),new AMap.LngLat(b.lng,b.lat),function(){idx+=1;setTimeout(next,130);});};next();});}
document.querySelectorAll(".amt").forEach(function(btn){btn.addEventListener("click",function(){document.querySelectorAll(".amt").forEach(function(b){b.classList.remove("on");});btn.classList.add("on");planRoute(btn.dataset.m);});});
</script></body></html>`;
    const el = document.getElementById(containerId);
    if (el) {
      el.innerHTML = `<iframe srcdoc="${html.replace(/&/g, "&amp;").replace(/"/g, "&quot;")}" style="width:100%;height:100%;border:0;border-radius:16px" allow="fullscreen"></iframe>`;
    }
  }

  /* ---------- 高德地图模板（行程路线：按天分色） ---------- */
  // 与 renderAmapCity 的区别：那里是「一个城市的所有景点」，这里是「一份行程里
  // 真正要去的地方，按天分色、按当天顺序编号并连线」。坐标仍取 geo-data.js，
  // 所以行程条目必须能对上景点库里的名字（matchTripSpot 负责匹配）。
  const TRIP_DAY_COLORS = ["#e53935", "#1e88e5", "#2e9e5b", "#f08c00", "#8e24aa", "#00897b", "#d81b60"];

  async function renderAmapTripMap(containerId, info) {
    await loadPublicConfig();
    const el0 = document.getElementById(containerId);
    if (!AMAP_KEY) { if (el0) el0.innerHTML = AMAP_FAIL_HTML; return; }
    if (!info || !info.days || !info.days.length) {
      if (el0) el0.innerHTML = `<div class="am-fail"><b>还没有可以上图的地点</b>
        <span>先让 AI 生成每日行程，或手动把景点加进某一天。</span></div>`;
      return;
    }
    const [cLat, cLng] = info.center;
    const [gLng, gLat] = wgs84ToGcj02(cLng, cLat);
    const days = info.days.map((d, di) => ({
      day: d.day,
      color: TRIP_DAY_COLORS[di % TRIP_DAY_COLORS.length],
      stops: d.stops.map((s, si) => {
        const [slng, slat] = wgs84ToGcj02(s.lng, s.lat);
        return { name: s.name, lng: +slng.toFixed(6), lat: +slat.toFixed(6), seq: si + 1, note: s.note || "" };
      })
    }));
    const payload = JSON.stringify({ city: info.city, center: { lng: +gLng.toFixed(6), lat: +gLat.toFixed(6) }, days })
      .replace(/</g, "\\u003c").replace(/>/g, "\\u003e");
    const html = `
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{height:100%;margin:0;padding:0;font-family:"Yuanti SC","Microsoft YaHei",sans-serif}
#am-map{width:100%;height:100%;border:2.5px solid #2b2b2b;border-radius:16px;box-shadow:4px 4px 0 rgba(43,43,43,.9)}
.pin{width:26px;height:26px;border-radius:50%;background:var(--c);color:#fff;border:2.5px solid #2b2b2b;
  display:flex;align-items:center;justify-content:center;font-weight: var(--fw-strong);font-size:12px;
  box-shadow:2px 2px 0 rgba(43,43,43,.55);line-height:1}
.amap-marker-label{border:2px solid #2b2b2b!important;border-radius:8px!important;padding:2px 7px!important;
  background:#fff9e0!important;color:#2b1d0e!important;font-weight: var(--fw-strong)!important;font-size:12px!important;
  box-shadow:2px 2px 0 rgba(43,43,43,.55)!important;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.am-fail{margin:16px;padding:18px 20px;background:#fff9e0;border:2px solid #2b2b2b;border-radius:14px;
  box-shadow:4px 4px 0 rgba(43,43,43,.55);color:#7a2b0e;font-size:13px;line-height:2;font-weight: var(--fw-medium)}
.am-fail b{display:block;font-size:15px;margin-bottom:6px;color:#c0392b}
.am-fail span{display:block}
</style></head><body>
<div id="am-map"></div>
<script>window._AMapSecurityConfig={securityJsCode:"${AMAP_JS_CODE}"};</script>
<script src="https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}"></script>
<script>
if(typeof AMap==="undefined"){document.body.innerHTML=${JSON.stringify(AMAP_FAIL_HTML)};throw new Error("AMap JS API 加载失败");}
const DATA=${payload};
const map=new AMap.Map("am-map",{center:[DATA.center.lng,DATA.center.lat],zoom:12,viewMode:"2D"});
map.setStatus({scrollWheel:true});
AMap.plugin(["AMap.Scale","AMap.ToolBar"],function(){try{map.addControl(new AMap.Scale());map.addControl(new AMap.ToolBar({position:"RT"}));}catch(e){}});
function esc(t){return String(t==null?"":t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
const all=[];
DATA.days.forEach(function(d){
  const path=[];
  d.stops.forEach(function(s){
    const mk=new AMap.Marker({
      position:[s.lng,s.lat],
      content:'<div class="pin" style="--c:'+d.color+'">'+s.seq+'</div>',
      offset:new AMap.Pixel(-13,-13),
      label:{content:"D"+d.day+"·"+esc(s.name),direction:"right",offset:new AMap.Pixel(14,-8)}
    });
    mk.on("click",function(){
      const iw=new AMap.InfoWindow({offset:new AMap.Pixel(0,-18),content:
        '<div style="font-weight: var(--fw-strong);font-size:14px">'+esc(s.name)+'</div>'+
        '<div style="color:#8a6a3b;font-size:12px;margin-top:4px">第 '+d.day+' 天 · 第 '+s.seq+' 站</div>'+
        (s.note?'<div style="color:#5b4636;font-size:12px;margin-top:4px">'+esc(s.note)+'</div>':'')});
      iw.open(map,[s.lng,s.lat]);
    });
    map.add(mk); all.push(mk); path.push([s.lng,s.lat]);
  });
  // 一天只有一个点时不画线：单点折线在高德里会退化成一个看不见的小圈
  if(path.length>1){
    map.add(new AMap.Polyline({path:path,strokeColor:d.color,strokeWeight:4,strokeOpacity:.85,
      showDir:true,lineJoin:"round",lineCap:"round"}));
  }
});
if(all.length) map.setFitView(all,false,[70,70,70,70]);
</script></body></html>`;
    const el = document.getElementById(containerId);
    if (el) {
      el.innerHTML = `<iframe title="行程地图" srcdoc="${html.replace(/&/g, "&amp;").replace(/"/g, "&quot;")}" style="width:100%;height:100%;border:0;border-radius:16px" allow="fullscreen"></iframe>`;
    }
  }

  /* ---------- 高德地图模板（跨城路线） ---------- */
  async function renderAmapRoute(containerId, fromCity, toCity) {
    await loadPublicConfig();
    const el0 = document.getElementById(containerId);
    if (!AMAP_KEY) { if (el0) el0.innerHTML = AMAP_FAIL_HTML; return; }
    const [fLat, fLng] = window.CITY_GEO[fromCity].center;
    const [tLat, tLng] = window.CITY_GEO[toCity].center;
    const [fGLng, fGLat] = wgs84ToGcj02(fLng, fLat);
    const [tGLng, tGLat] = wgs84ToGcj02(tLng, tLat);
    const payload = JSON.stringify({
      from: { name: fromCity, lng: +fGLng.toFixed(6), lat: +fGLat.toFixed(6) },
      to:   { name: toCity,   lng: +tGLng.toFixed(6), lat: +tGLat.toFixed(6) }
    }).replace(/</g, "\\u003c").replace(/>/g, "\\u003e");
    const fEsc = escapeHtml(fromCity), tEsc = escapeHtml(toCity);
    const html = `
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>*{margin:0;padding:0;box-sizing:border-box}html,body{height:100%}
#am-map{width:100%;height:100%}
#am-bar{position:absolute;top:10px;left:10px;z-index:99;background:#fff9e0;border:2px solid #2b2b2b;border-radius:10px;padding:8px 12px;font-size:13px;font-weight: var(--fw-strong);color:#2b1d0e;box-shadow:3px 3px 0 rgba(43,43,43,.55);max-width:92%}
.amap-marker-label{border:2px solid #2b2b2b!important;border-radius:8px!important;padding:2px 7px!important;background:#fff9e0!important;color:#2b1d0e!important;font-weight: var(--fw-strong)!important;font-size:12px!important;box-shadow:2px 2px 0 rgba(43,43,43,.55)!important}
.am-fail{margin:16px;padding:18px 20px;background:#fff9e0;border:2px solid #2b2b2b;border-radius:14px;box-shadow:4px 4px 0 rgba(43,43,43,.55);color:#7a2b0e;font-size:13px;line-height:2;font-weight: var(--fw-medium);position:relative;z-index:1}
.am-fail b{display:block;font-size:15px;margin-bottom:6px;color:#c0392b}
.am-fail span{display:block}
</style></head><body>
<div id="am-map"></div><div id="am-bar">🚗 正在规划 ${fEsc} → ${tEsc} 的驾车路线…</div>
<script>window._AMapSecurityConfig={securityJsCode:"${AMAP_JS_CODE}"};</script>
<script src="https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}"></script>
<script>
if(typeof AMap==="undefined"){document.body.innerHTML=${JSON.stringify(AMAP_FAIL_HTML)};throw new Error("AMap JS API 加载失败");}
const DATA=${payload};
const map=new AMap.Map("am-map",{zoom:5});
map.setStatus({scrollWheel:true});
AMap.plugin(["AMap.Scale","AMap.ToolBar"],function(){try{map.addControl(new AMap.Scale());map.addControl(new AMap.ToolBar({position:"RT"}));}catch(e){}});
function esc(t){return String(t==null?"":t).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
map.add([new AMap.Marker({position:[DATA.from.lng,DATA.from.lat],label:{content:"🚩 出发 · "+esc(DATA.from.name),direction:"right",offset:new AMap.Pixel(12,-6)}}),new AMap.Marker({position:[DATA.to.lng,DATA.to.lat],label:{content:"🏁 到达 · "+esc(DATA.to.name),direction:"right",offset:new AMap.Pixel(12,-6)}})]);
map.setFitView();
AMap.plugin("AMap.Driving",function(){const dr=new AMap.Driving({map:map,hideMarkers:true});dr.search(new AMap.LngLat(DATA.from.lng,DATA.from.lat),new AMap.LngLat(DATA.to.lng,DATA.to.lat),function(status,result){const bar=document.getElementById("am-bar");if(status==="complete"&&result.routes&&result.routes.length){const r=result.routes[0];const km=(r.distance/1000).toFixed(0);const h=Math.floor(r.duration/3600);const m=Math.round((r.duration%3600)/60);bar.textContent="🚗 "+esc(DATA.from.name)+" → "+esc(DATA.to.name)+" · 全程约 "+km+" 公里 · 驾车约 "+(h?h+" 小时"+(m?" "+m+" 分钟":""):m+" 分钟");}else{bar.textContent="⚠️ 驾车路线规划失败，已标注两城位置（距离过远或超出规划范围）";}});});
</script></body></html>`;
    const el = document.getElementById(containerId);
    if (el) {
      el.innerHTML = `<iframe srcdoc="${html.replace(/&/g, "&amp;").replace(/"/g, "&quot;")}" style="width:100%;height:100%;border:0;border-radius:16px" allow="fullscreen"></iframe>`;
    }
  }

  /* ---------- 城市选择辅助 ---------- */
  // 按拼音首字母分组，返回 [{ letter: "A", cities: [...] }, ...]，字母升序。
  // 城市多（350+）时，下拉框靠 optgroup 分组才找得到。
  function cityGroups() {
    const geo = window.CITY_GEO || {};
    const bucket = {};
    Object.keys(geo).forEach((name) => {
      const letter = (geo[name] && geo[name].py) || "#";
      (bucket[letter] = bucket[letter] || []).push(name);
    });
    return Object.keys(bucket).sort().map((letter) => ({
      letter: letter,
      cities: bucket[letter].sort((a, b) => a.localeCompare(b, "zh"))
    }));
  }

  // 生成带 <optgroup> 的 <option> 列表 HTML，供地图页 / 交通页的下拉框复用
  function cityOptionsHtml() {
    return cityGroups().map((g) => {
      const opts = g.cities.map((c) => `<option>${c}</option>`).join("");
      return `<optgroup label="${g.letter}">${opts}</optgroup>`;
    }).join("");
  }

  /* ---------- 用户自定义景点（增 / 删，存 localStorage） ---------- */
  // 结构：{ "北京": { added: [{n,lat,lng,cat}], removed: ["天安门广场"] } }
  // 只存「差异」，默认数据仍以 geo-data.js 为准，这样以后更新城市数据不会被用户改动卡住。
  const SPOT_OV_KEY = "tc_spot_overrides";
  const SPOT_CATS = ["地标", "古迹", "公园", "街区", "商圈", "自然", "乐园", "亲子", "体验", "场馆", "美食"];

  function loadSpotOv() {
    try {
      const o = JSON.parse(localStorage.getItem(SPOT_OV_KEY) || "{}");
      return (o && typeof o === "object") ? o : {};
    } catch (e) { return {}; }
  }
  function saveSpotOv(o) {
    try { localStorage.setItem(SPOT_OV_KEY, JSON.stringify(o)); } catch (e) {}
  }
  function citySpotOv(city) {
    const c = loadSpotOv()[city];
    return (c && typeof c === "object") ? c : {};
  }
  // 某城市是否有用户改动（用于显示「已自定义」角标与「恢复默认」按钮）
  function hasSpotOv(city) {
    const c = citySpotOv(city);
    return !!((c.added || []).length || (c.removed || []).length);
  }
  // 默认景点 + 用户增删 → 最终列表。返回深拷贝，避免污染 CITY_GEO 原始数据。
  function effectiveSpots(city) {
    const info = (window.CITY_GEO || {})[city];
    const base = (info && info.spots) || [];
    const ov = citySpotOv(city);
    const removed = new Set(ov.removed || []);
    const out = base.filter((s) => !removed.has(s[0])).map((s) => s.slice());
    (ov.added || []).forEach((a) => {
      if (!a || !a.n || !isFinite(a.lat) || !isFinite(a.lng)) return;
      const row = [a.n, +a.lat, +a.lng, SPOT_CATS.includes(a.cat) ? a.cat : "地标"];
      const i = out.findIndex((s) => s[0] === a.n);
      if (i >= 0) out[i] = row; else out.push(row);
    });
    return out;
  }
  function addSpotOv(city, name, lat, lng, cat) {
    const all = loadSpotOv();
    const c = (all[city] = all[city] || {});
    c.added = (c.added || []).filter((a) => a && a.n !== name);
    c.added.push({ n: name, lat: +lat, lng: +lng, cat: cat });
    // 如果这个同名景点本来在默认数据里，撤销它的「删除」标记
    c.removed = (c.removed || []).filter((n) => n !== name);
    saveSpotOv(all);
  }
  function removeSpotOv(city, name) {
    const all = loadSpotOv();
    const c = (all[city] = all[city] || {});
    c.added = (c.added || []).filter((a) => a && a.n !== name);
    // 只有「默认数据里存在」的景点才需要记删除标记
    const base = ((window.CITY_GEO || {})[city] || {}).spots || [];
    if (base.some((s) => s[0] === name)) {
      c.removed = c.removed || [];
      if (!c.removed.includes(name)) c.removed.push(name);
    }
    saveSpotOv(all);
  }
  function resetSpotOv(city) {
    const all = loadSpotOv();
    delete all[city];
    saveSpotOv(all);
  }

  /* ---------- 需求解析与景点筛选（前端复刻） ---------- */
  const TRAVEL_CAT_KEYS = {
    "地标": ["地标","标志","打卡","著名","必去","网红"],
    "古迹": ["历史","古迹","古建筑","文化","寺庙","文物","古镇","古街"],
    "公园": ["公园","绿地","园林","散步"],
    "街区": ["街区","胡同","老街","巷子","逛街","夜市"],
    "商圈": ["购物","商圈","商场","买买买"],
    "自然": ["自然","山水","风景","爬山","山","湖","海","江","河","草原","海滩","海边"],
    "乐园": ["乐园","游乐园","迪士尼","环球","欢乐谷","刺激"],
    "亲子": ["孩子","亲子","儿童","小孩","遛娃","家庭","带娃","宝宝","熊猫","动物园"],
    "体验": ["体验","手工","温泉","演出"],
    "场馆": ["场馆","博物馆","美术馆","科技馆","艺术","展览","剧院","音乐"],
    "美食": ["美食","小吃","吃","餐厅","馆子","夜市","好吃","味道","探店","特色菜","夜宵","早点","早餐","火锅","烧烤"]
  };
  // 城市别名 → CITY_GEO 的键。仅在「文本里找不到任何城市名」时才启用（见 parseTravelQuery），
  // 因此这里可以放心收录大量景区别名：用户说「想去庐山」，也能正确落到九江。
  const CITY_ALIASES = {
    // —— 城市雅称 ——
    "帝都": "北京", "魔都": "上海", "羊城": "广州", "鹏城": "深圳", "金陵": "南京",
    "江城": "武汉", "星城": "长沙", "春城": "昆明", "鹭岛": "厦门", "鹿城": "三亚",
    "蓉城": "成都", "山城": "重庆", "泉城": "济南", "冰城": "哈尔滨", "青城": "呼和浩特",
    "金城": "兰州", "夏都": "西宁", "日光城": "拉萨", "甬城": "宁波", "越城": "绍兴",
    "榕城": "福州", "洪城": "南昌", "邕城": "南宁", "椰城": "海口", "车城": "长春",
    // —— 省份 / 自治区 → 省会 ——
    "河北": "石家庄", "山西": "太原", "辽宁": "沈阳", "黑龙江": "哈尔滨", "江苏": "南京",
    "浙江": "杭州", "安徽": "合肥", "福建": "福州", "江西": "南昌", "山东": "济南",
    "河南": "郑州", "湖北": "武汉", "湖南": "长沙", "广东": "广州", "广西": "南宁",
    "海南": "海口", "四川": "成都", "贵州": "贵阳", "云南": "昆明", "陕西": "西安",
    "甘肃": "兰州", "青海": "西宁", "宁夏": "银川", "新疆": "乌鲁木齐", "西藏": "拉萨",
    "内蒙古": "呼和浩特",
    // —— 中国香港 / 中国澳门 / 中国台湾 ——
    "香港": "中国香港", "澳门": "中国澳门", "台北": "中国台北", "台湾": "中国台北",
    // —— 知名景区 → 所在城市 ——
    "庐山": "九江", "浔阳": "九江", "峨眉山": "乐山", "乐山大佛": "乐山",
    "黄果树": "安顺", "龙宫": "安顺", "雪乡": "牡丹江", "镜泊湖": "牡丹江",
    "千户苗寨": "黔东南", "西江苗寨": "黔东南", "肇兴侗寨": "黔东南", "镇远": "黔东南",
    "喀纳斯": "阿勒泰", "禾木": "阿勒泰", "可可托海": "阿勒泰",
    "那拉提": "伊犁", "赛里木湖": "伊犁", "伊宁": "伊犁", "果子沟": "伊犁",
    "普陀山": "舟山", "朱家尖": "舟山", "东极岛": "舟山",
    "泰山": "泰安", "岱庙": "泰安", "孔庙": "曲阜", "三孔": "曲阜", "尼山": "曲阜",
    "九曲溪": "武夷山", "天游峰": "武夷山", "避暑山庄": "承德", "木兰围场": "承德",
    "山海关": "秦皇岛", "北戴河": "秦皇岛", "阿那亚": "秦皇岛",
    "云冈石窟": "大同", "悬空寺": "大同", "恒山": "大同",
    "平遥古城": "平遥", "五爷庙": "五台山", "黛螺顶": "五台山",
    "三峡": "宜昌", "三峡大坝": "宜昌", "恩施大峡谷": "恩施", "腾龙洞": "恩施",
    "九寨": "九寨沟", "黄龙": "九寨沟",
    "洱海": "大理", "苍山": "大理", "双廊": "大理", "喜洲": "大理",
    "普达措": "香格里拉", "松赞林寺": "香格里拉", "梅里雪山": "香格里拉",
    "涠洲岛": "北海", "遇龙河": "阳朔", "兴坪": "阳朔",
    "遵义会议": "遵义", "赤水": "遵义", "茅台": "遵义",
    "莫高窟": "敦煌", "鸣沙山": "敦煌", "月牙泉": "敦煌", "玉门关": "敦煌",
    "七彩丹霞": "张掖", "马蹄寺": "张掖",
    "火焰山": "吐鲁番", "葡萄沟": "吐鲁番", "交河故城": "吐鲁番",
    "喀什古城": "喀什", "香妃": "喀什",
    "长白山天池": "长白山", "延边": "延吉", "帽儿山": "延吉",
    "满洲里": "呼伦贝尔", "额尔古纳": "呼伦贝尔", "阿尔山": "乌兰浩特",
    "沙坡头": "中卫", "腾格里": "中卫",
    "宏村": "黄山", "西递": "黄山", "屯溪": "黄山",
    "瓷都": "景德镇", "陶溪川": "景德镇",
    "凤凰古城": "凤凰", "沱江": "凤凰",
    "天门山": "张家界", "武陵源": "张家界", "袁家界": "张家界", "玻璃桥": "张家界",
    "瘦西湖": "扬州", "东关街": "扬州",
    "天一阁": "宁波", "东钱湖": "宁波", "溪口": "宁波",
    "鲁迅故里": "绍兴", "兰亭": "绍兴", "安昌": "绍兴",
    "开元寺": "泉州", "蟳埔": "泉州", "崇武": "泉州",
    "孔府": "曲阜", "孔林": "曲阜", "台儿庄": "枣庄",
    "岳阳楼": "岳阳", "洞庭湖": "岳阳",
    // —— 地级行政区 / 自治州 → 行政中心（新增城市用）——
    "吉林": "吉林市", "阿拉善": "阿拉善左旗", "阿拉善盟": "阿拉善左旗",
    "大兴安岭": "加格达奇", "兴安盟": "乌兰浩特", "锡林郭勒": "锡林浩特",
    "黔南": "都匀", "黔西南": "兴义", "红河": "蒙自", "德宏": "芒市",
    "甘南": "合作", "海南州": "共和", "博尔塔拉": "博乐", "克孜勒苏": "阿图什",
    "巴音郭楞": "库尔勒", "巴州": "库尔勒", "湘西": "吉首", "阿坝": "马尔康",
    "甘孜": "康定", "凉山": "西昌", "迪庆": "香格里拉",
    // —— 新增城市的知名景区 ——
    "梵净山": "铜仁", "织金洞": "毕节", "百里杜鹃": "毕节", "草海": "毕节",
    "荔波": "都匀", "小七孔": "都匀", "万峰林": "兴义", "马岭河": "兴义",
    "腾冲": "保山", "和顺古镇": "保山", "抚仙湖": "玉溪", "罗平": "曲靖",
    "九龙瀑布": "曲靖", "普者黑": "文山", "坝美": "文山", "元阳梯田": "蒙自",
    "景迈山": "普洱", "翁丁": "临沧", "元谋土林": "楚雄", "彝人古镇": "楚雄",
    "纳木错": "那曲", "羊卓雍措": "山南", "雍布拉康": "山南", "桑耶寺": "山南",
    "扎什伦布寺": "日喀则", "珠峰": "日喀则", "冈仁波齐": "阿里",
    "玛旁雍错": "阿里", "古格王朝": "阿里", "然乌湖": "昌都",
    "麦积山": "天水", "伏羲庙": "天水", "崆峒山": "平凉", "拉卜楞寺": "合作",
    "青海湖": "共和", "茶卡盐湖": "共和", "日月山": "共和", "沙湖": "石嘴山",
    "青铜峡": "吴忠", "六盘山": "固原", "须弥山": "固原",
    "世界魔鬼城": "克拉玛依", "天山天池": "昌吉", "博斯腾湖": "库尔勒",
    "罗布人村寨": "库尔勒", "库车大峡谷": "阿克苏", "克孜尔千佛洞": "阿克苏",
    "喀拉峻": "伊宁", "华山": "渭南", "法门寺": "宝鸡", "太白山": "宝鸡",
    "乾陵": "咸阳", "袁家村": "咸阳", "黄帝陵": "延安", "宝塔山": "延安",
    "壶口": "临汾", "剑门关": "广元", "昭化古城": "广元", "三星堆": "德阳",
    "阆中": "南充", "蜀南竹海": "宜宾", "兴文石海": "宜宾", "碧峰峡": "雅安",
    "牛背山": "雅安", "光雾山": "巴中", "邛海": "西昌", "泸沽湖": "西昌",
    "木格措": "康定", "新都桥": "康定", "塔公草原": "康定",
    "开平碉楼": "江门", "丹霞山": "韶关", "南华寺": "韶关", "罗浮山": "惠州",
    "巽寮湾": "惠州", "双月湾": "惠州", "雁南飞": "梅州", "广济桥": "潮州",
    "牌坊街": "潮州", "南澳岛": "汕头", "七星岩": "肇庆", "鼎湖山": "肇庆",
    "湖光岩": "湛江", "海陵岛": "阳江", "闸坡": "阳江", "古龙峡": "清远",
    "连州地下河": "清远", "万绿湖": "河源", "松山湖": "东莞", "孙中山故居": "中山",
    "黄姚古镇": "贺州", "姑婆山": "贺州", "德天瀑布": "崇左", "明仕田园": "崇左",
    "通灵大峡谷": "百色", "乐业天坑": "百色", "程阳八寨": "柳州", "三娘湾": "钦州",
    "银滩": "北海", "博鳌": "琼海", "玉带滩": "琼海", "东郊椰林": "文昌",
    "兴隆": "万宁", "日月湾": "万宁", "崀山": "邵阳", "韶山": "湘潭",
    "桃花源": "常德", "东江湖": "郴州", "莽山": "郴州", "高椅岭": "郴州",
    "九嶷山": "永州", "洪江古商城": "怀化", "芷江": "怀化", "紫鹊界": "娄底",
    "德夯": "吉首", "矮寨": "吉首", "明显陵": "荆门", "武当山": "十堰",
    "丹江口": "十堰", "古隆中": "襄阳", "东坡赤壁": "黄冈", "龟峰山": "黄冈",
    "九宫山": "咸宁", "炎帝陵": "株洲", "井冈山": "吉安", "龙虎山": "鹰潭",
    "明月山": "宜春", "三清山": "上饶", "篁岭": "上饶", "大觉山": "抚州",
    "流坑": "抚州", "武功山": "萍乡", "仙女湖": "新余", "郁孤台": "赣州",
    "瑞金": "赣州", "云台山": "焦作", "青天河": "焦作", "殷墟": "安阳",
    "红旗渠": "安阳", "太行大峡谷": "安阳", "万仙山": "新乡", "郭亮": "新乡",
    "八里沟": "新乡", "尧山": "平顶山", "中原大佛": "平顶山", "函谷关": "三门峡",
    "地坑院": "三门峡", "芒砀山": "商丘", "鸡公山": "信阳", "南湾湖": "信阳",
    "嵖岈山": "驻马店", "王屋山": "济源", "小浪底": "济源", "周村": "淄博",
    "黄河入海口": "东营", "杨家埠": "潍坊", "青州古城": "潍坊", "沂山": "潍坊",
    "微山湖": "济宁", "万平口": "日照", "五莲山": "日照", "沂蒙山": "临沂",
    "竹泉村": "临沂", "东昌湖": "聊城", "光岳楼": "聊城", "曹州牡丹园": "菏泽",
    "水浒好汉城": "菏泽", "鹤伴山": "滨州", "魏氏庄园": "滨州", "琅琊山": "滁州",
    "醉翁亭": "滁州", "天柱山": "安庆", "九华山": "池州", "敬亭山": "宣城",
    "查济": "宣城", "八里河": "阜阳", "天堂寨": "六安", "万佛湖": "六安",
    "花戏楼": "亳州", "皇藏峪": "宿州", "采石矶": "马鞍山", "八公山": "淮南",
    "寿县古城": "淮南", "云水谣": "漳州", "东山岛": "漳州", "南靖土楼": "漳州",
    "永定土楼": "龙岩", "冠豸山": "龙岩", "古田会议": "龙岩", "太姥山": "宁德",
    "白水洋": "宁德", "湄洲岛": "莆田", "妈祖": "莆田", "泰宁": "三明",
    "大金湖": "三明", "玉华洞": "三明", "雁荡山": "温州", "楠溪江": "温州",
    "乌镇": "嘉兴", "西塘": "嘉兴", "南浔": "湖州", "莫干山": "湖州",
    "横店": "金华", "双龙洞": "金华", "江郎山": "衢州", "龙游石窟": "衢州",
    "廿八都": "衢州", "天台山": "台州", "神仙居": "台州", "缙云仙都": "丽水",
    "云和梯田": "丽水", "鼋头渚": "无锡", "金山寺": "镇江", "西津渡": "镇江",
    "溱潼": "泰州", "项王故里": "宿迁", "中华恐龙园": "常州", "天目湖": "常州",
    "花果山": "连云港", "连岛": "连云港", "云龙湖": "徐州", "龟山汉墓": "徐州",
    "濠河": "南通", "狼山": "南通", "周恩来故居": "淮安", "河下古镇": "淮安",
    "中华麋鹿园": "盐城", "丹顶鹤": "盐城"
  };
  const CN_NUM = {"一":1,"两":2,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10};
  const SPOT_SUFFIXES = ["广场","公园","博物院","纪念馆","古街","步行街","基地","中心","寺","山","湖","岛"];
  function spotShort(name) {
    for (const s of SPOT_SUFFIXES) { if (name.endsWith(s) && name.length > s.length + 1) return name.slice(0, -s.length); }
    return name;
  }
  function parseTravelQuery(text) {
    const geo = window.CITY_GEO || {};
    // 只认「确实存在于 CITY_GEO 的城市」，避免别名指向不存在的键时后续 geo[city] 取值报错。
    // 城市名会互相包含（鞍山 ⊂ 马鞍山、眉山 ⊂ 峨眉山），所以必须取**最长**匹配，
    // 否则用户说「峨眉山」会被误判成「眉山」。
    let city = Object.keys(geo)
      .filter(c => text.includes(c))
      .sort((a, b) => b.length - a.length)[0] || null;
    let aliasHit = null;
    if (!city) {
      // 别名同样取最长匹配：「香格里拉」要优先于「香格」
      const aliasKeys = Object.keys(CITY_ALIASES)
        .filter(a => text.includes(a) && geo[CITY_ALIASES[a]])
        .sort((a, b) => b.length - a.length);
      if (aliasKeys.length) { aliasHit = aliasKeys[0]; city = CITY_ALIASES[aliasHit]; }
    }
    let t = city ? text.replace(city, "") : text;
    if (aliasHit) t = t.replace(aliasHit, "");
    const cats = Object.entries(TRAVEL_CAT_KEYS).filter(([c, keys]) => keys.some(k => t.includes(k))).map(([c]) => c);
    let days = null;
    const m = t.match(/(\d+|[一两二三四五六七八九十])\s*(?:天|日)/);
    if (m) { const g = m[1]; days = CN_NUM[g] || parseInt(g, 10); }
    // 用合并后的景点列表，这样用户自己加的景点也能被「必去」规则命中
    const must = city ? effectiveSpots(city).filter(s => text.includes(s[0]) || text.includes(spotShort(s[0]))) : [];
    return { city, cats, days, must };
  }
  function pickSpots(info, cats, days, must) {
    const spots = info.spots;
    const mustNames = new Set(must.map(s => s[0]));
    const target = Math.min((days || 3) * 3, spots.length);
    const picked = [], matched = new Set();
    for (const s of spots) {
      if (mustNames.has(s[0]) || (cats.length && cats.includes(s[3]))) { picked.push(s); matched.add(s[0]); }
    }
    for (const s of spots) { if (picked.length >= target) break; if (!picked.includes(s)) picked.push(s); }
    return { picked, matched };
  }

  /* ---------- 聊天页 ---------- */
  const AGENT_META = {
    planner: { icon: "🗓️", title: "行程规划师" },
    attractions: { icon: "🏛️", title: "景点顾问" },
    food: { icon: "🍜", title: "美食顾问" },
    analyst: { icon: "📊", title: "数据分析师" },
    consultant: { icon: "💬", title: "旅行咨询师" },
    supervisor: { icon: "🧭", title: "调度中心" },
  };
  const agentLabel = (n) => AGENT_META[n] ? `${AGENT_META[n].icon} ${AGENT_META[n].title}` : n;

  const sessKey = (u) => "tc_sessions_" + u;
  function loadSessions(u) {
    try { return JSON.parse(localStorage.getItem(sessKey(u)) || "[]"); } catch (e) { return []; }
  }
  function saveSessions(u, list) {
    try { localStorage.setItem(sessKey(u), JSON.stringify(list.slice(0, 50))); } catch (e) {}
  }

  async function initChatPage() {
    const container = document.getElementById("chat-app");
    if (!container) return;
    const user = authState();
    if (!user) {
      container.innerHTML = `<div class="app-gate"><h2>请先登录</h2><p>登录后即可使用 AI 旅行咨询</p><a href="index.html#login" class="btn btn-primary">去登录 <span class="fill"></span></a></div>`;
      return;
    }

    // 先渲壳、后填数据：原来 await 完 /api/agents 才写 innerHTML，弱网(800ms)时整页空白，
    // 用户看到的是「点了导航没反应」。骨架 3 行，行高对齐 .cs-agent，回填不跳版。
    const skelRows = Array.from({ length: 3 }, () => `<div class="skeleton cs-skel"></div>`).join("");

    container.innerHTML = `
      <div class="chat-wrap">
        <div class="chat-sidebar">
          <button class="btn btn-accent cs-new" id="chat-new">＋ 新建对话</button>
          <div class="cs-block">
            <div class="cs-head">历史会话</div>
            <div class="cs-sessions" id="cs-sessions"></div>
          </div>
          <div class="cs-block">
            <div class="cs-head">AI 旅行顾问团</div>
            <div class="cs-list" id="cs-list">${skelRows}</div>
          </div>
        </div>
        <div class="chat-main">
          <div class="chat-messages" id="chat-msgs"></div>
          <div class="chat-kb-hint" id="chat-kb-hint"></div>
          <div class="chat-inputbar">
            <input id="chat-in" type="text" placeholder="输入你的旅行需求，按回车发送…" autocomplete="off" />
            <button id="chat-send" class="btn btn-accent">发送</button>
          </div>
        </div>
      </div>`;

    /* ---- 顾问团：骨架 → 名单 / 空态 / 失败可重试 ---- */
    const csList = container.querySelector("#cs-list");
    const loadAgents = async () => {
      if (!csList) return;
      const paint = (html) => { csList.innerHTML = html; };
      paint(skelRows);
      const r = await apiGet("/api/agents");
      if (!r.ok) {
        // r.data.detail 是给开发者看的（"服务返回 502"），用户看了不知道能干什么。
        paint(`<div class="cs-empty">顾问团加载失败，<button type="button" class="cs-retry">重新加载</button></div>`);
        const again = csList.querySelector(".cs-retry");
        if (again) again.addEventListener("click", loadAgents);
        return;
      }
      const agents = (r.data && r.data.experts) || [];
      // 名单为空是后端没配专家，不是网络问题，别让用户反复点重试。
      paint(agents.length
        ? agents.map(a => `<div class="cs-agent">${escapeHtml(a.icon)} ${escapeHtml(a.title)}</div>`).join("")
        : `<div class="cs-empty">暂无可用顾问</div>`);
    };
    loadAgents();

    const msgs = container.querySelector("#chat-msgs");
    const input = container.querySelector("#chat-in");
    const sendBtn = container.querySelector("#chat-send");
    const sessEl = container.querySelector("#cs-sessions");
    let sessionId = "";
    let busy = false;
    let assistantCount = 0;

    const scrollDown = () => { msgs.scrollTop = msgs.scrollHeight; };

    /* ---- 知识库覆盖范围：提问之前就告诉用户边界，而不是答完再免责 ---- */
    (async () => {
      const hint = container.querySelector("#chat-kb-hint");
      if (!hint) return;
      try {
        const r = await apiGet("/api/knowledge/coverage");
        if (!r.ok || !r.data || !r.data.count) return;
        const d = r.data;
        // 三档分开说：只有把「精编攻略 / 景点导览 / 景点清单」分清楚，用户才知道
        // 门票、开放时间这类信息在哪些城市是攻略库给的、哪些是模型自己补的。
        // 不要在这里列出全部城市名（355 个会把提示条撑成一堵墙）。
        hint.innerHTML = `📚 攻略库覆盖 <strong>${d.count} 城</strong>：`
          + `<strong>${d.full_count} 城</strong>有精编攻略（${escapeHtml(d.full_cities.join(" · "))}），`
          + `${d.guided_count || 0} 城有景点导览（含介绍与部分门票），`
          + `其余 ${d.list_count} 城为景点清单（只有景点名与类型，不含门票与开放时间）`;
      } catch (e) { /* 提示拉取失败不影响聊天 */ }
    })();

    /* ---- 会话列表 ---- */
    function renderSessions() {
      const list = loadSessions(user.username);
      if (!list.length) {
        sessEl.innerHTML = `<div class="cs-empty">暂无历史会话</div>`;
        return;
      }
      sessEl.innerHTML = list.map(s => `
        <div class="cs-session${s.id === sessionId ? " on" : ""}" data-id="${escapeHtml(s.id)}">
          <span class="cs-s-title">${escapeHtml(s.title || "新对话")}</span>
          <span class="cs-s-meta">${s.message_count || 0}</span>
        </div>`).join("");
      sessEl.querySelectorAll(".cs-session").forEach(n =>
        n.addEventListener("click", () => openSession(n.dataset.id)));
    }

    function upsertSession(id, title, count) {
      if (!id) return;
      const list = loadSessions(user.username).filter(s => s.id !== id);
      list.unshift({ id, title: (title || "新对话").slice(0, 40), message_count: count, updated_at: Date.now() / 1000 });
      saveSessions(user.username, list);
      renderSessions();
    }

    async function syncSessions() {
      try {
        const r = await apiGet("/api/chat/sessions");
        if (!r.ok) return;
        const local = loadSessions(user.username);
        const map = {};
        (r.data || []).forEach(s => { map[s.id] = { id: s.id, title: s.title, message_count: s.message_count, updated_at: s.updated_at }; });
        local.forEach(s => { if (!map[s.id]) map[s.id] = s; });
        const merged = Object.values(map).sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
        saveSessions(user.username, merged);
        renderSessions();
      } catch (e) {}
    }

    async function openSession(id) {
      const r = await apiGet("/api/chat/history/" + encodeURIComponent(id));
      if (!r.ok) { toast("会话不存在或无权访问"); return; }
      sessionId = id;
      assistantCount = 0;
      msgs.innerHTML = "";
      (r.data.messages || []).forEach(m => {
        if (m.role === "user") addUserMsg(m.content);
        else { assistantCount++; addBotMsg(m.content, assistantCount); }
      });
      if (!msgs.children.length) greet();
      renderSessions();
      scrollDown();
    }

    /* ---- 消息渲染 ---- */
    function greet() {
      msgs.insertAdjacentHTML("beforeend",
        `<div class="msg bot"><div class="bubble">你好，${escapeHtml(user.username)}！想去哪儿？告诉我你的目的地、天数和偏好，我来帮你规划。</div></div>`);
    }

    function addUserMsg(text) {
      msgs.insertAdjacentHTML("beforeend", `<div class="msg user"><div class="bubble">${escapeHtml(text)}</div></div>`);
      scrollDown();
    }

    function addBotMsg(content, idx) {
      const el = document.createElement("div");
      el.className = "msg bot";
      el.innerHTML = `<div class="bubble"><div class="answer-body"></div></div>`;
      el.querySelector(".answer-body").innerHTML = renderMarkdown(content);
      msgs.appendChild(el);
      attachActions(el.querySelector(".bubble"), content, idx);
      scrollDown();
      return el;
    }

    // msgIndex 必须在「渲染这条消息时」就固定下来。
    // 之前是在点击回调里读外层的 assistantCount，用户给第 1 条点赞时如果已经聊了 3 轮，
    // 上报的 message_index 就变成 3，反馈记到了别的回答上。
    function attachActions(bubbleEl, content, msgIndex) {
      const bar = document.createElement("div");
      bar.className = "msg-actions";
      bar.innerHTML = `
        <button class="act" data-act="fav" title="收藏到我的收藏">⭐ 收藏</button>
        <button class="act" data-act="like" title="有帮助">👍</button>
        <button class="act" data-act="dislike" title="没帮助">👎</button>
        <button class="act" data-act="copy" title="复制全文">📋</button>
        <button class="act" data-act="export" title="导出 Markdown">📥 导出</button>`;
      bubbleEl.appendChild(bar);

      bar.addEventListener("click", async (e) => {
        const btn = e.target.closest(".act");
        if (!btn) return;
        const act = btn.dataset.act;
        if (act === "copy") {
          try { await navigator.clipboard.writeText(content); toast("已复制全文"); }
          catch (err) { toast("复制失败，请手动选择"); }
        } else if (act === "export") {
          downloadText(`旅行攻略-${Date.now()}.md`, content);
          toast("已导出 Markdown");
        } else if (act === "fav") {
          const r = await apiPost("/api/favorites", { title: content.slice(0, 40), content, session_id: sessionId });
          toast(r.ok ? "已收藏，可在「我的收藏」查看" : (r.data.detail || "收藏失败"));
        } else if (act === "like" || act === "dislike") {
          if (!sessionId) { toast("会话尚未建立，请先完成一次问答"); return; }
          const r = await apiPost("/api/chat/feedback", {
            session_id: sessionId, message_index: msgIndex, rating: act,
          });
          if (r.ok) { toast(act === "like" ? "感谢点赞 👍" : "已记录反馈 👎"); btn.classList.add("on"); }
          else toast(r.data.detail || "反馈失败");
        }
      });
    }

    /* ---- 发送 ---- */
    async function send() {
      const text = input.value.trim();
      if (!text || busy) return;
      busy = true;
      sendBtn.disabled = true;
      input.value = "";
      addUserMsg(text);

      const botId = "bot-" + Date.now();
      msgs.insertAdjacentHTML("beforeend", `
        <div class="msg bot" id="${botId}">
          <div class="bubble">
            <div class="trace-panel" data-role="trace"></div>
            <div class="answer-body" data-role="answer"><span class="typing-dots">正在调度顾问团队…</span></div>
          </div>
        </div>`);
      scrollDown();

      const botEl = document.getElementById(botId);
      const traceEl = botEl.querySelector('[data-role="trace"]');
      const ansEl = botEl.querySelector('[data-role="answer"]');

      let answer = "";
      let cov = null;
      let streamDone = false;
      let typerDone = false;
      let actionsAttached = false;
      let typer = null;
      const thinkParts = [];

      // 等待空窗计时：reasoner 多代理链路实测 65s，其中前 10-15s 只有
      // 「正在调度顾问团队…」一行 —— 是放弃高发窗口（ux-report P2#6）。
      // 让秒数与阶段预期走上去，等待从「卡住了吗」变成「进行到哪了」；
      // 首个轨迹/正文/完成信号出现即停，不与后续渲染竞争。
      const waitStart = Date.now();
      const waitTimer = setInterval(() => {
        const dots = ansEl.querySelector(".typing-dots");
        if (!dots || steps.length || answer || streamDone) {
          clearInterval(waitTimer);
          return;
        }
        dots.textContent = `正在调度顾问团队…（已思考 ${Math.round((Date.now() - waitStart) / 1000)}s · 检索攻略库 → 顾问思考中 → 汇总回答）`;
      }, 1000);

      function renderTrace() {
        if (!steps.length && !thinkParts.length) return;
        const stepsHtml = steps.map((s, i) => `
          <div class="trace-step${s.done ? " done" : ""}${s.failed ? " failed" : ""}">
            <span class="ts-idx">${s.failed ? "!" : i + 1}</span>
            <span class="ts-name">${escapeHtml(agentLabel(s.agent))}</span>
            ${s.reason ? `<span class="ts-reason">${escapeHtml(s.reason)}</span>` : ""}
          </div>`).join("");
        const thinkHtml = thinkParts.length ? `
          <details class="think-panel">
            <summary>🧠 思考过程（${thinkParts.length} 位顾问）</summary>
            <div class="think-body">${thinkParts.map(p =>
              `<div class="think-item"><div class="think-who">${escapeHtml(agentLabel(p.agent))}${p.seconds ? ` · ${p.seconds}s` : ""}</div><pre>${escapeHtml(p.content)}</pre></div>`).join("")}</div>
          </details>` : "";
        traceEl.innerHTML = `<div class="trace-title">🧭 协作轨迹</div>${stepsHtml}${thinkHtml}`;
      }

      const steps = [];
      // 后端在 done 事件里给了 elapsed_ms / agent_calls，但一直没人用 ——
      // 用户看不到「这条回答花了多久、几个专家参与」，答辩时也没法讲性能。
      // 耗时放 title 里（悬停可见）而不是直接铺在脸上：慢查询不该被当成卖点，
      // 但也不该藏起来。
      let stats = null;

      function renderStats() {
        if (!stats || !stats.calls) return;
        const secs = (stats.elapsed / 1000).toFixed(1);
        const el = document.createElement("div");
        el.className = "chat-stats";
        el.title = `本次耗时 ${secs} 秒`;
        el.innerHTML = `🧭 ${stats.calls} 位顾问协作 · ${steps.length} 步推理`;
        botEl.querySelector(".bubble").appendChild(el);
      }

      // 后端在回答正文里已按提示词标注「通用建议」，这里再在气泡底部补一条
      // 结构化提示：正文可能被汇总阶段压缩，提示条不会。
      //
      // 三档分开说。以前只有「有攻略 / 没攻略」，现在 165 城有景点导览、184 城只有
      // 景点清单 —— 把它们都标成「暂无攻略库」是错的（用户会以为景点名是编的），
      // 标成「有攻略」更错（用户会以为门票价来自精编攻略库）。所以要说清是哪一档。
      function renderCoverageTip() {
        if (!cov) return;
        const guided = cov.guided || [];
        const listed = cov.listed || [];
        const uncovered = cov.uncovered || [];
        if (!guided.length && !listed.length && !uncovered.length) return;
        const bits = [];
        if (guided.length) {
          bits.push(`<strong>${escapeHtml(guided.join("、"))}</strong> 为景点导览档（景点介绍 + 部分门票），`
            + "数据来自维基导游与地图，可能已过时，请以景区公告为准");
        }
        if (listed.length) {
          bits.push(`<strong>${escapeHtml(listed.join("、"))}</strong> 仅有景点清单（景点名与类型），`
            + "门票、开放时间、交通耗时未经攻略库校验");
        }
        if (uncovered.length) {
          bits.push(`<strong>${escapeHtml(uncovered.join("、"))}</strong> 暂无本地攻略库，相关部分为通用建议`);
        }
        const tip = document.createElement("div");
        tip.className = "coverage-tip";
        tip.innerHTML = `📍 ${bits.join("；")}。`;
        botEl.querySelector(".bubble").appendChild(tip);
      }

      function tryFinish() {
        if (!streamDone || !typerDone || actionsAttached) return;
        actionsAttached = true;
        renderCoverageTip();
        renderStats();
        assistantCount++;
        attachActions(botEl.querySelector(".bubble"), answer, assistantCount);
        if (answer) upsertSession(sessionId, text, assistantCount * 2);
      }

      function handle(ev) {
        if (ev.type === "session") {
          sessionId = ev.session_id || sessionId;
        } else if (ev.type === "coverage") {
          cov = ev;
        } else if (ev.type === "route") {
          steps.push({ agent: ev.agent, reason: ev.reason || "", done: false });
          renderTrace();
        } else if (ev.type === "agent_failed") {
          // 专家级降级：后端会继续汇总其余专家，但界面必须明确标出这一位没跑通。
          // 此前这个事件完全没被处理，失败专家在轨迹里还会被标成「已完成」，属于误导。
          const s = steps.find(x => x.agent === ev.agent && !x.done);
          if (s) { s.failed = true; s.reason = "执行失败，已跳过"; }
          else steps.push({ agent: ev.agent, reason: "执行失败，已跳过", done: false, failed: true });
          renderTrace();
        } else if (ev.type === "agent_done") {
          const s = steps.find(x => x.agent === ev.agent && !x.done);
          if (s) s.done = true;
          else steps.push({ agent: ev.agent, reason: "", done: true });
          renderTrace();
        } else if (ev.type === "agent_thinking") {
          thinkParts.push({ agent: ev.agent, content: ev.content, seconds: ev.seconds });
          renderTrace();
        } else if (ev.type === "answer") {
          answer = ev.content || "";
          if (ev.thinking) thinkParts.push({ agent: "final", content: ev.thinking, seconds: ev.thinking_seconds || 0 });
          renderTrace();
          if (answer) {
            typer = typewrite(ansEl, answer, { onTick: scrollDown, onDone: () => { typerDone = true; tryFinish(); } });
          } else { typerDone = true; }
        } else if (ev.type === "error") {
          ansEl.innerHTML = `<span class="err">⚠️ ${escapeHtml(ev.message || "服务异常")}</span>`;
          typerDone = true;
        } else if (ev.type === "done") {
          sessionId = ev.session_id || sessionId;
          stats = { elapsed: ev.elapsed_ms || 0, calls: ev.agent_calls || 0 };
          streamDone = true;
          if (!answer) {
            ansEl.innerHTML = ev.error
              ? `<span class="err">⚠️ ${escapeHtml(ev.error)}</span>`
              : `<span class="muted">（本次没有生成回答，请重试）</span>`;
            typerDone = true;
          }
          tryFinish();
        }
      }

      try {
        const r = await fetch(API_BASE + "/api/chat/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth-Token": (localStorage.getItem(TOKEN_KEY) || ""),
          },
          body: JSON.stringify({ message: text, session_id: sessionId || undefined }),
        });
        if (!r.ok || !r.body) {
          let detail = "服务返回 " + r.status;
          try { const j = await r.json(); detail = j.detail || detail; } catch (e) {}
          throw new Error(detail);
        }
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop();
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            let ev;
            try { ev = JSON.parse(line.slice(6)); } catch (e) { continue; }
            handle(ev);
          }
        }
        // 兜底：流结束但没收到 done
        if (!streamDone) {
          streamDone = true;
          if (typer) { /* 等待打字机 */ }
          else { ansEl.innerHTML = answer ? renderMarkdown(answer) : `<span class="err">⚠️ 连接中断，请重试</span>`; typerDone = true; }
          tryFinish();
        }
      } catch (e) {
        if (typer) typer();
        // 这里是唯一会把浏览器原话漏给用户的地方（断网时 e.message = "Failed to fetch"）
        ansEl.innerHTML = `<span class="err">⚠️ ${escapeHtml(netErrText(e))}</span>`;
        typerDone = true;
        streamDone = true;
        tryFinish();
        // 原地重试：问题填回输入框、删掉空气泡、走同一条 send()。
        // 不自动重试——真断网会连打三次，用户看到三个失败气泡还以为是自己点多了。
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn btn-ghost err-retry";
        retry.textContent = "重试";
        retry.addEventListener("click", () => {
          botEl.remove();
          input.value = text;
          send();
        });
        botEl.querySelector(".bubble").appendChild(retry);
      } finally {
        busy = false;
        sendBtn.disabled = false;
        input.focus();
        scrollDown();
      }
    }

    container.querySelector("#chat-new").addEventListener("click", () => {
      sessionId = "";
      assistantCount = 0;
      msgs.innerHTML = "";
      greet();
      renderSessions();
      input.focus();
    });
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) send(); });

    greet();
    renderSessions();
    syncSessions();
  }

  /* ---------- 地图页 ---------- */
  function initMapPage() {
    const container = document.getElementById("map-app");
    if (!container) return;
    container.innerHTML = `
      <div class="app-panel">
        <div class="app-toolbar">
          <select id="map-city" class="app-select">${cityOptionsHtml()}</select>
          <input id="map-query" class="app-input" type="text" placeholder="可选：输入需求，如「喜欢历史古迹 3 天」" />
          <button id="map-go" class="btn btn-accent">筛选</button>
        </div>
        <div class="app-split">
          <div class="app-map" id="amap-wrap"></div>
          <div class="app-list" id="spot-list"></div>
        </div>
      </div>`;
    const citySel = container.querySelector("#map-city");
    const queryIn = container.querySelector("#map-query");
    const goBtn = container.querySelector("#map-go");
    const wrap = container.querySelector("#amap-wrap");
    const list = container.querySelector("#spot-list");
    citySel.value = "北京";

    let curCity = "北京";   // 当前渲染的城市（事件委托里要用）

    // 地图按需加载：高德 SDK 约 1MB，解析 + WebGL 初始化会全部记在首屏 TBT 上
    // （见 deliverables/gstack/map-tbt-options.md）。所以首屏只渲染占位与列表，
    // 用户点了「显示地图」才创建 iframe。注意：延迟到 load/idle **没用** ——
    // TBT 统计的是 FCP→TTI 之间的长任务，挪到 load 之后仍然落在窗口内。
    let mapReady = false;
    let lastCity = "北京", lastSpots = [];

    function showMapPlaceholder() {
      wrap.innerHTML = `
        <div style="height:560px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;background:var(--paper-3);border:2px dashed var(--line);border-radius:16px;padding:24px;text-align:center">
          <div style="font-size:2rem" aria-hidden="true">🗺️</div>
          <div style="font-weight: var(--fw-strong)">地图按需加载</div>
          <p style="margin:0;max-width:32em;color:var(--muted);font-size:var(--fs-md);line-height:1.7">
            为了让你更快打开页面，地图不在首屏加载。点击后开始加载（首次约 1–2 秒），
            右侧景点列表已经可以正常使用。
          </p>
          <button type="button" id="map-load" class="btn btn-accent" style="min-height:48px;min-width:160px">显示地图</button>
        </div>`;
      wrap.querySelector("#map-load").addEventListener("click", loadMapNow);
    }

    function loadMapNow() {
      mapReady = true;
      wrap.innerHTML = '<div style="height:560px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-weight: var(--fw-strong)">地图加载中…</div>';
      renderAmapCity("amap-wrap", lastCity, { center: window.CITY_GEO[lastCity].center, spots: lastSpots });
    }

    function render(city, spots, matched) {
      wrap.style.height = "560px";
      lastCity = city;
      lastSpots = spots;
      if (mapReady) {
        renderAmapCity("amap-wrap", city, { center: window.CITY_GEO[city].center, spots: spots });
      } else {
        showMapPlaceholder();
      }
      const ov = citySpotOv(city);
      const addedNames = new Set((ov.added || []).map((a) => a && a.n));
      const custom = hasSpotOv(city);
      // 有筛选条件时 spots 是「挑出来的子集」，直接写个数会让人以为景点变少了
      const total = effectiveSpots(city).length;
      const headTitle = matched
        ? `${escapeHtml(city)} · 共 ${total} 个景点，筛选出 ${spots.length} 个`
        : `${escapeHtml(city)} · ${spots.length} 个景点`;
      list.innerHTML =
        `<div class="spot-head">
           <h3>${headTitle}${custom ? ' <span class="spot-badge">已自定义</span>' : ""}</h3>
           <div class="spot-acts">
             <button type="button" class="spot-btn" data-act="add">＋ 添加</button>
             ${custom ? '<button type="button" class="spot-btn" data-act="reset">↺ 恢复默认</button>' : ""}
           </div>
         </div>
         <div class="spot-form" id="spot-form" hidden>
           <input id="sf-name" class="app-input" type="text" maxlength="20" placeholder="景点名称，如「亮马河」" />
           <select id="sf-cat" class="app-select">${SPOT_CATS.map((c) => `<option>${c}</option>`).join("")}</select>
           <input id="sf-lat" class="app-input" type="text" placeholder="纬度，可留空" />
           <input id="sf-lng" class="app-input" type="text" placeholder="经度，可留空" />
           <div class="spot-form-acts">
             <button type="button" class="btn btn-accent" data-act="save">保存</button>
             <button type="button" class="spot-btn" data-act="cancel">取消</button>
           </div>
           <div class="spot-err" id="sf-err"></div>
         </div>` +
        (spots.length
          ? spots.map((s, i) => {
              const flag = matched ? (matched.has(s[0]) ? "✅" : "○") : "";
              const badge = addedNames.has(s[0]) ? ' <span class="spot-badge">自定义</span>' : "";
              return `<div class="spot-item">
                  <span class="spot-no">${i + 1}.</span>
                  <span class="spot-txt">${flag ? flag + " " : ""}<strong>${escapeHtml(s[0])}</strong> · ${escapeHtml(s[3])}${badge}</span>
                  <button type="button" class="spot-del" data-del="${escapeHtml(s[0])}" title="删除该景点" aria-label="删除 ${escapeHtml(s[0])}">🗑</button>
                </div>`;
            }).join("")
          : `<div class="spot-empty">该城市的景点被删空了，点「↺ 恢复默认」可以还原。</div>`);
    }

    function showForm(show) {
      const f = list.querySelector("#spot-form");
      if (!f) return;
      f.hidden = !show;
      if (show) {
        const n = f.querySelector("#sf-name");
        if (n) n.focus();
      } else {
        ["#sf-name", "#sf-lat", "#sf-lng"].forEach((sel) => {
          const el = f.querySelector(sel);
          if (el) el.value = "";
        });
        const e = f.querySelector("#sf-err");
        if (e) e.textContent = "";
      }
    }

    function saveForm() {
      const g = (sel) => { const el = list.querySelector(sel); return el ? el.value.trim() : ""; };
      const errEl = list.querySelector("#sf-err");
      const name = g("#sf-name");
      const cat = g("#sf-cat");
      const latRaw = g("#sf-lat");
      const lngRaw = g("#sf-lng");
      const fail = (msg) => { if (errEl) errEl.textContent = msg; };

      if (!name) return fail("请填写景点名称");
      if (effectiveSpots(curCity).some((s) => s[0] === name)) return fail("「" + name + "」已存在，换个名字吧");

      const center = (window.CITY_GEO[curCity] || {}).center || [35, 105];
      let lat = latRaw === "" ? NaN : parseFloat(latRaw);
      let lng = lngRaw === "" ? NaN : parseFloat(lngRaw);
      if (latRaw !== "" && !isFinite(lat)) return fail("纬度不是有效数字");
      if (lngRaw !== "" && !isFinite(lng)) return fail("经度不是有效数字");
      // 留空时在城市中心附近随机落点，避免多个自定义点完全重叠
      if (!isFinite(lat)) lat = center[0] + (Math.random() - 0.5) * 0.03;
      if (!isFinite(lng)) lng = center[1] + (Math.random() - 0.5) * 0.03;
      if (lat < 3 || lat > 54 || lng < 73 || lng > 136) {
        return fail("经纬度超出中国范围（纬度 3~54，经度 73~136）");
      }
      addSpotOv(curCity, name, lat, lng, cat);
      refresh();
    }

    // 事件委托：列表每次重绘，逐个绑监听会漏
    list.addEventListener("click", (e) => {
      const del = e.target.closest("[data-del]");
      if (del) {
        const name = del.getAttribute("data-del");
        if (window.confirm("确定删除「" + name + "」？")) {
          removeSpotOv(curCity, name);
          refresh();
        }
        return;
      }
      const act = e.target.closest("[data-act]");
      if (!act) return;
      const a = act.getAttribute("data-act");
      if (a === "add") showForm(true);
      else if (a === "cancel") showForm(false);
      else if (a === "save") saveForm();
      else if (a === "reset") {
        if (window.confirm("恢复「" + curCity + "」的默认景点列表？你添加和删除的都会清掉。")) {
          resetSpotOv(curCity);
          refresh();
        }
      }
    });
    list.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (!e.target.closest("#spot-form")) return;
      e.preventDefault();
      saveForm();
    });

    function refresh() {
      let city = citySel.value;
      if (!window.CITY_GEO[city]) city = Object.keys(window.CITY_GEO)[0];
      let spots = effectiveSpots(city);
      let matched = null;
      const q = queryIn.value.trim();
      if (q) {
        const p = parseTravelQuery(q);
        if (p.city) {
          city = p.city;
          citySel.value = city;
          spots = effectiveSpots(city);
          const res = pickSpots({ spots: spots }, p.cats, p.days, p.must);
          spots = res.picked;
          matched = res.matched;
        }
      }
      curCity = city;
      render(city, spots, matched);
    }
    citySel.addEventListener("change", refresh);
    goBtn.addEventListener("click", refresh);
    refresh();
  }

  /* ---------- 交通页 ---------- */
  function initTransitPage() {
    const container = document.getElementById("transit-app");
    if (!container) return;
    const options = cityOptionsHtml();
    container.innerHTML = `
      <div class="app-panel">
        <div class="app-toolbar">
          <select id="tr-from" class="app-select">${options}</select>
          <span style="font-weight: var(--fw-strong)">→</span>
          <select id="tr-to" class="app-select">${options}</select>
          <button id="tr-go" class="btn btn-accent">规划路线</button>
        </div>
        <div class="app-bar" id="tr-bar"></div>
        <div class="app-map" id="tr-map" style="height:540px"></div>
      </div>`;
    const fromSel = container.querySelector("#tr-from");
    const toSel = container.querySelector("#tr-to");
    const goBtn = container.querySelector("#tr-go");
    const bar = container.querySelector("#tr-bar");
    const mapEl = container.querySelector("#tr-map");
    fromSel.value = "北京";
    toSel.value = "上海";
    // 规划代号：连点「规划路线」或快速切换城市时，前一次的回调不能再覆盖后一次的结果
    let gen = 0;
    function refresh() {
      const fc = fromSel.value, tc = toSel.value;
      const my = ++gen;
      if (fc === tc) {
        bar.textContent = "出发与到达城市不能相同";
        if (mapEl) mapEl.innerHTML = "";   // 别把上一次的城市路线留在画面上
        return;
      }
      bar.innerHTML = `<div style="background:#fff9e0;border:2px solid #2b2b2b;border-radius:12px;padding:10px 14px;font-weight: var(--fw-strong);color:#2b1d0e;box-shadow:3px 3px 0 rgba(43,43,43,.55);display:inline-block">📍 ${escapeHtml(fc)} → ${escapeHtml(tc)} · 正在规划…</div>`;
      renderAmapRoute("tr-map", fc, tc);
      setTimeout(() => {
        if (my !== gen) return;   // 已经有更新的规划在跑，丢弃本次
        const [fLat, fLng] = window.CITY_GEO[fc].center;
        const [tLat, tLng] = window.CITY_GEO[tc].center;
        const R = 6371, p1 = fLat*Math.PI/180, p2 = tLat*Math.PI/180, dp=(tLat-fLat)*Math.PI/180, dl=(tLng-fLng)*Math.PI/180;
        const a = Math.sin(dp/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
        const dist = 2*R*Math.asin(Math.sqrt(a));
        let tip = dist < 150 ? "🚗 距离较近，推荐自驾或城际高铁" : dist < 800 ? "🚄 推荐高铁出行，快捷舒适" : dist < 1500 ? "🚄✈️ 高铁与飞机均可" : "✈️ 距离较远，推荐乘坐飞机";
        bar.innerHTML = `<div style="background:#fff9e0;border:2px solid #2b2b2b;border-radius:12px;padding:10px 14px;font-weight: var(--fw-strong);color:#2b1d0e;box-shadow:3px 3px 0 rgba(43,43,43,.55);display:inline-block">📍 ${escapeHtml(fc)} → ${escapeHtml(tc)} · 直线约 ${dist.toFixed(0)} 公里 · ${tip}</div>`;
      }, 1200);
    }
    goBtn.addEventListener("click", refresh);
    // 出发城市变了：若和到达城市撞车，自动换一个，避免直接落到「不能相同」的报错上
    fromSel.addEventListener("change", () => {
      if (fromSel.value === toSel.value) {
        const alt = Object.keys(window.CITY_GEO).find((c) => c !== fromSel.value);
        if (alt) toSel.value = alt;
      }
      refresh();
    });
    toSel.addEventListener("change", refresh);
    refresh();
  }

  /* ---------- 收藏页 ---------- */
  async function initFavoritesPage() {
    const container = document.getElementById("favorites-app");
    if (!container) return;
    const user = authState();
    if (!user) { container.innerHTML = `<div class="app-gate"><h2>请先登录</h2><p>登录后查看收藏</p><a href="index.html#login" class="btn btn-primary">去登录 <span class="fill"></span></a></div>`; return; }
    container.innerHTML = `<div class="app-panel" id="fav-list"><div class="skeleton" style="height:120px"></div></div>`;
    const r = await apiGet("/api/favorites");
    if (!r.ok) {
      // 不能把「接口失败」和「没有收藏」混为一谈，否则用户以为收藏丢了
      container.innerHTML = `<div class="app-panel app-empty">
        <div style="font-size:52px">⚠️</div>
        <h3>收藏加载失败</h3>
        <p>${escapeHtml((r.data && r.data.detail) || "登录可能已过期，请重新登录后再试")}</p>
        <button class="btn btn-primary" id="fav-retry">重新加载</button>
      </div>`;
      const btn = container.querySelector("#fav-retry");
      if (btn) btn.addEventListener("click", () => initFavoritesPage());
      return;
    }
    const items = (r.data || {}).favorites || [];
    if (!items.length) {
      container.innerHTML = `<div class="app-panel app-empty"><div style="font-size:52px">⭐</div><h3>收藏夹还是空的</h3><p>在 AI 对话中点击「⭐ 收藏」即可把攻略保存到这里</p></div>`;
      return;
    }
    container.innerHTML = `<div class="app-panel"><h3 style="margin-bottom:16px">我的收藏 (${items.length})</h3><div class="fav-grid">${items.map(it => `
      <div class="fav-card">
        <div class="fav-title">${escapeHtml(it.title || "未命名收藏")}</div>
        <div class="fav-body">${renderMarkdown((it.content || "").slice(0, 400))}</div>
        <div class="fav-actions">
          <button class="btn btn-ghost exp-fav" data-id="${escapeHtml(it.id)}">📥 导出</button>
          <button class="btn btn-primary del-fav" data-id="${escapeHtml(it.id)}">🗑️ 删除</button>
        </div>
      </div>`).join("")}</div></div>`;
    const byId = {};
    items.forEach(it => { byId[it.id] = it; });
    container.querySelectorAll(".exp-fav").forEach(b => b.addEventListener("click", (e) => {
      const it = byId[e.currentTarget.dataset.id];
      if (!it) return;
      downloadText(`${(it.title || "旅行攻略").replace(/[\\/:*?"<>|]/g, "_")}.md`, it.content || "");
      toast("已导出 Markdown");
    }));
    container.querySelectorAll(".del-fav").forEach(b => b.addEventListener("click", async (e) => {
      const id = e.currentTarget.dataset.id;
      const r = await api("DELETE", "/api/favorites/" + encodeURIComponent(id));
      if (!r.ok) { toast(r.data.detail || "删除失败"); return; }
      initFavoritesPage();
    }));
  }

  /* ---------- 行程工作台 ---------- */
  // 与收藏夹的分工：收藏是「把一段文字存起来」，行程是「把一次旅行排好并跟踪进度」。
  // 所以这里所有写操作都按条目粒度做（勾一条、加一条），不整篇覆盖 ——
  // 整篇覆盖会让用户勾了半天的进度在改一个字之后全部归零。
  const tripsView = { list: [], current: null };

  const TRIP_KIND_ICON = {
    spot: "🏛", food: "🍜", stay: "🛏", transit: "🚇", experience: "🎭", packing: "🎒", doc: "📄",
  };

  function tripPhaseText(t) {
    if (t.phase === "undated") return "日期待定";
    if (t.phase === "ongoing") return "旅行进行中";
    if (t.phase === "past") return "已完成";
    if (t.countdown === 0) return "今天出发";
    return `还有 ${t.countdown} 天出发`;
  }

  function tripProgressBar(progress, big) {
    const pct = progress ? progress.percent : 0;
    return `<div class="trip-bar${big ? " trip-bar--big" : ""}"><i style="width:${pct}%"></i></div>`;
  }

  async function initTripsPage() {
    const container = document.getElementById("trips-app");
    if (!container) return;
    const user = authState();
    if (!user) {
      container.innerHTML = `<div class="app-gate"><h2>请先登录</h2><p>登录后即可创建并管理你的行程</p><a href="index.html#login" class="btn btn-primary">去登录 <span class="fill"></span></a></div>`;
      return;
    }
    tripsView.el = container;
    if (tripsView.current) renderTripDetail(tripsView.current);
    else await renderTripList();
  }

  function tripNewFormHtml() {
    const cities = Object.keys(window.CITY_GEO || {}).sort();
    return `
      <div class="app-panel trip-new">
        <div class="trip-new-row">
          <input id="trip-city" list="trip-city-list" placeholder="目的地，如 北京" autocomplete="off" />
          <datalist id="trip-city-list">${cities.map(c => `<option value="${escapeHtml(c)}"></option>`).join("")}</datalist>
          <input id="trip-date" type="date" title="出发日期（可留空）" />
          <input id="trip-days" type="number" min="1" max="30" value="3" title="天数" />
          <input id="trip-budget" type="number" min="0" step="100" placeholder="人均预算(元)" />
          <button class="btn btn-accent" id="trip-create">创建行程</button>
        </div>
        <div class="trip-new-hint">创建后可一键生成每日安排与行前装备清单，逐项打勾跟踪进度。</div>
      </div>`;
  }

  async function renderTripList() {
    const el = tripsView.el;
    el.innerHTML = `${tripNewFormHtml()}<div class="app-panel" id="trip-list"><div class="skeleton" style="height:100px"></div></div>`;

    el.querySelector("#trip-create").addEventListener("click", createTripFromForm);
    el.querySelector("#trip-city").addEventListener("keydown", (e) => {
      if (e.key === "Enter") createTripFromForm();
    });

    const r = await apiGet("/api/trips");
    const box = el.querySelector("#trip-list");
    if (!r.ok) {
      // 只有文案的失败态等于把用户逼去刷整页：同一站里 chat 与 favorites 都给了
      // 「重新加载」，行程页没有，凭什么是它最难受。这里就地重试，重走的还是
      // renderTripList() —— 本页唯一的列表入口，创建表单与它的监听都在里面重挂，
      // 不新造一套请求逻辑。按钮样式与 favorites 的「重新加载」完全一致
      // （.app-empty 里的 .btn.btn-primary），手机端由 .btn{min-height:44px} 兜住。
      box.innerHTML = `<div class="app-empty">
        <div style="font-size:52px">⚠️</div>
        <h3>行程加载失败</h3>
        <p>${escapeHtml((r.data && r.data.detail) || "登录可能已过期")}</p>
        <button class="btn btn-primary" id="trip-retry">重新加载</button>
      </div>`;
      const retryBtn = box.querySelector("#trip-retry");
      if (retryBtn) retryBtn.addEventListener("click", () => {
        // 先把按钮锁住：弱网下一次点击要等 3~5 秒才见结果，不反馈会连点三次
        retryBtn.disabled = true;
        retryBtn.textContent = "加载中…";
        renderTripList();
      });
      return;
    }
    const list = (r.data || {}).trips || [];
    tripsView.list = list;
    if (!list.length) {
      // 空白页对第一次来的人（和答辩现场自己点开链接的老师）最不友好：
      // 他不知道「填目的地」之后会看到什么。给一个**确定性**的入口 ——
      // 后端用本地地图数据建一份，不调 AI，秒出，网络抖动也不影响。
      box.innerHTML = `<div class="app-empty">
        <div style="font-size:52px">🧳</div>
        <h3>还没有行程</h3>
        <p>在上面填一个目的地，就能开始排你的旅行</p>
        <button class="btn btn-ghost" id="trip-sample">先看一份示例（北京 3 天）</button>
        <p class="trip-sample-note">用本地景点数据生成，可随时删除</p>
      </div>`;
      const sampleBtn = box.querySelector("#trip-sample");
      if (sampleBtn) sampleBtn.addEventListener("click", () => loadSampleTrip(sampleBtn));
      return;
    }
    box.innerHTML = `<div class="trip-grid">${list.map(t => `
      <article class="trip-card" data-id="${escapeHtml(t.id)}">
        <div class="trip-card-top">
          <h3>${escapeHtml(t.city)}</h3>
          <span class="trip-chip">${t.days} 天</span>
        </div>
        <div class="trip-cd${t.phase === "undated" ? " is-empty" : ""}">${escapeHtml(tripPhaseText(t))}</div>
        <div class="trip-meta">${escapeHtml(t.start_date || "日期待定")}${t.budget ? ` · 预算 ¥${t.budget}` : ""}</div>
        ${tripProgressBar(t.progress)}
        <div class="trip-foot">已完成 ${t.progress.done}/${t.progress.total} 项</div>
      </article>`).join("")}</div>`;

    box.querySelectorAll(".trip-card").forEach(card => {
      card.addEventListener("click", () => openTrip(card.dataset.id));
    });
  }

  /**
   * 载入示例行程。
   *
   * 后端一次事务建完（行程 + 条目 + 花费），失败什么都不留，所以这里不用处理
   * 「建了一半」。请求期间禁用按钮：后端做了幂等（第二次直接返回同一份），
   * 但连点两下、按钮又没反应，用户会以为卡死了。
   */
  async function loadSampleTrip(btn) {
    const label = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.textContent = "正在生成…"; }
    const r = await apiPost("/api/trips/sample", { city: "北京" });
    if (!r.ok) {
      toast((r.data && r.data.detail) || "示例行程生成失败");
      if (btn) { btn.disabled = false; btn.textContent = label; }
      return;
    }
    toast(r.data.reused ? "已为你打开上次那份示例行程" : "示例行程已生成，可以随便改");
    await renderTripList();     // 先刷新列表：用户返回列表时能看到卡片，而不是空白
    openTrip(r.data.trip.id);   // 直接进详情，省掉一次点击
  }

  async function createTripFromForm() {
    const el = tripsView.el;
    const city = (el.querySelector("#trip-city").value || "").trim();
    if (!city) { toast("先填目的地"); return; }
    const days = parseInt(el.querySelector("#trip-days").value, 10) || 3;
    const budget = parseInt(el.querySelector("#trip-budget").value, 10) || 0;
    const start = el.querySelector("#trip-date").value || "";
    const r = await apiPost("/api/trips", { city, days, budget, start_date: start });
    if (!r.ok) { toast((r.data && r.data.detail) || "创建失败"); return; }
    toast("行程已创建");
    tripsView.current = r.data.trip;
    renderTripDetail(r.data.trip);
  }

  async function openTrip(id) {
    const r = await apiGet("/api/trips/" + encodeURIComponent(id));
    if (!r.ok) { toast((r.data && r.data.detail) || "行程不存在"); return; }
    tripsView.current = r.data.trip;
    renderTripDetail(r.data.trip);
  }

  function prepGroups(items) {
    const groups = [];
    const index = {};
    items.forEach(it => {
      const key = it.slot || "其他";
      if (!(key in index)) { index[key] = groups.length; groups.push({ name: key, items: [] }); }
      groups[index[key]].items.push(it);
    });
    return groups;
  }

  /* ---------- 行程地图：把每日条目对到景点库坐标 ---------- */

  // 条目名来自 AI 或用户手输，跟景点库不会字字相同（「故宫」vs「故宫博物院」、
  // 「天坛（需预约）」vs「天坛公园」）。先去掉括号备注与标点，再做「相等 → 包含」
  // 两轮匹配；包含匹配取名字最短的那个，避免「长城」命中名字更长的服务中心之类。
  function normSpotText(s) {
    return String(s == null ? "" : s)
      .replace(/[（(【\[][^)）】\]]*[)）】\]]/g, "")
      .replace(/[\s\u3000·・,，、。.!！?？:：;；'"“”‘’\-—–_/\\]/g, "");
  }

  function matchTripSpot(title, spots) {
    const t = normSpotText(title);
    if (t.length < 2) return null;          // 单字（「吃」「逛」）匹配出来的都是噪声
    const norm = spots.map(s => ({ row: s, key: normSpotText(s[0]) }));
    const exact = norm.find(x => x.key && x.key === t);
    if (exact) return exact.row;
    const cands = norm.filter(x => x.key && (x.key.includes(t) || t.includes(x.key)));
    if (!cands.length) return null;
    cands.sort((a, b) => a.key.length - b.key.length);
    return cands[0].row;
  }

  /**
   * 模板骨架条目 → 同类推荐景点。
   *
   * <p>模板只写「什么时候做什么类型的事」（老城区 / 城市地标、小吃街扫街…），刻意不含具体
   * 景点名 —— 于是按名字匹配必然 0 上图，行程地图对模板行程整个空转。这里按条目关键词映射到
   * 该市同分类的推荐景点（CITY_GEO 列表顺序即推荐顺序）；used 让不同条目拿到不同景点，
   * 避免全部塌到同一个点。抵达 / 返程 / 补漏这类本来就无地点的条目不强行匹配。
   */
  const SKELETON_RULES = [
    { re: /美食|小吃|夜市|晚餐|晚饭|馆子|餐厅|下午茶|甜品|早茶|扫街|菜市场/, cats: ["美食", "商圈"] },
    { re: /博物馆|科技馆|海洋馆|展览|展馆|演出|温泉|手作|室内馆/, cats: ["场馆", "体验"] },
    { re: /公园|动物园|亲子|乐园/, cats: ["公园", "亲子", "乐园"] },
    { re: /日出|日落|夜景|机位|蓝调|摄影|建筑群/, cats: ["地标", "自然", "街区"] },
    { re: /地标|老城|街区|核心景点|近郊|景点|名胜|古迹/, cats: ["地标", "古迹", "街区", "公园", "自然"] }
  ];
  const SKELETON_SKIP = /抵达|返程|寄存|入住|放下行李|补漏|收尾|特产|带走的/;
  function matchSkeletonEntry(it, spots, used) {
    const text = (it.title || "") + " " + (it.note || "");
    if (SKELETON_SKIP.test(text)) return null;
    // 级联：标题关键词规则 → 条目类型规则 → spot 类主打分类推荐序。
    // 前一档在当前城市没有可用景点（如北京没有「场馆」分类）时落到下一档，
    // 保证「套模板 → 看地图」主路径必上图；真正无地点的条目（抵达/返程/补漏）不匹配。
    const rules = [];
    const kw = SKELETON_RULES.find(r => r.re.test(text));
    if (kw) rules.push(kw);
    if (it.kind === "food") rules.push({ cats: ["美食", "商圈"] });
    if (it.kind === "experience") rules.push({ cats: ["场馆", "体验", "街区"] });
    if (it.kind === "spot") rules.push({ cats: ["地标", "古迹", "街区", "公园", "自然", "乐园"] });
    for (const rule of rules) {
      const hit = spots.find(s => !used.has(s[0]) && rule.cats.indexOf(s[3]) >= 0);
      if (hit) { used.add(hit[0]); return hit; }
    }
    return null;
  }

  /** 把一份行程算成「每天去哪几站」；对不上景点库的条目单独列出来，不静默丢弃。 */
  function tripMapPlan(t) {
    const city = t.city || "";
    const info = (window.CITY_GEO || {})[city];
    if (!info) return { ok: false, reason: `「${city || "未填城市"}」不在景点库里，暂时画不出地图` };
    const spots = effectiveSpots(city);
    const days = [];
    let total = 0;
    let located = 0;
    let fallback = 0;
    const used = new Set();
    const missing = [];
    (t.itinerary || []).forEach(d => {
      const stops = [];
      (d.items || []).forEach(it => {
        total += 1;
        let hit = matchTripSpot(it.title, spots);
        if (!hit) {
          hit = matchSkeletonEntry(it, spots, used);
          if (hit) fallback += 1;
        }
        if (hit) {
          stops.push({ name: hit[0], lng: hit[2], lat: hit[1], note: it.note || "" });
          located += 1;
        } else if (missing.indexOf(it.title) < 0) {
          missing.push(it.title);
        }
      });
      if (stops.length) days.push({ day: d.day, stops });
    });
    return { ok: true, city, center: info.center, days, total, located, missing, fallback };
  }

  function openTripMap(t) {
    const plan = tripMapPlan(t);
    const old = document.getElementById("trip-map-modal");
    if (old) old.remove();
    const box = document.createElement("div");
    box.id = "trip-map-modal";
    box.className = "modal open";
    const legend = plan.ok && plan.days.length
      ? plan.days.map((d, i) => `<span class="tmm-day"><i style="background:${TRIP_DAY_COLORS[i % TRIP_DAY_COLORS.length]}"></i>第 ${d.day} 天 · ${d.stops.length} 站</span>`).join("")
      : "";
    box.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-card modal-card--wide">
        <button class="modal-close" aria-label="关闭">&times;</button>
        <div class="tmm-head">
          <h3>🗺 ${escapeHtml(t.title)}</h3>
          <span class="trip-meta">${plan.ok ? `已上图 ${plan.located}/${plan.total} 项` : "无法上图"}</span>
        </div>
        ${plan.ok && plan.days.length
          ? `<div class="tmm-legend">${legend}</div>
             <div class="tmm-canvas" id="trip-map-canvas"></div>
             <p class="trip-hint tmm-foot">同一天按游玩顺序编号并连线，颜色区分天；点击标记看详情。</p>
             ${plan.fallback ? `<p class="trip-hint tmm-foot">其中 ${plan.fallback} 项是模板骨架，已按条目类型匹配同类推荐景点；想精确控制，把条目改成具体地点名即可。</p>` : ""}`
          : plan.ok
            ? `<p class="trip-hint">这份行程还没有能对上景点库的地点。可以点上方「✨ 生成每日行程」让 AI 排一版，或直接去景点库挑几个加进来：</p>
               <div style="margin:10px 0 4px"><a class="btn btn-primary" href="spots.html?city=${encodeURIComponent(plan.city)}">去景点库挑几个</a></div>`
            : `<p class="trip-hint">${escapeHtml(plan.reason)}</p>`}
        ${plan.ok && plan.missing.length
          ? `<details class="tmm-missing"><summary>${plan.missing.length} 项未上图（不是景点库里的具体地点）</summary>${plan.missing.map(escapeHtml).join("、")}</details>`
          : ""}
      </div>`;
    document.body.appendChild(box);
    const close = () => box.remove();
    box.querySelector(".modal-backdrop").addEventListener("click", close);
    box.querySelector(".modal-close").addEventListener("click", close);
    document.addEventListener("keydown", function onEsc(e) {
      if (e.key === "Escape") { close(); document.removeEventListener("keydown", onEsc); }
    });
    if (plan.ok && plan.days.length) renderAmapTripMap("trip-map-canvas", plan);
  }

  function itemRow(it) {
    const slot = (it.slot || "").trim();
    return `
      <label class="trip-item${it.done ? " done" : ""}" data-item-id="${it.id}" data-day="${it.day_index}">
        <input type="checkbox" class="trip-check" data-id="${it.id}"${it.done ? " checked" : ""} />
        ${slot ? `<span class="trip-item-slot" style="flex:none;font-size:var(--fs-xs);color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 7px">${escapeHtml(slot)}</span>` : ""}
        <span class="trip-item-title">${escapeHtml(it.title)}</span>
        ${it.note ? `<span class="trip-item-note">${escapeHtml(it.note)}</span>` : ""}
        <button type="button" class="trip-item-edit" data-id="${it.id}" title="编辑这一项" aria-label="编辑 ${escapeHtml(it.title)}" style="flex:none;background:none;border:0;cursor:pointer;font-size:var(--fs-md);line-height:1;padding:2px 6px;opacity:.6">✏️</button>
        <button type="button" class="trip-item-del" data-id="${it.id}" title="删除">×</button>
      </label>`;
  }

  /* ---------- 两个列表分区（拆出来才能「只重画这一块」） ---------- */

  function prepPanelHtml(t) {
    const prep = t.prep || [];
    const groups = prepGroups(prep);
    return `<div class="app-panel">
        <div class="trip-sec-head"><h3>行前清单</h3><span class="trip-meta">${prep.length} 项</span></div>
        ${groups.length ? groups.map(g => `
          <div class="trip-group">
            <div class="trip-group-name">${escapeHtml(g.name)}</div>
            ${g.items.map(itemRow).join("")}
          </div>`).join("") : `<div class="app-empty" style="padding:24px"><p>还没有清单，点上方「🎒 生成装备清单」自动生成</p></div>`}
        <div class="trip-add-row">
          <input class="trip-add-input" data-day="0" placeholder="手动添加一条行前准备…" />
          <input class="trip-add-input trip-add-slot" data-slot-day="0" maxlength="20" placeholder="分组（可选，如 证件与票据）" style="flex:0 0 170px" />
          <button class="btn btn-ghost trip-add-btn" data-day="0">添加</button>
        </div>
      </div>`;
  }

  // 时段候选：冲突检测靠 slot 非空，手输自由文本会写出「上午」「上午9点」「9:00」三种说法，
  // 同一时段就撞不上，提示形同虚设。给候选 + 允许自由输入，兼顾一致性和灵活。
  const TRIP_SLOTS = ["上午", "中午", "下午", "晚上", "全天"];

  function itineraryPanelHtml(t) {
    const itinerary = t.itinerary || [];
    return `<div class="app-panel">
        <div class="trip-sec-head"><h3>每日行程</h3><span class="trip-meta">${itinerary.length} 天</span></div>
        <div class="trip-revise">
          <input class="trip-add-input" id="trip-revise-input" placeholder="想怎么改？例如「第三天想换室内，怕下雨」" />
          <button class="btn btn-accent" id="trip-revise-btn">🤖 按我说的改</button>
        </div>
        <p class="trip-hint">只改你提到的那几天，已勾选的条目会保留勾选状态。</p>
        <datalist id="trip-slot-list">${TRIP_SLOTS.map(s => `<option value="${s}"></option>`).join("")}</datalist>
        ${itinerary.length ? itinerary.map(d => `
          <div class="trip-day">
            <div class="trip-day-name">第 ${d.day} 天</div>
            ${d.items.map(itemRow).join("")}
            <div class="trip-add-row">
              <input class="trip-add-input" data-day="${d.day}" placeholder="给第 ${d.day} 天加一项…" />
              <input class="trip-add-input trip-add-slot" data-slot-day="${d.day}" maxlength="20" list="trip-slot-list" placeholder="时段（可选）" style="flex:0 0 110px" />
              <button class="btn btn-ghost trip-add-btn" data-day="${d.day}">添加</button>
            </div>
          </div>`).join("") : `
          <div class="app-empty" style="padding:12px 24px"><p>手动加一条，或点上方「✨ 生成每日行程」让 AI 排一版</p></div>
          ${Array.from({ length: Math.max(1, t.days || 1) }, (_, i) => `
          <div class="trip-day">
            <div class="trip-day-name">第 ${i + 1} 天</div>
            <div class="trip-add-row">
              <input class="trip-add-input" data-day="${i + 1}" placeholder="给第 ${i + 1} 天加一项…" />
              <input class="trip-add-input trip-add-slot" data-slot-day="${i + 1}" maxlength="20" list="trip-slot-list" placeholder="时段（可选）" style="flex:0 0 110px" />
              <button class="btn btn-ghost trip-add-btn" data-day="${i + 1}">添加</button>
            </div>
          </div>`).join("")}`}
      </div>`;
  }

  /**
   * 把接口回的行程合并进当前对象（就地改，不换引用）。
   *
   * <p>所有事件处理器都闭包捕获了同一个 t，换引用会让它们读到旧数据 —— 表现就是
   * 「改完再点一次编辑，弹回来还是老值」。就地合并才能让局部刷新和闭包共存。
   */
  function applyTripView(t, trip) {
    if (!trip || trip.id !== t.id) return t;
    Object.assign(t, trip);
    if (tripsView.current && tripsView.current.id === t.id) Object.assign(tripsView.current, trip);
    return t;
  }

  /** 条目增删改之后列表变了，但只有列表变了 —— 摘要/冲突/两个清单重画，不碰预算与游记。 */
  function refreshTripBody(t) {
    refreshTripHero(t);
    refreshTripConflicts(t);
    refreshPrep(t);
    refreshItinerary(t);
  }

  function refreshPrep(t) {
    const box = document.getElementById("trip-prep-wrap");
    if (!box) return;
    box.innerHTML = prepPanelHtml(t);
    bindItemRows(box, t);
    bindAddRows(box, t);
  }

  function refreshItinerary(t) {
    const box = document.getElementById("trip-itinerary-wrap");
    if (!box) return;
    box.innerHTML = itineraryPanelHtml(t);
    bindItemRows(box, t);
    bindAddRows(box, t);
    bindRevise(box, t);
  }

  async function reloadTrip(t) {
    const r = await apiGet(`/api/trips/${encodeURIComponent(t.id)}`);
    if (!r.ok) return null;
    return applyTripView(t, r.data.trip);
  }

  /* ---------- 条目行内编辑 ---------- */

  /**
   * 点 ✏️ 就地展开编辑行（文字/时段/备注）。
   *
   * <p>为什么不是整页表单：用户改的是「第 2 天下午那一项」，眼睛正盯着那一行；
   * 跳到另一个页面再回来，他得重新找回自己刚才在看的位置。
   *
   * <p>注意 .trip-item 是 &lt;label&gt;，里面点按钮会被 label 转发给 checkbox，
   * 所以所有按钮都要 preventDefault + stopPropagation。
   */
  function openItemEditor(root, t, itemId) {
    const label = root.querySelector(`.trip-item[data-item-id="${itemId}"]`);
    if (!label || label.nextElementSibling && label.nextElementSibling.classList.contains("trip-item--edit")) return;
    const day = parseInt(label.dataset.day, 10) || 0;
    const pool = day === 0 ? (t.prep || []) : (t.itinerary || []).reduce((a, d) => a.concat(d.items || []), []);
    const it = pool.find((x) => String(x.id) === String(itemId));
    if (!it) return;

    const box = document.createElement("div");
    box.className = "trip-item trip-item--edit";
    box.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 0";
    box.innerHTML = `
      <input class="trip-add-input trip-edit-title" maxlength="120" placeholder="这一项是什么" style="flex:1 1 180px" />
      <input class="trip-add-input trip-edit-slot" maxlength="20" placeholder="${day === 0 ? "分组" : "时段"}" style="flex:0 0 120px"${day === 0 ? "" : ' list="trip-slot-list"'} />
      <input class="trip-add-input trip-edit-note" maxlength="500" placeholder="备注（可选）" style="flex:1 1 160px" />
      <button type="button" class="btn btn-primary trip-edit-save">保存</button>
      <button type="button" class="btn btn-ghost trip-edit-cancel">取消</button>`;

    const titleEl = box.querySelector(".trip-edit-title");
    const slotEl = box.querySelector(".trip-edit-slot");
    const noteEl = box.querySelector(".trip-edit-note");
    titleEl.value = it.title || "";
    slotEl.value = it.slot || "";
    noteEl.value = it.note || "";

    label.hidden = true;
    label.after(box);
    titleEl.focus();

    const close = () => { box.remove(); label.hidden = false; };
    box.querySelector(".trip-edit-cancel").addEventListener("click", close);

    const saveBtn = box.querySelector(".trip-edit-save");
    saveBtn.addEventListener("click", async () => {
      const title = (titleEl.value || "").trim();
      if (!title) { toast("这一项不能为空"); titleEl.focus(); return; }
      const payload = {};
      if (title !== (it.title || "")) payload.title = title;
      if ((slotEl.value || "").trim() !== (it.slot || "")) payload.slot = (slotEl.value || "").trim();
      if ((noteEl.value || "").trim() !== (it.note || "")) payload.note = (noteEl.value || "").trim();
      if (!Object.keys(payload).length) { close(); toast("没有改动"); return; }
      saveBtn.disabled = true;
      saveBtn.textContent = "保存中…";
      const r = await api("PATCH", `/api/trips/${encodeURIComponent(t.id)}/items/${it.id}`, payload);
      saveBtn.disabled = false;
      saveBtn.textContent = "保存";
      if (!r.ok) { toast((r.data && r.data.detail) || "保存失败"); return; }
      applyTripView(t, r.data.trip);
      // 时段/分组改了会换组、换天块，整块列表重画才自洽；预算与游记不动
      refreshTripBody(t);
      toast("已保存");
    });
  }

  /** 勾选 / 删除 / 编辑：三种都是「单条条目」操作。 */
  function bindItemRows(root, t) {
    root.querySelectorAll(".trip-check").forEach(box => {
      box.addEventListener("change", async (e) => {
        const el = e.currentTarget;
        const id = el.dataset.id;
        const want = el.checked;
        el.disabled = true;
        const r = await api("PATCH", `/api/trips/${encodeURIComponent(t.id)}/items/${id}`, { done: want });
        el.disabled = false;
        if (!r.ok) { el.checked = !want; toast((r.data && r.data.detail) || "更新失败"); return; }
        const row = el.closest(".trip-item");
        if (row) row.classList.toggle("done", want);
        applyTripView(t, r.data.trip);
        // 只更新摘要里的进度，不重画列表 —— 否则勾一条滚回顶部，勾十条就疯了
        refreshTripHero(t);
        refreshTripConflicts(t);
      });
    });

    root.querySelectorAll(".trip-item-del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = e.currentTarget.dataset.id;
        const r = await api("DELETE", `/api/trips/${encodeURIComponent(t.id)}/items/${id}`);
        if (!r.ok) { toast((r.data && r.data.detail) || "删除失败"); return; }
        if (!(await reloadTrip(t))) { toast("已删除，但刷新失败，请重开这份行程"); return; }
        refreshTripBody(t);
      });
    });

    root.querySelectorAll(".trip-item-edit").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openItemEditor(root, t, e.currentTarget.dataset.id);
      });
    });
  }

  /**
   * 手动添加条目。
   *
   * <p>「时段」不是可选装饰：冲突检测（TripService.conflicts）只比较 slot 非空的条目，
   * 手加的行要是永远没有 slot，它就永远不进检测，用户排了两项同一时段也收不到提示。
   */
  function bindAddRows(root, t) {
    root.querySelectorAll(".trip-add-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const day = parseInt(btn.dataset.day, 10) || 0;
        const titleEl = root.querySelector(`.trip-add-input[data-day="${day}"]`);
        const slotEl = root.querySelector(`.trip-add-slot[data-slot-day="${day}"]`);
        const title = (titleEl.value || "").trim();
        const slot = slotEl ? (slotEl.value || "").trim() : "";
        if (!title) { toast(day === 0 ? "先写要准备什么" : "先写要去哪/做什么"); titleEl.focus(); return; }
        btn.disabled = true;
        const r = await apiPost(`/api/trips/${encodeURIComponent(t.id)}/items`, {
          title, day_index: day, slot: slot || null, kind: day === 0 ? "doc" : "spot",
        });
        btn.disabled = false;
        if (!r.ok) { toast((r.data && r.data.detail) || "添加失败"); return; }
        // POST /items 只回单条，拿不到新的进度，拉一次完整视图
        if (!(await reloadTrip(t))) { toast("已添加，但刷新失败，请重开这份行程"); return; }
        refreshTripBody(t);
        toast("已添加");
      });
    });
  }

  /** AI 改行程：只改提到的那几天，已勾选的条目保留勾选状态。 */
  function bindRevise(root, t) {
    const reviseBtn = root.querySelector("#trip-revise-btn");
    if (!reviseBtn) return;
    reviseBtn.addEventListener("click", async () => {
      const input = root.querySelector("#trip-revise-input");
      const instruction = (input.value || "").trim();
      if (!instruction) { toast("先说一下想怎么改"); input.focus(); return; }
      reviseBtn.disabled = true;
      reviseBtn.textContent = "修改中…";
      const r = await apiPost(`/api/trips/${encodeURIComponent(t.id)}/revise`, { instruction });
      reviseBtn.disabled = false;
      reviseBtn.textContent = "🤖 按我说的改";
      if (!r.ok) { toast((r.data && r.data.detail) || "修改失败"); return; }
      toast(`已调整为 ${r.data.items} 项，勾选状态保留`);
      applyTripView(t, r.data.trip);
      refreshTripBody(t);
    });
  }

  /**
   * 顶部摘要。
   *
   * <p>抽成函数只为一件事：改完日期/预算时能**只换这一块**。整页 innerHTML 重建会把
   * 滚动位置、正在输入的框、已展开的模板行一起冲掉，改一个字闪一下，用起来很难受。
   */
  function tripHeroHtml(t) {
    const cd = t.countdown !== null && t.countdown > 0;
    return `<div class="app-panel trip-hero">
        <div class="trip-hero-main">
          <div class="trip-cd-big">${cd ? t.countdown : "—"}<span>${cd ? "天后出发" : escapeHtml(tripPhaseText(t))}</span></div>
          <div>
            <h2>${escapeHtml(t.title)}</h2>
            <div class="trip-meta">${escapeHtml(t.start_date || "日期待定")} · ${t.days} 天${t.budget ? ` · 人均预算 ¥${t.budget}` : ""}</div>
          </div>
        </div>
        ${tripProgressBar(t.progress, true)}
        <div class="trip-foot">已完成 ${t.progress.done}/${t.progress.total} 项（${t.progress.percent}%）</div>
      </div>`;
  }

  function refreshTripHero(t) {
    const box = document.getElementById("trip-hero-wrap");
    if (!box) return;
    box.innerHTML = tripHeroHtml(t);
  }

  function refreshTripConflicts(t) {
    const box = document.getElementById("trip-conflicts-wrap");
    if (!box) return;
    box.innerHTML = conflictBar(t);
  }

  /** 预算块整体换掉：汇总数字、进度条、两张图都在这一块里。 */
  function refreshTripBudget(t) {
    const box = document.getElementById("trip-budget-wrap");
    if (!box) return;
    disposeCharts();
    box.innerHTML = budgetPanel(t);
    bindBudgetPanel(box, t);
    drawBudgetCharts(t);
    fillExpenseList(t.id);
  }

  /**
   * 行程属性编辑行（目的地/标题/日期/天数/预算/备注）。
   *
   * <p>就地展开一行，不跳页、不弹窗：这些字段用户是「边看行程边改」的，
   * 跳走再回来会丢掉他刚才在看的安排。
   */
  function tripEditRowHtml() {
    const cities = Object.keys(window.CITY_GEO || {}).sort();
    return `
      <div class="trip-new-row trip-edit-row" id="trip-edit-row" hidden>
        <input id="edit-title" maxlength="80" placeholder="行程标题" style="flex:1 1 180px" />
        <input id="edit-city" list="trip-edit-city-list" placeholder="目的地" autocomplete="off" style="flex:0 0 130px" />
        <datalist id="trip-edit-city-list">${cities.map(c => `<option value="${escapeHtml(c)}"></option>`).join("")}</datalist>
        <input id="edit-date" type="date" title="出发日期（可留空）" style="flex:0 0 150px" />
        <input id="edit-days" type="number" min="1" max="30" title="天数" style="flex:0 0 78px" />
        <input id="edit-budget" type="number" min="0" step="100" placeholder="人均预算" style="flex:0 0 120px" />
        <input id="edit-note" maxlength="500" placeholder="备注（可选）" style="flex:1 1 200px" />
        <button class="btn btn-primary" id="edit-save">保存</button>
        <button class="btn btn-ghost" id="edit-cancel">取消</button>
      </div>`;
  }

  /** 展开/收起编辑行。用 onclick 而不是 addEventListener：反复点不能叠一堆监听器。 */
  function openTripEditor(t) {
    const row = document.getElementById("trip-edit-row");
    if (!row) return;
    if (!row.hidden) { row.hidden = true; return; }
    // 局部刷新不会重绑动作栏，闭包里捕获的 t 可能是保存前的旧对象 —— 以 current 为准
    const cur = tripsView.current && tripsView.current.id === t.id ? tripsView.current : t;
    row.querySelector("#edit-title").value = cur.title || "";
    row.querySelector("#edit-city").value = cur.city || "";
    row.querySelector("#edit-date").value = cur.start_date || "";
    row.querySelector("#edit-days").value = cur.days;
    row.querySelector("#edit-budget").value = cur.budget || "";
    row.querySelector("#edit-note").value = cur.note || "";
    row.hidden = false;
    row.querySelector("#edit-title").focus();
    row.querySelector("#edit-save").onclick = () => saveTripProps(cur, row.querySelector("#edit-save"));
    row.querySelector("#edit-cancel").onclick = () => { row.hidden = true; };
  }

  /**
   * 保存行程属性（PATCH /api/trips/{id}，null 字段 = 不改，所以只提交真正动过的）。
   *
   * <p>天数改小时必须拦：后端的 update 只改 trip.days，**不会**清理 day_index 超出的条目，
   * 那些条目会继续以「第 5 天」挂在 3 天的行程里 —— 用户看到的是一份自相矛盾的行程，
   * 而且日程页只列 1~3 天，他既看不见也删不掉。所以这里确认后主动删掉，别留脏数据。
   */
  async function saveTripProps(t, btn) {
    const row = document.getElementById("trip-edit-row");
    if (!row) return;
    const val = (sel) => (row.querySelector(sel).value || "").trim();

    const title = val("#edit-title");
    const city = val("#edit-city");
    const startDate = val("#edit-date");
    const note = val("#edit-note");
    const daysRaw = val("#edit-days");
    const budgetRaw = val("#edit-budget");

    const days = daysRaw === "" ? NaN : parseInt(daysRaw, 10);
    if (!isFinite(days) || days < 1 || days > 30) { toast("天数要在 1~30 之间"); return; }
    const budget = budgetRaw === "" ? null : parseInt(budgetRaw, 10);
    if (budget !== null && (!isFinite(budget) || budget < 0)) { toast("预算不能为负"); return; }

    const payload = {};
    if (title && title !== (t.title || "")) payload.title = title;
    if (city && city !== (t.city || "")) payload.city = city;
    if (startDate !== (t.start_date || "")) payload.start_date = startDate;
    if (days !== t.days) payload.days = days;
    if (budget !== null && budget !== t.budget) payload.budget = budget;
    if (note !== (t.note || "")) payload.note = note;

    if (!Object.keys(payload).length) { toast("没有改动"); row.hidden = true; return; }

    const overflow = [];
    if (payload.days != null && payload.days < t.days) {
      (t.itinerary || []).forEach((d) => {
        (d.items || []).forEach((it) => {
          const day = it.day_index == null ? d.day : it.day_index;
          if (day > payload.days) overflow.push({ id: it.id, day });
        });
      });
      if (overflow.length) {
        const dayList = Array.from(new Set(overflow.map((x) => x.day))).sort((a, b) => a - b);
        if (!confirm(`改为 ${payload.days} 天后，第 ${dayList.join("、")} 天的 ${overflow.length} 项安排会超出行程天数。保存将一并删除这 ${overflow.length} 项，且不可撤销。继续？`)) return;
      }
    }

    btn.disabled = true;
    btn.textContent = "保存中…";
    const r = await api("PATCH", `/api/trips/${encodeURIComponent(t.id)}`, payload);
    btn.disabled = false;
    btn.textContent = "保存";
    if (!r.ok) { toast((r.data && r.data.detail) || "保存失败"); return; }

    let trip = r.data.trip;
    if (overflow.length) {
      let failed = 0;
      for (const it of overflow) {
        const dr = await api("DELETE", `/api/trips/${encodeURIComponent(t.id)}/items/${it.id}`);
        if (!dr.ok) failed += 1;
      }
      if (failed) toast(`${failed} 项超出天数的安排没删掉，可在每日行程里逐条删除`);
      // 删了条目，进度与每日行程都变了，拉一次完整视图再整块渲染
      const fresh = await apiGet(`/api/trips/${encodeURIComponent(t.id)}`);
      if (fresh.ok) trip = fresh.data.trip;
      applyTripView(t, trip);   // 就地合并：别换对象，否则闭包里拿到的还是旧数据
      row.hidden = true;
      renderTripDetail(t);
      return;
    }

    // 就地合并而不是换 tripsView.current：动作栏/条目行/预算面板的处理器都闭包捕获了 t，
    // 换引用会让「保存后再点编辑」读回旧值。
    applyTripView(t, trip);
    row.hidden = true;
    refreshTripHero(t);
    refreshTripConflicts(t);
    refreshTripBudget(t);
    toast("已保存");
  }

  function renderTripDetail(t) {
    const el = tripsView.el;
    // 详情页整块重渲染：先销毁上一轮的图表实例，否则每点一次勾选就多留一份 ECharts
    disposeCharts();

    el.innerHTML = `
      <div class="trip-detail-head">
        <button class="btn btn-ghost" id="trip-back">← 返回列表</button>
        <div class="trip-actions">
          <button class="btn btn-primary" data-act="edit">✏️ 编辑</button>
          <button class="btn btn-accent" data-act="plan">✨ 生成每日行程</button>
          <button class="btn btn-primary" data-act="packing">🎒 生成装备清单</button>
          <button class="btn btn-ghost" data-act="weather">🌦 天气与建议</button>
          <button class="btn btn-ghost" data-act="map">🗺 行程地图</button>
          <button class="btn btn-ghost" data-act="template">📋 套用模板</button>
          <button class="btn btn-ghost" data-act="share">🔗 分享</button>
          <button class="btn btn-ghost" data-act="export">🖨 导出</button>
          <button class="btn btn-ghost trip-danger" data-act="del">🗑 删除行程</button>
        </div>
      </div>

      ${t.share_token ? `<div class="trip-share-bar" id="trip-share-bar">
          <span class="trip-share-url">${escapeHtml(location.origin)}/s/${escapeHtml(t.share_token)}</span>
          <button class="btn btn-ghost" data-act="share">📋 复制链接</button>
          <button class="btn btn-ghost trip-danger" data-act="unshare">取消分享</button>
        </div>` : ""}

      <div class="trip-tpl-row" id="trip-tpl-row" hidden></div>
      <div class="trip-export-row" id="trip-export-row" hidden>
        <button class="trip-export-btn" id="trip-export-ics"><b>📅 下载日历（.ics）</b><span>导入手机 / 电脑日历应用</span></button>
        <button class="trip-export-btn" id="trip-export-print"><b>🖨 打印版</b><span>新窗口打开，浏览器里「打印 → 存为 PDF」</span></button>
      </div>

      ${tripEditRowHtml()}

      <div id="trip-hero-wrap">${tripHeroHtml(t)}</div>

      <div id="trip-weather"></div>

      <div id="trip-conflicts-wrap">${conflictBar(t)}</div>

      <div id="trip-budget-wrap">${budgetPanel(t)}</div>

      <div id="trip-prep-wrap">${prepPanelHtml(t)}</div>

      <div id="trip-itinerary-wrap">${itineraryPanelHtml(t)}</div>

      ${notesPanel(t)}`;

    el.querySelector("#trip-back").addEventListener("click", () => {
      tripsView.current = null;
      renderTripList();
    });

    // 条目 / 添加 / AI 改行程：绑定都抽成函数，局部刷新时对新区块重绑一次即可
    bindItemRows(el, t);
    bindAddRows(el, t);
    bindRevise(el, t);

    // ---- 预算记账（绑定抽成函数：记账后只重画预算块，不再整页重渲染）
    bindBudgetPanel(el, t);
    fillExpenseList(t.id);
    drawBudgetCharts(t);
    fillNotes(t.id);
    bindNoteEditor(t.id);

    el.querySelectorAll(".trip-actions [data-act]").forEach(btn => {
      btn.addEventListener("click", () => tripAction(btn.dataset.act, t, btn));
    });
  }

  // ------------------------------------------------------------ 预算面板

  function money(n) {
    const v = Number(n || 0);
    return v.toFixed(2).replace(/\.00$/, "");
  }

  // ------------------------------------------------------------ 排期冲突

  /**
   * 冲突提示条（任务书 2(2)）。
   * 只提示不拦截：想上午连逛两个挨着的景点是合理的，硬拦会逼用户去猜规则。
   */
  function conflictBar(t) {
    const list = t.conflicts || [];
    if (!list.length) return "";
    return `<div class="app-panel trip-conflicts">
      <div class="trip-sec-head"><h3>⚠️ 排期提示</h3><span class="trip-meta">${list.length} 条</span></div>
      <ul>${list.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
      <p class="trip-hint">这些只是提醒，不影响保存。真要上午赶两个地方，把时段改成「上午」「下午」就分开了。</p>
    </div>`;
  }

  // ------------------------------------------------------------ 游记

  function notesPanel(t) {
    return `<div class="app-panel trip-notes">
      <div class="trip-sec-head"><h3>游记</h3><span class="trip-meta">图文记录，图片存在本地</span></div>
      <div id="note-list" class="note-list"><p class="trip-hint">加载中…</p></div>
      <div class="note-editor">
        <input id="note-title" class="trip-add-input" placeholder="标题（不填就用正文首行）" maxlength="80" />
        <textarea id="note-content" class="note-text" rows="4" placeholder="这一天发生了什么？走了多久、吃了什么、哪里值得再去一次…"></textarea>
        <div class="note-tools">
          <input id="note-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden />
          <button class="btn btn-ghost" id="note-pick">🖼 添加图片</button>
          <span id="note-imgs" class="note-imgs"></span>
          <button class="btn btn-primary" id="note-save">保存游记</button>
        </div>
      </div>
    </div>`;
  }

  /** 待上传的图片地址（本页生命周期内有效）。 */
  let noteImages = [];

  async function fillNotes(tripId) {
    const box = document.querySelector("#note-list");
    if (!box) return;
    const r = await apiGet(`/api/trips/${encodeURIComponent(tripId)}/notes`);
    if (!r.ok) { box.innerHTML = `<p class="trip-hint">游记加载失败</p>`; return; }
    const rows = (r.data && r.data.notes) || [];
    if (!rows.length) {
      box.innerHTML = `<p class="trip-hint">还没有游记。玩完回来写一篇，图片会一起存下来。</p>`;
      return;
    }
    box.innerHTML = rows.map((n) => `
      <article class="note-card" data-note-id="${n.id}">
        <div class="note-head">
          <h4>${escapeHtml(n.title)}</h4>
          <span class="note-acts" style="display:flex;align-items:center;gap:2px;flex:none">
            <button class="note-edit" data-id="${n.id}" title="编辑这篇游记" aria-label="编辑 ${escapeHtml(n.title)}" style="background:none;border:0;cursor:pointer;opacity:.6;font-size:var(--fs-md);padding:0 4px">✏️</button>
            <button class="note-del" data-id="${n.id}" title="删除">×</button>
          </span>
        </div>
        <div class="note-time">${escapeHtml(String(n.created_at || "").slice(0, 10))}</div>
        <div class="note-body">${escapeHtml(n.content)}</div>
        ${(n.images || []).length ? `<div class="note-imgs">${n.images.map((src) => `<img src="${escapeHtml(src)}" alt="游记配图" loading="lazy" />`).join("")}</div>` : ""}
      </article>`).join("");

    box.querySelectorAll(".note-del").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const id = e.currentTarget.dataset.id;
        if (!confirm("删除这篇游记？")) return;
        const r2 = await api("DELETE", `/api/trips/${encodeURIComponent(tripId)}/notes/${id}`);
        if (!r2.ok) { toast("删除失败"); return; }
        fillNotes(tripId);
      });
    });

    box.querySelectorAll(".note-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        const note = rows.find((x) => String(x.id) === btn.dataset.id);
        if (note) openNoteEditor(tripId, note, btn.closest(".note-card"));
      });
    });
  }

  /**
   * 就地改一篇游记（PUT /api/trips/{tripId}/notes/{id}）。
   *
   * <p>只提交标题与正文：后端 images 传 null 表示「不动」，所以编辑正文不会把已存的图弄丢。
   * 想在编辑里加图得复用上传流程，代价是这一屏两套上传状态，暂时不值。
   */
  /**
   * 标题留空时的默认标题：正文首行前 20 字，取不到就「未命名游记」。
   *
   * <p>逐字对齐 `NoteService.defaultTitle()`（创建游记时用的是同一套规则）。
   * 改那边记得改这里 —— 创建允许留空、更新不允许，是最容易让人困惑的那种不一致。
   */
  function defaultNoteTitle(content) {
    const first = String(content || "").split(/\r?\n/)[0].trim();
    if (!first) return "未命名游记";
    return first.length > 20 ? first.slice(0, 20) : first;
  }

  function openNoteEditor(tripId, note, card) {
    if (!card || card.dataset.editing === "1") return;
    card.dataset.editing = "1";
    const imgs = note.images || [];
    card.innerHTML = `
      <div class="note-editor" style="margin:0">
        <input id="note-edit-title" class="trip-add-input" maxlength="80" placeholder="标题（留空则用正文首行）" style="width:100%;margin-bottom:8px" />
        <textarea id="note-edit-content" class="note-text" rows="5" placeholder="正文" style="width:100%"></textarea>
        ${imgs.length ? `<div class="note-imgs">${imgs.map((src) => `<img src="${escapeHtml(src)}" alt="游记配图" />`).join("")}</div><p class="trip-hint">配图保持不变</p>` : ""}
        <div class="note-tools">
          <button class="btn btn-primary" id="note-edit-save">保存</button>
          <button class="btn btn-ghost" id="note-edit-cancel">取消</button>
        </div>
      </div>`;

    const titleEl = card.querySelector("#note-edit-title");
    const contentEl = card.querySelector("#note-edit-content");
    titleEl.value = note.title || "";
    contentEl.value = note.content || "";
    contentEl.focus();

    const cancel = card.querySelector("#note-edit-cancel");
    cancel.addEventListener("click", () => fillNotes(tripId));   // 重新拉一次，未保存的改动丢弃

    const save = card.querySelector("#note-edit-save");
    save.addEventListener("click", async () => {
      const content = (contentEl.value || "").trim();
      if (!content) { toast("正文不能为空"); contentEl.focus(); return; }
      // 不能把 "" 交给后端：NoteService.update 对空标题是「跳过」，接口照样回 200，
      // 前端再提示「已更新」就成了假成功。留空 = 用正文首行，与创建时的规则一致。
      const title = (titleEl.value || "").trim() || defaultNoteTitle(content);
      const payload = {};
      if (title !== (note.title || "")) payload.title = title;
      if (content !== (note.content || "")) payload.content = content;
      if (!Object.keys(payload).length) { fillNotes(tripId); toast("没有改动"); return; }
      save.disabled = true;
      save.textContent = "保存中…";
      const r = await apiPut(`/api/trips/${encodeURIComponent(tripId)}/notes/${note.id}`, payload);
      save.disabled = false;
      save.textContent = "保存";
      if (!r.ok) { toast((r.data && r.data.detail) || "保存失败"); return; }
      toast("游记已更新");
      fillNotes(tripId);
    });
  }

  /** 游记编辑器的事件绑定：上传是「先传图再存文」，图片地址随正文一起提交。 */
  function bindNoteEditor(tripId) {
    const pick = document.querySelector("#note-pick");
    const file = document.querySelector("#note-file");
    const save = document.querySelector("#note-save");
    if (!pick || !file || !save) return;

    noteImages = [];
    const imgsBox = document.querySelector("#note-imgs");
    const renderImgs = () => {
      imgsBox.innerHTML = noteImages.map((u) => `<img src="${escapeHtml(u)}" alt="待发布图片" />`).join("");
    };

    pick.addEventListener("click", () => file.click());
    file.addEventListener("change", async () => {
      const f = file.files && file.files[0];
      if (!f) return;
      if (f.size > 5 * 1024 * 1024) { toast("图片不能超过 5MB"); file.value = ""; return; }
      pick.disabled = true;
      pick.textContent = "上传中…";
      const fd = new FormData();
      fd.append("file", f);
      const t = localStorage.getItem("tc_token");
      let data = {};
      try {
        const resp = await fetch("/api/uploads", {
          method: "POST",
          headers: t ? { "X-Auth-Token": t } : {},
          body: fd,
        });
        data = await resp.json().catch(() => ({}));
        if (!resp.ok) { toast(data.detail || "上传失败"); return; }
        noteImages.push(data.url);
        renderImgs();
      } catch (e) {
        toast("上传失败，请检查网络");
      } finally {
        pick.disabled = false;
        pick.textContent = "🖼 添加图片";
        file.value = "";
      }
    });

    save.addEventListener("click", async () => {
      const title = (document.querySelector("#note-title").value || "").trim();
      const content = (document.querySelector("#note-content").value || "").trim();
      if (!content) { toast("先写点内容"); return; }
      save.disabled = true;
      const r = await apiPost(`/api/trips/${encodeURIComponent(tripId)}/notes`, { title, content, images: noteImages });
      save.disabled = false;
      if (!r.ok) { toast((r.data && r.data.detail) || "保存失败"); return; }
      document.querySelector("#note-title").value = "";
      document.querySelector("#note-content").value = "";
      noteImages = [];
      renderImgs();
      toast("游记已保存");
      fillNotes(tripId);
    });
  }

  // ------------------------------------------------------------ 费用图表（ECharts）

  /** 图表实例集中管一下：详情页每次重渲染都会换掉 DOM，旧实例不 dispose 会一直占内存。 */
  let charts = [];
  function disposeCharts() {
    charts.forEach((c) => { try { c.dispose(); } catch (e) { /* 已销毁 */ } });
    charts = [];
  }

  function drawBudgetCharts(t) {
    if (typeof echarts === "undefined") return;
    const e = t.expenses || {};
    const cats = Object.entries(e.by_category || {});
    const days = (e.by_day || []).map((d) => ({ day: d.day, amount: Number(d.amount) || 0 }));

    const catBox = document.querySelector("#chart-cat");
    const dayBox = document.querySelector("#chart-day");
    const palette = ["#FF5436", "#FFA53D", "#0E9E94", "#6C4DF6", "#2EBDa8", "#877D6C"];

    if (catBox && cats.length) {
      const c = echarts.init(catBox);
      c.setOption({
        color: palette,
        tooltip: { trigger: "item", formatter: "{b}：¥{c}（{d}%）" },
        legend: { bottom: 0, icon: "circle", itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11 } },
        series: [{
          type: "pie",
          radius: ["46%", "68%"],
          center: ["50%", "44%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: { show: false },
          data: cats.map(([k, v]) => ({ name: k, value: Number(v) })),
        }],
      });
      charts.push(c);
    } else if (catBox) {
      catBox.innerHTML = `<p class="trip-hint">记几笔账，这里会出现分类占比</p>`;
    }

    if (dayBox && days.length) {
      const c = echarts.init(dayBox);
      c.setOption({
        color: ["#FF5436"],
        grid: { left: 8, right: 12, top: 24, bottom: 8, containLabel: true },
        tooltip: { trigger: "axis", formatter: (p) => `${p[0].name}：¥${p[0].value}` },
        xAxis: {
          type: "category",
          data: days.map((d) => (d.day > 0 ? `第${d.day}天` : "行前")),
          axisLine: { lineStyle: { color: "#CFC4AC" } },
          axisTick: { show: false },
          axisLabel: { color: "#877D6C", fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: "#EFE9DC" } },
          axisLabel: { color: "#877D6C", fontSize: 11 },
        },
        series: [{ type: "bar", barMaxWidth: 26, itemStyle: { borderRadius: [6, 6, 0, 0] }, data: days.map((d) => d.amount) }],
      });
      charts.push(c);
    } else if (dayBox) {
      dayBox.innerHTML = `<p class="trip-hint">按天分布会出现在这里</p>`;
    }
  }

  function budgetPanel(t) {
    const e = t.expenses || { budget: 0, spent: 0, remaining: 0, percent: 0, by_category: {} };
    const over = e.budget > 0 && Number(e.spent) > e.budget;
    const pct = Math.max(0, Math.min(100, Number(e.percent) || 0));
    const cats = Object.keys(e.by_category || {});
    const dayOptions = [`<option value="0">行前</option>`]
      .concat(Array.from({ length: t.days }, (_, i) => `<option value="${i + 1}">第 ${i + 1} 天</option>`))
      .join("");

    return `
      <div class="app-panel trip-budget">
        <div class="trip-sec-head">
          <h3>预算与花费</h3>
          <span class="trip-meta">${e.budget > 0 ? `预算 ¥${money(e.budget)} · 已花 ¥${money(e.spent)} · 剩余 ¥${money(e.remaining)}` : `已花 ¥${money(e.spent)}（未设预算）`}</span>
        </div>
        ${e.budget > 0 ? `<div class="budget-bar"><i style="width:${pct}%" class="${over ? "over" : ""}"></i></div>
          <p class="trip-hint">${over ? `已超预算 ¥${money(Number(e.spent) - e.budget)}，后面几天可以压一压餐饮与门票` : `已用 ${pct}% 的预算`}</p>` : ""}
        ${cats.length ? `<div class="budget-cats">${cats.map(c => `<span class="budget-cat">${escapeHtml(c)} <b>¥${money(e.by_category[c])}</b></span>`).join("")}</div>` : ""}
        <div class="budget-charts">
          <div class="budget-chart">
            <div class="budget-chart-title">分类占比</div>
            <div id="chart-cat" class="chart-box"></div>
          </div>
          <div class="budget-chart">
            <div class="budget-chart-title">按天花费</div>
            <div id="chart-day" class="chart-box"></div>
          </div>
        </div>
        <div class="budget-form">
          <select id="budget-cat">
            <option>交通</option><option>住宿</option><option>餐饮</option>
            <option>门票</option><option>购物</option><option>其他</option>
          </select>
          <input id="budget-title" placeholder="花在什么上？如 故宫门票" maxlength="40" />
          <input id="budget-amount" type="number" min="0" step="0.01" placeholder="金额" />
          <select id="budget-day">${dayOptions}</select>
          <button class="btn btn-primary" id="budget-add">记一笔</button>
        </div>
        <div id="budget-list" class="budget-list"></div>
      </div>`;
  }

  /**
   * 预算面板的事件绑定。
   *
   * <p>记一笔之后只重画预算块（`refreshTripBudget`），不调 `openTrip()`：
   * 记账往往是连着记好几笔，每笔都整页重建会把光标和滚动位置一起甩掉。
   * 后端 POST /expenses 顺手回了汇总，够用；万一没有就用返回体里的 trip.expenses。
   */
  function bindBudgetPanel(root, t) {
    const addExpense = root.querySelector("#budget-add");
    if (addExpense) {
      addExpense.addEventListener("click", async () => {
        const category = root.querySelector("#budget-cat").value;
        const titleEl = root.querySelector("#budget-title");
        const amountEl = root.querySelector("#budget-amount");
        const dayEl = root.querySelector("#budget-day");
        const title = (titleEl.value || "").trim();
        const amount = parseFloat(amountEl.value);
        if (!title) { toast("填一下这笔花在什么上"); titleEl.focus(); return; }
        if (!isFinite(amount) || amount <= 0) { toast("金额要大于 0"); amountEl.focus(); return; }
        addExpense.disabled = true;
        const r = await apiPost(`/api/trips/${encodeURIComponent(t.id)}/expenses`, {
          category, title, amount, day_index: parseInt(dayEl.value, 10) || 0,
        });
        addExpense.disabled = false;
        if (!r.ok) { toast((r.data && r.data.detail) || "记账失败"); return; }
        applyBudgetView(t, r.data);
        refreshTripBudget(t);
        toast("已记一笔");
      });
    }

    root.querySelectorAll(".budget-del").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        const id = e.currentTarget.dataset.id;
        const r = await api("DELETE", `/api/trips/${encodeURIComponent(t.id)}/expenses/${id}`);
        if (!r.ok) { toast("删除失败"); return; }
        applyBudgetView(t, r.data);
        refreshTripBudget(t);
      });
    });
  }

  /** 把记账接口回的汇总塞回当前行程对象：summary 优先，没有就取 trip.expenses。 */
  function applyBudgetView(t, data) {
    const summary = (data && data.summary) || (data && data.trip && data.trip.expenses);
    if (!summary) return;
    t.expenses = summary;
    if (tripsView.current && tripsView.current.id === t.id) tripsView.current.expenses = summary;
  }

  /** 明细单独拉一次：详情接口只带汇总，把每一笔都塞进去会让列表页也变重。 */
  async function fillExpenseList(tripId) {
    const box = document.querySelector("#budget-list");
    if (!box) return;
    const r = await apiGet(`/api/trips/${encodeURIComponent(tripId)}/expenses`);
    if (!r.ok) { box.innerHTML = ""; return; }
    const rows = (r.data && r.data.expenses) || [];
    if (!rows.length) {
      box.innerHTML = `<p class="trip-hint">还没有记账。把门票、餐饮、交通记下来，剩下的预算一目了然。</p>`;
      return;
    }
    box.innerHTML = rows.map(x => `
      <div class="budget-item" data-expense-id="${x.id}">
        <span class="budget-tag">${escapeHtml(x.category)}</span>
        <span class="budget-name">${escapeHtml(x.title)}</span>
        <span class="budget-day">${x.day_index > 0 ? `第${x.day_index}天` : "行前"}</span>
        <span class="budget-amt">¥${money(x.amount)}</span>
        <button class="budget-edit" data-id="${x.id}" title="编辑这一笔" aria-label="编辑 ${escapeHtml(x.title)}" style="background:none;border:0;cursor:pointer;opacity:.6;font-size:var(--fs-sm);padding:0 2px">✏️</button>
        <button class="budget-del" data-id="${x.id}" title="删除">×</button>
      </div>`).join("");

    box.querySelectorAll(".budget-edit").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const row = rows.find(x => String(x.id) === btn.dataset.id);
        if (row) openExpenseEditor(tripId, row, btn.closest(".budget-item"));
      });
    });
  }

  const EXPENSE_CATS = ["交通", "住宿", "餐饮", "门票", "购物", "其他"];

  /**
   * 就地改一笔账（PATCH /api/trips/{tripId}/expenses/{id}）。
   *
   * <p>记账最常见的动作是「金额记错了改一下」和「忘了选第几天」。为此让人删掉重记，
   * 等于把已经填对的三项重新填一遍。这里把这一行换成四个输入框，改完立刻重算汇总。
   */
  function openExpenseEditor(tripId, row, el) {
    if (!el || el.dataset.editing === "1") return;
    el.dataset.editing = "1";
    const days = Math.max(
      (tripsView.current && tripsView.current.days) || 1,
      Number(row.day_index) || 0,
      1
    );
    const dayOpts = [`<option value="0">行前</option>`]
      .concat(Array.from({ length: days }, (_, i) => `<option value="${i + 1}">第 ${i + 1} 天</option>`))
      .join("");

    el.innerHTML = `
      <select class="exp-cat" style="flex:0 0 88px">${EXPENSE_CATS.map(c => `<option${c === row.category ? " selected" : ""}>${escapeHtml(c)}</option>`).join("")}</select>
      <input class="exp-title trip-add-input" maxlength="120" style="flex:1 1 130px" />
      <input class="exp-amount trip-add-input" type="number" min="0" step="0.01" style="flex:0 0 88px" />
      <select class="exp-day" style="flex:0 0 96px">${dayOpts}</select>
      <button class="btn btn-primary exp-save" type="button">保存</button>
      <button class="btn btn-ghost exp-cancel" type="button">取消</button>`;

    const catEl = el.querySelector(".exp-cat");
    const titleEl = el.querySelector(".exp-title");
    const amountEl = el.querySelector(".exp-amount");
    const dayEl = el.querySelector(".exp-day");
    titleEl.value = row.title || "";
    amountEl.value = Number(row.amount) || 0;
    dayEl.value = String(row.day_index || 0);

    const cancel = el.querySelector(".exp-cancel");
    cancel.addEventListener("click", () => fillExpenseList(tripId));

    const save = el.querySelector(".exp-save");
    save.addEventListener("click", async () => {
      const title = (titleEl.value || "").trim();
      const amount = parseFloat(amountEl.value);
      if (!title) { toast("填一下这笔花在什么上"); titleEl.focus(); return; }
      if (!isFinite(amount) || amount <= 0) { toast("金额要大于 0"); amountEl.focus(); return; }
      const payload = {};
      if (catEl.value !== row.category) payload.category = catEl.value;
      if (title !== (row.title || "")) payload.title = title;
      if (Number(amount) !== Number(row.amount)) payload.amount = amount;
      if (Number(dayEl.value) !== Number(row.day_index || 0)) payload.day_index = Number(dayEl.value);
      if (!Object.keys(payload).length) { fillExpenseList(tripId); toast("没有改动"); return; }
      save.disabled = true;
      save.textContent = "保存中…";
      const r = await api("PATCH", `/api/trips/${encodeURIComponent(tripId)}/expenses/${row.id}`, payload);
      save.disabled = false;
      save.textContent = "保存";
      if (!r.ok) { toast((r.data && r.data.detail) || "保存失败"); return; }
      const t = tripsView.current;
      if (t) {
        applyBudgetView(t, r.data);
        refreshTripBudget(t);   // 汇总、进度条、两张图一起跟着变
      } else {
        fillExpenseList(tripId);
      }
      toast("已更新这一笔");
    });
  }

  async function tripAction(act, t, btn) {
    const id = encodeURIComponent(t.id);
    if (act === "del") {
      if (!confirm(`删除行程「${t.title}」？清单与安排会一起删除。`)) return;
      const r = await api("DELETE", `/api/trips/${id}`);
      if (!r.ok) { toast("删除失败"); return; }
      tripsView.current = null;
      toast("已删除");
      renderTripList();
      return;
    }
    if (act === "template") { await openTemplatePicker(t); return; }
    if (act === "edit") { openTripEditor(t); return; }
    if (act === "share") { await shareTrip(t); return; }
    if (act === "unshare") { await revokeShare(t); return; }
    if (act === "export") { openExportPicker(t); return; }
    if (act === "map") { openTripMap(t); return; }

    // 「生成每日行程」是整段替换（后端 replaceItinerary）：会删掉已有的每日安排，
    // 并把勾选状态一并重置。用户手动加了几条、勾了一半的时候点一下就没，所以先确认。
    // 空行程不弹——那种情况下「生成」是唯一有意义的操作，多问一步只是噪音。
    // 放在禁用按钮之前：用户点「取消」时按钮还没变成「生成中…」，界面不会有闪烁。
    if (act === "plan") {
      const existing = [];
      (t.itinerary || []).forEach((d) => {
        (d.items || []).forEach((it) => {
          const day = it.day_index == null ? d.day : it.day_index;
          if (day >= 1) existing.push(it);
        });
      });
      if (existing.length) {
        const doneCount = existing.filter((it) => it.done).length;
        if (!confirm(`生成会清空现有 ${existing.length} 项每日安排与已勾选的 ${doneCount} 项，且不可撤销。继续？`)) return;
      }
    }

    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = act === "plan" ? "生成中…" : act === "packing" ? "生成中…" : "查询中…";
    try {
      if (act === "weather") {
        const r = await apiGet(`/api/trips/${id}/weather`);
        renderTripWeather(r.ok ? r.data : { supported: false, reason: (r.data && r.data.detail) || "查询失败" });
      } else if (act === "packing") {
        const r = await apiPost(`/api/trips/${id}/packing`);
        if (!r.ok) { toast((r.data && r.data.detail) || "生成失败"); return; }
        toast(r.data.source === "forecast" ? "已按行程期间天气生成清单" : "已按季节估算生成清单");
        await openTrip(t.id);
      } else if (act === "plan") {
        const r = await apiPost(`/api/trips/${id}/plan`);
        if (!r.ok) { toast((r.data && r.data.detail) || "生成失败，可手动添加"); return; }
        toast(`已生成 ${r.data.items} 项安排`);
        await openTrip(t.id);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  /** 模板选择：直接在当前页展开一行，不用弹窗（少一层点击）。 */
  async function openTemplatePicker(t) {
    const row = document.getElementById("trip-tpl-row");
    if (!row) return;
    if (!row.hidden) { row.hidden = true; return; }
    const r = await apiGet("/api/templates");
    if (!r.ok) { toast("模板加载失败"); return; }
    const list = (r.data && r.data.templates) || [];
    row.innerHTML = list.map(x => `
      <button class="trip-tpl" data-key="${escapeHtml(x.key)}" title="${escapeHtml(x.description)}">
        <b>${escapeHtml(x.name)}</b>
        <span>${escapeHtml(x.description)}</span>
      </button>`).join("");
    row.hidden = false;
    row.querySelectorAll(".trip-tpl").forEach(b => {
      b.addEventListener("click", async () => {
        if (!confirm("套用模板会替换现有的每日安排（行前清单不动），继续？")) return;
        const rr = await apiPost(`/api/trips/${encodeURIComponent(t.id)}/templates/${b.dataset.key}`);
        if (!rr.ok) { toast((rr.data && rr.data.detail) || "套用失败"); return; }
        toast(`已套用模板，共 ${rr.data.items} 项安排`);
        await openTrip(t.id);
      });
    });
  }

  /** 分享：生成只读链接；已有链接就提示复制，再点一次取消分享。 */
  async function shareTrip(t) {
    if (!t.share_token) {
      const r = await apiPost(`/api/trips/${encodeURIComponent(t.id)}/share`);
      if (!r.ok) { toast((r.data && r.data.detail) || "生成分享链接失败"); return; }
      const url = location.origin + r.data.url;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url).catch(() => {});
      }
      toast("分享链接已复制，任何人打开都只能看不能改");
      await openTrip(t.id);
      return;
    }
    // 已分享时只做「复制」：链接常驻在分享条里（renderTripDetail 的 trip-share-bar），
    // 想看链接的用户直接复制即可；「取消分享」是独立的低强调按钮 + 二次确认，
    // 不再捆在同一个 confirm 里 —— 旧交互里想看链接的用户极易误杀链接（ux-report P2#7）。
    const url = location.origin + "/s/" + t.share_token;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url).catch(() => {});
    }
    toast("分享链接已复制");
  }

  /** 取消分享：独立入口 + 二次确认（文案里写清后果），不与「复制链接」共用任何弹窗。 */
  async function revokeShare(t) {
    if (!confirm("取消后这个链接会立即失效，已经拿到链接的人也将无法打开。确定取消分享吗？")) return;
    const r = await api("DELETE", `/api/trips/${encodeURIComponent(t.id)}/share`);
    if (!r.ok) { toast((r.data && r.data.detail) || "取消失败"); return; }
    toast("已取消分享");
    await openTrip(t.id);
  }

  /** 导出：点「🖨 导出」在按钮行下方展开双按钮（下载 ics / 打印版），不再用 confirm 让「取消」承载打印版。 */
  function openExportPicker(t) {
    const row = document.getElementById("trip-export-row");
    if (!row) return;
    row.hidden = !row.hidden;
    if (row.hidden) return;
    const icsBtn = row.querySelector("#trip-export-ics");
    const printBtn = row.querySelector("#trip-export-print");
    icsBtn.onclick = () => { row.hidden = true; downloadTripIcs(t); };
    printBtn.onclick = () => { row.hidden = true; openTripPrintVersion(t); };
  }

  async function downloadTripIcs(t) {
    const id = encodeURIComponent(t.id);
    const r = await fetch(API_BASE + `/api/trips/${id}/export/ics`, { headers: authHeaders() });
    if (!r.ok) { toast("导出失败"); return; }
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${t.title || "行程"}.ics`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    toast("日历文件已下载");
  }

  async function openTripPrintVersion(t) {
    const id = encodeURIComponent(t.id);
    const r = await fetch(API_BASE + `/api/trips/${id}/export/print`, { headers: authHeaders() });
    if (!r.ok) { toast("打开打印版失败"); return; }
    const html = await r.text();
    const w = window.open("", "_blank");
    if (!w) { toast("浏览器拦截了新窗口，请允许弹窗后重试"); return; }
    w.document.open();
    w.document.write(html);
    w.document.close();
  }

  function renderTripWeather(data) {
    const box = document.getElementById("trip-weather");
    if (!box) return;
    if (!data || data.supported === false) {
      box.innerHTML = `<div class="app-panel trip-weather"><h3>🌦 天气与出行建议</h3><p class="trip-meta">${escapeHtml((data && data.reason) || "暂无预报")}</p></div>`;
      return;
    }
    const rows = data.rows || [];
    const advice = data.advice || [];
    box.innerHTML = `<div class="app-panel trip-weather">
      <h3>🌦 行程期间天气</h3>
      <div class="trip-wx-grid">${rows.map(w => `
        <div class="trip-wx">
          <div class="trip-wx-date">${escapeHtml(w.date.slice(5))}</div>
          <div class="trip-wx-cond">${escapeHtml(w.cond)}</div>
          <div class="trip-wx-temp">${w.tmin}~${w.tmax}℃</div>
          <div class="trip-wx-pop">降水 ${w.precip === null || w.precip === undefined ? "-" : w.precip + "%"}</div>
        </div>`).join("")}</div>
      ${advice.length ? `<ul class="trip-advice">${advice.map(a => `<li>${escapeHtml(a)}</li>`).join("")}</ul>` : ""}
    </div>`;
  }

  /* ---------- 运营管理页 ---------- */
  // 内容库来源枚举，与后端 app/notes.py 的 SOURCES 保持一致
  const NOTE_SOURCES = [
    { v: "xiaohongshu", t: "小红书" },
    { v: "douyin", t: "抖音" },
    { v: "manual", t: "手工录入" },
    { v: "other", t: "其他" },
  ];
  const NOTE_SOURCE_LABEL = NOTE_SOURCES.reduce((m, s) => { m[s.v] = s.t; return m; }, {});

  // 内容库页的本地视图状态：筛选条件 / 分页 / 正在编辑的那一条
  const noteView = { city: "", source: "", q: "", page: 0, size: 20, editing: null };

  async function initAdminPage() {
    const container = document.getElementById("admin-app");
    if (!container) return;
    const user = authState();
    if (!user || user.role !== "admin") {
      container.innerHTML = `<div class="app-gate"><h2>权限不足</h2><p>仅管理员可访问此页面</p></div>`;
      return;
    }

    container.innerHTML = `
      <div class="admin-tabs" role="tablist">
        <button class="admin-tab is-active" data-tab="overview" role="tab" aria-selected="true">运营看板</button>
        <button class="admin-tab" data-tab="notes" role="tab" aria-selected="false">内容库</button>
      </div>
      <div id="admin-panel-overview"></div>
      <div id="admin-panel-notes" hidden></div>`;

    const tabs = Array.prototype.slice.call(container.querySelectorAll(".admin-tab"));
    const overview = container.querySelector("#admin-panel-overview");
    const notesHost = container.querySelector("#admin-panel-notes");
    let notesLoaded = false;

    tabs.forEach((btn) => btn.addEventListener("click", () => {
      const showNotes = btn.dataset.tab === "notes";
      tabs.forEach((b) => {
        const on = b === btn;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      overview.hidden = showNotes;
      notesHost.hidden = !showNotes;
      // 首次切到「内容库」才拉数据，避免一进页面就多打两个接口
      if (showNotes && !notesLoaded) { notesLoaded = true; renderNotesTab(notesHost); }
    }));

    renderAdminOverview(overview);
  }

  async function renderAdminOverview(host) {
    host.innerHTML = `<div class="app-panel"><div class="skeleton" style="height:200px"></div></div>`;
    const [sr, lr, ur] = await Promise.all([apiGet("/api/admin/stats"), apiGet("/api/admin/sessions?limit=20"), apiGet("/api/admin/users")]);
    if (!sr.ok || !lr.ok || !ur.ok) { host.innerHTML = `<div class="app-gate"><h2>无法加载</h2><p>需要管理员身份（请重新登录后访问）</p></div>`; return; }
    const s = sr.data || {};
    const sessions = (lr.data || []);
    const users = (ur.data && ur.data.users) || [];
    const fmt = (ts) => ts ? new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
    // token 用量：AI 应用最该被看见的指标。只统计调用次数无法回答「烧了多少钱」。
    const usage = s.llm_usage || {};
    const fmtTok = (n) => !n ? "0" : n >= 1e6 ? (n / 1e6).toFixed(2) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : String(n);
    const usageRows = Object.entries(usage.by_agent || {}).map(([name, v]) =>
      `<div class="session-row"><span>${escapeHtml(name)}</span><span style="color:var(--muted);font-size:var(--fs-sm)">${v.calls||0} 次 · ${fmtTok(v.prompt_tokens)} 入 / ${fmtTok(v.completion_tokens)} 出</span></div>`).join("");
    host.innerHTML = `
      <div class="app-panel">
        <h3 style="margin-bottom:16px">运营看板</h3>
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-num">${s.total_sessions||0}</div><div class="stat-label">总会话</div></div>
          <div class="stat-card"><div class="stat-num">${s.total_messages||0}</div><div class="stat-label">总消息</div></div>
          <div class="stat-card"><div class="stat-num">${s.likes||0}</div><div class="stat-label">点赞</div></div>
          <div class="stat-card"><div class="stat-num">${s.dislikes||0}</div><div class="stat-label">点踩</div></div>
        </div>
        <h4 style="margin:24px 0 12px">模型用量与成本</h4>
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-num">${fmtTok(usage.total_tokens||0)}</div><div class="stat-label">累计 tokens</div></div>
          <div class="stat-card"><div class="stat-num">${usage.calls||0}</div><div class="stat-label">模型调用</div></div>
          <div class="stat-card"><div class="stat-num">¥${(usage.estimated_cost_cny||0).toFixed(2)}</div><div class="stat-label">估算成本</div></div>
          <div class="stat-card"><div class="stat-num">${fmtTok(usage.reasoning_tokens||0)}</div><div class="stat-label">思维链 tokens</div></div>
        </div>
        <div class="session-list">${usageRows || `<div class="session-row"><span style="color:var(--muted)">暂无模型调用记录（Mock 模式不产生 token 消耗）</span></div>`}</div>
        <h4 style="margin:24px 0 12px">开通新账号</h4>
        <div class="app-toolbar">
          <input id="au-name" class="app-input" type="text" placeholder="用户名" autocomplete="off" />
          <input id="au-pwd" class="app-input" type="password" placeholder="密码（至少 6 位）" autocomplete="new-password" />
          <select id="au-role" class="app-select">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>
          <button id="au-go" class="btn btn-accent">创建账号</button>
        </div>
        <div class="modal-err" id="au-err" style="margin-bottom:14px"></div>
        <h4 style="margin:24px 0 12px">注册用户使用情况（${users.length}）</h4>
        <div class="session-list">${users.map(u => `
          <div class="session-row session-row--wrap">
            <span><strong>${escapeHtml(u.username)}</strong>
              <span style="font-size:var(--fs-xs);padding:2px 8px;border-radius:999px;${u.role === "admin" ? "background:var(--grad-sunset);color:#fff" : "background:var(--paper-3);color:var(--muted)"}">${u.role === "admin" ? "管理员" : "用户"}</span>
            </span>
            <span style="color:var(--muted);font-size:var(--fs-sm)">会话 ${u.session_count} · 消息 ${u.message_count}</span>
            <span style="color:var(--muted);font-size:var(--fs-sm)">注册 ${fmt(u.created_at)}</span>
            <span style="color:var(--muted);font-size:var(--fs-sm)">最近活跃 ${u.last_active ? fmt(u.last_active) : "从未使用"}</span>
          </div>`).join("")}</div>
        <h4 style="margin:24px 0 12px">最近会话</h4>
        <div class="session-list">${sessions.map(ss => `
          <div class="session-row">
            <span>${escapeHtml(ss.preview || "…")}${ss.username ? ` <span style="font-size:var(--fs-xs);color:var(--teal-ink)">@${escapeHtml(ss.username)}</span>` : ""}</span>
            <span style="color:var(--muted);font-size:var(--fs-sm)">消息 ${ss.message_count}</span>
          </div>`).join("")}</div>
      </div>`;

    // 开通账号：公网部署关闭开放注册后，这里是唯一的开号入口
    const auErr = host.querySelector("#au-err");
    host.querySelector("#au-go").addEventListener("click", async () => {
      auErr.textContent = "";
      const username = host.querySelector("#au-name").value.trim();
      const password = host.querySelector("#au-pwd").value.trim();
      const role = host.querySelector("#au-role").value;
      if (!username || !password) { auErr.textContent = "请填写用户名和密码"; return; }
      if (password.length < 6) { auErr.textContent = "密码至少 6 位"; return; }
      const r = await apiPost("/api/admin/users", { username, password, role });
      if (!r.ok) { auErr.textContent = r.data.detail || "创建失败"; return; }
      toast(r.data.message || "账号已创建");
      renderAdminOverview(host);
    });
  }

  /* ---------- 运营管理 · 内容库标签页 ---------- */
  function noteSourceBadge(src) {
    const key = NOTE_SOURCE_LABEL[src] ? src : "other";
    return `<span class="note-badge note-badge-${key}">${escapeHtml(NOTE_SOURCE_LABEL[key])}</span>`;
  }

  async function renderNotesTab(host) {
    host.innerHTML = `<div class="app-panel"><div class="skeleton" style="height:220px"></div></div>`;

    const qs = new URLSearchParams();
    if (noteView.city) qs.set("city", noteView.city);
    if (noteView.source) qs.set("source", noteView.source);
    if (noteView.q) qs.set("q", noteView.q);
    qs.set("limit", String(noteView.size));
    qs.set("offset", String(noteView.page * noteView.size));

    const [stR, lsR] = await Promise.all([
      apiGet("/api/notes/stats"),
      apiGet("/api/notes?" + qs.toString()),
    ]);
    if (!stR.ok || !lsR.ok) {
      const d = (stR.data && stR.data.detail) || (lsR.data && lsR.data.detail) || "请重新登录后再试";
      host.innerHTML = `<div class="app-panel"><div class="app-gate"><h2>无法加载内容库</h2><p>${escapeHtml(d)}</p></div></div>`;
      return;
    }

    const st = stR.data || {};
    const items = Array.isArray(lsR.data) ? lsR.data : [];
    // 分页总数走响应头（返回体仍是数组，保持接口向后兼容）
    const rawTotal = (lsR.headers && typeof lsR.headers.get === "function")
      ? lsR.headers.get("X-Total-Count") : null;
    const total = rawTotal != null ? Number(rawTotal) : items.length;
    const pageCount = Math.max(1, Math.ceil(total / noteView.size));
    // 删掉某页最后一条后，当前页码可能已经越界。这时不能只改页码就往下渲染 ——
    // items 是按旧 offset 拉的，会渲染出「空列表 + 第 1/1 页」这种自相矛盾的界面。
    // 直接带着修正后的页码重拉一次。
    if (noteView.page > pageCount - 1) {
      noteView.page = pageCount - 1;
      return renderNotesTab(host);
    }

    const byId = {};
    items.forEach((n) => { byId[n.id] = n; });

    const fmtTs = (ts) => ts ? new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
    const cityOpts = [`<option value="">全部城市</option>`].concat((st.cities || []).map((c) =>
      `<option value="${escapeHtml(c.city)}"${c.city === noteView.city ? " selected" : ""}>${escapeHtml(c.city)}（${c.count}）</option>`)).join("");
    const srcOpts = [`<option value="">全部来源</option>`].concat(NOTE_SOURCES.map((s) =>
      `<option value="${s.v}"${s.v === noteView.source ? " selected" : ""}>${s.t}</option>`)).join("");
    const srcChips = Object.keys(st.by_source || {}).map((k) =>
      `<span class="note-chip">${escapeHtml(k)} ${st.by_source[k]}</span>`).join("")
      || `<span class="note-chip">暂无内容</span>`;

    const e = noteView.editing || {};
    // 空态要分两种情况：库本身是空的 vs 筛选没命中。
    // 都显示「还没有内容 / 去导入第一条」会让用户以为数据丢了。
    const hasFilter = !!(noteView.city || noteView.source || noteView.q);
    const emptyHtml = hasFilter
      ? `<div class="app-empty"><h3>没有匹配的内容</h3><p>换个城市 / 来源或关键词试试，或点「重置」</p></div>`
      : `<div class="app-empty"><h3>还没有内容</h3><p>用上面的表单导入第一条攻略吧</p></div>`;
    const rows = items.map((n) => {
      const body = n.content || "";
      const short = body.slice(0, 110);
      return `
        <div class="note-row" data-id="${escapeHtml(n.id)}">
          <div class="note-row-main">
            <div class="note-row-title">
              ${noteSourceBadge(n.source)}
              <strong>${escapeHtml(n.title || "（无标题）")}</strong>
              ${n.city ? `<span class="note-city">📍 ${escapeHtml(n.city)}</span>` : ""}
            </div>
            <div class="note-row-meta">${fmtTs(n.created_at)}${n.author ? " · 作者 " + escapeHtml(n.author) : ""}${n.tags ? " · " + escapeHtml(n.tags) : ""}</div>
            <div class="note-row-preview">${escapeHtml(short)}${body.length > 110 ? "…" : ""}</div>
            <div class="note-full" hidden>${escapeHtml(body)}</div>
          </div>
          <div class="note-row-actions">
            <button class="btn btn-primary note-view" data-id="${escapeHtml(n.id)}">查看</button>
            <button class="btn btn-primary note-edit" data-id="${escapeHtml(n.id)}">编辑</button>
            <button class="btn btn-primary note-del" data-id="${escapeHtml(n.id)}">删除</button>
          </div>
        </div>`;
    }).join("");

    host.innerHTML = `
      <div class="app-panel">
        <h3 style="margin-bottom:14px">内容库概览</h3>
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-num">${st.total || 0}</div><div class="stat-label">内容总量</div></div>
          <div class="stat-card"><div class="stat-num">${st.city_count || 0}</div><div class="stat-label">覆盖城市</div></div>
          <div class="stat-card"><div class="stat-num">${total}</div><div class="stat-label">当前筛选结果</div></div>
        </div>
        <div class="note-chips">${srcChips}</div>
        <p class="note-tip">小红书 / 抖音均未开放通用旅游内容接口（需企业资质），所以这里走「人工导入 → 落库检索 → 导出知识库」的合规通道。导入后点「导出到知识库」，内容即可被智能助手检索引用。</p>
      </div>

      <div class="app-panel" style="margin-top:18px" id="note-form-panel">
        <h4 style="margin-bottom:14px">${e.id ? "编辑内容" : "导入一条攻略"}</h4>
        <div class="note-form">
          <select id="note-f-source" class="app-select">
            ${NOTE_SOURCES.map((s) => `<option value="${s.v}"${(e.source || "manual") === s.v ? " selected" : ""}>${s.t}</option>`).join("")}
          </select>
          <input id="note-f-city" class="app-input" type="text" placeholder="城市（如 北京，可留空）" value="${escapeHtml(e.city || "")}" />
          <input id="note-f-title" class="app-input" type="text" placeholder="标题（留空取正文前 40 字）" value="${escapeHtml(e.title || "")}" />
          <input id="note-f-tags" class="app-input" type="text" placeholder="标签，逗号分隔" value="${escapeHtml(e.tags || "")}" />
          <input id="note-f-author" class="app-input" type="text" placeholder="原作者" value="${escapeHtml(e.author || "")}" />
          <input id="note-f-url" class="app-input" type="text" placeholder="原文链接" value="${escapeHtml(e.url || "")}" />
        </div>
        <textarea id="note-f-content" class="note-textarea" placeholder="粘贴攻略正文…（上限 20000 字）">${escapeHtml(e.content || "")}</textarea>
        <div class="modal-err" id="note-err"></div>
        <div class="note-form-actions">
          <button class="btn btn-accent" id="note-save">${e.id ? "保存修改" : "导入内容"}</button>
          <button class="btn btn-primary" id="note-cancel"${e.id ? "" : " hidden"}>取消编辑</button>
          <button class="btn btn-primary" id="note-export">导出到知识库</button>
        </div>
      </div>

      <div class="app-panel" style="margin-top:18px">
        <h4 style="margin-bottom:14px">内容列表（${total}）</h4>
        <div class="app-toolbar">
          <select id="note-flt-city" class="app-select">${cityOpts}</select>
          <select id="note-flt-source" class="app-select">${srcOpts}</select>
          <input id="note-flt-q" class="app-input" type="text" placeholder="搜索标题 / 正文 / 标签" value="${escapeHtml(noteView.q)}" />
          <button class="btn btn-accent" id="note-search">搜索</button>
          <button class="btn btn-primary" id="note-reset">重置</button>
        </div>
        <div class="note-list">${items.length ? rows : emptyHtml}</div>
        ${pageCount > 1 ? `<div class="note-pager">
          <button class="btn btn-primary" data-page="${noteView.page - 1}"${noteView.page <= 0 ? " disabled" : ""}>上一页</button>
          <span class="note-pager-info">第 ${noteView.page + 1} / ${pageCount} 页 · 共 ${total} 条</span>
          <button class="btn btn-primary" data-page="${noteView.page + 1}"${noteView.page >= pageCount - 1 ? " disabled" : ""}>下一页</button>
        </div>` : ""}
      </div>`;

    const $ = (sel) => host.querySelector(sel);

    // 筛选：城市 / 来源改变立即生效；关键词支持回车
    $("#note-flt-city").addEventListener("change", (ev) => { noteView.city = ev.currentTarget.value; noteView.page = 0; renderNotesTab(host); });
    $("#note-flt-source").addEventListener("change", (ev) => { noteView.source = ev.currentTarget.value; noteView.page = 0; renderNotesTab(host); });
    $("#note-search").addEventListener("click", () => { noteView.q = $("#note-flt-q").value.trim(); noteView.page = 0; renderNotesTab(host); });
    $("#note-flt-q").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { noteView.q = ev.currentTarget.value.trim(); noteView.page = 0; renderNotesTab(host); } });
    $("#note-reset").addEventListener("click", () => { noteView.city = ""; noteView.source = ""; noteView.q = ""; noteView.page = 0; renderNotesTab(host); });

    // 导入 / 保存修改
    const err = $("#note-err");
    $("#note-save").addEventListener("click", async () => {
      err.textContent = "";
      const payload = {
        source: $("#note-f-source").value,
        city: $("#note-f-city").value.trim(),
        title: $("#note-f-title").value.trim(),
        tags: $("#note-f-tags").value.trim(),
        author: $("#note-f-author").value.trim(),
        url: $("#note-f-url").value.trim(),
        content: $("#note-f-content").value.trim(),
      };
      if (!payload.content) { err.textContent = "正文不能为空"; return; }
      const btn = $("#note-save");
      const editing = noteView.editing;
      btn.disabled = true;
      const r = editing
        ? await apiPut("/api/notes/" + encodeURIComponent(editing.id), payload)
        : await apiPost("/api/notes", payload);
      btn.disabled = false;
      if (!r.ok) { err.textContent = r.data.detail || "保存失败"; return; }
      toast(editing ? "已保存修改" : "已导入");
      noteView.editing = null;
      renderNotesTab(host);
    });

    $("#note-cancel").addEventListener("click", () => { noteView.editing = null; renderNotesTab(host); });

    // 导出到知识库并重建索引（首次会加载向量模型，较慢）
    $("#note-export").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget;
      btn.disabled = true;
      btn.textContent = "⏳ 导出并重建索引中…";
      const r = await apiPost("/api/notes/export-to-kb", {});
      btn.disabled = false;
      btn.textContent = "导出到知识库";
      toast(r.ok ? (r.data.message || "导出完成") : (r.data.detail || "导出失败"));
    });

    // 查看全文 / 编辑 / 删除
    host.querySelectorAll(".note-view").forEach((b) => b.addEventListener("click", (ev) => {
      const row = ev.currentTarget.closest(".note-row");
      const full = row && row.querySelector(".note-full");
      if (!full) return;
      full.hidden = !full.hidden;
      ev.currentTarget.textContent = full.hidden ? "查看" : "收起";
    }));

    host.querySelectorAll(".note-edit").forEach((b) => b.addEventListener("click", (ev) => {
      noteView.editing = byId[ev.currentTarget.dataset.id] || null;
      renderNotesTab(host);
      const panel = document.getElementById("note-form-panel");
      if (panel && panel.scrollIntoView) panel.scrollIntoView({ behavior: "smooth", block: "center" });
    }));

    host.querySelectorAll(".note-del").forEach((b) => b.addEventListener("click", async (ev) => {
      const id = ev.currentTarget.dataset.id;
      const item = byId[id];
      const name = (item && item.title) || id;
      if (typeof window.confirm === "function" && !window.confirm(`确定删除「${name}」？该操作不可撤销。`)) return;
      const r = await api("DELETE", "/api/notes/" + encodeURIComponent(id));
      if (!r.ok) { toast(r.data.detail || "删除失败"); return; }
      if (noteView.editing && noteView.editing.id === id) noteView.editing = null;
      toast("已删除");
      renderNotesTab(host);
    }));

    // 分页
    host.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", (ev) => {
      const p = Number(ev.currentTarget.dataset.page);
      if (!isNaN(p) && p >= 0 && p < pageCount) { noteView.page = p; renderNotesTab(host); }
    }));
  }

  /* ---------- 知识库管理页 ---------- */
  async function initKbPage() {
    const container = document.getElementById("kb-app");
    if (!container) return;
    const user = authState();
    if (!user || user.role !== "admin") { container.innerHTML = `<div class="app-gate"><h2>权限不足</h2><p>仅管理员可访问此页面</p></div>`; return; }
    container.innerHTML = `<div class="app-panel"><div class="skeleton" style="height:200px"></div></div>`;
    const r = await apiGet("/api/knowledge/documents");
    if (!r.ok) {
      container.innerHTML = `<div class="app-gate"><h2>无法加载知识库</h2><p>${escapeHtml(r.data.detail || "需要管理员权限，请重新登录")}</p></div>`;
      return;
    }
    const docs = (r.data || []);
    // 这一页只列「精编攻略」（根目录，可手改）。导览档与清单档是脚本生成的，
    // 手改会被下次重跑覆盖，所以不列出来 —— 但标题只写「知识库文档 (7)」会让人
    // 以为整个攻略库就 7 篇，而点「重建索引」又报 356 篇。这里把另外两档的
    // 城数显式标出来（数字走接口，不写死）。
    let tierHint = "";
    try {
      const cov = await apiGet("/api/knowledge/coverage");
      if (cov.ok && cov.data) {
        const g = cov.data.guided_count || 0, l = cov.data.list_count || 0;
        tierHint = `另有导览档 ${g} 城、清单档 ${l} 城，由脚本生成（改 geo-data.js / 快照后重跑脚本），不在此处编辑；重建索引对全部文档生效。`;
      }
    } catch (e) { /* 提示条拿不到不影响主流程 */ }
    // 「重建索引」只渲染一份，位置跟着状态走：有文档时在工具栏，0 篇时放进空态块里
    // （读到这里就能直接点）。两处并存会有两个同 id 节点，也会让人以为一个是增量一个是全量。
    const rebuildHtml = () => `<button class="btn btn-accent" id="kb-rebuild">🔄 重建索引</button>`;
    // 0 篇时不能只剩一个「精编攻略 (0)」：那是把「还没开始」和「刚被清空」混成同一块
    // 空白，用户不知道该做什么。这里给一句「为什么需要它」+ 一个当场能点的入口。
    // 用站点既有的 .app-empty（与收藏空态、行程空态同一套：图标 + h3 + p + .trip-sample-note
    // 副标），标题走 --ink、正文走 --muted，不出现任何告警红。
    const listHtml = docs.length
      ? `<div class="doc-list">${docs.map(d => `
          <div class="doc-row">
            <span>${escapeHtml(d.name)}</span>
            <span style="color:var(--muted);font-size:var(--fs-sm)">${(d.size_bytes/1024).toFixed(1)} KB · ${escapeHtml(d.modified)}</span>
            <button class="btn btn-primary del-doc" data-name="${escapeHtml(d.name)}">删除</button>
          </div>`).join("")}</div>`
      : `<div class="app-empty">
          <div style="font-size:52px">📚</div>
          <h3>精编攻略还是空的</h3>
          <p>把 .md / .txt 攻略放进 knowledge_base/ 目录，重建索引后 AI 回答时就会引用它</p>
          ${rebuildHtml()}
          <p class="trip-sample-note">重建会把导览档与清单档一起重新灌进索引</p>
        </div>`;
    container.innerHTML = `
      <div class="app-panel">
        <h3 style="margin-bottom:6px">精编攻略 (${docs.length})</h3>
        ${tierHint ? `<p style="color:var(--muted);font-size:.82rem;margin-bottom:12px">${escapeHtml(tierHint)}</p>` : `<div style="height:6px"></div>`}
        ${docs.length ? `<div class="kb-actions app-toolbar">${rebuildHtml()}</div>` : ""}
        ${listHtml}
      </div>`;
    container.querySelector("#kb-rebuild").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.textContent = "⏳ 重建中（首次需加载向量模型）…";
      const rr = await apiPost("/api/knowledge/rebuild", {});
      if (rr.ok) toast(`索引重建完成：${rr.data.documents} 篇文档 / ${rr.data.chunks} 个片段`);
      else toast(rr.data.detail || "重建失败");
      initKbPage();
    });
    container.querySelectorAll(".del-doc").forEach(b => b.addEventListener("click", async (e) => {
      const name = e.currentTarget.dataset.name;
      const rr = await api("DELETE", "/api/knowledge/documents/" + encodeURIComponent(name));
      if (!rr.ok) { toast(rr.data.detail || "删除失败"); return; }
      toast("已删除，请点击「重建索引」使其生效");
      initKbPage();
    }));
  }

  /* ---------- 登录弹窗（注入到 index.html） ---------- */
  function initLoginModal() {
    if (document.getElementById("login-modal")) return;
    const div = document.createElement("div");
    div.id = "login-modal";
    div.className = "modal";
    div.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-card">
        <h3 id="modal-title">登录</h3>
        <input id="mod-user" class="app-input" type="text" placeholder="用户名" autocomplete="username" />
        <input id="mod-pwd" class="app-input" type="password" placeholder="密码" autocomplete="current-password" />
        <input id="mod-pwd2" class="app-input" type="password" placeholder="确认密码（注册时）" style="display:none" />
        <div class="modal-err" id="mod-err"></div>
        <div class="modal-actions">
          <button class="btn btn-primary" id="mod-submit">登录 <span class="fill"></span></button>
          <button class="btn btn-ghost" id="mod-toggle">去注册</button>
        </div>
        <button class="modal-close" aria-label="关闭">&times;</button>
      </div>`;
    document.body.appendChild(div);
    let mode = "login";
    const title = div.querySelector("#modal-title");
    const submit = div.querySelector("#mod-submit");
    const toggle = div.querySelector("#mod-toggle");
    const pwd2 = div.querySelector("#mod-pwd2");
    const err = div.querySelector("#mod-err");

    function open() { div.classList.add("open"); document.getElementById("mod-user").focus(); }
    function close() { div.classList.remove("open"); err.textContent = ""; }
    div.querySelector(".modal-backdrop").addEventListener("click", close);
    div.querySelector(".modal-close").addEventListener("click", close);

    toggle.addEventListener("click", () => {
      mode = mode === "login" ? "register" : "login";
      title.textContent = mode === "login" ? "登录" : "注册";
      submit.textContent = mode === "login" ? "登录" : "注册";
      toggle.textContent = mode === "login" ? "去注册" : "去登录";
      pwd2.style.display = mode === "register" ? "block" : "none";
      err.textContent = "";
    });

    submit.addEventListener("click", async () => {
      err.textContent = "";
      const u = document.getElementById("mod-user").value.trim();
      const p = document.getElementById("mod-pwd").value.trim();
      if (!u || !p) { err.textContent = "请填写用户名和密码"; return; }
      if (mode === "register") {
        const p2 = document.getElementById("mod-pwd2").value.trim();
        if (p !== p2) { err.textContent = "两次密码不一致"; return; }
        const r = await apiPost("/api/auth/register", { username: u, password: p });
        if (!r.ok) { err.textContent = r.data.detail || r.data.message || "注册失败"; return; }
        setAuth(r.data.token, { username: r.data.username, role: r.data.role });
        if (location.hash) history.replaceState(null, "", location.pathname + location.search);
        close(); location.reload();
      } else {
        const r = await apiPost("/api/auth/login", { username: u, password: p });
        if (!r.ok) { err.textContent = r.data.detail || r.data.message || "登录失败"; return; }
        setAuth(r.data.token, { username: r.data.username, role: r.data.role });
        if (location.hash) history.replaceState(null, "", location.pathname + location.search);
        close(); location.reload();
      }
    });

    // 通过 hash 打开（已登录则不再弹出）
    if (location.hash === "#login" && !authState()) open();
    // 首页 CTA 绑定（已登录则不再弹出登录框）
    document.querySelectorAll("a[href='#login']").forEach(a => a.addEventListener("click", (e) => { e.preventDefault(); if (!authState()) open(); }));

    // 拉取站点选项：公网部署关闭开放注册时，隐藏「去注册」入口并给出说明，
    // 避免用户点了半天最后拿到一个 403。
    apiGet("/api/auth/options").then((r) => {
      if (!r.ok || r.data.allow_registration !== false) return;
      toggle.style.display = "none";
      const hint = document.createElement("div");
      hint.className = "modal-hint";
      hint.textContent = "本站已关闭开放注册，需要账号请联系管理员开通。";
      div.querySelector(".modal-actions").insertAdjacentElement("afterend", hint);
    }).catch(() => {});
  }

  /* ---------- 统一初始化 ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    injectAppNav();
    initLoginModal();
    initChatPage();
    initMapPage();
    initTransitPage();
    initTripsPage();
    initFavoritesPage();
    initAdminPage();
    initKbPage();
  });
})();
