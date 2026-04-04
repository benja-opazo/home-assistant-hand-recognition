const TOPIC_DEFAULTS = {
  "frigate/events": [
    { property:"type",           comparator:"==", value:"update" },
    { property:"after.label",    comparator:"==", value:"person" },
    { property:"after.top_score",comparator:">",  value:"0.7"    },
  ],
  "frigate/tracked_object_update": [
    { property:"type",  comparator:"==", value:"face"    },
    { property:"name",  comparator:"!=", value:"unknown" },
    { property:"score", comparator:">",  value:"0.7"     },
  ],
};

const PREDEFINED = ["frigate/events","frigate/tracked_object_update"];
let currentTopic = INIT_TOPIC;

function initTopicRadios() {
  const isCustom = !PREDEFINED.includes(currentTopic);
  document.querySelectorAll("input[name='mqtt_topic_choice']").forEach(r => {
    r.checked = isCustom ? r.value === "__custom__" : r.value === currentTopic;
  });
  document.getElementById("custom-topic-wrap").style.display = isCustom ? "block" : "none";
  if (isCustom) document.getElementById("custom-topic-input").value = currentTopic;
  updateTopicOptionStyles();
}

function updateTopicOptionStyles() {
  document.querySelectorAll(".topic-option").forEach(opt => {
    opt.classList.toggle("selected", opt.querySelector("input[type=radio]").checked);
  });
}

document.querySelectorAll("input[name='mqtt_topic_choice']").forEach(r => {
  r.addEventListener("change", () => {
    const isCustom = r.value === "__custom__";
    document.getElementById("custom-topic-wrap").style.display = isCustom ? "block" : "none";
    if (!isCustom) { currentTopic = r.value; renderDefaultFiltersForTopic(r.value); }
    updateTopicOptionStyles();
  });
});

function getSelectedTopic() {
  const checked = document.querySelector("input[name='mqtt_topic_choice']:checked");
  if (!checked) return "frigate/events";
  if (checked.value === "__custom__") return document.getElementById("custom-topic-input").value.trim();
  return checked.value;
}

function renderDefaultFiltersForTopic(topic) { renderFilters(TOPIC_DEFAULTS[topic] || []); }

function renderFilters(filters) {
  const list = document.getElementById("filters-list");
  list.innerHTML = "";
  if (filters.length === 0) {
    list.innerHTML = '<div class="filters-empty">No filters — all messages will trigger processing.</div>';
    return;
  }
  filters.forEach(f => addFilterRow(f));
}

function addFilterRow(f = { property:"", comparator:"==", value:"" }) {
  const list = document.getElementById("filters-list");
  const placeholder = list.querySelector(".filters-empty");
  if (placeholder) placeholder.remove();

  const row = document.createElement("div");
  row.className = "filter-row";
  const cmpOptions = COMPARATORS.map(c =>
    `<option value="${c}"${c === f.comparator ? " selected" : ""}>${c}</option>`
  ).join("");
  row.innerHTML = `
    <input class="filter-prop" type="text"  placeholder="property (e.g. after.label)" value="${escHtml(f.property)}" />
    <select class="filter-cmp">${cmpOptions}</select>
    <input class="filter-val"  type="text"  placeholder="value" value="${escHtml(f.value)}" />
    <button type="button" class="filter-remove" title="Remove">✕</button>`;

  row.querySelector(".filter-remove").addEventListener("click", () => {
    row.remove();
    if (document.getElementById("filters-list").children.length === 0) {
      document.getElementById("filters-list").innerHTML =
        '<div class="filters-empty">No filters — all messages will trigger processing.</div>';
    }
  });
  list.appendChild(row);
}

function collectFilters() {
  return [...document.querySelectorAll("#filters-list .filter-row")].map(row => ({
    property:   row.querySelector(".filter-prop").value.trim(),
    comparator: row.querySelector(".filter-cmp").value,
    value:      row.querySelector(".filter-val").value.trim(),
  })).filter(f => f.property);
}

document.getElementById("btn-add-filter").addEventListener("click", () => addFilterRow());
document.getElementById("btn-reset-filters").addEventListener("click", () => {
  renderDefaultFiltersForTopic(getSelectedTopic());
});

document.getElementById("detection-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("detection-status");
  const payload = { mqtt_topic: getSelectedTopic(), topic_filters: collectFilters() };
  status.textContent = "Saving…"; status.className = "save-status";
  try {
    const res  = await fetch(URL_CONFIG, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
    const json = await res.json();
    if (res.ok) { status.textContent = "Saved. Restart the add-on to apply topic changes."; status.className = "save-status ok"; }
    else        { status.textContent = "Error: "+(json.error||res.statusText); status.className = "save-status err"; }
  } catch(err) { status.textContent = "Network error: "+err.message; status.className = "save-status err"; }
});

initTopicRadios();
renderFilters(INIT_FILTERS);
