const $ = (selector) => document.querySelector(selector);
let meta = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.remove("hidden");
  setTimeout(() => element.classList.add("hidden"), 3200);
}

function money(value) {
  return `S$${Number(value).toFixed(2)}`;
}

function itemNames(plan) {
  return plan.items.map((item) => item.item).join(" + ");
}

function nutrition(plan) {
  return `<div class="macro-strip">
    <div><strong>${money(plan.totals.price_sgd)}</strong><span>cost</span></div>
    <div><strong>${plan.totals.protein_g}g</strong><span>protein</span></div>
    <div><strong>${plan.totals.carbs_g}g</strong><span>carbs</span></div>
    <div><strong>${plan.totals.kcal}</strong><span>kcal</span></div>
  </div>`;
}

function planMarkup(plan) {
  const rows = plan.items.map((item, index) => `
    <div class="meal-row">
      <span class="meal-num">${index + 1}</span>
      <div>
        <h3>${item.item}</h3>
        <p>${item.shop} · ${item.location_name} · ${item.distance_km} km · ${money(item.price_sgd)}</p>
      </div>
    </div>`).join("");
  return `${rows}${nutrition(plan)}`;
}

async function init() {
  try {
    meta = await api("/api/meta");
    $("#model-status").innerHTML = `<span></span>${meta.openrouter_ready ? `OpenRouter · ${meta.model}` : "Demo mode"}`;
    $("#model-status").classList.toggle("ready", meta.openrouter_ready);
    $("#model-toggle").disabled = !meta.openrouter_ready;
  } catch (error) {
    toast(error.message);
  }
}

$("#budget").addEventListener("input", (event) => {
  $("#budget-output").textContent = `S$${event.target.value}`;
});

$("#model-toggle").addEventListener("change", (event) => {
  $("#mode-hint").textContent = event.target.checked
    ? "OpenRouter ranks the same shortlist"
    : "Demo heuristic — not LLM evidence";
});

$("#planner-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  button.firstElementChild.textContent = "Searching all plans…";
  const body = {
    budget: +$("#budget").value,
    protein_g: +$("#protein").value,
    carbs_g: +$("#carbs").value,
    preferences: $("#preferences").value,
    mode: $("#model-toggle").checked ? "openrouter" : "demo",
  };
  try {
    const data = await api("/api/rank", {method: "POST", body: JSON.stringify(body)});
    renderResults(data);
    $("#results").classList.remove("hidden");
    $("#results").scrollIntoView({behavior: "smooth"});
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = "Build my shortlist";
  }
});

function renderResults(data) {
  const plan = data.model_pick;
  $("#pick-card").innerHTML = planMarkup(plan);
  $("#model-reason").textContent = data.ranking.reason;
  $("#ranker-label").textContent = data.ranking.mode === "openrouter"
    ? `OpenRouter · ${data.ranking.model}`
    : "Demo preference heuristic";
  $("#result-title").textContent = data.ranking.mode === "openrouter"
    ? "Your recommended meals"
    : "Demo recommendation";
  $("#feasible-badge").textContent = plan.feasible ? "Targets met" : "Closest available";
  $("#search-summary").textContent = `${data.solution.evaluated_count.toLocaleString()} plans checked · ${data.solution.feasible_count.toLocaleString()} feasible`;
  $("#shortlist").innerHTML = data.solution.shortlist.map((option, index) => `
    <article class="mini-plan">
      <span class="rank">OPTION ${index + 1}</span>
      <h4>${itemNames(option)}</h4>
      <p>${money(option.totals.price_sgd)} · ${option.totals.protein_g}g protein</p>
      <p>${option.totals.carbs_g}g carbs</p>
    </article>`).join("");
}

init();
