(function () {
  "use strict";

  const fallbackData = {
    query: "private library search",
    collections: ["operations"],
    results: [
      {
        source_id: "S1",
        document_id: "ce465ba7e29f049d35f7ea86108647be",
        collection: "operations",
        title: "edge1-private-library-search-module-realistic-build-20260716",
        source_path: "operations/edge1-private-library-search-module-realistic-build-20260716.md",
        classification: "internal",
        chunk_index: 2,
        locator: "document",
        excerpt: "Phone layout uses cards, not a wide table. Each card shows title, source path, classification, and a short excerpt.",
        score: -54.82
      },
      {
        source_id: "S2",
        document_id: "7376ea3add8e63c737934695f4715462",
        collection: "operations",
        title: "edge1-build-backlog-20260716",
        source_path: "operations/edge1-build-backlog-20260716.md",
        classification: "internal",
        chunk_index: 0,
        locator: "document",
        excerpt: "Phase 2: Private Library Module. Add library search page, collection list, source/document detail view, and import queue page.",
        score: -17.33
      }
    ]
  };

  const state = {
    allResults: [],
    visibleResults: [],
    selectedIndex: -1
  };

  const els = {
    form: document.getElementById("search-form"),
    query: document.getElementById("query"),
    collection: document.getElementById("collection"),
    limit: document.getElementById("limit"),
    resultCount: document.getElementById("result-count"),
    resultsTitle: document.getElementById("results-title"),
    stateMessage: document.getElementById("state-message"),
    results: document.getElementById("results"),
    detailTitle: document.getElementById("detail-title"),
    detailSourcePath: document.getElementById("detail-source-path"),
    detailClassification: document.getElementById("detail-classification"),
    detailDocumentId: document.getElementById("detail-document-id"),
    detailChunk: document.getElementById("detail-chunk"),
    detailLocator: document.getElementById("detail-locator"),
    detailExcerpt: document.getElementById("detail-excerpt"),
    copyCitation: document.getElementById("copy-citation"),
    copySource: document.getElementById("copy-source")
  };

  function text(value) {
    if (value === null || value === undefined || value === "") {
      return "Not available";
    }
    return String(value);
  }

  function normalize(value) {
    return text(value).toLowerCase();
  }

  function resultMatchesQuery(result, query) {
    if (!query) {
      return true;
    }

    const haystack = [
      result.title,
      result.source_path,
      result.classification,
      result.locator,
      result.excerpt,
      result.document_id,
      result.source_id
    ].map(normalize).join(" ");

    return query.split(/\s+/).filter(Boolean).every((part) => haystack.includes(part));
  }

  function setMessage(message) {
    els.stateMessage.textContent = message || "";
  }

  function setCount(count) {
    els.resultCount.textContent = count === 1 ? "1 result" : `${count} results`;
  }

  function renderResults() {
    els.results.replaceChildren();
    setCount(state.visibleResults.length);

    if (state.visibleResults.length === 0) {
      setMessage("No results matched the current query and collection.");
      clearDetail();
      return;
    }

    setMessage("");

    state.visibleResults.forEach((result, index) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "result-card";
      card.setAttribute("aria-selected", String(index === state.selectedIndex));
      card.dataset.index = String(index);

      const title = document.createElement("h3");
      title.textContent = text(result.title);

      const path = document.createElement("p");
      path.className = "result-path";
      path.textContent = text(result.source_path);

      const meta = document.createElement("p");
      meta.className = "result-meta";
      meta.textContent = `${text(result.collection)} | ${text(result.classification)} | chunk ${text(result.chunk_index)}`;

      const excerpt = document.createElement("p");
      excerpt.className = "result-excerpt";
      excerpt.textContent = text(result.excerpt);

      card.append(title, path, meta, excerpt);
      card.addEventListener("click", () => selectResult(index));
      els.results.appendChild(card);
    });
  }

  function clearDetail() {
    state.selectedIndex = -1;
    els.detailTitle.textContent = "Select a result";
    els.detailSourcePath.textContent = "Not selected";
    els.detailClassification.textContent = "Not selected";
    els.detailDocumentId.textContent = "Not selected";
    els.detailChunk.textContent = "Not selected";
    els.detailLocator.textContent = "Not selected";
    els.detailExcerpt.textContent = "Choose a search result to inspect the retrieved passage and trace metadata.";
    els.copyCitation.disabled = true;
    els.copySource.disabled = true;
  }

  function selectResult(index) {
    const result = state.visibleResults[index];
    if (!result) {
      clearDetail();
      return;
    }

    state.selectedIndex = index;
    els.detailTitle.textContent = text(result.title);
    els.detailSourcePath.textContent = text(result.source_path);
    els.detailClassification.textContent = text(result.classification);
    els.detailDocumentId.textContent = text(result.document_id);
    els.detailChunk.textContent = text(result.chunk_index);
    els.detailLocator.textContent = text(result.locator);
    els.detailExcerpt.textContent = text(result.excerpt);
    els.copyCitation.disabled = false;
    els.copySource.disabled = false;

    Array.from(els.results.querySelectorAll(".result-card")).forEach((card, cardIndex) => {
      card.setAttribute("aria-selected", String(cardIndex === index));
    });
  }

  function applySearch() {
    const query = normalize(els.query.value).trim();
    const collection = els.collection.value;
    const limit = Math.max(1, Math.min(Number(els.limit.value) || 5, 20));

    state.visibleResults = state.allResults
      .filter((result) => result.collection === collection)
      .filter((result) => resultMatchesQuery(result, query))
      .slice(0, limit);

    els.resultsTitle.textContent = query ? `Results for "${els.query.value.trim()}"` : "All Results";
    state.selectedIndex = state.visibleResults.length ? 0 : -1;
    renderResults();

    if (state.selectedIndex >= 0) {
      selectResult(state.selectedIndex);
    }
  }

  async function copyText(value) {
    if (!navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(value);
  }

  function selectedResult() {
    return state.visibleResults[state.selectedIndex] || null;
  }

  async function loadFixture() {
    setMessage("Loading fixture data.");
    try {
      const response = await fetch("./private-library-search.fixture.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Fixture request failed: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      setMessage("Using embedded fixture data because fixture JSON could not be fetched in this browser context.");
      return fallbackData;
    }
  }

  function bindEvents() {
    els.form.addEventListener("submit", (event) => {
      event.preventDefault();
      applySearch();
    });

    document.querySelectorAll("[data-query]").forEach((button) => {
      button.addEventListener("click", () => {
        els.query.value = button.dataset.query || "";
        applySearch();
      });
    });

    els.copyCitation.addEventListener("click", async () => {
      const result = selectedResult();
      if (result) {
        await copyText(`${result.title} (${result.source_path}) chunk ${result.chunk_index}`);
      }
    });

    els.copySource.addEventListener("click", async () => {
      const result = selectedResult();
      if (result) {
        await copyText(result.source_path);
      }
    });
  }

  async function init() {
    bindEvents();
    const data = await loadFixture();
    state.allResults = Array.isArray(data.results) ? data.results : [];
    applySearch();
  }

  init();
})();

