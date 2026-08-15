"use strict";

const byId = (id) => document.getElementById(id);

async function getJson(path) {
  const response = await fetch(path, {cache: "no-store", credentials: "same-origin"});
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function badge(text, className = "") {
  const span = document.createElement("span");
  span.className = `badge ${className}`.trim();
  span.textContent = text;
  return span;
}

function renderListeners(status) {
  const root = byId("listeners");
  root.replaceChildren();
  const listeners = status.config.listeners;
  for (const [name, item] of Object.entries(listeners)) {
    const row = document.createElement("div");
    row.className = "listener";
    const label = document.createElement("strong");
    label.textContent = name.toUpperCase();
    const endpoint = document.createElement("code");
    endpoint.textContent = `${item.host}:${item.port}`;
    row.append(label, endpoint, badge(item.enabled ? (item.tls ? "TLS" : "local/plain") : "disabled", item.enabled ? "good" : ""));
    root.append(row);
  }
}

function renderChannels(status) {
  const root = byId("channels");
  const channels = status.irc.channels || [];
  root.className = channels.length ? "row-stack" : "empty";
  root.replaceChildren();
  if (!channels.length) {
    root.textContent = status.irc.mode === "live" ? "No active IRC channels." : "Live IRC state is unavailable in standalone control mode.";
    return;
  }
  for (const channel of channels) {
    const row = document.createElement("div");
    row.className = "row-card";
    const text = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = channel.name;
    const small = document.createElement("small");
    small.textContent = channel.topic || "No topic";
    text.append(strong, small);
    row.append(text, badge(`${channel.members} member${channel.members === 1 ? "" : "s"}`, "good"));
    root.append(row);
  }
}

function renderGroups(groups) {
  const root = byId("groups");
  root.className = groups.length ? "row-stack" : "empty";
  root.replaceChildren();
  if (!groups.length) {
    root.textContent = "No newsgroups configured.";
    return;
  }
  for (const group of groups) {
    const row = document.createElement("div");
    row.className = "row-card";
    const text = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = group.name;
    const small = document.createElement("small");
    small.textContent = group.description;
    text.append(strong, small);
    row.append(text, badge(`${group.count} article${group.count === 1 ? "" : "s"}${group.moderated ? " · moderated" : ""}`));
    root.append(row);
  }
}

function renderAudit(rows) {
  const body = byId("audit");
  body.replaceChildren();
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.textContent = "No audit events recorded.";
    tr.append(td);
    body.append(tr);
    return;
  }
  for (const item of rows.slice(0, 50)) {
    const tr = document.createElement("tr");
    for (const value of [item.created_at_utc, item.protocol, item.action, item.target || "—", item.outcome]) {
      const td = document.createElement("td");
      td.textContent = String(value);
      tr.append(td);
    }
    body.append(tr);
  }
}

async function refresh() {
  const state = byId("service-state");
  state.textContent = "Refreshing…";
  try {
    const [status, groups, audit] = await Promise.all([
      getJson("/api/comms/status"),
      getJson("/api/comms/news/groups"),
      getJson("/api/comms/audit?limit=50")
    ]);
    state.textContent = "Healthy · read-only console";
    byId("irc-users").textContent = status.irc.connected_users ?? "—";
    byId("irc-channels").textContent = (status.irc.channels || []).length;
    byId("news-groups").textContent = status.storage.newsgroups;
    byId("news-articles").textContent = status.storage.articles;
    byId("federation").textContent = `Federation: IRC ${status.federation.irc}; NNTP ${status.federation.nntp}. Public exposure is ${status.config.network_exposure.enabled ? "enabled by configuration" : "disabled by default"}.`;
    renderListeners(status);
    renderChannels(status);
    renderGroups(groups);
    renderAudit(audit);
  } catch (error) {
    state.textContent = "Control API unavailable";
    byId("federation").textContent = error instanceof Error ? error.message : "Unknown error";
  }
}

byId("refresh").addEventListener("click", refresh);
refresh();
