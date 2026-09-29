const state = {
  view: "all",
  query: "",
  verification: "",
  rows: [],
  selected: null,
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path) {
  const response = await fetch(path, {
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;

    try {
      const payload = await response.json();
      if (payload.error) {
        detail += `: ${payload.error}`;
      }
    } catch (_) {
      // Preserve HTTP status when no JSON body is available.
    }

    throw new Error(detail);
  }

  return response.json();
}

function titleForView(view) {
  return {
    all: "All Contacts",
    organizations: "Organizations",
    people: "People",
    phones: "Phone Contacts",
    emails: "Email Contacts",
    domains: "Domains",
    unassigned: "Unassigned Phone Numbers",
    sources: "Sources & Provenance",
    observations: "Observations",
  }[view] || "All Contacts";
}

async function loadSummary() {
  const summary = await api("/api/contacts/summary");

  $("#metric-entities").textContent =
    summary.entities.toLocaleString();

  $("#metric-organizations").textContent =
    summary.organizations.toLocaleString();

  $("#metric-people").textContent =
    summary.people.toLocaleString();

  $("#metric-phones").textContent =
    summary.phones.toLocaleString();

  $("#metric-emails").textContent =
    summary.emails.toLocaleString();

  $("#metric-domains").textContent =
    Number(summary.domains ?? 0).toLocaleString();

  $("#metric-unassigned").textContent =
    Number(
      summary.unassigned_phones ??
      summary.unassigned
    ).toLocaleString();

  $("#metric-sources").textContent =
    summary.provenance.toLocaleString();

  $("#metric-observations").textContent =
    summary.observations.toLocaleString();
}

function rowKey(row) {
  if (row.provenance_id && !row.observation_id) {
    return `source:${row.provenance_id}`;
  }

  if (row.observation_id) {
    return `observation:${row.observation_id}`;
  }

  if (row.entity_id && !row.contact_point_id) {
    return `entity:${row.entity_id}`;
  }

  if (row.entity_id) {
    return `entity:${row.entity_id}:${row.contact_point_id}`;
  }

  return `point:${row.contact_point_id}`;
}

function passesVerification(row) {
  if (!state.verification) {
    return true;
  }

  if (state.view === "sources") {
    return row.verification_status ===
      state.verification;
  }

  if (state.view === "observations") {
    return row.provenance_verification ===
      state.verification ||
      row.confidence === state.verification;
  }

  if (
    row.entity_id &&
    !row.contact_point_id
  ) {
    return row.verification_status ===
      state.verification;
  }

  if (state.verification === "verified") {
    return row.verification_status === "verified";
  }

  return (
    row.confidence === state.verification ||
    row.verification_status === state.verification ||
    row.provenance_verification === state.verification
  );
}

function resultTemplate(row) {
  if (row.observation_id) {
    const value =
      row.display_value ||
      row.normalized_value ||
      row.observed_value ||
      "Observed contact point";

    return `
      <button
        class="result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">
              ${escapeHtml(value)}
            </div>
            <div class="result-value">
              ${escapeHtml(
                row.source_name ||
                row.source_reference ||
                "Source unavailable"
              )}
            </div>
          </div>

          <span class="badge ${escapeHtml(row.confidence)}">
            ${escapeHtml(row.confidence)}
          </span>
        </div>

        <div class="result-meta">
          <span>observation</span>
          <span>${escapeHtml(row.observation_type)}</span>
          <span>${escapeHtml(row.classification)}</span>
          <span>
            ${escapeHtml(
              row.provenance_verification ||
              "unverified"
            )}
          </span>
        </div>
      </button>
    `;
  }

  if (row.provenance_id && !row.entity_id) {
    const name =
      row.source_name ||
      row.source_reference ||
      `Source ${row.provenance_id}`;

    const reference =
      row.source_reference ||
      row.source_url ||
      "No external reference";

    return `
      <button
        class="result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">
              ${escapeHtml(name)}
            </div>
            <div class="result-value">
              ${escapeHtml(reference)}
            </div>
          </div>

          <span class="badge ${escapeHtml(
            row.verification_status
          )}">
            ${escapeHtml(row.verification_status)}
          </span>
        </div>

        <div class="result-meta">
          <span>${escapeHtml(row.source_kind)}</span>
          <span>
            ${escapeHtml(row.assertion_links)} identity links
          </span>
          <span>
            ${escapeHtml(row.observation_links)} observations
          </span>
        </div>
      </button>
    `;
  }

  if (row.entity_id && !row.contact_point_id) {
    const name =
      row.display_name ||
      row.canonical_name ||
      `Entity ${row.entity_id}`;

    const meta = [
      row.entity_type,
      `${row.contact_point_count ?? 0} contact points`,
      `${row.alias_count ?? 0} aliases`,
      `${row.attestation_count ?? 0} attestations`,
    ];

    return `
      <button
        class="result entity-result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">
              ${escapeHtml(name)}
            </div>
            <div class="result-value">
              Canonical ${escapeHtml(row.entity_type || "entity")}
            </div>
          </div>

          <span class="badge ${escapeHtml(
            row.verification_status || "unverified"
          )}">
            ${escapeHtml(
              row.verification_status || "unverified"
            )}
          </span>
        </div>

        <div class="result-meta">
          ${meta.map(
            (item) => `<span>${escapeHtml(item)}</span>`
          ).join("")}
        </div>
      </button>
    `;
  }

  const unassigned = !row.entity_id;

  const name = unassigned
    ? (row.display_value || row.normalized_value)
    : (row.display_name || row.canonical_name);

  const value = unassigned
    ? "No canonical identity association"
    : (
        row.display_value ||
        row.normalized_value ||
        "No asserted contact point"
      );

  const status = unassigned
    ? (row.legacy_status || "unassigned")
    : (
        row.confidence ||
        row.verification_status ||
        "unverified"
      );

  const meta = [];

  if (unassigned) {
    meta.push("phone");

    if (
      row.occurrence_count !== null &&
      row.occurrence_count !== undefined
    ) {
      meta.push(
        `${row.occurrence_count} aggregate occurrences`
      );
    }
  } else {
    meta.push(row.entity_type);

    if (row.point_type) {
      meta.push(row.point_type);
    }

    if (row.verification_status) {
      meta.push(row.verification_status);
    }
  }

  return `
    <button
      class="result"
      data-key="${escapeHtml(rowKey(row))}"
      type="button">
      <div class="result-head">
        <div>
          <div class="result-name">
            ${escapeHtml(name)}
          </div>
          <div class="result-value">
            ${escapeHtml(value)}
          </div>
        </div>

        <span class="badge ${escapeHtml(status)}">
          ${escapeHtml(status)}
        </span>
      </div>

      <div class="result-meta">
        ${meta.map(
          (item) => `<span>${escapeHtml(item)}</span>`
        ).join("")}
      </div>
    </button>
  `;
}

function renderResults(rows) {
  state.rows = rows;

  $("#directory-title").textContent =
    titleForView(state.view);

  $("#result-count").textContent =
    `${rows.length.toLocaleString()} records shown`;

  if (!rows.length) {
    $("#results").innerHTML =
      `<div class="no-results">No matching records.</div>`;
    return;
  }

  $("#results").innerHTML =
    rows.map(resultTemplate).join("");
}

function detailBlock(label, value) {
  return `
    <div class="detail-block">
      <div class="detail-label">
        ${escapeHtml(label)}
      </div>
      <div class="detail-value">
        ${escapeHtml(value ?? "—")}
      </div>
    </div>
  `;
}

function evidenceHtml(detail) {
  const evidence = detail.assertion_evidence || [];
  const observations = detail.observations || [];

  const identity = evidence.length
    ? evidence.map((row) => `
        <div class="evidence-item identity-evidence">
          <strong>
            ${escapeHtml(
              row.source_name ||
              row.source_reference ||
              "Identity evidence"
            )}
          </strong>
          <span>
            ${escapeHtml(row.evidence_role)}
            ·
            ${escapeHtml(row.verification_status)}
          </span>
          <p>
            ${escapeHtml(
              row.evidence_summary ||
              "Evidence supports the canonical assertion."
            )}
          </p>
        </div>
      `).join("")
    : `
        <div class="evidence-empty">
          No linked identity-evidence record for this
          contact point.
        </div>
      `;

  const observed = observations.length
    ? observations.map((row) => `
        <div class="evidence-item observation-evidence">
          <strong>
            ${escapeHtml(
              row.source_name ||
              row.source_reference ||
              "Observed source"
            )}
          </strong>
          <span>
            observation ·
            ${escapeHtml(row.provenance_verification)}
          </span>
          <p>
            This contact point appeared in this source.
            This observation does not establish ownership
            or identity.
          </p>
        </div>
      `).join("")
    : `
        <div class="evidence-empty">
          No contextual source observations recorded.
        </div>
      `;

  return `
    <section class="evidence-section">
      <h3>Identity evidence</h3>
      ${identity}

      <h3>Contextual observations</h3>
      ${observed}
    </section>
  `;
}

function entityEvidenceHtml(detail) {
  const assertions = detail.assertions || [];
  const aliases = detail.aliases || [];
  const attestations = detail.attestations || [];
  const observations = detail.observations || [];

  const points = assertions.length
    ? assertions.map((row) => `
        <div class="evidence-item">
          <strong>
            ${escapeHtml(
              row.display_value ||
              row.normalized_value ||
              "Contact point"
            )}
          </strong>
          <span>
            ${escapeHtml(row.point_type || "contact")}
            ·
            ${escapeHtml(row.confidence || "unverified")}
          </span>
        </div>
      `).join("")
    : `<div class="evidence-empty">
         No asserted contact points.
       </div>`;

  const aliasHtml = aliases.length
    ? aliases.map((row) => `
        <div class="evidence-item">
          <strong>${escapeHtml(row.alias_name)}</strong>
          <span>
            alias ·
            ${escapeHtml(row.alias_type || "alternate_name")}
            ·
            ${escapeHtml(row.confidence || "unverified")}
          </span>
        </div>
      `).join("")
    : `<div class="evidence-empty">
         No aliases recorded.
       </div>`;

  const attestationHtml = attestations.length
    ? attestations.map((row) => {
        const subject = row.contact_point_id
          ? `contact point ${row.contact_point_id}`
          : "entity";

        return `
          <div class="evidence-item">
            <strong>
              ${escapeHtml(row.attribute)}
            </strong>
            <span>
              ${escapeHtml(subject)}
              ·
              ${escapeHtml(
                row.verification_status || "unverified"
              )}
            </span>
            <p>
              ${escapeHtml(row.attested_value)}
            </p>
          </div>
        `;
      }).join("")
    : `<div class="evidence-empty">
         No attestations recorded.
       </div>`;

  const observationHtml = observations.length
    ? observations.map((row) => `
        <div class="evidence-item">
          <strong>
            ${escapeHtml(
              row.source_name ||
              row.source_reference ||
              "Observed source"
            )}
          </strong>
          <span>
            observation ·
            ${escapeHtml(
              row.provenance_verification || "unverified"
            )}
          </span>
        </div>
      `).join("")
    : `<div class="evidence-empty">
         No contextual observations recorded.
       </div>`;

  return `
    <section class="evidence-section">
      <h3>Contact points</h3>
      ${points}

      <h3>Aliases</h3>
      ${aliasHtml}

      <h3>Attestations</h3>
      ${attestationHtml}

      <h3>Contextual observations</h3>
      ${observationHtml}
    </section>
  `;
}

async function renderEntityDetail(row) {
  const name =
    row.display_name ||
    row.canonical_name ||
    `Entity ${row.entity_id}`;

  $("#detail-title").textContent = name;
  $("#detail-content").className = "";

  $("#detail-content").innerHTML =
    detailBlock("Entity type", row.entity_type) +
    detailBlock(
      "Verification",
      row.verification_status
    ) +
    detailBlock(
      "Lifecycle",
      row.lifecycle_status
    ) +
    detailBlock(
      "Contact points",
      row.contact_point_count
    ) +
    detailBlock(
      "Aliases",
      row.alias_count
    ) +
    detailBlock(
      "Entity attestations",
      row.attestation_count
    ) +
    `<div class="loading">
       Loading entity evidence…
     </div>`;

  try {
    const detail = await api(
      "/api/contacts/evidence?" +
      new URLSearchParams({
        entity_id: String(row.entity_id),
        limit: "250",
      })
    );

    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML =
        entityEvidenceHtml(detail);
    }
  } catch (error) {
    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = `
        <div class="evidence-empty">
          Unable to load entity evidence:
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

async function renderContactDetail(row) {
  const unassigned = !row.entity_id;
  const value =
    row.display_value || row.normalized_value;

  if (unassigned) {
    $("#detail-title").textContent = value;

    $("#detail-content").className = "";

    $("#detail-content").innerHTML =
      detailBlock(
        "Status",
        "Unassigned contact point"
      ) +
      detailBlock(
        "Normalized phone",
        row.normalized_value
      ) +
      detailBlock(
        "Research state",
        row.legacy_status
      ) +
      detailBlock(
        "Aggregate activity count",
        row.occurrence_count
      ) +
      detailBlock(
        "Identity rule",
        "No canonical person or organization is " +
        "asserted to own or use this contact point."
      ) +
      `<div class="loading">
         Loading evidence and observations…
       </div>`;

  } else {
    const name =
      row.display_name || row.canonical_name;

    $("#detail-title").textContent = name;

    $("#detail-content").className = "";

    $("#detail-content").innerHTML =
      detailBlock("Entity type", row.entity_type) +
      detailBlock(
        "Entity verification",
        row.verification_status
      ) +
      detailBlock(
        "Contact type",
        row.point_type || "—"
      ) +
      detailBlock(
        "Contact point",
        row.display_value ||
        row.normalized_value ||
        "—"
      ) +
      detailBlock(
        "Association confidence",
        row.confidence || "—"
      ) +
      `<div class="loading">
         Loading evidence and observations…
       </div>`;
  }

  if (!row.contact_point_id) {
    return;
  }

  try {
    const detail = await api(
      "/api/contacts/evidence?" +
      new URLSearchParams({
        contact_point_id:
          String(row.contact_point_id),
        limit: "250",
      })
    );

    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = evidenceHtml(detail);
    }

  } catch (error) {
    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = `
        <div class="evidence-empty">
          Unable to load evidence:
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

function renderSourceDetail(row) {
  $("#detail-title").textContent =
    row.source_name ||
    row.source_reference ||
    `Source ${row.provenance_id}`;

  $("#detail-content").className = "";

  $("#detail-content").innerHTML =
    detailBlock("Source kind", row.source_kind) +
    detailBlock(
      "Verification",
      row.verification_status
    ) +
    detailBlock(
      "Reference",
      row.source_reference
    ) +
    detailBlock(
      "Page",
      row.source_page
    ) +
    detailBlock(
      "Extraction method",
      row.extraction_method
    ) +
    detailBlock(
      "Identity evidence links",
      row.assertion_links
    ) +
    detailBlock(
      "Observation links",
      row.observation_links
    ) +
    detailBlock(
      "Interpretation",
      "A source records provenance. Its presence alone " +
      "does not create a canonical identity relationship."
    );
}

function renderObservationDetail(row) {
  $("#detail-title").textContent =
    row.display_value ||
    row.normalized_value ||
    row.observed_value ||
    "Observation";

  $("#detail-content").className = "";

  $("#detail-content").innerHTML =
    detailBlock(
      "Observation type",
      row.observation_type
    ) +
    detailBlock(
      "Classification",
      row.classification
    ) +
    detailBlock(
      "Observation confidence",
      row.confidence
    ) +
    detailBlock(
      "Observed value",
      row.observed_value
    ) +
    detailBlock(
      "Source",
      row.source_name ||
      row.source_reference
    ) +
    detailBlock(
      "Source verification",
      row.provenance_verification
    ) +
    detailBlock(
      "Observed at",
      row.occurred_at
    ) +
    detailBlock(
      "Identity rule",
      "This is contextual evidence that the contact " +
      "point appeared in a source. It does not establish " +
      "who owned or controlled the contact point."
    );
}

async function renderDetail(row) {
  state.selected = row;

  document
    .querySelectorAll(".result")
    .forEach((element) => {
      element.classList.toggle(
        "selected",
        element.dataset.key === rowKey(row),
      );
    });

  if (row.observation_id) {
    renderObservationDetail(row);
    return;
  }

  if (row.provenance_id && !row.entity_id) {
    renderSourceDetail(row);
    return;
  }

  if (row.entity_id && !row.contact_point_id) {
    await renderEntityDetail(row);
    return;
  }

  await renderContactDetail(row);
}

async function canonicalSearch() {
  const params = new URLSearchParams({
    q: state.query,
    kind: state.view === "all"
      ? "all"
      : state.view,
    limit: "250",
  });

  return api(`/api/contacts/search?${params}`);
}

async function entitySearch(entityType) {
  const params = new URLSearchParams({
    q: state.query,
    entity_type: entityType,
    limit: "250",
    offset: "0",
  });

  return api(`/api/contacts/entities?${params}`);
}

async function unassignedSearch() {
  const params = new URLSearchParams({
    q: state.query,
    limit: "250",
  });

  return api(`/api/contacts/unassigned?${params}`);
}

async function sourceSearch() {
  const params = new URLSearchParams({
    q: state.query,
    limit: "250",
    offset: "0",
  });

  if (state.verification) {
    params.set(
      "verification",
      state.verification
    );
  }

  return api(`/api/contacts/sources?${params}`);
}

async function observationSearch() {
  const params = new URLSearchParams({
    q: state.query,
    limit: "250",
    offset: "0",
  });

  if (
    state.verification === "document_sourced" ||
    state.verification === "missing_source"
  ) {
    params.set(
      "verification",
      state.verification
    );
  }

  return api(
    `/api/contacts/observations?${params}`
  );
}

async function loadDirectory() {
  $("#results").innerHTML =
    `<div class="loading">Loading directory…</div>`;

  let rows = [];

  if (state.view === "sources") {
    rows = await sourceSearch();

  } else if (state.view === "observations") {
    rows = await observationSearch();

  } else if (state.view === "unassigned") {
    rows = await unassignedSearch();

  } else if (state.view === "organizations") {
    rows = await entitySearch("organization");

  } else if (state.view === "people") {
    rows = await entitySearch("person");

  } else if (
    state.view === "phones" ||
    state.view === "emails" ||
    state.view === "domains"
  ) {
    rows = await canonicalSearch();

    if (state.view === "phones") {
      const unresolved = await unassignedSearch();
      rows = rows.concat(unresolved);
    }

  } else if (state.view === "all") {
    const [canonical, unresolved] =
      await Promise.all([
        canonicalSearch(),
        unassignedSearch(),
      ]);

    rows = canonical.concat(unresolved);

  } else {
    rows = await canonicalSearch();
  }

  rows = rows.filter(passesVerification);

  renderResults(rows);

  $("#detail-title").textContent =
    "Select a record";

  $("#detail-content").className =
    "detail-empty";

  $("#detail-content").textContent =
    state.view === "sources"
      ? "Select a source to inspect its provenance role."
      : state.view === "observations"
        ? "Select an observation to inspect its context."
        : "Select a directory entry to inspect identity, " +
          "contact points, evidence and observations.";
}

async function runSearch() {
  state.query = $("#search").value.trim();
  state.verification = $("#verification").value;

  try {
    await loadDirectory();
  } catch (error) {
    $("#results").innerHTML =
      `<div class="no-results">
        Unable to load directory:
        ${escapeHtml(error.message)}
      </div>`;
  }
}

$("#search-button").addEventListener(
  "click",
  runSearch,
);

$("#search").addEventListener(
  "keydown",
  (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  },
);

$("#clear-button").addEventListener(
  "click",
  () => {
    $("#search").value = "";
    $("#verification").value = "";

    state.query = "";
    state.verification = "";

    loadDirectory();
  },
);

$("#view-tabs").addEventListener(
  "click",
  (event) => {
    const button =
      event.target.closest("button[data-view]");

    if (!button) {
      return;
    }

    state.view = button.dataset.view;

    document
      .querySelectorAll("#view-tabs button")
      .forEach((item) => {
        item.classList.toggle(
          "active",
          item === button,
        );
      });

    runSearch();
  },
);

$("#results").addEventListener(
  "click",
  (event) => {
    const result =
      event.target.closest(".result");

    if (!result) {
      return;
    }

    const row = state.rows.find(
      (item) =>
        rowKey(item) === result.dataset.key
    );

    if (row) {
      renderDetail(row);
    }
  },
);

Promise.all([
  loadSummary(),
  loadDirectory(),
]).catch((error) => {
  $("#results").innerHTML =
    `<div class="no-results">
      Unable to load Unified Contacts:
      ${escapeHtml(error.message)}
    </div>`;
});
