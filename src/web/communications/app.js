(() => {
  "use strict";

  const state = { channel: "all", queueState: "", query: "" };
  const timeline = document.querySelector("#timeline");
  const status = document.querySelector("#workspace-status");
  const resultCount = document.querySelector("#result-count");
  const inspector = document.querySelector("#inspector");
  const inspectorEmpty = document.querySelector("#inspector-empty");
  const readinessGrid = document.querySelector("#readiness-grid");

  const text = (value) => value === null || value === undefined || value === "" ? "—" : String(value);

  function channelLabel(channel) {
    return ({ email: "Mail", sms: "SMS", mms: "MMS", voice: "Voice", sip: "SIP", nntp: "News", relay: "Relay", system: "System" })[channel] || channel;
  }

  function buildQuery() {
    const params = new URLSearchParams({ limit: "200" });
    if (state.channel !== "all") params.set("channel", state.channel);
    if (state.queueState) params.set("state", state.queueState);
    if (state.query) params.set("q", state.query);
    return params.toString();
  }

  function renderInspector(event) {
    inspector.replaceChildren();
    const rows = [
      ["Event", event.communications_event_id],
      ["Conversation", event.conversation_id],
      ["Thread", event.thread_id],
      ["Case", event.case_id],
      ["Channel", channelLabel(event.channel)],
      ["Direction", event.direction],
      ["State", event.status],
      ["Sender identity", event.sender_identity_ref],
      ["Recipients", (event.recipient_identity_refs || []).join(", ")],
      ["Security", event.security && event.security.state],
      ["Native source", event.native_record && event.native_record.source],
      ["Native record", event.native_record && event.native_record.record_id],
      ["Provider", event.native_record && event.native_record.provider],
      ["AI derived", event.derived && event.derived.ai_generated ? "yes" : "no"],
      ["Audit", (event.audit_refs || []).join(", ")],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = text(value);
      inspector.append(dt, dd);
    }
    inspector.hidden = false;
    inspectorEmpty.hidden = true;
  }

  function renderTimeline(events) {
    timeline.replaceChildren();
    resultCount.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
    if (!events.length) {
      const empty = document.createElement("li");
      empty.className = "empty-state";
      empty.textContent = "No canonical communications metadata matched this view.";
      timeline.append(empty);
      return;
    }
    for (const event of events.slice().reverse()) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "timeline-item";
      const occurred = new Date(event.timestamp_utc);
      const time = Number.isNaN(occurred.valueOf()) ? event.timestamp_utc : occurred.toLocaleString();
      const summary = event.subject_or_summary || `${channelLabel(event.channel)} ${event.direction} event`;
      button.innerHTML = `<span class="timeline-time"></span><span class="channel-badge"></span><strong class="timeline-summary"></strong><span class="timeline-meta"></span>`;
      button.querySelector(".timeline-time").textContent = time;
      button.querySelector(".channel-badge").textContent = channelLabel(event.channel);
      button.querySelector(".timeline-summary").textContent = summary;
      button.querySelector(".timeline-meta").textContent = [event.status, event.case_id, event.native_record && event.native_record.source].filter(Boolean).join(" · ");
      button.addEventListener("click", () => renderInspector(event));
      item.append(button);
      timeline.append(item);
    }
  }

  async function loadEvents() {
    status.textContent = "Loading communications metadata…";
    try {
      const response = await fetch(`./api/v1/events?${buildQuery()}`, { headers: { accept: "application/json" } });
      if (!response.ok) throw new Error(`workspace API returned HTTP ${response.status}`);
      const payload = await response.json();
      if (payload.mutation_authorized !== false) throw new Error("workspace read boundary was not preserved");
      renderTimeline(Array.isArray(payload.events) ? payload.events : []);
      status.textContent = payload.count ? "Canonical metadata loaded. Message content remains untrusted." : "Workspace connected. No canonical events are currently loaded.";
    } catch (error) {
      renderTimeline([]);
      status.textContent = `Read-only workspace API unavailable: ${error.message}`;
    }
  }

  function readinessBadge(value) {
    const span = document.createElement("span");
    span.className = `readiness-value readiness-${String(value).replaceAll("_", "-")}`;
    span.textContent = text(value).replaceAll("_", " ");
    return span;
  }

  async function loadReadiness() {
    readinessGrid.replaceChildren();
    try {
      const response = await fetch("./api/v1/readiness", { headers: { accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      for (const [channel, values] of Object.entries(payload.channels || {})) {
        const card = document.createElement("article");
        card.className = "readiness-channel";
        const heading = document.createElement("h3");
        heading.textContent = channel.replaceAll("_", " / ");
        card.append(heading);
        for (const key of ["repository_implementation", "edge1_runtime", "private_ai_adapter", "identity_mapping", "security_quarantine", "provider_configuration", "production_authorization", "live_acceptance", "rollback_evidence"]) {
          const row = document.createElement("div");
          const label = document.createElement("span");
          label.textContent = key.replaceAll("_", " ");
          row.append(label, readinessBadge(values[key]));
          card.append(row);
        }
        readinessGrid.append(card);
      }
    } catch (error) {
      const message = document.createElement("p");
      message.className = "empty-state";
      message.textContent = `Readiness matrix unavailable: ${error.message}`;
      readinessGrid.append(message);
    }
  }

  document.querySelector("#search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.query = document.querySelector("#search-input").value.trim();
    loadEvents();
  });

  document.querySelectorAll("#channel-filters button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("#channel-filters button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.channel = button.dataset.channel || "all";
      loadEvents();
    });
  });

  document.querySelectorAll(".queue").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".queue").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.queueState = button.dataset.state || "";
      loadEvents();
    });
  });

  loadEvents();
  loadReadiness();
})();
