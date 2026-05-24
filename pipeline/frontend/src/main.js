import { ensureAuth, getIdToken } from '/src/auth.js';

/* global Vue, Vuetify */
const sfcLoader = window["vue3-sfc-loader"];

const options = {
  moduleCache: { vue: Vue },
  async getFile(url) {
    const res = await fetch(url);
    if (!res.ok) throw Object.assign(new Error(res.statusText + " " + url), { res });
    return { getContentData: (asBinary) => (asBinary ? res.arrayBuffer() : res.text()) };
  },
  addStyle(textContent) {
    const style = Object.assign(document.createElement("style"), { textContent });
    const ref = document.head.getElementsByTagName("style")[0] || null;
    document.head.insertBefore(style, ref);
  },
};

(async () => {
  await ensureAuth(); // redirects to Cognito if not logged in; blocks on /callback until tokens stored

  // Intercept fetch for same-origin and API requests to attach the Bearer token automatically.
  // External calls (OpenFoodFacts, Nominatim, Cognito token endpoint) are not intercepted.
  const _fetch = window.fetch.bind(window);
  const ownOrigin = window.location.origin;
  let apiOrigin = '';
  if (window.CTBUS_API && window.CTBUS_API !== 'CTBUS_API_PLACEHOLDER') {
    try { apiOrigin = new URL(window.CTBUS_API).origin; } catch (_) {}
  }
  window.fetch = async function (url, opts = {}) {
    const s = typeof url === 'string' ? url : (url?.url ?? String(url));
    if (s.startsWith(ownOrigin) || (apiOrigin && s.startsWith(apiOrigin))) {
      const token = await getIdToken();
      if (token) opts = { ...opts, headers: { Authorization: `Bearer ${token}`, ...(opts.headers || {}) } };
    }
    return _fetch(url, opts);
  };

  window._sfcOptions = options;
  const [App, DashboardView, WeekView, MonthView, RecipesView, EntryView, UsageView] = await Promise.all([
    sfcLoader.loadModule("/src/App.vue", options),
    sfcLoader.loadModule("/src/views/Dashboard.vue", options),
    sfcLoader.loadModule("/src/views/Week.vue", options),
    sfcLoader.loadModule("/src/views/Month.vue", options),
    sfcLoader.loadModule("/src/views/Recipes.vue", options),
    sfcLoader.loadModule("/src/views/Entry.vue", options),
    sfcLoader.loadModule("/src/views/Usage.vue", options),
  ]);

  const vuetify = Vuetify.createVuetify({ theme: { defaultTheme: "light" } });
  const app = Vue.createApp(App).use(vuetify);
  app.component("DashboardView", DashboardView);
  app.component("WeekView", WeekView);
  app.component("MonthView", MonthView);
  app.component("RecipesView", RecipesView);
  app.component("EntryView", EntryView);
  app.component("UsageView", UsageView);
  app.mount("#app");
})();
