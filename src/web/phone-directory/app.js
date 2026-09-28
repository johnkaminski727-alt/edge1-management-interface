(function () {
  "use strict";

  const API_BASE = "/api/intelligence";

function sourceStatusLabel(status) {
  const labels = {
    recovered: "Source document recovered",
    missing: "Source document not recovered",
    partial: "Source document partially recovered",
    verified: "Source document verified",
  };

  return labels[status] || status || "Source status unavailable";
}
  const PAGE_SIZE = 25;

  const state = {
    mode: "live",
    status: "",
    query: "",
    npa: "",
    offset: 0,
    total: 0,
    phones: [],
    selectedId: null,
    view: "phones",
    sources: [],
  };

  const elements = {
    form: document.querySelector("#search-form"),
    query: document.querySelector("#query"),
    status: document.querySelector("#status"),
    npa: document.querySelector("#npa"),
    clear: document.querySelector("#clear-filters"),
    results: document.querySelector("#phone-results"),
    count: document.querySelector("#result-count"),
    title: document.querySelector("#results-title"),
    message: document.querySelector("#state-message"),
    previous: document.querySelector("#previous-page"),
    next: document.querySelector("#next-page"),
    page: document.querySelector("#page-status"),
    detailTitle: document.querySelector("#detail-title"),
    detailStatus: document.querySelector("#detail-status"),
    detail: document.querySelector("#detail-content"),
    mobileTotal: document.querySelector("#mobile-total"),
    mobileConfirmed: document.querySelector("#mobile-confirmed"),
    mobileSearch: document.querySelector("#mobile-search-button"),
    mobileFilter: document.querySelector("#mobile-filter-button"),
    mobileBack: document.querySelector("#mobile-back-results"),
    filterPanel: document.querySelector("#directory-filters"),
    detailPanel: document.querySelector("#record-detail"),
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function statusBadge(status) {
    const safe = [
      "confirmed",
      "probable",
      "unresolved",
      "disputed",
    ].includes(status)
      ? status
      : "unresolved";

    return (
      `<span class="badge ${safe}">` +
      `${escapeHtml(status || "unresolved")}` +
      "</span>"
    );
  }

  async function loadDashboard() {
    try {
      const response = await fetch(
        `${API_BASE}/dashboard`,
        {
          cache: "no-store",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Dashboard request returned ${response.status}`
        );
      }

      const payload = await response.json();

      document.querySelector("#stat-total").textContent =
        Number(payload.total_numbers || 0).toLocaleString();

      document.querySelector("#stat-confirmed").textContent =
        Number(
          payload.statuses?.confirmed || 0
        ).toLocaleString();

      document.querySelector("#stat-probable").textContent =
        Number(
          payload.statuses?.probable || 0
        ).toLocaleString();

      document.querySelector("#stat-unresolved").textContent =
        Number(
          payload.statuses?.unresolved || 0
        ).toLocaleString();

      document.querySelector("#stat-occurrences").textContent =
        Number(
          payload.aggregate_occurrences || 0
        ).toLocaleString();

      document.querySelector("#stat-bills").textContent =
        Number(
          payload.bill_relationships || 0
        ).toLocaleString();

      if (elements.mobileTotal) {
        elements.mobileTotal.textContent =
          `${Number(
            payload.total_numbers || 0
          ).toLocaleString()} Numbers`;
      }

      if (elements.mobileConfirmed) {
        elements.mobileConfirmed.textContent =
          `${Number(
            payload.statuses?.confirmed || 0
          ).toLocaleString()} Confirmed`;
      }

    } catch (error) {
      console.warn(
        "Live dashboard unavailable:",
        error
      );
    }
  }

  async function loadPhones() {
    state.view = "phones";

    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(state.offset),
    });

    if (state.query) {
      params.set("q", state.query);
    }

    if (state.status) {
      params.set("status", state.status);
    }

    if (state.npa) {
      params.set("npa", state.npa);
    }

    elements.message.textContent = "Loading directory…";

    try {
      const response = await fetch(
        `${API_BASE}/phones?${params}`,
        {
          cache: "no-store",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Directory request returned ${response.status}`
        );
      }

      const payload = await response.json();

      state.mode = "live";
      state.total = payload.total;
      state.phones = payload.phones || [];
      elements.message.textContent = "";

    } catch (error) {
      console.warn(
        "Live phone directory unavailable:",
        error
      );

      state.mode = "unavailable";
      state.total = 0;
      state.phones = [];

      elements.message.textContent =
        "The live Edge1 contact directory is unavailable. " +
        "No preview or fixture records are being substituted.";
    }

    renderPhones();
  }

  async function loadSources() {
    state.view = "sources";
    state.selectedId = null;

    elements.title.textContent = "Sources";
    elements.message.textContent =
      "Loading source documents…";

    document
      .querySelectorAll("[data-status]")
      .forEach((button) => {
        button.classList.remove("active");
      });

    document
      .querySelector("#sources-view")
      .classList.add("active");

    try {
      const response = await fetch(
        `${API_BASE}/sources?limit=100`,
        {
          cache: "no-store",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Sources request returned ${response.status}`
        );
      }

      const payload = await response.json();

      state.sources = payload.sources || [];
      state.total = payload.total || state.sources.length;

      elements.count.textContent =
        `${Number(state.total).toLocaleString()} sources`;

      elements.message.textContent =
        "Source-document references imported from the " +
        "imported source index. A listed source is not " +
        "the same as independent recovery of the original PDF.";

      elements.results.innerHTML = state.sources
        .map((source) => {
          const relationships = Number(
            source.relationship_count ??
            source.phone_count ??
            0
          );

          return `
            <article class="phone-card">
              <div class="phone-card-header">
                <span class="phone-number">
                  ${escapeHtml(source.source_name)}
                </span>

                <span class="badge unresolved">
                  Source
                </span>
              </div>

              <p class="association">
                ${escapeHtml(
                  source.document_type ||
                  "Source document reference"
                )}
              </p>

              <div class="phone-meta">
                <span>
                  ${relationships.toLocaleString()}
                  relationships
                </span>

                ${
                  source.statement_date
                    ? `<span>${escapeHtml(
                        source.statement_date
                      )}</span>`
                    : ""
                }
              </div>
            </article>
          `;
        })
        .join("");

      if (!state.sources.length) {
        elements.results.innerHTML =
          '<p class="empty-state">' +
          'No source documents returned.' +
          '</p>';
      }

      elements.previous.disabled = true;
      elements.next.disabled = true;
      elements.page.textContent = "Source index";

      elements.detailTitle.textContent =
        "Source provenance";

      elements.detailStatus.className =
        "badge unresolved";

      elements.detailStatus.textContent =
        "Reference";

      elements.detail.innerHTML = `
        <p>
          The database contains
          <strong>${Number(
            state.total
          ).toLocaleString()}</strong>
          source-document references from the imported
          research workbook.
        </p>

        <p>
          These references establish workbook provenance.
          They do not imply that every original bill PDF
          has been independently recovered or re-verified.
        </p>
      `;

    } catch (error) {
      state.sources = [];

      elements.count.textContent = "Unavailable";
      elements.message.textContent =
        "Live source index could not be loaded.";

      elements.results.innerHTML =
        '<p class="empty-state">' +
        'The source gateway is unavailable.' +
        '</p>';

      elements.previous.disabled = true;
      elements.next.disabled = true;
      elements.page.textContent = "Source index";
    }
  }

  function renderPhones() {
    elements.count.textContent =
      `${state.total.toLocaleString()} records`;

    const label = state.status
      ? (
          state.status.charAt(0).toUpperCase() +
          state.status.slice(1)
        )
      : "All Numbers";

    elements.title.textContent = label;

    if (!state.phones.length) {
      elements.results.innerHTML =
        '<p class="empty-state">No matching numbers.</p>';
    } else {
      elements.results.innerHTML = state.phones
        .map((phone) => {
          const selected =
            phone.id === state.selectedId
              ? " selected"
              : "";

          return `
            <button
              type="button"
              class="phone-card${selected}"
              data-phone-id="${escapeHtml(phone.id)}"
            >
              <div class="phone-card-header">
                <span class="phone-number">
                  ${escapeHtml(phone.display_number)}
                </span>

                ${statusBadge(phone.status)}
              </div>

              <p class="association">
                ${escapeHtml(
                  phone.association_label ||
                  "No verified public association"
                )}
              </p>

              <div class="phone-meta">
                <span>
                  ${escapeHtml(
                    phone.category || "Unclassified"
                  )}
                </span>

                <span>
                  ${Number(
                    phone.occurrence_count || 0
                  ).toLocaleString()}
                  occurrences
                </span>

                ${
                  phone.location
                    ? `<span>${escapeHtml(
                        phone.location
                      )}</span>`
                    : ""
                }
              </div>
            </button>
          `;
        })
        .join("");
    }

    document
      .querySelectorAll("[data-phone-id]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          selectPhone(
            Number(button.dataset.phoneId)
          );
        });
      });

    const page =
      Math.floor(state.offset / PAGE_SIZE) + 1;

    const pages = Math.max(
      1,
      Math.ceil(state.total / PAGE_SIZE)
    );

    elements.page.textContent =
      `Page ${page} of ${pages}`;

    elements.previous.disabled =
      state.offset === 0;

    elements.next.disabled =
      state.offset + PAGE_SIZE >= state.total;
  }

  async function selectPhone(id) {
    state.selectedId = id;
    renderPhones();

    if (
      elements.detailPanel &&
      window.matchMedia("(max-width: 760px)").matches
    ) {
      elements.detailPanel.classList.add("mobile-open");
      document.body.classList.add("mobile-detail-open");
    }

    let detail = state.phones.find(
      (phone) => phone.id === id
    );

    if (state.mode === "live") {
      try {
        const response = await fetch(
          `${API_BASE}/phones/${id}`,
          {
            cache: "no-store",
            headers: {
              Accept: "application/json",
            },
          }
        );

        if (response.ok) {
          detail = await response.json();
        }
      } catch (error) {
        // Keep list-level preview.
      }
    }

    renderDetail(detail);
  }

  function renderDetail(detail) {
    if (!detail) {
      return;
    }

    elements.detailTitle.textContent =
      detail.display_number;

    elements.detailStatus.className =
      `badge ${detail.status || "unresolved"}`;

    elements.detailStatus.textContent =
      detail.status || "unresolved";

    const evidence = detail.evidence || [];
    const sources = detail.sources || [];

    elements.detail.innerHTML = `
      <dl>
        <div>
          <dt>Normalized number</dt>
          <dd>${escapeHtml(
            detail.normalized_number
          )}</dd>
        </div>

        <div>
          <dt>Association</dt>
          <dd>${escapeHtml(
            detail.association_label ||
            "No verified public association"
          )}</dd>
        </div>

        <div>
          <dt>Category</dt>
          <dd>${escapeHtml(
            detail.category || "Unclassified"
          )}</dd>
        </div>

        <div>
          <dt>Location</dt>
          <dd>${escapeHtml(
            detail.location ||
            detail.region ||
            "Not recorded"
          )}</dd>
        </div>

        <div>
          <dt>Aggregate occurrences</dt>
          <dd>${Number(
            detail.occurrence_count || 0
          ).toLocaleString()}</dd>
        </div>

        <div>
          <dt>Research notes</dt>
          <dd>${escapeHtml(
            detail.research_notes ||
            "No additional research note."
          )}</dd>
        </div>
      </dl>

      <section class="detail-section">
        <h3>Evidence</h3>

        ${
          evidence.length
            ? evidence.map((item) => `
                <article class="evidence-card">
                  ${statusBadge(
                    item.verification_status
                  )}
                  <p>
                    ${escapeHtml(
                      item.evidence_summary ||
                      item.source_title ||
                      "Evidence record"
                    )}
                  </p>
                </article>
              `).join("")
            : '<p class="empty-state">' +
              'Evidence details load from the live gateway.' +
              '</p>'
        }
      </section>

      <section class="detail-section">
        <h3>Source relationships</h3>

        ${
          sources.length
            ? sources.map((item) => `
                <article class="source-card">
                  <strong>
                    ${escapeHtml(item.source_name)}
                  </strong>
                  <p>
                    ${escapeHtml(
                      item.verification_status ||
                      "Referenced"
                    )}
                  </p>
                </article>
              `).join("")
            : '<p class="empty-state">' +
              'Source details load from the live gateway.' +
              '</p>'
        }
      </section>
    `;
  }

  function applyFilters() {
    state.query = elements.query.value.trim();
    state.status = elements.status.value;
    state.npa = elements.npa.value
      .replace(/\D/g, "")
      .slice(0, 3);
    state.offset = 0;
    state.selectedId = null;

    document
      .querySelector("#sources-view")
      .classList.remove("active");

    document
      .querySelectorAll("[data-status]")
      .forEach((button) => {
        button.classList.toggle(
          "active",
          button.dataset.status === state.status
        );
      });

    loadPhones();
  }

  elements.form.addEventListener(
    "submit",
    (event) => {
      event.preventDefault();
      applyFilters();
    }
  );

  elements.clear.addEventListener(
    "click",
    () => {
      elements.query.value = "";
      elements.status.value = "";
      elements.npa.value = "";
      applyFilters();
    }
  );

  document
    .querySelectorAll("[data-status]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        elements.status.value =
          button.dataset.status;
        applyFilters();
      });
    });

  document
    .querySelector("#sources-view")
    .addEventListener(
      "click",
      () => {
        loadSources();
      }
    );

  elements.previous.addEventListener(
    "click",
    () => {
      state.offset = Math.max(
        0,
        state.offset - PAGE_SIZE
      );
      loadPhones();
    }
  );

  elements.next.addEventListener(
    "click",
    () => {
      state.offset += PAGE_SIZE;
      loadPhones();
    }
  );

  function closeMobileFilters() {
    if (!elements.filterPanel) {
      return;
    }

    elements.filterPanel.classList.remove("mobile-open");

    if (elements.mobileFilter) {
      elements.mobileFilter.setAttribute(
        "aria-expanded",
        "false"
      );
    }
  }

  function closeMobileDetail() {
    if (!elements.detailPanel) {
      return;
    }

    elements.detailPanel.classList.remove("mobile-open");
    document.body.classList.remove("mobile-detail-open");

    const selected = document.querySelector(
      `[data-phone-id="${state.selectedId}"]`
    );

    if (selected) {
      selected.focus();
    }
  }

  if (elements.mobileFilter) {
    elements.mobileFilter.addEventListener(
      "click",
      () => {
        const open =
          elements.filterPanel.classList.toggle(
            "mobile-open"
          );

        elements.mobileFilter.setAttribute(
          "aria-expanded",
          String(open)
        );

        if (open) {
          elements.query.focus();
        }
      }
    );
  }

  if (elements.mobileSearch) {
    elements.mobileSearch.addEventListener(
      "click",
      () => {
        elements.filterPanel.classList.add("mobile-open");

        elements.mobileFilter.setAttribute(
          "aria-expanded",
          "true"
        );

        elements.query.focus();
      }
    );
  }

  if (elements.mobileBack) {
    elements.mobileBack.addEventListener(
      "click",
      closeMobileDetail
    );
  }

  window.addEventListener(
    "keydown",
    (event) => {
      if (event.key !== "Escape") {
        return;
      }

      closeMobileFilters();
      closeMobileDetail();
    }
  );

  loadDashboard();
  loadPhones();
})();
