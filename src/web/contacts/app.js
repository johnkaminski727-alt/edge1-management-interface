const state = {
  view: "all",
  query: (new URLSearchParams(window.location.search).get("q") || "").slice(0, 200),
  verification: "",
  maintenanceKind: "all",
  rows: [],
  selected: null,
};

const $ = (selector) => document.querySelector(selector);
if (state.query) { const searchInput = $("#search"); if (searchInput) searchInput.value = state.query; }

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path) {
  const routedPath = path.startsWith("/api/")
    ? `/edge1-ops/contacts${path}`
    : path;
  const response = await fetch(routedPath, {
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
    connections: "Connections",
    maintenance: "Maintenance & Review",
  }[view] || "All Contacts";
}

async function loadSummary() {
  const [summary, maintenance] = await Promise.all([
    api("/api/contacts/summary"),
    api("/api/contacts/maintenance-summary"),
  ]);

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

  $("#metric-maintenance-review").textContent =
    Number(
      maintenance.review_required_findings ?? 0
    ).toLocaleString();

  $("#metric-identity-jobs").textContent =
    Number(
      maintenance.pending_identity_resolution ?? 0
    ).toLocaleString();
}

function rowKey(row) {
  if (row.maintenance_item_id) {
    return `maintenance:${row.maintenance_kind}:${row.maintenance_item_id}`;
  }

  if (row.relationship_id) {
    return `relationship:${row.relationship_id}`;
  }

  if (row.correlation_id) {
    return `correlation:${row.correlation_id}`;
  }

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
  if (state.view === "maintenance") {
    return true;
  }

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


function verificationBadgeLabel(value) {
  const normalized =
    String(value || "").toLowerCase();

  if (
    normalized === "verified" ||
    normalized === "confirmed"
  ) {
    return `✓ ${value || "Verified"}`;
  }

  if (normalized === "unverified") {
    return "✕ Unverified";
  }

  return value || "Unverified";
}

function resultTemplate(row) {
  if (row.maintenance_item_id) {
    const kind = row.maintenance_kind || "maintenance";
    const title =
      row.title ||
      row.proposed_entity_name ||
      row.entity_name ||
      row.normalized_value ||
      row.task_type ||
      `${kind} item`;
    const detail =
      row.review_summary ||
      row.detail ||
      row.rationale ||
      row.proposed_value ||
      row.normalized_value ||
      "Maintenance review item";
    const status = row.status || "pending";
    const action = row.action_level || "AUTO_STAGE";
    return `
      <button
        class="result maintenance-result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">${escapeHtml(title)}</div>
            <div class="result-value">${escapeHtml(detail)}</div>
          </div>
          <span class="badge ${escapeHtml(status)}">${escapeHtml(status)}</span>
        </div>
        <div class="result-meta">
          <span>${escapeHtml(kind)}</span>
          <span>${escapeHtml(action)}</span>
          ${row.entity_name ? `<span>${escapeHtml(row.entity_name)}</span>` : ""}
          ${row.matched_entity_name ? `<span>match: ${escapeHtml(row.matched_entity_name)}</span>` : ""}
        </div>
      </button>
    `;
  }

  if (row.relationship_id) {
    const left =
      row.left_display_name ||
      row.left_display_value ||
      "Left endpoint";

    const right =
      row.right_display_name ||
      row.right_display_value ||
      "Right endpoint";

    return `
      <button
        class="result relationship-result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">
              ${escapeHtml(left)}
              <span class="connection-arrow">
                ${row.directionality === "directed" ? "→" : "↔"}
              </span>
              ${escapeHtml(right)}
            </div>
            <div class="result-value">
              ${escapeHtml(row.relationship_type)}
            </div>
          </div>
          <span class="badge ${escapeHtml(verificationBadgeLabel(row.confidence))}">
            ${escapeHtml(verificationBadgeLabel(row.confidence))}
          </span>
        </div>
        <div class="result-meta">
          <span>established relationship</span>
          <span>${escapeHtml(row.lifecycle_status)}</span>
          <span>
            ${Number(row.evidence_count || 0).toLocaleString()}
            evidence
          </span>
        </div>
      </button>
    `;
  }

  if (row.correlation_id) {
    const left =
      row.left_display_name ||
      row.left_display_value ||
      "Candidate endpoint";

    const right =
      row.right_display_name ||
      row.right_display_value ||
      "Candidate endpoint";

    return `
      <button
        class="result correlation-result"
        data-key="${escapeHtml(rowKey(row))}"
        type="button">
        <div class="result-head">
          <div>
            <div class="result-name">
              ${escapeHtml(left)}
              <span class="connection-arrow">⋯</span>
              ${escapeHtml(right)}
            </div>
            <div class="result-value">
              ${escapeHtml(row.correlation_type || "candidate correlation")}
            </div>
          </div>
          <span class="badge ${escapeHtml(verificationBadgeLabel(row.confidence || "unverified"))}">
            ${escapeHtml(verificationBadgeLabel(row.confidence || "unverified"))}
          </span>
        </div>
        <div class="result-meta">
          <span>candidate only</span>
          <span>${escapeHtml(row.review_status || "pending")}</span>
        </div>
      </button>
    `;
  }

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

          <span class="badge ${escapeHtml(verificationBadgeLabel(row.confidence))}">
            ${escapeHtml(verificationBadgeLabel(row.confidence))}
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
            ${escapeHtml(verificationBadgeLabel(row.verification_status))}
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

  /*
   * Entity-centric directory views accumulate every active
   * contact point on row.contact_points.  Render those methods
   * together instead of making the first point look canonical.
   */
  const entityPointSummary =
    !unassigned &&
    Array.isArray(row.contact_points) &&
    row.contact_points.length
      ? row.contact_points
          .map((point) => {
            const type =
              point.point_type || "contact";

            const value =
              point.display_value ||
              point.normalized_value ||
              "";

            if (!value) {
              return "";
            }

            return `
              <span class="entity-contact-method">
                <span class="entity-contact-type">
                  ${escapeHtml(type)}
                </span>
                <span class="entity-contact-value">
                  ${escapeHtml(value)}
                </span>
              </span>
            `;
          })
          .filter(Boolean)
          .join("")
      : "";

  const name = unassigned
    ? (row.display_value || row.normalized_value)
    : (row.display_name || row.canonical_name);

  const value = unassigned
    ? "No canonical identity association"
    : (
        entityPointSummary ||
        escapeHtml(
          row.display_value ||
          row.normalized_value ||
          "No asserted contact point"
        )
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
            ${
              !unassigned && entityPointSummary
                ? entityPointSummary
                : escapeHtml(value)
            }
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


function entityDirectoryRows(rows) {
  if (!Array.isArray(rows)) {
    return [];
  }

  const grouped = new Map();

  for (const row of rows) {
    const entityId = Number(row.entity_id);

    /*
     * Rows without a canonical entity remain independent.
     * This preserves unresolved contact-point behaviour.
     */
    if (!Number.isInteger(entityId) || entityId <= 0) {
      grouped.set(
        `unresolved:${rowKey(row)}`,
        row
      );
      continue;
    }

    const key = `entity:${entityId}`;
    let entity = grouped.get(key);

    if (!entity) {
      entity = {
        ...row,
        entity_id: entityId,
        contact_points: [],
      };

      grouped.set(key, entity);
    }

    const pointId = Number(row.contact_point_id);

    if (
      Number.isInteger(pointId) &&
      pointId > 0 &&
      !entity.contact_points.some(
        (point) =>
          Number(point.contact_point_id) === pointId
      )
    ) {
      entity.contact_points.push({
        contact_point_id: pointId,
        point_type: row.point_type,
        normalized_value: row.normalized_value,
        display_value: row.display_value,
        classification: row.classification,
        assertion_id: row.assertion_id,
        assertion_valid_from: row.assertion_valid_from,
        assertion_valid_to: row.assertion_valid_to,
        confidence:
          row.confidence ||
          row.verification_status ||
          "unverified",
      });
    }
  }

  return Array.from(grouped.values());
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

function safeEvidenceUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.href;
    }
  } catch (_) {}
  return "";
}

function evidenceSourceLink(row, label = "View source") {
  const url = safeEvidenceUrl(row.source_url);
  const provenanceId = Number(row.provenance_id || 0);
  if (url) {
    return `<a class="evidence-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} ↗</a>`;
  }
  if (provenanceId > 0) {
    return `<button type="button" class="evidence-link evidence-link-button" data-open-source="${provenanceId}">${escapeHtml(label)}</button>`;
  }
  return `<span class="evidence-link unavailable">Source unavailable</span>`;
}

function evidenceLocationLine(row) {
  const bits = [];
  if (row.source_reference) bits.push(row.source_reference);
  if (row.source_page) bits.push(`page ${row.source_page}`);
  if (!bits.length && row.verification_status === "missing_source") {
    return `<span class="evidence-location missing">Source file is currently unavailable</span>`;
  }
  return bits.length
    ? `<span class="evidence-location">${escapeHtml(bits.join(" · "))}</span>`
    : "";
}

function evidenceHtml(detail) {
  const evidence = detail.assertion_evidence || [];
  const observations = detail.observations || [];
  const openpgpKeys = detail.openpgp_keys || [];
  const openpgpPolicies = detail.openpgp_policies || [];

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
            ${escapeHtml(verificationBadgeLabel(row.verification_status))}
          </span>
          <p>
            ${escapeHtml(
              row.evidence_summary ||
              "Evidence supports the canonical assertion."
            )}
          </p>
          ${evidenceLocationLine(row)}
          <div class="evidence-actions">${evidenceSourceLink(row)}</div>
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
          ${evidenceLocationLine(row)}
          <div class="evidence-actions">${evidenceSourceLink(row)}</div>
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


function contactVerificationHtml(status) {
  const normalized =
    String(status || "unverified").toLowerCase();

  if (normalized === "verified") {
    return `
      <span
        class="contact-verification verified"
        data-verification="verified"
      >
        Verified
      </span>
    `;
  }

  return `
    <span
      class="contact-verification unverified"
      data-verification="unverified"
    >
      Unverified
    </span>
  `;
}

function contactPointIcon(type) {
  const icons = {
    phone: "☎",
    fax: "▤",
    email: "✉",
    website: "↗",
    domain: "⌁",
    postal: "⌖",
  };

  return icons[type] || "•";
}

function contactPointTypeLabel(type) {
  const labels = {
    phone: "Phone",
    fax: "Fax",
    email: "Email",
    website: "Website",
    domain: "Domain",
    postal: "Address",
  };

  return labels[type] || "Contact information";
}

function contactPointRowHtml(row, selectedPointId = null) {
  const value =
    row.display_value ||
    row.normalized_value ||
    "Contact information";

  const type =
    row.point_type || "contact";

  const label =
    row.classification ||
    contactPointTypeLabel(type);

  const confidence =
    row.confidence || "unverified";

  const selected =
    selectedPointId &&
    String(row.contact_point_id) ===
      String(selectedPointId);

  return `
    <div
      class="contact-info-row${selected ? " selected" : ""}"
    >
      <div class="contact-info-icon" aria-hidden="true">
        ${escapeHtml(contactPointIcon(type))}
      </div>

      <div class="contact-info-main">
        <div class="contact-info-value">
          ${escapeHtml(value)}
        </div>

        <div class="contact-info-meta">
          ${escapeHtml(label)}
          <span aria-hidden="true"> · </span>
          ${escapeHtml(confidence)}
        </div>
      </div>

      ${
        row.entity_id && row.contact_point_id
          ? pointActionHtml(row)
          : ""
      }
    </div>
  `;
}

function contactRecordTechnicalDetails(row) {
  return `
    <details class="contact-technical-details">
      <summary>Record details</summary>

      <dl>
        <div>
          <dt>Entity ID</dt>
          <dd>${escapeHtml(row.entity_id ?? "—")}</dd>
        </div>

        <div>
          <dt>Lifecycle</dt>
          <dd>
            ${escapeHtml(row.lifecycle_status || "active")}
          </dd>
        </div>

        ${
          row.contact_point_id
            ? `
              <div>
                <dt>Contact point ID</dt>
                <dd>
                  ${escapeHtml(row.contact_point_id)}
                </dd>
              </div>
            `
            : ""
        }
      </dl>
    </details>
  `;
}

function entityEvidenceHtml(
  detail,
  entityRow = null,
  selectedPointId = null
) {
  const assertions = detail.assertions || [];
  const aliases = detail.aliases || [];
  const attestations = detail.attestations || [];
  const observations = detail.observations || [];

  const contactInfo = assertions.length
    ? assertions.map((item) => {
        const actionRow = {
          ...item,
          entity_id:
            item.entity_id ||
            (entityRow && entityRow.entity_id),
        };

        return contactPointRowHtml(
          actionRow,
          selectedPointId
        );
      }).join("")
    : `
        <div class="contact-section-empty">
          No contact information recorded.
        </div>
      `;

  const aliasHtml = aliases.length
    ? aliases.map((item) => `
        <div class="contact-secondary-row">
          <strong>
            ${escapeHtml(item.alias_name)}
          </strong>
          <span>
            ${escapeHtml(
              item.alias_type || "Alternate name"
            )}
          </span>
        </div>
      `).join("")
    : `
        <div class="contact-section-empty">
          No alternate names recorded.
        </div>
      `;

  const evidenceCount =
    attestations.length + observations.length;

  const evidenceHtml = evidenceCount
    ? `
        <div class="contact-evidence-summary">
          ${escapeHtml(evidenceCount)}
          linked evidence
          ${evidenceCount === 1 ? "record" : "records"}
        </div>

        ${attestations.map((item) => `
          <div class="evidence-item">
            <strong>
              ${escapeHtml(
                item.attribute || "Attestation"
              )}
            </strong>
            <span>
              ${escapeHtml(
                item.verification_status ||
                "unverified"
              )}
            </span>
            <p>
              ${escapeHtml(
                item.attested_value || ""
              )}
            </p>
            ${evidenceLocationLine(item)}
            <div class="evidence-actions">${evidenceSourceLink(item)}</div>
          </div>
        `).join("")}

        ${observations.map((item) => `
          <div class="evidence-item">
            <strong>
              ${escapeHtml(
                item.source_name ||
                item.source_reference ||
                "Observed source"
              )}
            </strong>
            <span>
              observation ·
              ${escapeHtml(
                item.provenance_verification ||
                "unverified"
              )}
            </span>
            ${evidenceLocationLine(item)}
            <div class="evidence-actions">${evidenceSourceLink(item)}</div>
          </div>
        `).join("")}
      `
    : `
        <div class="contact-section-empty">
          No linked evidence recorded.
        </div>
      `;

  return `
    <section class="contact-record-section">
      <div class="contact-section-heading">
        <h3>Contact information</h3>

        ${
          entityRow && entityRow.entity_id
            ? `
              <button
                type="button"
                class="contact-add-action"
                data-contact-action="add-point"
              >
                + Add
              </button>
            `
            : ""
        }
      </div>

      <div class="contact-info-list">
        ${contactInfo}
      </div>
    </section>

    ${
      aliases.length
        ? `
          <section class="contact-record-section">
            <h3>Alternate names</h3>
            ${aliasHtml}
          </section>
        `
        : ""
    }

    ${openpgpKeys.length || openpgpPolicies.length ? `
      <section class="contact-record-section contact-security-section">
        <h3>Email security</h3>
        ${openpgpPolicies.map((item) => `
          <div class="contact-secondary-row">
            <strong>${escapeHtml(item.email_address || "Email")}</strong>
            <span>OpenPGP policy · ${escapeHtml(item.mode || "disabled")}</span>
          </div>
        `).join("")}
        ${openpgpKeys.map((item) => `
          <div class="contact-secondary-row">
            <strong>OpenPGP ${escapeHtml(item.verification_status || "unverified")}</strong>
            <span class="contact-key-fingerprint">${escapeHtml(item.fingerprint || "")}</span>
            <span>${escapeHtml(item.expires_at ? `expires ${item.expires_at}` : "no recorded expiry")}</span>
          </div>
        `).join("")}
      </section>
    ` : ""}

    <section class="contact-record-section">
      <h3>Evidence &amp; provenance</h3>
      ${evidenceHtml}
    </section>
  `;
}

async function renderEntityDetail(row) {
  const name =
    row.display_name ||
    row.canonical_name ||
    `Entity ${row.entity_id}`;

  $("#detail-title").textContent = name;
  $("#detail-content").className =
    "contact-record-body";

  $("#detail-content").innerHTML = `
    <div class="contact-identity-summary">

      <div class="contact-identity-copy">
        ${contactVerificationHtml(
          row.verification_status
        )}

        <div class="contact-entity-kind">
          ${escapeHtml(
            row.entity_type === "person"
              ? "Person"
              : "Organization"
          )}
        </div>
      </div>

      ${entityActionHtml(row)}

    </div>

    <div class="loading">
      Loading contact information…
    </div>

    ${contactRecordTechnicalDetails(row)}
  `;

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
        entityEvidenceHtml(
          detail,
          row,
          null
        );
    }
  } catch (error) {
    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = `
        <div class="contact-section-empty">
          Unable to load contact information:
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

async function renderContactDetail(row) {
  const unassigned = !row.entity_id;

  const value =
    row.display_value ||
    row.normalized_value ||
    "Contact point";

  if (unassigned) {
    $("#detail-title").textContent = value;
    $("#detail-content").className =
      "contact-record-body";

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
        loading.outerHTML =
          evidenceHtml(detail);
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

    return;
  }

  const name =
    row.display_name ||
    row.canonical_name ||
    `Entity ${row.entity_id}`;

  $("#detail-title").textContent = name;
  $("#detail-content").className =
    "contact-record-body";

  $("#detail-content").innerHTML = `
    <div class="contact-identity-summary">

      <div class="contact-identity-copy">
        ${contactVerificationHtml(
          row.verification_status
        )}

        <div class="contact-entity-kind">
          ${escapeHtml(
            row.entity_type === "person"
              ? "Person"
              : "Organization"
          )}
        </div>
      </div>

      ${entityActionHtml(row)}

    </div>

    <div class="loading">
      Loading contact information…
    </div>

    ${contactRecordTechnicalDetails(row)}
  `;

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
        entityEvidenceHtml(
          detail,
          row,
          row.contact_point_id
        );
    }
  } catch (error) {
    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = `
        <div class="contact-section-empty">
          Unable to load contact information:
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

async function renderRelationshipDetail(row) {
  const left =
    row.left_display_name ||
    row.left_display_value ||
    "Left endpoint";

  const right =
    row.right_display_name ||
    row.right_display_value ||
    "Right endpoint";

  $("#detail-title").textContent =
    `${left} ${row.directionality === "directed" ? "→" : "↔"} ${right}`;

  $("#detail-content").className = "";

  $("#detail-content").innerHTML =
    detailBlock("Record type", "Established relationship") +
    detailBlock("Relationship", row.relationship_type) +
    detailBlock("Confidence", row.confidence) +
    detailBlock("Directionality", row.directionality) +
    detailBlock("Lifecycle", row.lifecycle_status) +
    detailBlock("Left endpoint", left) +
    detailBlock("Right endpoint", right) +
    detailBlock("Notes", row.notes) +
    `<section class="evidence-section">
       <h3>Relationship evidence</h3>
       <div class="loading">Loading relationship evidence…</div>
     </section>`;

  try {
    const evidence = await api(
      "/api/contacts/relationship-evidence?" +
      new URLSearchParams({
        relationship_id: String(row.relationship_id),
        limit: "250",
        offset: "0",
      })
    );

    const loading =
      $("#detail-content .loading");

    if (!loading) {
      return;
    }

    loading.outerHTML = evidence.length
      ? evidence.map((item) => `
          <div class="evidence-item identity-evidence">
            <strong>
              ${escapeHtml(
                item.source_name ||
                item.source_reference ||
                `Provenance ${item.provenance_id}`
              )}
            </strong>
            <span>
              ${escapeHtml(item.evidence_role || "supporting")}
              ·
              ${escapeHtml(
                item.verification_status || "unverified"
              )}
            </span>
            <p>
              ${escapeHtml(
                item.evidence_summary ||
                "Evidence linked to this relationship."
              )}
            </p>
            ${evidenceLocationLine(item)}
            <div class="evidence-actions">${evidenceSourceLink(item)}</div>
          </div>
        `).join("")
      : `<div class="evidence-empty">
           No provenance evidence is linked to this relationship.
         </div>`;
  } catch (error) {
    const loading =
      $("#detail-content .loading");

    if (loading) {
      loading.outerHTML = `
        <div class="evidence-empty">
          Unable to load relationship evidence:
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

function renderCorrelationDetail(row) {
  const left =
    row.left_display_name ||
    row.left_display_value ||
    "Candidate endpoint";

  const right =
    row.right_display_name ||
    row.right_display_value ||
    "Candidate endpoint";

  $("#detail-title").textContent =
    `${left} ⋯ ${right}`;

  $("#detail-content").className = "";

  $("#detail-content").innerHTML =
    detailBlock("Record type", "Candidate correlation") +
    detailBlock(
      "Correlation type",
      row.correlation_type || "—"
    ) +
    detailBlock("Confidence", row.confidence) +
    detailBlock(
      "Review status",
      row.review_status || "pending"
    ) +
    detailBlock("Left endpoint", left) +
    detailBlock("Right endpoint", right) +
    detailBlock("Notes", row.notes) +
    detailBlock(
      "Interpretation",
      "This is a review candidate, not an established " +
      "relationship or identity assertion."
    ) +
    correlationReviewHtml(row);
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
      "Source URL",
      row.source_url
    ) +
    detailBlock(
      "Resolved location",
      row.resolved_location
    ) +
    detailBlock(
      "Location verification",
      row.location_verification
    ) +
    detailBlock(
      "Location match",
      row.location_match_method
    ) +
    `<div class="detail-block"><div class="detail-label">Evidence link</div><div class="detail-value">${evidenceSourceLink(row, "Open source")}</div></div>` +
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
    `<div class="detail-block"><div class="detail-label">Evidence link</div><div class="detail-value">${evidenceSourceLink(row, "Open source")}</div></div>` +
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

function maintenanceActionButtons(row) {
  const buttons = [];

  const searchValue =
    row.matched_entity_name ||
    row.entity_name ||
    row.proposed_entity_name ||
    row.normalized_value ||
    row.proposed_value ||
    "";

  if (searchValue) {
    buttons.push(`
      <button type="button" class="primary" data-maintenance-action="find-match" data-maintenance-search="${escapeHtml(searchValue)}">
        Find matching contact
      </button>
    `);
  }

  if (row.entity_name || row.matched_entity_name) {
    buttons.push(`
      <button type="button" class="secondary" data-maintenance-action="open-contact" data-maintenance-search="${escapeHtml(row.matched_entity_name || row.entity_name)}">
        Open existing contact
      </button>
    `);
  }

  const creatableCandidate =
    row.maintenance_kind === "identity" ||
    (row.maintenance_kind === "finding" &&
      ["phone", "email"].includes(row.candidate_type));

  if (creatableCandidate && !row.matched_entity_id) {
    buttons.push(`
      <button type="button" class="secondary" data-maintenance-action="create-contact" data-maintenance-name="${escapeHtml(row.proposed_entity_name || "")}" data-maintenance-value="${escapeHtml(row.normalized_value || "")}" data-maintenance-point-type="${escapeHtml(row.candidate_type || "phone")}" data-maintenance-confidence="${escapeHtml(row.confidence || "unverified")}">
        Create warranted contact
      </button>
    `);
  }

  return buttons.length
    ? `<div class="maintenance-actions">${buttons.join("")}</div>`
    : "";
}

function renderMaintenanceDetail(row) {
  const title =
    row.title ||
    row.proposed_entity_name ||
    row.entity_name ||
    row.normalized_value ||
    row.task_type ||
    "Maintenance item";

  $("#detail-title").textContent = title;
  $("#detail-content").className = "contact-record-body";

  const blocks = [
    detailBlock("Work type", row.maintenance_kind),
    detailBlock("Status", row.status || "pending"),
    detailBlock("Action policy", row.action_level || "AUTO_STAGE"),
  ];

  if (row.finding_type) blocks.push(detailBlock("Finding", row.finding_type));
  if (row.severity) blocks.push(detailBlock("Severity", row.severity));
  if (row.entity_name) blocks.push(detailBlock("Contact", row.entity_name));
  if (row.matched_entity_name) blocks.push(detailBlock("Matched contact", row.matched_entity_name));
  if (row.normalized_value) blocks.push(detailBlock("Normalized value", row.normalized_value));
  if (row.proposed_entity_name) blocks.push(detailBlock("Proposed identity", row.proposed_entity_name));
  if (row.task_type) blocks.push(detailBlock("Enrichment task", row.task_type));
  if (row.candidate_type) blocks.push(detailBlock("Candidate type", row.candidate_type));
  if (row.evidence_count) blocks.push(detailBlock("Evidence occurrences", row.evidence_count));
  if (row.source_kind || row.source_reference) blocks.push(detailBlock("Source context", [row.source_kind, row.source_reference].filter(Boolean).join(" · ")));
  if (row.example_message_id) blocks.push(detailBlock("Example message", row.example_message_id));
  if (row.target_table || row.target_field) {
    blocks.push(detailBlock("Candidate field", [row.target_table, row.target_field].filter(Boolean).join(" · ")));
  }
  if (row.current_value !== undefined && row.current_value !== null) blocks.push(detailBlock("Current value", row.current_value));
  if (row.proposed_value !== undefined && row.proposed_value !== null) blocks.push(detailBlock("Proposed value", row.proposed_value));
  blocks.push(detailBlock("Reason", row.review_summary || row.detail || row.rationale || "Review this item against existing contact evidence."));
  if (row.occurrences) blocks.push(detailBlock("Times observed", row.occurrences));
  blocks.push(detailBlock("Safety rule", "Search and reconcile against existing canonical contacts before creating or attaching anything. Ambiguous identity changes remain review-required."));

  $("#detail-content").innerHTML =
    `<section class="maintenance-review-card">${blocks.join("")}${maintenanceActionButtons(row)}</section>`;
}

async function renderDetail(row) {
  state.selected = row;

  if (row.maintenance_item_id) {
    renderMaintenanceDetail(row);
    return;
  }

  document
    .querySelectorAll(".result")
    .forEach((element) => {
      element.classList.toggle(
        "selected",
        element.dataset.key === rowKey(row),
      );
    });

  if (row.relationship_id) {
    await renderRelationshipDetail(row);
    return;
  }

  if (row.correlation_id) {
    renderCorrelationDetail(row);
    return;
  }

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
    limit: "250",
    offset: "0",
  });

    if (state.query && state.query.trim()) {
      params.set("q", state.query.trim());
    }

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
    limit: "250",
    offset: "0",
  });

  if (state.query && state.query.trim()) {
    params.set(
      "q",
      state.query.trim()
    );
  }

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

async function relationshipSearch() {
  const params = new URLSearchParams({
    lifecycle_status: "active",
    limit: "250",
    offset: "0",
  });

  if (state.verification) {
    params.set("confidence", state.verification);
  }

  return api(
    `/api/contacts/relationships?${params}`
  );
}

async function maintenanceSearch() {
  const params = new URLSearchParams({
    kind: state.maintenanceKind || "all",
    status: "pending",
    limit: "250",
    offset: "0",
  });

  if (state.query && state.query.trim()) {
    params.set("q", state.query.trim());
  }

  return api(`/api/contacts/maintenance?${params}`);
}

async function correlationSearch() {
  const params = new URLSearchParams({
    review_status: "pending",
    limit: "250",
    offset: "0",
  });

  if (state.verification) {
    params.set("confidence", state.verification);
  }

  return api(
    `/api/contacts/correlations?${params}`
  );
}

async function loadDirectory() {
  $("#results").innerHTML =
    `<div class="loading">Loading directory…</div>`;

  let rows = [];

  if (state.view === "maintenance") {
    rows = await maintenanceSearch();

  } else if (state.view === "connections") {
    const [relationships, correlations] =
      await Promise.all([
        relationshipSearch(),
        correlationSearch(),
      ]);

    rows = relationships.concat(correlations);
  } else if (state.view === "sources") {
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

  /*
   * Contact-oriented views represent people and organizations,
   * not individual contact-point assertions.
   *
   * Endpoint-oriented views intentionally retain one row per
   * phone/email/domain.
   */
  if (
    state.view === "all" ||
    state.view === "people" ||
    state.view === "organizations"
  ) {
    rows = entityDirectoryRows(rows);
  }

  renderResults(rows);

  $("#detail-title").textContent = "Select a contact";

  $("#detail-content").className =
    "detail-empty contact-record-body";

  if (
    state.view === "all" ||
    state.view === "people" ||
    state.view === "organizations" ||
    state.view === "phones" ||
    state.view === "emails" ||
    state.view === "domains" ||
    state.view === "unassigned" ||
    state.view === "maintenance"
  ) {
    $("#detail-content").innerHTML = `
      <div class="contact-record-empty-state">
        <div class="contact-record-empty-copy">
          <div class="contact-record-empty-title">
            Select a contact to view its record
          </div>
          <div class="contact-record-empty-detail">
            Inspect identity, contact methods, evidence,
            connections and observations.
          </div>
        </div>
      </div>
    `;
  } else {
    $("#detail-content").textContent =
      state.view === "connections"
        ? "Established relationships and pending candidate " +
          "correlations are separate. Candidates do not " +
          "establish identity or a relationship."
        : state.view === "sources"
          ? "Select a source to inspect its provenance role."
          : state.view === "observations"
            ? "Select an observation to inspect its context."
            : "";
  }
}

function updateViewControls() {
  const maintenance = state.view === "maintenance";
  const verificationFilter = $("#verification-filter");
  const maintenanceFilter = $("#maintenance-kind-filter");
  const newButton = $("#new-contact-button");
  const search = $("#search");
  const safety = document.querySelector(".directory-safety-note");

  if (verificationFilter) verificationFilter.hidden = maintenance;
  if (maintenanceFilter) maintenanceFilter.hidden = !maintenance;
  if (newButton) newButton.hidden = maintenance;
  if (search) {
    search.placeholder = maintenance
      ? "Search maintenance work, number, contact or task"
      : "Search contacts, numbers or email";
  }
  if (safety) {
    safety.textContent = maintenance
      ? "Review existing identity and evidence before attaching information or creating a new canonical contact."
      : "Matches do not create identity associations.";
  }
}

async function runSearch() {
  state.query = $("#search").value.trim();
  state.verification = $("#verification").value;
  state.maintenanceKind = $("#maintenance-kind")?.value || "all";

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

if ($("#maintenance-kind")) {
  $("#maintenance-kind").addEventListener(
    "change",
    () => {
      if (state.view === "maintenance") runSearch();
    },
  );
}

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
    if ($("#maintenance-kind")) $("#maintenance-kind").value = "all";

    state.query = "";
    state.verification = "";
    state.maintenanceKind = "all";

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
    updateViewControls();

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

async function openMaintenanceSearch(value) {
  const text = String(value || "").trim();
  if (!text) return;
  state.view = "all";
  updateViewControls();
  state.query = text;
  state.verification = "";
  $("#search").value = text;
  $("#verification").value = "";
  document.querySelectorAll("#view-tabs button").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === "all");
  });
  await loadDirectory();
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-maintenance-action]");
  if (!button) return;

  const action = button.dataset.maintenanceAction;
  if (action === "find-match" || action === "open-contact") {
    event.preventDefault();
    await openMaintenanceSearch(button.dataset.maintenanceSearch || "");
    return;
  }

  if (action === "create-contact") {
    event.preventDefault();
    openNewContactEditor();
    const name = button.dataset.maintenanceName || "";
    const pointValue = button.dataset.maintenanceValue || "";
    const pointType = button.dataset.maintenancePointType || "phone";
    const confidence = button.dataset.maintenanceConfidence || "unverified";
    const nameField = document.querySelector('#editor-fields [name="canonical_name"]');
    const displayField = document.querySelector('#editor-fields [name="display_name"]');
    const typeField = document.querySelector('#editor-fields [name="initial_point_type"]');
    const valueField = document.querySelector('#editor-fields [name="initial_point_value"]');
    const confidenceField = document.querySelector('#editor-fields [name="initial_point_confidence"]');
    const notesField = document.querySelector('#editor-fields [name="initial_point_notes"]');
    if (nameField && name) nameField.value = name;
    if (displayField && name) displayField.value = name;
    if (typeField) {
      typeField.value = ["phone", "email"].includes(pointType) ? pointType : "phone";
      typeField.dispatchEvent(new Event("change"));
    }
    if (valueField) valueField.value = pointValue;
    if (confidenceField) confidenceField.value = ["confirmed","probable","unverified"].includes(confidence) ? confidence : "unverified";
    if (notesField) notesField.value = "Created from Contacts maintenance identity-resolution review. Verify existing contacts and evidence before saving.";
  }
});

document.addEventListener("click", async (event) => {
  const sourceButton = event.target.closest("[data-open-source]");
  if (!sourceButton) return;
  event.preventDefault();
  event.stopPropagation();
  const provenanceId = Number(sourceButton.dataset.openSource || 0);
  if (!provenanceId) return;

  state.view = "sources";
  state.query = "";
  state.verification = "";
  $("#search").value = "";
  $("#verification").value = "";
  document.querySelectorAll("#view-tabs button").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === "sources");
  });

  try {
    const rows = await api(`/api/contacts/sources?provenance_id=${encodeURIComponent(provenanceId)}&limit=1&offset=0`);
    await loadDirectory();
    if (rows && rows.length) renderDetail(rows[0]);
  } catch (error) {
    console.error("Unable to open evidence source", error);
  }
});

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

/*
 * Candidate-review source contract.
 *
 * Browser authentication is the existing Edge1 session.
 * The Operations API HMAC credential is never exposed here.
 * Activation occurs only after the authenticated review route
 * is separately integrated and tested.
 */

function edge1Cookie(name) {
  const prefix = `${name}=`;

  for (const item of document.cookie.split(";")) {
    const value = item.trim();

    if (value.startsWith(prefix)) {
      return decodeURIComponent(
        value.slice(prefix.length)
      );
    }
  }

  return "";
}

function correlationReviewAvailable(row) {
  return Boolean(
    row &&
    Number.isInteger(Number(row.correlation_id)) &&
    Number(row.correlation_id) > 0 &&
    ["pending", "accepted"].includes(
      row.review_status || "pending"
    )
  );
}

function correlationReviewHtml(row) {
  if (!correlationReviewAvailable(row)) {
    return "";
  }

  const status = row.review_status || "pending";

  if (status === "pending") {
    return `
      <section class="correlation-review">
        <div class="detail-label">Review candidate</div>
        <div class="correlation-review-actions">
          <button
            type="button"
            data-correlation-action="accept"
            data-correlation-id="${Number(row.correlation_id)}"
          >Accept candidate</button>
          <button
            type="button"
            data-correlation-action="reject"
            data-correlation-id="${Number(row.correlation_id)}"
          >Reject candidate</button>
        </div>
        <div class="correlation-review-note">
          Accepting a candidate does not merge identities and
          does not itself create a durable relationship.
        </div>
      </section>
    `;
  }

  return `
    <section class="correlation-review">
      <div class="detail-label">Accepted candidate</div>
      <div class="correlation-review-note">
        Promotion requires supporting provenance and creates a
        durable relationship. It does not merge identities.
      </div>
    </section>
  `;
}

async function submitCorrelationReview(
  candidateId,
  operation,
  payload = {}
) {
  const csrf = edge1Cookie(
    "__Secure-wwcx_edge1_ops_csrf"
  );

  if (!csrf) {
    throw new Error(
      "Authenticated Edge1 review session is required."
    );
  }

  const response = await fetch(
    `/edge1-ops/api/v1/contacts/correlations/` +
      `${candidateId}/${operation}`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-WWCX-CSRF": csrf,
      },
      body: JSON.stringify(payload),
    }
  );

  let body = {};

  try {
    body = await response.json();
  } catch (_) {
    body = {};
  }

  if (!response.ok) {
    throw new Error(
      body.error ||
      body.message ||
      `Review request failed (HTTP ${response.status})`
    );
  }

  return body;
}

async function handleCorrelationReviewClick(event) {
  const button = event.target.closest(
    "[data-correlation-action]"
  );

  if (!button) {
    return;
  }

  const candidateId = Number(
    button.dataset.correlationId
  );

  const operation =
    button.dataset.correlationAction;

  if (
    !Number.isInteger(candidateId) ||
    candidateId < 1 ||
    !["accept", "reject"].includes(operation)
  ) {
    return;
  }

  button.disabled = true;

  try {
    await submitCorrelationReview(
      candidateId,
      operation,
      {}
    );

    await loadDirectory();
  } catch (error) {
    window.alert(
      error instanceof Error
        ? error.message
        : "Candidate review failed."
    );
  } finally {
    button.disabled = false;
  }
}

document.addEventListener(
  "click",
  handleCorrelationReviewClick
);

/* ==========================================================
 * Contact Manager CRUD editor
 *
 * UI may be deployed while the server mutation gate is OFF.
 * The authenticated server bridge remains authoritative.
 * ========================================================== */

const CONTACT_CRUD_ROOT =
  "/edge1-ops/api/v1/contacts/crud/";

function contactIdempotencyKey(operation) {
  const safeOperation = String(operation)
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .slice(0, 32);

  if (
    window.crypto &&
    typeof window.crypto.randomUUID === "function"
  ) {
    return (
      `contacts-${safeOperation}-` +
      window.crypto.randomUUID()
    );
  }

  return (
    `contacts-${safeOperation}-` +
    `${Date.now()}-${Math.floor(Math.random() * 1e9)}`
  );
}

const contactMutationsInFlight = new Map();

async function submitContactMutation(
  operation,
  parameters = {}
) {
  const csrf = edge1Cookie(
    "__Secure-wwcx_edge1_ops_csrf"
  );

  if (!csrf) {
    throw new Error(
      "An authenticated Edge1 session is required."
    );
  }

  const logicalKey = contactIdempotencyKey(operation);
  const payload = {
    ...parameters,
    idempotency_key: logicalKey,
  };

  const signature =
    String(operation) + ":" + JSON.stringify(parameters);

  if (contactMutationsInFlight.has(signature)) {
    return contactMutationsInFlight.get(signature);
  }

  const execute = async () => {
    let lastError = null;

    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetch(
          CONTACT_CRUD_ROOT + operation,
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
              "X-WWCX-CSRF": csrf,
            },
            body: JSON.stringify(payload),
          }
        );

        let body = {};

        try {
          body = await response.json();
        } catch (_) {
          body = {};
        }

        if (!response.ok) {
          throw new Error(
            body.error ||
            body.message ||
            `Contact update failed (HTTP ${response.status})`
          );
        }

        return body;
      } catch (error) {
        lastError = error;

        if (attempt !== 0) {
          throw error;
        }
      }
    }

    throw lastError;
  };

  const pending = execute();
  contactMutationsInFlight.set(signature, pending);

  try {
    return await pending;
  } finally {
    if (contactMutationsInFlight.get(signature) === pending) {
      contactMutationsInFlight.delete(signature);
    }
  }
}

function editorModal() {
  return $("#contact-editor-modal");
}

function editorMessage(message = "", kind = "") {
  const target = $("#contact-editor-message");

  if (!target) {
    return;
  }

  if (!message) {
    target.hidden = true;
    target.textContent = "";
    target.className = "contact-editor-message";
    return;
  }

  target.hidden = false;
  target.textContent = message;
  target.className =
    `contact-editor-message ${kind}`.trim();
}

function closeContactEditor() {
  const modal = editorModal();

  if (!modal) {
    return;
  }

  modal.hidden = true;
  editorMessage();

  const form = $("#contact-editor-form");

  if (form) {
    form.reset();
  }
}

function verificationChoiceLabel(value) {
  const labels = {
    verified: "✓ Verified",
    unverified: "✕ Unverified",
  };

  return labels[value] || value;
}

function editorField(
  id,
  label,
  value = "",
  options = {}
) {
  const {
    type = "text",
    required = false,
    wide = false,
    choices = null,
    placeholder = "",
  } = options;

  const requiredText =
    required ? " required" : "";

  const wideClass =
    wide ? " wide" : "";

  if (Array.isArray(choices)) {
    const optionHtml = choices
      .map((choice) => {
        const choiceValue =
          choice &&
          typeof choice === "object"
            ? choice.value
            : choice;

        const choiceLabel =
          choice &&
          typeof choice === "object"
            ? choice.label
            : verificationChoiceLabel(choice);

        const selected =
          String(choiceValue) === String(value)
            ? " selected"
            : "";

        return (
          `<option value="${escapeHtml(choiceValue)}"` +
          `${selected}>` +
          `${escapeHtml(choiceLabel)}</option>`
        );
      })
      .join("");

    return `
      <div class="contact-editor-field${wideClass}">
        <label for="${escapeHtml(id)}">
          ${escapeHtml(label)}
        </label>
        <select
          id="${escapeHtml(id)}"
          name="${escapeHtml(id)}"
          ${requiredText}
        >
          ${optionHtml}
        </select>
      </div>
    `;
  }

  if (type === "textarea") {
    return `
      <div class="contact-editor-field${wideClass}">
        <label for="${escapeHtml(id)}">
          ${escapeHtml(label)}
        </label>
        <textarea
          id="${escapeHtml(id)}"
          name="${escapeHtml(id)}"
          placeholder="${escapeHtml(placeholder)}"
          ${requiredText}
        >${escapeHtml(value || "")}</textarea>
      </div>
    `;
  }

  return `
    <div class="contact-editor-field${wideClass}">
      <label for="${escapeHtml(id)}">
        ${escapeHtml(label)}
      </label>
      <input
        id="${escapeHtml(id)}"
        name="${escapeHtml(id)}"
        type="${escapeHtml(type)}"
        value="${escapeHtml(value || "")}"
        placeholder="${escapeHtml(placeholder)}"
        ${requiredText}
      >
    </div>
  `;
}

function openContactEditor({
  mode,
  title,
  entityId = "",
  contactPointId = "",
  fieldsHtml,
  submitLabel = "Save",
}) {
  const modal = editorModal();

  if (!modal) {
    throw new Error(
      "Contact editor is not available."
    );
  }

  $("#editor-mode").value = mode;
  $("#editor-entity-id").value = entityId || "";
  $("#editor-contact-point-id").value =
    contactPointId || "";

  $("#contact-editor-title").textContent = title;
  $("#editor-fields").innerHTML =
    `<div class="contact-editor-grid">` +
    fieldsHtml +
    `</div>` +
    `<div class="contact-editor-note">` +
    `Changes are recorded through the authenticated ` +
    `Edge1 Operations service. Identity records are never ` +
    `silently merged.` +
    `</div>`;

  const classificationField =
      $("#editor-fields [name=\"classification\"]");

    if (classificationField) {
      const help = document.createElement("div");
      help.className = "field-help";
      help.textContent =
        "What is this used for? Examples: Main, Mobile, " +
        "Office, Support, Billing or Fax.";
      classificationField.insertAdjacentElement(
        "afterend",
        help
      );
    }

    $("#editor-submit").textContent = submitLabel;

  const initialType =
    $("#editor-fields [name=\"initial_point_type\"]");

  if (initialType) {
    const dependentNames = [
      "initial_point_value",
      "initial_point_classification",
      "initial_point_confidence",
      "initial_point_notes",
    ];

    const updateInitialPointVisibility = () => {
      const visible =
        Boolean(initialType.value);

      const valueField =
        $("#editor-fields [name=\"initial_point_value\"]");

      const valueLabel =
        valueField &&
        valueField.closest(".contact-editor-field")
          ?.querySelector("label");

      const labels = {
        phone: "Phone number",
        email: "Email address",
        postal: "Street / mailing address",
        website: "Website address",
        domain: "Domain name",
      };

      if (valueLabel) {
        valueLabel.textContent =
          labels[initialType.value] ||
          "Contact information";
      }

      if (valueField) {
        const placeholders = {
          phone: "Example: (306) 555-0123",
          email: "Example: name@example.com",
          postal: "Street, city, province/state, postal code",
          website: "Example: https://example.com",
          domain: "Example: example.com",
        };

        valueField.placeholder =
          placeholders[initialType.value] || "";
      }

      for (const name of dependentNames) {
        const field =
          $("#editor-fields [name=\"" + name + "\"]");

        const wrapper =
          field &&
          field.closest(
            ".contact-editor-field"
          );

        if (wrapper) {
          wrapper.hidden = !visible;
        }
      }
    };

    initialType.addEventListener(
      "change",
      updateInitialPointVisibility
    );

    updateInitialPointVisibility();
  }

  editorMessage();
  modal.hidden = false;
}


function openNewContactEditor() {
  openContactEditor({
    mode: "entity.create",
    title: "New Contact",
    fieldsHtml:
      editorField(
        "entity_type",
        "Contact type",
        "person",
        {
          choices: [
            {
              value: "person",
              label: "👤 Person",
            },
            {
              value: "organization",
              label: "🏢 Organization",
            },
          ],
          required: true,
        }
      ) +
      editorField(
        "canonical_name",
        "Name",
        "",
        {required: true}
      ) +
      editorField(
        "display_name",
        "Display name (optional)"
      ) +
      editorField(
        "verification_status",
        "Verification",
        "unverified",
        {
          choices: [
            "verified",
            "unverified",
          ],
          required: true,
        }
      ) +
      editorField(
        "notes",
        "Notes",
        "",
        {
          type: "textarea",
          wide: true,
        }
      ) +
      `
        <div class="contact-editor-field wide">
          <div class="field-help">
            Contact information below is optional.
            It can also be added after creating
            the contact.
          </div>
        </div>
      ` +
      editorField(
        "initial_point_type",
        "Contact information type (optional)",
        "",
        {
          choices: [
            {
              value: "",
              label: "Choose a type…",
            },
            {
              value: "phone",
              label: "☎ Phone",
            },
            {
              value: "email",
              label: "✉ Email",
            },
            {
              value: "postal",
              label: "⌂ Address",
            },
            {
              value: "website",
              label: "🌐 Website",
            },
            {
              value: "domain",
              label: "◎ Domain",
            },
          ],
          wide: true,
        }
      ) +
      editorField(
        "initial_point_value",
        "Phone, email, address or web address",
        "",
        {
          wide: true,
          placeholder:
            "Leave blank to create the contact without contact information",
        }
      ) +
      editorField(
        "initial_point_classification",
        "Label (optional)",
        "",
        {
          placeholder:
            "Examples: Mobile, Work, Home, Main office",
        }
      ) +
      editorField(
        "initial_point_confidence",
        "Association confidence",
        "unverified",
        {
          choices: [
            "unverified",
            "probable",
            "confirmed",
          ],
        }
      ) +
      editorField(
        "initial_point_notes",
        "Why does this belong to this contact? (optional)",
        "",
        {
          type: "textarea",
          wide: true,
          placeholder:
            "Evidence or reason for associating this information with the contact",
        }
      ),
    submitLabel: "Create Contact",
  });
}

function openEditEntityEditor(row) {
  openContactEditor({
    mode: "entity.update",
    title: "Edit Contact",
    entityId: row.entity_id,
    fieldsHtml:
      editorField(
        "canonical_name",
        "Name",
        row.canonical_name || "",
        {required: true}
      ) +
      editorField(
        "display_name",
        "Display name (optional)",
        row.display_name || ""
      ) +
      editorField(
        "verification_status",
        "Verification",
        row.verification_status || "unverified",
        {
          choices: [
            "verified",
            "unverified",
          ],
          required: true,
        }
      ) +
      (
        Object.prototype.hasOwnProperty.call(
          row,
          "notes"
        )
          ? editorField(
              "notes",
              "Notes",
              row.notes || "",
              {
                type: "textarea",
                wide: true,
              }
            )
          : `
              <div
                class="contact-editor-field wide"
              >
                <div class="field-help">
                  Existing notes are preserved.
                  Notes are not available in this
                  directory view.
                </div>
              </div>
            `
      ),
  });
}

function openAddPointEditor(row) {
  openContactEditor({
    mode: "point.add",
    title: "Add Contact Information",
    entityId: row.entity_id,
    fieldsHtml:
      editorField(
        "point_type",
        "Contact information type",
        "phone",
        {
          choices: [
            {
              value: "phone",
              label: "☎ Phone",
            },
            {
              value: "fax",
              label: "▣ Fax",
            },
            {
              value: "email",
              label: "✉ Email",
            },
            {
              value: "postal",
              label: "⌂ Address",
            },
            {
              value: "website",
              label: "🌐 Website",
            },
            {
              value: "domain",
              label: "◎ Domain",
            },
          ],
          required: true,
        }
      ) +
      editorField(
        "value",
        "Phone, email, address or web address",
        "",
        {
          required: true,
          placeholder:
            "Enter the contact information",
        }
      ) +
      editorField(
        "classification",
        "Label (optional)"
      ) +
      editorField(
        "confidence",
        "Association confidence",
        "unverified",
        {
          choices: [
            "unverified",
            "probable",
            "confirmed",
          ],
          required: true,
        }
      ) +
      editorField(
        "assertion_notes",
        "Why does this belong to this contact?",
        "",
        {
          type: "textarea",
          wide: true,
          placeholder:
            "Why is this contact information associated " +
            "with this person or organization?",
        }
      ),
    submitLabel: "Add Contact Information",
  });
}

function openEditPointEditor(row) {
  openContactEditor({
    mode: "point.update",
    title: "Edit Contact Information",
    entityId: row.entity_id,
    contactPointId: row.contact_point_id,
    fieldsHtml:
      editorField(
        "value",
        "Value",
        row.display_value ||
          row.normalized_value ||
          "",
        {required: true}
      ) +
      editorField(
        "classification",
        "Label (optional)",
        row.classification || ""
      ),
  });
}

function entityActionHtml(row) {
  if (!row || !row.entity_id) {
    return "";
  }

  const lifecycle =
    row.lifecycle_status || "active";

  const lifecycleMenu =
    lifecycle === "inactive"
      ? `
        <button
          type="button"
          class="contact-menu-item"
          data-contact-action="restore"
        >
          Restore contact
        </button>
      `
      : `
        <button
          type="button"
          class="contact-menu-item destructive"
          data-contact-action="archive"
        >
          Archive contact
        </button>
      `;

  return `
    <div class="contact-record-actions compact-actions">

      <button
        type="button"
        class="contact-icon-action"
        data-contact-action="edit-entity"
        title="Edit contact"
        aria-label="Edit contact"
      >
        ✎
      </button>

      <div class="contact-menu">
        <button
          type="button"
          class="contact-icon-action contact-menu-trigger"
          data-contact-menu-trigger
          title="More contact actions"
          aria-label="More contact actions"
          aria-expanded="false"
        >
          ⋯
        </button>

        <div
          class="contact-menu-popover"
          hidden
        >
          <button
            type="button"
            class="contact-menu-item"
            data-contact-action="merge"
          >
            Merge with another contact…
          </button>

          ${lifecycleMenu}
        </div>
      </div>

    </div>
  `;
}

function pointActionHtml(row) {
  if (
    !row ||
    !row.entity_id ||
    !row.contact_point_id
  ) {
    return "";
  }

  const mailAddress = String(
    row.normalized_value || row.display_value || ""
  ).trim();

  const mailAction =
    row.point_type === "email" && mailAddress.includes("@")
      ? `
        <a
          class="contact-icon-action"
          href="/edge1-ops/mail-room/?compose=1&to=${encodeURIComponent(mailAddress)}"
          title="Compose email in Mail Room"
          aria-label="Compose email to ${escapeHtml(mailAddress)} in Mail Room"
        >
          ✉
        </a>
      `
      : "";

  return `
    <div class="contact-point-actions contextual-actions">

      ${mailAction}

      <button
        type="button"
        class="contact-icon-action"
        data-contact-action="edit-point"
        title="Edit contact information"
        aria-label="Edit contact information"
      >
        ✎
      </button>

      <div class="contact-menu">
        <button
          type="button"
          class="contact-icon-action contact-menu-trigger"
          data-contact-menu-trigger
          title="More contact information actions"
          aria-label="More contact information actions"
          aria-expanded="false"
        >
          ⋯
        </button>

        <div
          class="contact-menu-popover"
          hidden
        >
          <button
            type="button"
            class="contact-menu-item destructive"
            data-contact-action="detach-point"
          >
            Remove from contact
          </button>
        </div>
      </div>

    </div>
  `;
}


function closeContactMenus(exceptMenu = null) {
  document
    .querySelectorAll(".contact-menu-popover")
    .forEach((menu) => {
      if (menu !== exceptMenu) {
        menu.hidden = true;

        const trigger =
          menu.parentElement?.querySelector(
            "[data-contact-menu-trigger]"
          );

        if (trigger) {
          trigger.setAttribute(
            "aria-expanded",
            "false"
          );
        }
      }
    });
}

document.addEventListener("click", (event) => {
  const trigger =
    event.target.closest(
      "[data-contact-menu-trigger]"
    );

  if (trigger) {
    event.preventDefault();
    event.stopPropagation();

    const menu =
      trigger.parentElement?.querySelector(
        ".contact-menu-popover"
      );

    if (!menu) {
      return;
    }

    const opening = menu.hidden;

    closeContactMenus(menu);

    menu.hidden = !opening;

    trigger.setAttribute(
      "aria-expanded",
      opening ? "true" : "false"
    );

    return;
  }

  if (!event.target.closest(".contact-menu")) {
    closeContactMenus();
  }
});

async function refreshContactManager() {
  await Promise.all([
    loadSummary(),
    loadDirectory(),
  ]);
}

function editorPayload(mode) {
  const value = (id) => {
    const el = $("#" + id);
    return el ? el.value.trim() : "";
  };

  const entityId =
    Number($("#editor-entity-id").value);

  const pointId =
    Number($("#editor-contact-point-id").value);

  if (mode === "entity.create") {
    return {
      entity_type: value("entity_type"),
      canonical_name: value("canonical_name"),
      display_name:
        value("display_name") || null,
      verification_status:
        value("verification_status"),
      notes: value("notes") || null,
    };
  }

  if (mode === "entity.update") {
    const payload = {
      entity_id: entityId,
      canonical_name: value("canonical_name"),
      display_name:
        value("display_name") || null,
      verification_status:
        value("verification_status"),
    };

    const notesField =
      document.querySelector(
        '#contact-editor-form [name="notes"]'
      );

    if (notesField) {
      payload.notes =
        notesField.value.trim() || null;
    }

    return payload;
  }

  if (mode === "point.add") {
    return {
      entity_id: entityId,
      point_type: value("point_type"),
      value: value("value"),
      classification:
        value("classification") || null,
      confidence: value("confidence"),
      assertion_notes:
        value("assertion_notes") || null,
    };
  }

  if (mode === "point.update") {
    return {
      entity_id: entityId,
      contact_point_id: pointId,
      value: value("value"),
      classification:
        value("classification") || null,
    };
  }

  throw new Error(
    "Unsupported editor operation."
  );
}


function initialContactPointPayload() {
  const value = (id) => {
    const el = $("#" + id);
    return el ? el.value.trim() : "";
  };

  const pointType =
    value("initial_point_type");

  const pointValue =
    value("initial_point_value");

  if (!pointType && !pointValue) {
    return null;
  }

  if (!pointType || !pointValue) {
    throw new Error(
      "Choose a contact information type and enter its value, or leave both blank."
    );
  }

  return {
    point_type: pointType,
    value: pointValue,
    classification:
      value(
        "initial_point_classification"
      ) || null,
    confidence:
      value(
        "initial_point_confidence"
      ) || "unverified",
    assertion_notes:
      value(
        "initial_point_notes"
      ) || null,
  };
}

async function handleContactEditorSubmit(event) {
  event.preventDefault();

  const mode = $("#editor-mode").value;
  const button = $("#editor-submit");

  button.disabled = true;
  editorMessage("Saving…");

  try {
    if (mode === "entity.merge") {
      const sourceId =
        Number($("#editor-entity-id")?.value || 0);

      const targetId =
        Number($("#merge-target-entity")?.value || 0);

      const survivorChoice =
        document.querySelector(
          'input[name="merge_survivor"]:checked'
        )?.value;

      const confirmed =
        Boolean($("#merge-confirm")?.checked);

      if (
        !Number.isInteger(sourceId) ||
        sourceId < 1 ||
        !Number.isInteger(targetId) ||
        targetId < 1 ||
        sourceId === targetId
      ) {
        throw new Error(
          "Choose two different contacts to merge."
        );
      }

      if (!confirmed) {
        throw new Error(
          "Review and confirm the merge first."
        );
      }

      const survivorId =
        survivorChoice === "target"
          ? targetId
          : sourceId;

      const absorbedId =
        survivorId === sourceId
          ? targetId
          : sourceId;

      const targetLabel =
        $("#merge-target-entity")
          ?.selectedOptions?.[0]
          ?.textContent?.trim() ||
        `Contact ${targetId}`;

      const sourceLabel =
        state.selected?.display_name ||
        state.selected?.canonical_name ||
        `Contact ${sourceId}`;

      const survivorLabel =
        survivorChoice === "target"
          ? targetLabel
          : sourceLabel;

      const absorbedLabel =
        survivorChoice === "target"
          ? sourceLabel
          : targetLabel;


      await submitContactMutation(
        "entity.merge",
        {
          survivor_entity_id: survivorId,
          absorbed_entity_id: absorbedId,
        }
      );

      await refreshContactManager();

      const selected =
        (Array.isArray(state.rows)
          ? state.rows
          : []
        ).find(
          (candidate) =>
            Number(candidate.entity_id) ===
            survivorId
        );

      if (selected) {
        state.selected = selected;
      }

      renderContactManager();

      editorMessage(
        "Contacts merged successfully.",
        "success"
      );

      closeContactEditor();
      return;
    }

    if (mode === "entity.create") {
      const initialPoint =
        initialContactPointPayload();

      const body =
        await submitContactMutation(
          mode,
          editorPayload(mode)
        );

      const entityId =
        Number(body.entity_id);

      if (
        !Number.isInteger(entityId) ||
        entityId < 1
      ) {
        throw new Error(
          "The contact was created, but its contact identifier was not returned."
        );
      }

      let pointFailure = null;

      if (initialPoint) {
        try {
          await submitContactMutation(
            "point.add",
            {
              entity_id: entityId,
              ...initialPoint,
            }
          );
        } catch (error) {
          pointFailure = error;
        }
      }

      await refreshContactManager();

      const selected =
        (Array.isArray(state.rows)
          ? state.rows
          : []
        ).find(
          (row) =>
            Number(row.entity_id) ===
            entityId
        );

      if (selected) {
        state.selected = selected;
      }

      renderContactManager();

      if (pointFailure) {
        editorMessage(
          "Contact created successfully, but the contact information could not be added. The contact was not created again. Add the information from the Contact Record.",
          "error"
        );
        return;
      }

      editorMessage(
        initialPoint
          ? "Contact and contact information created successfully."
          : "Contact created successfully.",
        "success"
      );

      closeContactEditor();
      return;
    }

    await submitContactMutation(
      mode,
      editorPayload(mode)
    );

    editorMessage(
      "Saved successfully.",
      "success"
    );

    await refreshContactManager();

    closeContactEditor();
  } catch (error) {
    editorMessage(
      error instanceof Error
        ? error.message
        : "Unable to save contact.",
      "error"
    );
  } finally {
    button.disabled = false;
  }
}


function mergeContactName(row) {
  if (!row) {
    return "Unknown contact";
  }

  return (
    row.display_name ||
    row.canonical_name ||
    `Contact ${Number(row.entity_id) || "?"}`
  );
}

function mergeContactMethods(row) {
  const points = Array.isArray(row?.contact_points)
    ? row.contact_points
    : [];

  if (!points.length) {
    return `
      <div class="field-help">
        No contact methods are shown for this record.
      </div>
    `;
  }

  return points.map((point) => {
    const type = point.point_type || "contact";
    const value =
      point.display_value ||
      point.normalized_value ||
      "Unknown";

    /*
     * Association state belongs to the assertion, not the
     * underlying reusable contact point.  An active point can
     * therefore still be historical for this entity.
     */
    const ended =
      point.assertion_valid_to !== null &&
      point.assertion_valid_to !== undefined &&
      String(point.assertion_valid_to).trim() !== "";

    const stateLabel = ended
      ? "Historical"
      : "Current";

    const temporalDetail = ended
      ? ` · ended ${escapeHtml(
          String(point.assertion_valid_to)
        )}`
      : "";

    return `
      <div class="field-help">
        ${escapeHtml(type)}:
        ${escapeHtml(value)}
        · <strong>${stateLabel}</strong>${temporalDetail}
      </div>
    `;
  }).join("");
}

function mergeComparisonCard(label, row) {
  if (!row) {
    return `
      <div class="contact-editor-field wide">
        <label>${escapeHtml(label)}</label>
        <div class="field-help">
          Select a contact to compare.
        </div>
      </div>
    `;
  }

  return `
    <div class="contact-editor-field wide">
      <label>${escapeHtml(label)}</label>
      <strong>${escapeHtml(mergeContactName(row))}</strong>
      <div class="field-help">
        ${escapeHtml(row.entity_type || "contact")}
        · ${escapeHtml(
          row.verification_status || "unverified"
        )}
      </div>
      ${mergeContactMethods(row)}
    </div>
  `;
}

async function hydrateMergeEntity(row) {
  if (!row || !row.entity_id) {
    return row;
  }

  const entityId = Number(row.entity_id);

  /*
   * Reuse the entity-centric rows already loaded by the
   * directory when possible.
   */
  const localRows = Array.isArray(state.rows)
    ? state.rows
    : [];

  const local = localRows.find(
    (candidate) =>
      Number(candidate?.entity_id) === entityId &&
      Array.isArray(candidate?.contact_points)
  );

  if (local) {
    return {
      ...row,
      ...local,
      entity_id: entityId,
      contact_points: local.contact_points,
    };
  }

  /*
   * /entities is intentionally a one-row-per-entity summary.
   * Hydrate Merge comparison through the existing detailed
   * search projection, then retain only rows for this exact
   * canonical entity.
   */
  const searchName =
    row.canonical_name ||
    row.display_name ||
    "";

  const params = new URLSearchParams({
    q: String(searchName),
    kind: "all",
    limit: "100",
  });

  const body = await api(
    `/api/contacts/search?${params}`
  );

  let rows = [];

  if (Array.isArray(body)) {
    rows = body;
  } else {
    for (const key of [
      "rows",
      "results",
      "items",
    ]) {
      if (Array.isArray(body?.[key])) {
        rows = body[key];
        break;
      }
    }
  }

  const exactRows = rows.filter(
    (candidate) =>
      Number(candidate?.entity_id) === entityId
  );

  const hydratedRows =
    entityDirectoryRows(exactRows);

  const hydrated = hydratedRows.find(
    (candidate) =>
      Number(candidate?.entity_id) === entityId
  );

  if (!hydrated) {
    return {
      ...row,
      entity_id: entityId,
      contact_points: [],
    };
  }

  return {
    ...row,
    ...hydrated,
    entity_id: entityId,
  };
}

async function mergeEntitySearch(query, entityType) {
  const params = new URLSearchParams({
    q: String(query || "").trim(),
    entity_type: String(entityType || "").trim(),
    limit: "25",
    offset: "0",
  });

  const body = await api(
    `/api/contacts/entities?${params}`
  );

  let rows = [];

  if (Array.isArray(body)) {
    rows = body;
  } else {
    for (const key of [
      "rows",
      "results",
      "entities",
      "items",
    ]) {
      if (Array.isArray(body?.[key])) {
        rows = body[key];
        break;
      }
    }
  }

  return Promise.all(
    rows.map((row) =>
      hydrateMergeEntity(row)
    )
  );
}

async function openMergeContactPreview(row) {
  if (!row || !row.entity_id) {
    return;
  }

  const sourceId = Number(row.entity_id);
  const sourceName = mergeContactName(row);

  openContactEditor({
    mode: "entity.merge",
    title: "Merge Contacts",
    entityId: sourceId,
    fieldsHtml: `
      ${mergeComparisonCard("Current contact", row)}

      <div class="contact-editor-field wide">
        <label for="merge-target-search">
          Find the other contact
        </label>
        <input
          id="merge-target-search"
          type="search"
          autocomplete="off"
          placeholder="Search by contact name…"
        >
        <div class="field-help">
          Search for another
          ${escapeHtml(row.entity_type || "contact")}.
        </div>
      </div>

      <div class="contact-editor-field wide">
        <label for="merge-target-entity">
          Merge with
        </label>
        <select
          id="merge-target-entity"
          name="merge_target_entity"
          disabled
        >
          <option value="">
            Search for a contact first
          </option>
        </select>
      </div>

      <div
        id="merge-target-preview"
        class="contact-editor-field wide"
      >
        <div class="field-help">
          Select a search result to compare the records.
        </div>
      </div>

      <fieldset class="merge-survivor-fieldset">
        <legend>Which contact should we keep?</legend>

        <label class="merge-choice is-selected">
          <input
            type="radio"
            name="merge_survivor"
            value="source"
            checked
          >
          <span class="merge-choice-copy">
            <strong>Keep this contact</strong>
            <span>${escapeHtml(sourceName)}</span>
          </span>
        </label>

        <label
          class="merge-choice merge-choice-target is-disabled"
        >
          <input
            type="radio"
            name="merge_survivor"
            value="target"
            disabled
          >
          <span class="merge-choice-copy">
            <strong>Keep selected contact</strong>
            <span id="merge-target-survivor-name">
              Select the other contact first
            </span>
          </span>
        </label>
      </fieldset>

      <label class="merge-confirmation">
        <input
          id="merge-confirm"
          type="checkbox"
        >
        <span>
          <strong>I reviewed both records.</strong>
          <span>
            Merge these contacts and retain the other
            record in contact history.
          </span>
        </span>
      </label>

      <div class="merge-safety-note">
        Matching information never merges contacts automatically.
      </div>
    `,
    submitLabel: "Merge contacts",
  });

  const search = $("#merge-target-search");
  const select = $("#merge-target-entity");
  const preview = $("#merge-target-preview");
  const submit = $("#editor-submit");
  const survivorChoices = [
    ...document.querySelectorAll(
      'input[name="merge_survivor"]'
    ),
  ];

  const syncSurvivorChoices = () => {
    survivorChoices.forEach((radio) => {
      const choice = radio.closest(".merge-choice");

      if (!choice) {
        return;
      }

      choice.classList.toggle(
        "is-selected",
        Boolean(radio.checked)
      );

      choice.classList.toggle(
        "is-disabled",
        Boolean(radio.disabled)
      );
    });
  };

  survivorChoices.forEach((radio) => {
    radio.addEventListener(
      "change",
      syncSurvivorChoices
    );
  });

  syncSurvivorChoices();

  let results = [];
  let timer = null;

  const syncSubmit = () => {
    const targetId = Number(select?.value || 0);
    const confirmed =
      Boolean($("#merge-confirm")?.checked);

    if (submit) {
      submit.disabled =
        !confirmed ||
        !Number.isInteger(targetId) ||
        targetId < 1 ||
        targetId === sourceId;
    }
  };

  const renderTarget = () => {
    const targetId = Number(select?.value || 0);

    const target = results.find(
      (candidate) =>
        Number(candidate.entity_id) === targetId
    );

    if (preview) {
      preview.innerHTML = mergeComparisonCard(
        "Selected contact",
        target || null
      );
    }

    const targetRadio =
      document.querySelector(
        'input[name="merge_survivor"][value="target"]'
      );

    if (targetRadio) {
      targetRadio.disabled = !target;

      const targetSurvivorName =
        $("#merge-target-survivor-name");

      if (targetSurvivorName) {
        targetSurvivorName.textContent =
          target
            ? mergeContactName(target)
            : "Select the other contact first";
      }
    }

    syncSurvivorChoices();
    syncSubmit();
  };

  const runSearch = async () => {
    const query =
      String(search?.value || "").trim();

    if (query.length < 2) {
      results = [];

      if (select) {
        select.innerHTML = `
          <option value="">
            Enter at least two characters
          </option>
        `;
        select.disabled = true;
      }

      renderTarget();
      return;
    }

    if (select) {
      select.innerHTML =
        '<option value="">Searching…</option>';
      select.disabled = true;
    }

    try {
      results = (
        await mergeEntitySearch(
          query,
          row.entity_type
        )
      ).filter(
        (candidate) =>
          Number(candidate.entity_id) !== sourceId
      );

      if (!select) {
        return;
      }

      if (!results.length) {
        select.innerHTML = `
          <option value="">
            No matching contacts found
          </option>
        `;
        select.disabled = true;
      } else {
        select.innerHTML = `
          <option value="">
            Select a contact…
          </option>
          ${results.map((candidate) => `
            <option
              value="${Number(candidate.entity_id)}"
            >
              ${escapeHtml(mergeContactName(candidate))}
            </option>
          `).join("")}
        `;
        select.disabled = false;
      }

      renderTarget();

    } catch (error) {
      results = [];

      if (select) {
        select.innerHTML = `
          <option value="">
            Search unavailable
          </option>
        `;
        select.disabled = true;
      }

      if (preview) {
        preview.innerHTML = `
          <div class="contact-editor-message error">
            ${escapeHtml(
              error instanceof Error
                ? error.message
                : "Unable to search contacts."
            )}
          </div>
        `;
      }

      syncSubmit();
    }
  };

  search?.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(runSearch, 250);
  });

  select?.addEventListener(
    "change",
    renderTarget
  );

  $("#merge-confirm")?.addEventListener(
    "change",
    syncSubmit
  );

  syncSubmit();
}

async function handleContactManagerClick(event) {
  const close = event.target.closest(
    "[data-editor-close]"
  );

  if (close) {
    closeContactEditor();
    return;
  }

  const action = event.target.closest(
    "[data-contact-action]"
  );

  if (!action) {
    return;
  }

  const row = state.selected;

  if (!row || !row.entity_id) {
    return;
  }

  const operation =
    action.dataset.contactAction;

  if (operation === "merge") {
    closeContactMenus();
    openMergeContactPreview(row);
    return;
  }

  if (operation === "edit-entity") {
    openEditEntityEditor(row);
    return;
  }

  if (operation === "add-point") {
    openAddPointEditor(row);
    return;
  }

  if (operation === "edit-point") {
    openEditPointEditor(row);
    return;
  }

  if (operation === "archive") {
    if (
      !window.confirm(
        "Archive this contact? Historical evidence " +
        "and contact associations will be retained."
      )
    ) {
      return;
    }

    action.disabled = true;

    try {
      await submitContactMutation(
        "entity.archive",
        {
          entity_id: Number(row.entity_id),
        }
      );

      state.selected = null;
      await refreshContactManager();
    } catch (error) {
      window.alert(
        error instanceof Error
          ? error.message
          : "Unable to archive contact."
      );
    } finally {
      action.disabled = false;
    }

    return;
  }

  if (operation === "restore") {
    action.disabled = true;

    try {
      await submitContactMutation(
        "entity.restore",
        {
          entity_id: Number(row.entity_id),
        }
      );

      await refreshContactManager();
    } catch (error) {
      window.alert(
        error instanceof Error
          ? error.message
          : "Unable to restore contact."
      );
    } finally {
      action.disabled = false;
    }

    return;
  }

  if (operation === "detach-point") {
    if (
      !window.confirm(
        "Remove this contact information from this " +
        "contact? Historical association evidence " +
        "will be retained."
      )
    ) {
      return;
    }

    action.disabled = true;

    try {
      await submitContactMutation(
        "point.detach",
        {
          entity_id: Number(row.entity_id),
          contact_point_id:
            Number(row.contact_point_id),
        }
      );

      state.selected = null;
      await refreshContactManager();
    } catch (error) {
      window.alert(
        error instanceof Error
          ? error.message
          : "Unable to remove contact information."
      );
    } finally {
      action.disabled = false;
    }
  }
}

const newContactButton =
  $("#new-contact-button");

if (newContactButton) {
  newContactButton.addEventListener(
    "click",
    openNewContactEditor
  );
}

const contactEditorForm =
  $("#contact-editor-form");

if (contactEditorForm) {
  contactEditorForm.addEventListener(
    "submit",
    handleContactEditorSubmit
  );
}

document.addEventListener(
  "click",
  handleContactManagerClick
);

document.addEventListener(
  "keydown",
  (event) => {
    if (
      event.key === "Escape" &&
      editorModal() &&
      !editorModal().hidden
    ) {
      closeContactEditor();
    }
  }
);
