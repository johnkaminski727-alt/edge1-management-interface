"use strict";

const byId = (id) => document.getElementById(id);
let groups = [];
let sources = [];
let selectedGroup = "";

async function getJson(path) {
  const response = await fetch(path, {cache: "no-store", credentials: "same-origin"});
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function text(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function fmtDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function badge(value, className = "") {
  const span = document.createElement("span");
  span.className = `badge ${className}`.trim();
  span.textContent = value;
  return span;
}

function sourceLabel(name) {
  if (!name) return "native";
  if (name === "wwcx-bootstrap") return "WW.CX Bootstrap";
  if (name === "edge1-repository") return "Edge1 Repository";
  if (name.startsWith("eternal.")) return "Eternal September";
  return name;
}

function renderGroups() {
  const root = byId("reader-groups");
  root.replaceChildren();
  for (const group of groups) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `reader-group${group.name === selectedGroup ? " active" : ""}`;
    const title = document.createElement("strong");
    title.textContent = group.name;
    const detail = document.createElement("small");
    detail.textContent = `${group.count} article${group.count === 1 ? "" : "s"} · ${group.retention_days}d retention`;
    button.append(title, detail);
    button.addEventListener("click", () => selectGroup(group.name));
    root.append(button);
  }
  if (!groups.length) root.textContent = "No newsgroups available.";
}

function renderSources() {
  const root = byId("reader-sources");
  root.replaceChildren();
  for (const source of sources) {
    const row = document.createElement("div");
    row.className = "source-card";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = sourceLabel(source.name);
    const small = document.createElement("small");
    const mapping = source.group && source.upstream_group ? `${source.upstream_group} → ${source.group}` : (source.group || source.type);
    small.textContent = mapping;
    copy.append(title, small);
    const right = document.createElement("div");
    right.className = "source-meta";
    right.append(badge(source.enabled ? "enabled" : "disabled", source.enabled ? "good" : ""));
    const state = document.createElement("small");
    state.textContent = source.cursor ? `cursor ${source.cursor} · ${source.items || 0} items` : `${source.items || 0} items`;
    right.append(state);
    row.append(copy, right);
    root.append(row);
  }
}

function renderArticles(payload) {
  const body = byId("article-list");
  body.replaceChildren();
  const rows = payload.articles || [];
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = payload.query ? "No matching articles." : "No articles in this group.";
    tr.append(td);
    body.append(tr);
    return;
  }
  for (const article of rows) {
    const tr = document.createElement("tr");
    tr.className = "article-row";
    tr.tabIndex = 0;
    const values = [article.subject, article.author, fmtDate(article.created_at_utc), sourceLabel(article.source_name)];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = text(value);
      if (index === 0) td.className = "article-subject-cell";
      tr.append(td);
    });
    const open = () => openArticle(article.id);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
    body.append(tr);
  }
}

async function loadArticles() {
  if (!selectedGroup) return;
  const query = byId("article-search").value.trim();
  const params = new URLSearchParams({limit: "200"});
  if (query) params.set("q", query);
  const payload = await getJson(`/api/comms/news/groups/${encodeURIComponent(selectedGroup)}/articles?${params}`);
  renderArticles(payload);
  byId("metric-selected").textContent = payload.group.count;
}

async function selectGroup(name) {
  selectedGroup = name;
  renderGroups();
  const group = groups.find((item) => item.name === name);
  byId("selected-group").textContent = name;
  byId("selected-description").textContent = group ? group.description : "";
  byId("article-search").value = "";
  byId("article-panel").hidden = true;
  await loadArticles();
}

function addProvenance(dl, label, value) {
  if (value === null || value === undefined || value === "") return;
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = String(value);
  dl.append(dt, dd);
}

async function openArticle(id) {
  const article = await getJson(`/api/comms/news/articles/${id}`);
  byId("article-panel").hidden = false;
  byId("article-group").textContent = article.group_name;
  byId("article-subject").textContent = article.subject;
  byId("article-meta").textContent = `${article.author} · ${fmtDate(article.date_rfc5322 || article.created_at_utc)}`;
  byId("article-body").textContent = article.body;
  byId("article-headers").textContent = JSON.stringify(article.headers || {}, null, 2);
  const provenance = byId("article-provenance");
  provenance.replaceChildren();
  addProvenance(provenance, "Source", sourceLabel(article.source_name));
  addProvenance(provenance, "Source name", article.source_name);
  addProvenance(provenance, "Source item ID", article.source_item_id);
  addProvenance(provenance, "Local Message-ID", article.message_id);
  addProvenance(provenance, "Imported", article.ingested_at_utc);
  const headers = article.headers || {};
  addProvenance(provenance, "Upstream server", headers["X-WWCX-Upstream-Server"]);
  addProvenance(provenance, "Upstream group", headers["X-WWCX-Upstream-Group"]);
  addProvenance(provenance, "Upstream article", headers["X-WWCX-Upstream-Article-Number"]);
  addProvenance(provenance, "Upstream Message-ID", headers["X-WWCX-Upstream-Message-ID"]);
  byId("article-panel").scrollIntoView({behavior: "smooth", block: "start"});
}

async function refresh() {
  const state = byId("reader-state");
  state.textContent = "Refreshing…";
  try {
    const [status, groupRows, sourceRows] = await Promise.all([
      getJson("/api/comms/status"),
      getJson("/api/comms/news/groups"),
      getJson("/api/comms/news/sources")
    ]);
    groups = groupRows;
    sources = sourceRows;
    byId("metric-groups").textContent = status.storage.newsgroups;
    byId("metric-articles").textContent = status.storage.articles;
    byId("metric-sources").textContent = sources.filter((item) => item.enabled).length;
    renderGroups();
    renderSources();
    state.textContent = "Healthy · read-only";
    if (!selectedGroup && groups.length) await selectGroup(groups[0].name);
    else if (selectedGroup) await loadArticles();
  } catch (error) {
    state.textContent = "Reader unavailable";
    byId("selected-description").textContent = error instanceof Error ? error.message : "Unknown error";
  }
}

byId("refresh-reader").addEventListener("click", refresh);
byId("search-form").addEventListener("submit", async (event) => { event.preventDefault(); await loadArticles(); });
byId("close-article").addEventListener("click", () => { byId("article-panel").hidden = true; });
refresh();
