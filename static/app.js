const form = document.querySelector("#searchForm");
const statusBox = document.querySelector("#status");
const summaryBox = document.querySelector("#summary");
const resultsBox = document.querySelector("#results");
const ao3Link = document.querySelector("#ao3Link");
const searchButton = document.querySelector("#searchButton");
const template = document.querySelector("#workTemplate");

document.querySelector("#polytrixPreset").addEventListener("click", async () => {
  setStatus("Loading preset...");
  const response = await fetch("/api/preset/polytrix");
  const data = await response.json();
  fillForm(data.options);
  ao3Link.href = data.ao3_url;
  ao3Link.hidden = false;
  setStatus("Polytrix fluff preset loaded. Adjust anything you want, then search.");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = readForm();

  searchButton.disabled = true;
  resultsBox.innerHTML = "";
  summaryBox.hidden = true;
  setStatus("Searching AO3 public result pages. This may take a few seconds.");

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    ao3Link.href = data.ao3_url || "#";
    ao3Link.hidden = !data.ao3_url;

    if (!data.ok) {
      setStatus(`AO3 search failed: ${data.error || "Unknown error"}`);
      return;
    }

    renderSummary(data);
    renderResults(data.works || []);
    setStatus(`Finished. Parsed ${data.result_count} visible result cards.`);
  } catch (error) {
    setStatus(`Search failed: ${error.message}`);
  } finally {
    searchButton.disabled = false;
  }
});

function readForm() {
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

function fillForm(options) {
  for (const [key, value] of Object.entries(options)) {
    const field = form.elements[key];
    if (field) {
      field.value = value ?? "";
    }
  }
}

function setStatus(message) {
  statusBox.hidden = false;
  statusBox.textContent = message;
}

function renderSummary(data) {
  summaryBox.hidden = false;
  const reported = data.total_reported ? `AO3 reported ${data.total_reported} matching works.` : "AO3 did not provide a clear total.";
  const urls = (data.searched_urls || [])
    .map((url, index) => `<li><a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">Page ${index + 1}</a></li>`)
    .join("");

  summaryBox.innerHTML = `
    <strong>${reported}</strong>
    <p>Parsed ${data.result_count} result cards and sorted them by cozy score, then kudos/bookmarks/hits.</p>
    <details>
      <summary>AO3 pages searched</summary>
      <ul>${urls}</ul>
    </details>
  `;
}

function renderResults(works) {
  resultsBox.innerHTML = "";

  if (!works.length) {
    resultsBox.innerHTML = `<section class="status">No visible works were parsed. Try fewer exclusions, fewer exact tags, or opening the AO3 search link directly to see what AO3 returned.</section>`;
    return;
  }

  for (const work of works) {
    const node = template.content.cloneNode(true);
    const score = node.querySelector(".score");
    const title = node.querySelector(".work-title");

    title.textContent = work.title || "(Untitled)";
    title.href = work.url || "#";

    node.querySelector(".byline").textContent = `by ${(work.authors || ["Anonymous"]).join(", ")}`;
    score.textContent = `Score ${work.score ?? 0}`;
    if ((work.score ?? 0) < 0) {
      score.classList.add("negative");
    }

    const stats = [
      work.words && `${work.words} words`,
      work.chapters && `${work.chapters} chapters`,
      work.kudos && `${work.kudos} kudos`,
      work.bookmarks && `${work.bookmarks} bookmarks`,
      work.comments && `${work.comments} comments`,
      work.hits && `${work.hits} hits`,
      work.updated && `Updated ${work.updated}`,
    ].filter(Boolean).join(" · ");

    node.querySelector(".meta").textContent = stats || "No stats parsed.";
    node.querySelector(".summary-text").textContent = work.summary || "No summary visible.";

    renderTags(node.querySelector(".relationships"), work.relationships || []);
    renderTags(node.querySelector(".freeforms"), work.freeforms || []);

    const notes = node.querySelector(".score-notes");
    const scoreNotes = work.score_notes?.length ? work.score_notes : ["No score notes."];
    notes.innerHTML = scoreNotes.map(note => `<li>${escapeHtml(note)}</li>`).join("");

    resultsBox.appendChild(node);
  }
}

function renderTags(container, tags) {
  container.innerHTML = "";
  if (!tags.length) {
    container.innerHTML = `<span class="tag">None parsed</span>`;
    return;
  }

  for (const tag of tags.slice(0, 40)) {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = tag;
    container.appendChild(span);
  }

  if (tags.length > 40) {
    const more = document.createElement("span");
    more.className = "tag";
    more.textContent = `+${tags.length - 40} more`;
    container.appendChild(more);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}
