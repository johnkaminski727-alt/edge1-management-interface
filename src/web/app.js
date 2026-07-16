(function () {
  "use strict";

  const API_PATH = "/api/private-library/search";
  const FIXTURE_PATH = "./fixtures/private-library-search-results.json";
  const DEFAULT_COLLECTION = "operations";
  const DEFAULT_LIMIT = 10;

  const state = {
    query: "",
    collection: DEFAULT_COLLECTION,
    limit: DEFAULT_LIMIT,
    mode: "loading",
    results: [],
    error: "",
  };

  const elements = {
    form: document.querySelector("form"),
    searchInput:
      document.querySelector('input[type="search"]') ||
      document.querySelector('input[name="q"]') ||
      document.querySelector("#search"),
    collection:
      document.querySelector('select[name="collection"]') ||
      document.querySelector("#collection"),
    results:
      document.querySelector("#results") ||
      document.querySelector('[data-results]') ||
      document.querySelector(".results"),
    count:
      document.querySelector("[data-result-count]") ||
      document.querySelector(".result-count"),
    status:
      document.querySelector("[data-search-status]") ||
      document.querySelector(".search-status"),
  };

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizeResult(item, index) {
    return {
      id: String(item.id || item.document_id || `result-${index + 1}`),
      title: String(item.title || item.name || "Untitled result"),
      collection: String(item.collection || DEFAULT_COLLECTION),
      path: String(item.path || item.source || ""),
      updated_at: String(item.updated_at || item.updated || ""),
      score: Number(item.score || 0),
      snippet: String(item.snippet || item.summary || ""),
    };
  }

  function setStatus(message) {
    if (elements.status) {
      elements.status.textContent = message;
    }
  }

  function render() {
    if (!elements.results) {
      return;
    }

    if (elements.count) {
      elements.count.textContent = String(state.results.length);
    }

    if (state.mode === "loading") {
      elements.results.innerHTML = '<p class="empty-state">Searching private library...</p>';
      setStatus("Searching");
      return;
    }

    if (state.error) {
      elements.results.innerHTML = `<p class="empty-state">${escapeHtml(state.error)}</p>`;
      setStatus("Search unavailable");
      return;
    }

    if (!state.results.length) {
      elements.results.innerHTML = '<p class="empty-state">No matching operations records found.</p>';
      setStatus("No results");
      return;
    }

    elements.results.innerHTML = state.results
      .map((result) => {
        const score = result.score ? `${Math.round(result.score * 100)}% match` : "Match";
        const path = result.path ? `<p class="result-path">${escapeHtml(result.path)}</p>` : "";
        const updated = result.updated_at
          ? `<span>${escapeHtml(result.updated_at.replace("T", " ").replace("Z", " UTC"))}</span>`
          : "";

        return `
          <article class="result-card" data-result-id="${escapeHtml(result.id)}">
            <div class="result-card__header">
              <h2>${escapeHtml(result.title)}</h2>
              <span class="score">${escapeHtml(score)}</span>
            </div>
            ${path}
            <p>${escapeHtml(result.snippet)}</p>
            <footer>
              <span>${escapeHtml(result.collection)}</span>
              ${updated}
            </footer>
          </article>
        `;
      })
      .join("");

    setStatus(state.mode === "live" ? "Live results" : "Fixture fallback");
  }

  async function loadFixture(query, collection, limit) {
    const response = await fetch(FIXTURE_PATH, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Fixture request failed with ${response.status}`);
    }

    const payload = await response.json();
    const terms = query
      .toLowerCase()
      .split(/\s+/)
      .map((term) => term.trim())
      .filter(Boolean);

    const results = (payload.results || [])
      .map(normalizeResult)
      .filter((result) => result.collection === collection)
      .filter((result) => {
        if (!terms.length) {
          return true;
        }
        const haystack = `${result.title} ${result.path} ${result.snippet} ${result.id}`.toLowerCase();
        return terms.every((term) => haystack.includes(term));
      })
      .slice(0, limit);

    return {
      mode: "fixture",
      results,
    };
  }

  async function search(query, collection, limit) {
    state.mode = "loading";
    state.error = "";
    render();

    const params = new URLSearchParams({
      q: query,
      collection,
      limit: String(limit),
    });

    try {
      const response = await fetch(`${API_PATH}?${params.toString()}`, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Search request failed with ${response.status}`);
      }

      const payload = await response.json();
      state.mode = payload.mode || "live";
      state.results = (payload.results || []).map(normalizeResult);
      render();
      return;
    } catch (error) {
      try {
        const fallback = await loadFixture(query, collection, limit);
        state.mode = fallback.mode;
        state.results = fallback.results;
        render();
      } catch (fixtureError) {
        state.mode = "error";
        state.error = "Search is unavailable and fixture fallback could not be loaded.";
        state.results = [];
        render();
      }
    }
  }

  function currentQuery() {
    if (elements.searchInput) {
      return elements.searchInput.value.trim();
    }
    return state.query;
  }

  function currentCollection() {
    if (elements.collection) {
      return elements.collection.value || DEFAULT_COLLECTION;
    }
    return DEFAULT_COLLECTION;
  }

  function submitSearch(query) {
    state.query = query;
    state.collection = currentCollection();
    search(state.query, state.collection, state.limit);
  }

  function bindEvents() {
    if (elements.form) {
      elements.form.addEventListener("submit", (event) => {
        event.preventDefault();
        submitSearch(currentQuery());
      });
    }

    document.querySelectorAll("[data-query], .suggested-search, .chip").forEach((button) => {
      button.addEventListener("click", () => {
        const query = button.getAttribute("data-query") || button.textContent.trim();
        if (elements.searchInput) {
          elements.searchInput.value = query;
        }
        submitSearch(query);
      });
    });
  }

  bindEvents();
  submitSearch(currentQuery());
})();

