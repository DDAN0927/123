/* ==========================================================================
   景点库页 · Vue 3 + Element Plus
   条件检索 / 偏好标签匹配推荐 / 一键加入行程
   ========================================================================== */
(function () {
  "use strict";

  const TOKEN_KEY = "tc_token";

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    const t = token();
    if (t) opts.headers["X-Auth-Token"] = t;
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    try {
      const r = await fetch(path, opts);
      const text = await r.text();
      let data = {};
      if (text) {
        try { data = JSON.parse(text); } catch (e) { data = { detail: "响应格式异常" }; }
      }
      return { ok: r.ok, status: r.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { detail: "网络异常，请稍后重试" } };
    }
  }

  /** 401 统一回登录页：这个页面所有数据都要登录才有。 */
  function requireLogin(r) {
    if (r.status === 401) {
      // 401 直接就地渲染登录闸门（与 trips/favorites 的 .app-gate 同款）。
      // 旧做法是 600ms 后整页跳 index.html#login —— 用户先看到完整落地内容再闪跳一次
      // （ux-report P2#8）；闸门留在本页，无闪跳，登录后回到原页还能保留筛选状态。
      const host = document.getElementById("spots-app");
      if (host) {
        host.innerHTML = '<div class="app-gate"><h2>请先登录</h2><p>登录后浏览 355 城景点库</p>'
          + '<a href="index.html#login" class="btn btn-primary">去登录</a></div>';
      }
      return true;
    }
    return false;
  }

  const { createApp, ref, computed, onMounted } = Vue;
  const { ElMessage } = ElementPlus;

  createApp({
    setup() {
      const meta = ref({ categories: [], tags: [], cities: [], total: 0 });
      const list = ref([]);
      const recommend = ref([]);
      const total = ref(0);
      const page = ref(1);
      const size = ref(12);
      const loading = ref(false);
      const prefs = ref([]);
      const prefDirty = ref(false);
      const savingPrefs = ref(false);
      const trips = ref([]);

      const filters = ref({ city: "", q: "", category: "", tag: "", free: "", maxMinutes: 0 });

      const dialog = ref({ visible: false, spotName: "", tripId: "", day: 1, slot: "上午", saving: false });
      const dialogDays = computed(() => {
        const t = trips.value.find((x) => x.id === dialog.value.tripId);
        return t ? t.days : 1;
      });

      // ---- 管理员维护（任务书 3(2)：景点库维护）
      const isAdmin = ref(false);
      const edit = ref({ visible: false, id: null, saving: false, form: blankForm() });

      function blankForm() {
        return {
          city: "", name: "", category: "地标", tags: [],
          ticket_price: null, suggest_minutes: null,
          address: "", rating: "", open_time: ""
        };
      }

      function openCreate() {
        edit.value = { visible: true, id: null, saving: false, form: blankForm() };
      }

      function openEdit(s) {
        edit.value = {
          visible: true,
          id: s.id,
          saving: false,
          form: {
            city: s.city, name: s.name, category: s.category || "地标",
            tags: s.tags || [],
            ticket_price: s.ticket_price === null || s.ticket_price === undefined ? null : Number(s.ticket_price),
            suggest_minutes: s.suggest_minutes || null,
            address: s.address || "", rating: s.rating || "", open_time: s.open_time || ""
          }
        };
      }

      async function saveSpot() {
        const f = edit.value.form;
        if (!f.city.trim() || !f.name.trim()) {
          ElMessage.warning("城市和景点名都要填");
          return;
        }
        edit.value.saving = true;
        const body = {
          city: f.city.trim(),
          name: f.name.trim(),
          category: f.category || "地标",
          tags: f.tags || [],
          ticket_price: f.ticket_price === "" ? null : f.ticket_price,
          suggest_minutes: f.suggest_minutes === "" ? null : f.suggest_minutes,
          address: f.address || null,
          rating: f.rating || null,
          open_time: f.open_time || null
        };
        const r = edit.value.id
          ? await api("PUT", "/api/spots/" + edit.value.id, body)
          : await api("POST", "/api/spots", body);
        edit.value.saving = false;
        if (requireLogin(r)) return;
        if (!r.ok) {
          ElMessage.error((r.data && r.data.detail) || "保存失败");
          return;
        }
        edit.value.visible = false;
        ElMessage.success(edit.value.id ? "已更新" : "已新增");
        await loadMeta();
        await search();
      }

      async function removeSpot(s) {
        if (!confirm(`删除景点「${s.name}」？`)) return;
        const r = await api("DELETE", "/api/spots/" + s.id);
        if (requireLogin(r)) return;
        if (!r.ok) {
          ElMessage.error((r.data && r.data.detail) || "删除失败");
          return;
        }
        ElMessage.success("已删除");
        await search();
      }

      function priceText(v) {
        if (v === null || v === undefined) return "未录入";
        return Number(v) === 0 ? "免费" : "¥" + Number(v);
      }

      function timeText(min) {
        if (!min) return "—";
        const h = min / 60;
        return (h >= 1 ? (Number.isInteger(h) ? h : h.toFixed(1)) + " 小时" : min + " 分钟");
      }

      async function loadMeta() {
        const r = await api("GET", "/api/spots/meta");
        if (requireLogin(r)) return;
        if (r.ok) meta.value = r.data;
      }

      async function loadPrefs() {
        const r = await api("GET", "/api/auth/preferences");
        if (requireLogin(r)) return;
        if (r.ok) prefs.value = r.data.tags || [];
        prefDirty.value = false;
      }

      function togglePref(t) {
        const i = prefs.value.indexOf(t);
        if (i >= 0) {
          prefs.value.splice(i, 1);
        } else {
          if (prefs.value.length >= 8) {
            ElMessage.warning("最多选 8 个偏好");
            return;
          }
          prefs.value.push(t);
        }
        prefDirty.value = true;
      }

      async function savePrefs() {
        savingPrefs.value = true;
        const r = await api("PUT", "/api/auth/preferences", { tags: prefs.value });
        savingPrefs.value = false;
        if (requireLogin(r)) return;
        if (!r.ok) {
          ElMessage.error((r.data && r.data.detail) || "保存失败");
          return;
        }
        prefs.value = r.data.tags || [];
        prefDirty.value = false;
        ElMessage.success("偏好已保存");
        loadRecommend();
      }

      async function search(p) {
        if (typeof p === "number") page.value = p;
        loading.value = true;
        const f = filters.value;
        const qs = new URLSearchParams();
        if (f.city) qs.set("city", f.city);
        if (f.q) qs.set("q", f.q);
        if (f.category) qs.set("category", f.category);
        if (f.tag) qs.set("tag", f.tag);
        if (f.free === "free") qs.set("free", "true");
        if (f.free === "paid") qs.set("free", "false");
        if (f.maxMinutes) qs.set("max_minutes", String(f.maxMinutes));
        qs.set("page", String(page.value));
        qs.set("size", String(size.value));
        const r = await api("GET", "/api/spots?" + qs.toString());
        loading.value = false;
        if (requireLogin(r)) return;
        if (!r.ok) {
          ElMessage.error((r.data && r.data.detail) || "查询失败");
          return;
        }
        list.value = r.data.items || [];
        total.value = r.data.total || 0;
      }

      async function loadRecommend() {
        const qs = new URLSearchParams();
        if (filters.value.city) qs.set("city", filters.value.city);
        qs.set("limit", "6");
        const r = await api("GET", "/api/spots/recommend?" + qs.toString());
        if (requireLogin(r)) return;
        if (r.ok) recommend.value = r.data.items || [];
      }

      function reset() {
        filters.value = { city: "", q: "", category: "", tag: "", free: "", maxMinutes: 0 };
        search(1);
        loadRecommend();
      }

      async function openAdd(spot) {
        dialog.value = { visible: true, spotName: spot.name, tripId: "", day: 1, slot: "上午", saving: false };
        if (!trips.value.length) {
          const r = await api("GET", "/api/trips");
          if (requireLogin(r)) return;
          trips.value = (r.ok && r.data.trips) || [];
        }
        if (trips.value.length) {
          dialog.value.tripId = trips.value[0].id;
        }
      }

      async function confirmAdd() {
        if (!dialog.value.tripId) {
          ElMessage.warning("先选一个行程（没有的话去「我的行程」建一个）");
          return;
        }
        dialog.value.saving = true;
        const r = await api("POST", "/api/trips/" + encodeURIComponent(dialog.value.tripId) + "/items", {
          title: dialog.value.spotName,
          day_index: dialog.value.day,
          slot: dialog.value.slot,
          kind: "spot"
        });
        dialog.value.saving = false;
        if (requireLogin(r)) return;
        if (!r.ok) {
          ElMessage.error((r.data && r.data.detail) || "加入失败");
          return;
        }
        dialog.value.visible = false;
        ElMessage.success("已加入第 " + dialog.value.day + " 天");
      }

      onMounted(async () => {
        try {
          const u = JSON.parse(localStorage.getItem("tc_user") || "{}");
          isAdmin.value = u.role === "admin";
        } catch (e) {
          isAdmin.value = false;
        }
        await Promise.all([loadMeta(), loadPrefs()]);
        // 行程地图「未上图」弹窗带 ?city= 跳过来：预填城市再查，落点即该市景点列表
        const urlCity = new URLSearchParams(location.search).get("city");
        if (urlCity && ((meta.value.cities || []).includes(urlCity) || !meta.value.cities)) {
          filters.value.city = urlCity;
        }
        await Promise.all([search(1), loadRecommend()]);
      });

      return {
        meta, list, recommend, total, page, size, loading, prefs, prefDirty, savingPrefs,
        filters, dialog, dialogDays, trips, isAdmin, edit,
        priceText, timeText, togglePref, savePrefs, search, reset, openAdd, confirmAdd,
        openCreate, openEdit, saveSpot, removeSpot
      };
    }
  }).use(ElementPlus).mount("#spots-app");
})();
