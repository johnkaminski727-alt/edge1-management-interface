(() => {
  "use strict";
  const script = document.currentScript;
  if (!script) return;
  const registryUrl = script.dataset.registry;
  const activeId = script.dataset.module || "";
  const mount = document.querySelector("#wwcx-operator-shell");
  if (!registryUrl || !mount) return;

  const recentKey = "wwcx.edge1.operator.recent.v2";
  const favoriteKey = "wwcx.edge1.operator.favorites.v2";
  const collapseKey = "wwcx.edge1.operator.rail-collapsed.v1";
  const iconPaths = {
    home:["M3 11.5 12 4l9 7.5","M5 10.5V20h14v-9.5","M9 20v-6h6v6"],
    contacts:["M15 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2","M8.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8","M17 11a3 3 0 1 0 0-6","M22 21v-2a4 4 0 0 0-3-3.87"],
    sparkles:["M12 3l1.2 3.3L16.5 7.5l-3.3 1.2L12 12l-1.2-3.3-3.3-1.2 3.3-1.2L12 3z","M19 13l.8 2.2L22 16l-2.2.8L19 19l-.8-2.2L16 16l2.2-.8L19 13z","M5 14l.7 1.8L7.5 16.5l-1.8.7L5 19l-.7-1.8-1.8-.7 1.8-.7L5 14z"],
    "phone-book":["M5 3h13a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5z","M5 3v18","M9 8a2 2 0 1 0 4 0 2 2 0 0 0-4 0","M8 15c.7-2 5.3-2 6 0"],
    shield:["M12 3l8 3v5c0 5-3.3 8.5-8 10-4.7-1.5-8-5-8-10V6l8-3z","M9 12l2 2 4-4"],
    firewall:["M3 5h18v14H3z","M3 10h18","M3 15h18","M8 5v5","M16 5v5","M11 10v5","M6 15v4","M17 15v4"],
    network:["M6 6h.01","M18 6h.01","M12 18h.01","M6 6l6 12","M18 6l-6 12","M6 6h12"],
    route:["M4 6h10a4 4 0 0 1 4 4v0a4 4 0 0 1-4 4H8a4 4 0 0 0-4 4","M7 15l-3 3 3 3","M17 3l3 3-3 3"],
    dns:["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z","M3 12h18","M12 3c3 3 3 15 0 18","M12 3c-3 3-3 15 0 18"],
    bitcoin:["M9 4h5a3 3 0 0 1 0 6H9h6a3 3 0 0 1 0 6H9","M11 2v4","M14 2v4","M11 16v4","M14 16v4","M7 4h2v12H7"],
    pickaxe:["M14 4l6 6","M13 5c-3-2-6-1-9 2l2 2c2-2 4-2 6-1","M15 9L6 20"],
    clock:["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z","M12 7v5l3 2"],
    release:["M4 7h11","M12 4l3 3-3 3","M20 17H9","M12 14l-3 3 3 3"],
    backup:["M7 18H6a4 4 0 0 1-.7-7.94A6 6 0 0 1 17 8a5 5 0 0 1 1 9.9","M12 20V11","M9 14l3-3 3 3"],
    "mail-shield":["M3 6h13v9H3z","M3 7l6.5 5L16 7","M18 11l4 1.5v3c0 2.4-1.6 4.1-4 5-2.4-.9-4-2.6-4-5v-3L18 11z"],
    mail:["M3 5h18v14H3z","M3 7l9 7 9-7"],
    messages:["M4 5h16v11H8l-4 4z","M8 9h8","M8 12h5"],
    sms:["M4 5h16v13H8l-4 3z","M8 9h8","M8 13h6"],
    "phone-call":["M7 4l3 4-2 2c1.5 3 3 4.5 6 6l2-2 4 3-2 4c-1 1-3 1-5 0-5-2-9-6-11-11-1-2-1-4 0-5l4-1z","M15 5c2 0 4 2 4 4","M15 2c4 0 7 3 7 7"],
    link:["M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1","M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"],
    newspaper:["M4 4h14v16H4z","M18 7h2v11a2 2 0 0 1-2 2","M7 8h8","M7 12h3","M12 12h3","M7 16h8"],
    brain:["M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 0V7a3 3 0 0 0-3-3z","M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 0V7a3 3 0 0 1 3-3z"],
    cookie:["M20 13a8 8 0 1 1-9-9 4 4 0 0 0 5 5 4 4 0 0 0 4 4z","M8 14h.01","M9 8h.01","M14 16h.01"],
    settings:["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z","M12 2v3","M12 19v3","M4.9 4.9L7 7","M17 17l2.1 2.1","M2 12h3","M19 12h3","M4.9 19.1L7 17","M17 7l2.1-2.1"],
    navigation:["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z","M15 8l-2 6-6 2 2-6 6-2z"],
    change:["M4 7h10","M18 7h2","M14 4v6","M4 17h2","M10 17h10","M10 14v6"],
    history:["M4 12a8 8 0 1 0 2-5.3","M4 5v5h5","M12 8v5l3 2"],
    circle:["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"]
  };
  const fallbackIcon = {Security:"shield", Network:"network", "Email & Messaging":"mail", Communications:"messages", Tools:"settings", Operations:"home", "AI & Automation":"sparkles", Intelligence:"contacts", Configuration:"settings"};
  const moduleIcon = (item) => {
    const key = iconPaths[item.icon] ? item.icon : (fallbackIcon[item.section] || "circle");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.8");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("aria-hidden", "true");
    for (const d of iconPaths[key]) {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const readIds = (key) => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value.filter((item) => typeof item === "string").slice(0, 20) : [];
    } catch (_) { return []; }
  };
  const writeIds = (key, ids) => {
    try { localStorage.setItem(key, JSON.stringify(ids.slice(0, 20))); } catch (_) {}
  };
  const remember = (id) => {
    if (!id) return;
    const prior = readIds(recentKey);
    writeIds(recentKey, [id, ...prior.filter((item) => item !== id)].slice(0, 8));
  };
  const toggleFavorite = (id) => {
    const prior = readIds(favoriteKey);
    writeIds(favoriteKey, prior.includes(id) ? prior.filter((item) => item !== id) : [id, ...prior]);
  };
  const isLive = (item) => item.availability === "accepted_live" &&
    typeof item.browser_route === "string" && item.browser_route.startsWith("/");
  const visible = (item) => item.menu_visibility !== "hidden";
  const badgeLabel = (item) => {
    if (isLive(item)) return "Live";
    if (item.availability === "loopback_only") return "Private";
    if (item.availability === "runtime_only") return "Runtime";
    if (item.availability === "browser_acceptance_unverified") return "Pending";
    return "Upcoming";
  };

  function moduleNode(item, compact=false) {
    if (isLive(item)) {
      const link = make("a", compact ? "wwcx-shell-module compact" : "wwcx-shell-module");
      link.href = item.browser_route;
      link.dataset.moduleId = item.id;
      if (item.id === activeId) link.setAttribute("aria-current", "page");
      const icon = make("span", "wwcx-shell-module-icon");
      icon.append(moduleIcon(item));
      icon.setAttribute("aria-hidden", "true");
      link.title = item.label;
      link.append(icon);
      link.append(make("span", "wwcx-shell-module-label", item.label));
      link.append(make("span", "wwcx-shell-module-badge live", badgeLabel(item)));
      link.addEventListener("click", () => remember(item.id));
      return link;
    }
    const row = make("div", compact ? "wwcx-shell-module upcoming compact" : "wwcx-shell-module upcoming");
    row.setAttribute("aria-disabled", "true");
    row.title = item.description || "Module not yet accepted for browser navigation.";
    const icon = make("span", "wwcx-shell-module-icon");
    icon.append(moduleIcon(item));
    icon.setAttribute("aria-hidden", "true");
    row.title = item.label + " · " + (item.description || "Upcoming module");
    row.append(icon);
    row.append(make("span", "wwcx-shell-module-label", item.label));
    row.append(make("span", "wwcx-shell-module-badge", badgeLabel(item)));
    return row;
  }

  function render(registry) {
    const modules = (registry.modules || []).filter(visible).sort((a,b) => a.sort_order - b.sort_order);
    const accepted = modules.filter(isLive);
    const sections = [...new Set(modules.map((item) => item.section))];

    document.documentElement.classList.add("wwcx-shell-active");
    mount.className = "wwcx-operator-shell";

    const bar = make("div", "wwcx-shell-bar");
    const brand = make("a", "wwcx-shell-brand");
    brand.href = "/edge1-ops/status/";
    brand.setAttribute("aria-label", "WW.CX Edge1 Control Center home");
    const brandMark = make("span", "wwcx-shell-brand-mark");
    const brandImage = document.createElement("img");
    brandImage.src = "/edge1-ops/status/favicon.svg";
    brandImage.alt = "";
    brandMark.append(brandImage);
    const brandCopy = make("span", "wwcx-shell-brand-copy");
    brandCopy.append(make("strong", "", "WW.CX"), make("small", "", "Edge1 Control Center"));
    brand.append(brandMark, brandCopy);
    const brandWrap = make("div", "wwcx-shell-brand-wrap");
    brandWrap.append(brand);

    const activeModule = (modules.find((item) => item.id === activeId) || {});
    // Theme belongs to the navigation/module registry, not to a page-specific rail.
    // "inherit" preserves an application-provided theme; light/dark makes the
    // shared rail deterministic for that module.
    if (activeModule.theme === "light" || activeModule.theme === "dark") {
      document.body.dataset.edge1Theme = activeModule.theme;
    }
    const breadcrumb = make("div", "wwcx-shell-breadcrumb");
    breadcrumb.append(make("span", "wwcx-shell-breadcrumb-root", "EDGE1"));
    breadcrumb.append(make("strong", "", activeModule.label || "Control Center"));

    const mobile = make("button", "wwcx-shell-action wwcx-shell-mobile", "Menu");
    mobile.type = "button";
    mobile.setAttribute("aria-expanded", "false");
    mobile.setAttribute("aria-controls", "wwcx-shell-drawer");

    const collapse = make("button", "wwcx-shell-collapse", "‹");
    collapse.type = "button";
    collapse.setAttribute("aria-label", "Collapse Edge1 toolbar");
    collapse.setAttribute("aria-expanded", "true");
    collapse.title = "Collapse toolbar";
    let collapsed = false;
    try { collapsed = localStorage.getItem(collapseKey) === "1"; } catch (_) {}
    // A page may start compact regardless of the remembered shared preference.
    if (script.dataset.railDefault === "collapsed") collapsed = true;
    const applyCollapsed = (value, persist = true) => {
      collapsed = Boolean(value);
      document.documentElement.classList.toggle("wwcx-shell-collapsed", collapsed);
      collapse.textContent = collapsed ? "›" : "‹";
      collapse.setAttribute("aria-expanded", String(!collapsed));
      collapse.setAttribute("aria-label", collapsed ? "Expand Edge1 toolbar" : "Collapse Edge1 toolbar");
      collapse.title = collapsed ? "Expand toolbar" : "Collapse toolbar";
      if (persist) { try { localStorage.setItem(collapseKey, collapsed ? "1" : "0"); } catch (_) {} }
    };
    applyCollapsed(collapsed, false);
    collapse.addEventListener("click", () => applyCollapsed(!collapsed));
    brandWrap.append(collapse);

    const nav = make("nav", "wwcx-shell-nav");
    nav.setAttribute("aria-label", "Edge1 modules");
    for (const section of sections) {
      const group = make("section", "wwcx-shell-group");
      group.append(make("div", "wwcx-shell-section-title", section));
      for (const item of modules.filter((module) => module.section === section)) {
        group.append(moduleNode(item));
      }
      nav.append(group);
    }

    const toolbox = make("div", "wwcx-shell-toolbox");
    toolbox.append(make("strong", "", "ToolBox"));
    for (const item of accepted.filter((module) => module.toolbox)) {
      const link = make("a", "", item.label);
      link.href = item.browser_route;
      link.addEventListener("click", () => remember(item.id));
      toolbox.append(link);
    }

    const jump = make("button", "wwcx-shell-action", "Jump to…  Ctrl/⌘ K");
    jump.type = "button";
    const safety = make("span", "wwcx-shell-safety", "Read-only · mutations disabled");
    const utility = make("div", "wwcx-shell-utility");
    utility.append(jump, safety);
    bar.append(brandWrap, mobile, breadcrumb, nav, toolbox, make("span", "wwcx-shell-spacer"), utility);
    mount.replaceChildren(bar);

    if (!document.querySelector(".wwcx-control-footer")) {
      const footer = make("footer", "wwcx-control-footer");
      footer.setAttribute("role", "contentinfo");
      const footerInner = make("div", "wwcx-control-footer-inner");
      const footerBrand = make("div", "wwcx-control-footer-brand");
      footerBrand.append(make("strong", "", "WW.CX Edge1 Control Center"), make("span", "", "Authorized administrative access only."));
      const footerLegal = make("div", "wwcx-control-footer-legal");
      footerLegal.append(
        make("span", "", "Unauthorized access is prohibited. Security and administrative activity may be logged."),
        make("span", "", `© ${new Date().getFullYear()} WW.CX. All rights reserved.`)
      );
      footerInner.append(footerBrand, footerLegal);
      footer.append(footerInner);
      document.body.append(footer);
    }

    const drawer = make("nav", "wwcx-shell-drawer");
    drawer.id = "wwcx-shell-drawer";
    drawer.hidden = true;
    drawer.setAttribute("aria-label", "Mobile Edge1 modules");
    for (const section of sections) {
      drawer.append(make("div", "wwcx-shell-section-title", section));
      for (const item of modules.filter((module) => module.section === section)) {
        drawer.append(moduleNode(item, true));
      }
    }
    mount.append(drawer);

    const closeDrawer = () => {
      if (drawer.hidden) return;
      drawer.hidden = true;
      mobile.setAttribute("aria-expanded", "false");
      mobile.focus();
    };
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
    input.placeholder = "Find a live Edge1 module";
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
      const rank = (item) =>
        favorites.includes(item.id) ? -200 + favorites.indexOf(item.id) :
        recent.includes(item.id) ? -100 + recent.indexOf(item.id) : item.sort_order;
      const matches = accepted
        .filter((item) => (item.label + " " + item.section + " " + (item.description || "")).toLowerCase().includes(q))
        .sort((a,b) => rank(a) - rank(b));
      if (!matches.length) {
        results.append(make("div", "wwcx-shell-empty", "No accepted navigation target matches."));
        return;
      }
      for (const item of matches) {
        const row = make("div", "wwcx-shell-result");
        const link = make("a", "", item.label);
        link.href = item.browser_route;
        link.append(make("small", "", item.section + " · " + (item.description || "")));
        link.addEventListener("click", () => remember(item.id));
        const fav = make("button", "wwcx-shell-fav", favorites.includes(item.id) ? "★" : "☆");
        fav.type = "button";
        fav.setAttribute("aria-label", (favorites.includes(item.id) ? "Remove " : "Add ") + item.label +
          (favorites.includes(item.id) ? " from favourites" : " to favourites"));
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
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); open(); return;
      }
      if (event.key === "Escape" && !palette.hidden) { close(); return; }
      if (event.key === "Escape" && !drawer.hidden) closeDrawer();
    });
    remember(activeId);
  }

  fetch(registryUrl, { cache: "no-store", credentials: "same-origin" })
    .then((response) => {
      if (!response.ok) throw new Error("navigation registry unavailable");
      return response.json();
    })
    .then((registry) => {
      const safety = registry && registry.safety || {};
      if (
        safety.navigation_grants_authorization !== false ||
        safety.generic_execution_authorized !== false ||
        safety.production_traffic_authorized !== false ||
        safety.mutations_enabled !== false ||
        safety.unknown_status_is_healthy !== false
      ) throw new Error("navigation safety contract rejected");
      render(registry);
    })
    .catch(() => {
      document.documentElement.classList.add("wwcx-shell-active");
      mount.className = "wwcx-operator-shell";
      const bar = make("div", "wwcx-shell-bar");
      const escape = make("a", "wwcx-shell-action", "Operations Center");
      escape.href = "/edge1-ops/status/";
      bar.append(
        make("div", "wwcx-shell-brand wwcx-shell-brand-fallback", "WW.CX Edge1 Control Center"),
        escape,
        make("span", "wwcx-shell-spacer"),
        make("span", "wwcx-shell-safety", "Navigation unavailable · safety state unknown")
      );
      mount.replaceChildren(bar);
    });
})();
