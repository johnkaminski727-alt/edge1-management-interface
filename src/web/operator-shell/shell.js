(() => {
  "use strict";
  const script = document.currentScript;
  if (!script) return;
  const registryUrl = script.dataset.registry;
  const activeId = script.dataset.module || "";
  const mount = document.querySelector("#wwcx-operator-shell");
  if (!registryUrl || !mount) return;
  const recentKey = "wwcx.edge1.operator.recent.v1";
  const favoriteKey = "wwcx.edge1.operator.favorites.v1";

  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const readIds = (key) => {
    try { const value = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(value) ? value.filter((item) => typeof item === "string").slice(0, 20) : []; }
    catch (_) { return []; }
  };
  const writeIds = (key, ids) => { try { localStorage.setItem(key, JSON.stringify(ids.slice(0, 20))); } catch (_) {} };
  function remember(id) {
    if (!id) return;
    const prior = readIds(recentKey);
    writeIds(recentKey, [id, ...prior.filter((item) => item !== id)].slice(0, 8));
  }
  function toggleFavorite(id) {
    const prior = readIds(favoriteKey);
    writeIds(favoriteKey, prior.includes(id) ? prior.filter((item) => item !== id) : [id, ...prior]);
  }

  function render(registry) {
    const modules = (registry.modules || []).filter((item) => item.availability === "accepted_live" && typeof item.browser_route === "string" && item.browser_route.startsWith("/"));
    document.documentElement.classList.add("wwcx-shell-active");
    mount.className = "wwcx-operator-shell";
    const bar = make("div", "wwcx-shell-bar");
    const brand = make("div", "wwcx-shell-brand", "WW.CX");
    brand.append(make("small", "", "Edge1 Operator"));
    const mobile = make("button", "wwcx-shell-action wwcx-shell-mobile", "Menu");
    mobile.type = "button";
    mobile.setAttribute("aria-expanded", "false");
    mobile.setAttribute("aria-controls", "wwcx-shell-drawer");
    const crumb = make("div", "wwcx-shell-breadcrumb", "Edge1 / " + ((modules.find((item) => item.id === activeId) || {}).label || "Operator"));
    const nav = make("nav", "wwcx-shell-nav");
    nav.setAttribute("aria-label", "Edge1 operator modules");
    for (const item of modules) {
      const link = make("a", "", item.label);
      link.href = item.browser_route;
      if (item.id === activeId) link.setAttribute("aria-current", "page");
      link.addEventListener("click", () => remember(item.id));
      nav.append(link);
    }
    const toolbox = make("div", "wwcx-shell-toolbox");
    toolbox.append(make("strong", "", "ToolBox"));
    for (const item of modules.filter((module) => module.toolbox)) {
      const link = make("a", "", item.label);
      link.href = item.browser_route;
      link.addEventListener("click", () => remember(item.id));
      toolbox.append(link);
    }
    const jump = make("button", "wwcx-shell-action", "Jump to…  Ctrl/⌘ K");
    jump.type = "button";
    const safety = make("span", "wwcx-shell-safety", "Read-only · mutations disabled · production traffic unauthorized");
    bar.append(brand, mobile, crumb, nav, toolbox, make("span", "wwcx-shell-spacer"), jump, safety);
    mount.replaceChildren(bar);

    const drawer = make("nav", "wwcx-shell-drawer");
    drawer.id = "wwcx-shell-drawer";
    drawer.hidden = true;
    drawer.setAttribute("aria-label", "Mobile Edge1 operator modules");
    for (const item of modules) {
      const link = make("a", "", item.label);
      link.href = item.browser_route;
      if (item.id === activeId) link.setAttribute("aria-current", "page");
      link.addEventListener("click", () => remember(item.id));
      drawer.append(link);
    }
    mount.append(drawer);
    mobile.addEventListener("click", () => {
      drawer.hidden = !drawer.hidden;
      mobile.setAttribute("aria-expanded", String(!drawer.hidden));
    });

    const palette = make("div", "wwcx-shell-palette");
    palette.hidden = true;
    palette.setAttribute("role", "presentation");
    const dialog = make("div", "wwcx-shell-dialog");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", "Jump to an Edge1 module");
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Find an accepted Edge1 module";
    input.autocomplete = "off";
    const results = make("div", "wwcx-shell-results");
    dialog.append(input, results);
    palette.append(dialog);
    document.body.append(palette);

    const paint = () => {
      const q = input.value.trim().toLowerCase();
      results.replaceChildren();
      const favorites = readIds(favoriteKey);
      const recent = readIds(recentKey);
      const rank = (item) => favorites.includes(item.id) ? -200 + favorites.indexOf(item.id) : recent.includes(item.id) ? -100 + recent.indexOf(item.id) : item.sort_order;
      const matches = modules.filter((item) => (item.label + " " + item.section + " " + item.description).toLowerCase().includes(q)).sort((a, b) => rank(a) - rank(b));
      if (!matches.length) {
        results.append(make("div", "wwcx-shell-empty", "No accepted navigation target matches."));
        return;
      }
      for (const item of matches) {
        const row = make("div", "wwcx-shell-result");
        const link = make("a", "", item.label);
        link.href = item.browser_route;
        link.append(make("small", "", item.section + " · " + item.description));
        link.addEventListener("click", () => remember(item.id));
        const fav = make("button", "wwcx-shell-fav", favorites.includes(item.id) ? "★" : "☆");
        fav.type = "button";
        fav.setAttribute("aria-label", (favorites.includes(item.id) ? "Remove " : "Add ") + item.label + (favorites.includes(item.id) ? " from favourites" : " to favourites"));
        fav.setAttribute("aria-pressed", String(favorites.includes(item.id)));
        fav.addEventListener("click", () => { toggleFavorite(item.id); paint(); });
        row.append(link, fav);
        results.append(row);
      }
    };
    const open = () => { palette.hidden = false; input.value = ""; paint(); input.focus(); };
    const close = () => { palette.hidden = true; jump.focus(); };
    jump.addEventListener("click", open);
    input.addEventListener("input", paint);
    palette.addEventListener("click", (event) => { if (event.target === palette) close(); });
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); open(); return; }
      if (event.key === "Escape" && !palette.hidden) close();
    });
    remember(activeId);
  }

  fetch(registryUrl, { cache: "no-store", credentials: "same-origin" })
    .then((response) => { if (!response.ok) throw new Error("navigation registry unavailable"); return response.json(); })
    .then((registry) => {
      const safety = registry && registry.safety || {};
      if (safety.navigation_grants_authorization !== false || safety.generic_execution_authorized !== false || safety.production_traffic_authorized !== false || safety.mutations_enabled !== false || safety.unknown_status_is_healthy !== false) throw new Error("navigation safety contract rejected");
      render(registry);
    })
    .catch(() => {
      document.documentElement.classList.add("wwcx-shell-active");
      mount.className = "wwcx-operator-shell";
      const bar = make("div", "wwcx-shell-bar");
      bar.append(make("div", "wwcx-shell-brand", "WW.CX Edge1 Operator"), make("span", "wwcx-shell-spacer"), make("span", "wwcx-shell-safety", "Navigation unavailable · safety state unknown"));
      mount.replaceChildren(bar);
    });
})();
