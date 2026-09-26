const $ = (selector) => document.querySelector(selector);
let meta = null;
let currentData = null;

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

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
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
  const rows = plan.schedule.map((entry) => {
    const item = entry.item;
    return `<div class="meal-row">
      <div class="meal-time"><strong>${escapeHtml(entry.eat_at)}</strong><span>${escapeHtml(entry.label)}</span></div>
      <div>
        <h3>${escapeHtml(item.item)}</h3>
        <p>${escapeHtml(item.shop)} · ${escapeHtml(item.location_name)} · ${item.distance_km} km · ${money(item.price_sgd)}</p>
        <small>Suggested window: ${escapeHtml(entry.window)}</small>
      </div>
    </div>`;
  }).join("");
  return `${rows}${nutrition(plan)}`;
}

function updateBudget(value) {
  $("#budget-output").textContent = money(value);
}

async function init() {
  try {
    meta = await api("/api/meta");
    $("#model-status").innerHTML = `<span></span>${meta.openrouter_ready ? `OpenRouter · ${escapeHtml(meta.model)}` : "Demo mode"}`;
    $("#model-status").classList.toggle("ready", meta.openrouter_ready);
    $("#model-toggle").disabled = !meta.openrouter_ready;

    const minimum = Number(meta.minimum_three_meal_budget_sgd);
    const budget = $("#budget");
    budget.min = minimum;
    if (+budget.value < minimum) budget.value = minimum;
    $("#budget-floor").textContent = `Minimum for one light breakfast, lunch, and dinner: ${money(minimum)}`;
    updateBudget(budget.value);
  } catch (error) {
    toast(error.message);
  }
}

$("#budget").addEventListener("input", (event) => updateBudget(event.target.value));

$("#model-toggle").addEventListener("change", (event) => {
  $("#mode-hint").textContent = event.target.checked
    ? "OpenRouter ranks the same tool-approved shortlist"
    : "Demo heuristic — not LLM evidence";
});

$("#planner-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter || $("#planner-form button[type=submit]");
  button.disabled = true;
  button.firstElementChild.textContent = "Building three meals…";
  const body = {
    budget: +$("#budget").value,
    age: +$("#age").value,
    weight_kg: +$("#weight").value,
    height_cm: +$("#height").value,
    calculation_sex: $("#calculation-sex").value,
    activity_level: $("#activity").value,
    goal: $("#goal").value,
    preferences: $("#preferences").value,
    mode: $("#model-toggle").checked ? "openrouter" : "demo",
  };
  try {
    const data = await api("/api/rank", {method: "POST", body: JSON.stringify(body)});
    currentData = data;
    renderResults(data);
    $("#results").classList.remove("hidden");
    $("#results").scrollIntoView({behavior: "smooth"});
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = "Build my three-meal day";
  }
});

function renderResults(data) {
  $("#decision-card").classList.remove("hidden");
  $("#completion-card").classList.add("hidden");
  $("#rejection-box").classList.add("hidden");
  $("#intake-result").classList.add("hidden");

  if (!data.solution.available) {
    $("#plan-results").classList.add("hidden");
    $("#no-plan").classList.remove("hidden");
    $("#no-plan").innerHTML = `<h2>No three-meal plan at this budget</h2><p>${escapeHtml(data.solution.message)}</p>`;
    return;
  }

  $("#no-plan").classList.add("hidden");
  $("#plan-results").classList.remove("hidden");
  const plan = data.model_pick;
  const targets = data.targets;
  $("#target-summary").innerHTML = `
    <div><strong>${targets.estimated_daily_calories_kcal}</strong><span>estimated kcal/day</span></div>
    <div><strong>${targets.protein_target_g}g</strong><span>protein estimate</span></div>
    <div><strong>${targets.carb_target_g}g</strong><span>carbohydrate estimate</span></div>
    <div><strong>${targets.fat_target_g}g</strong><span>fat estimate</span></div>`;
  $("#pick-card").innerHTML = planMarkup(plan);
  $("#model-reason").textContent = data.ranking.reason;
  $("#ranker-label").textContent = data.ranking.mode === "openrouter"
    ? `OpenRouter · ${data.ranking.model}`
    : "Demo preference heuristic";
  $("#result-title").textContent = "Breakfast, lunch, and dinner";
  $("#feasible-badge").textContent = plan.feasible ? "Targets met" : "Closest available";
  $("#search-summary").textContent = `${data.solution.evaluated_count.toLocaleString()} scheduled plans checked · ${data.solution.feasible_count.toLocaleString()} meet all constraints`;
  $("#shortlist").innerHTML = data.solution.shortlist.map((option, index) => `
    <article class="mini-plan">
      <span class="rank">OPTION ${index + 1}</span>
      <h4>${escapeHtml(itemNames(option))}</h4>
      <p>${money(option.totals.price_sgd)} · ${option.totals.kcal} kcal</p>
      <p>${option.totals.protein_g}g protein · ${option.totals.carbs_g}g carbs</p>
    </article>`).join("");
}

$("#accept-plan").addEventListener("click", () => {
  if (!currentData?.model_pick) return;
  $("#decision-card").classList.add("hidden");
  $("#completion-card").classList.remove("hidden");
  renderChecklist(currentData.model_pick);
  $("#completion-card").scrollIntoView({behavior: "smooth", block: "center"});
});

$("#reject-plan").addEventListener("click", () => {
  $("#rejection-box").classList.remove("hidden");
  $("#rejection-preference").focus();
});

$("#try-again").addEventListener("click", () => {
  const preference = $("#rejection-preference").value.trim();
  if (!preference) {
    toast("Tell MacroFit what you would prefer first.");
    return;
  }
  $("#preferences").value = preference;
  $("#planner-form").requestSubmit();
});

function menuOptions(selectedId) {
  return meta.menu.map((item) => `<option value="${item.item_id}" ${item.item_id === selectedId ? "selected" : ""}>${escapeHtml(item.item)} — ${escapeHtml(item.shop)} (${money(item.price_sgd)})</option>`).join("");
}

function renderChecklist(plan) {
  $("#analyze-day").classList.add("hidden");
  $("#meal-checklist").innerHTML = plan.schedule.map((entry) => `
    <div class="checklist-row" data-meal="${entry.meal}" data-planned-id="${entry.item.item_id}">
      <div class="checklist-heading"><strong>${escapeHtml(entry.label)} · ${escapeHtml(entry.eat_at)}</strong><span>Planned: ${escapeHtml(entry.item.item)}</span></div>
      <label>What did you actually eat?
        <select class="actual-item">${menuOptions(entry.item.item_id)}</select>
      </label>
      <label class="complete-check"><input type="checkbox"> I completed this meal and confirm this log</label>
      <p class="log-status">Not logged</p>
    </div>`).join("");

  document.querySelectorAll(".complete-check input").forEach((checkbox) => {
    checkbox.addEventListener("change", logCompletedMeal);
  });
}

async function logCompletedMeal(event) {
  const checkbox = event.target;
  if (!checkbox.checked) return;
  const row = checkbox.closest(".checklist-row");
  const select = row.querySelector(".actual-item");
  const itemId = select.value;
  const key = `meal_${Date.now()}_${row.dataset.meal}`;
  checkbox.disabled = true;
  select.disabled = true;
  row.querySelector(".log-status").textContent = "Logging confirmed meal…";
  try {
    const logged = await api("/api/log", {
      method: "POST",
      body: JSON.stringify({
        meal: row.dataset.meal,
        item_id: itemId,
        quantity: 1,
        status: "consumed",
        idempotency_key: key,
        user_confirmed: true,
      }),
    });
    row.dataset.loggedId = itemId;
    const changed = itemId !== row.dataset.plannedId;
    row.querySelector(".log-status").textContent = `${logged.item} logged${changed ? " · deviation recorded" : " · as planned"}`;
    const rows = [...document.querySelectorAll(".checklist-row")];
    if (rows.every((item) => item.dataset.loggedId)) $("#analyze-day").classList.remove("hidden");
  } catch (error) {
    checkbox.checked = false;
    checkbox.disabled = false;
    select.disabled = false;
    row.querySelector(".log-status").textContent = "Not logged";
    toast(error.message);
  }
}

$("#analyze-day").addEventListener("click", async () => {
  const actualItems = [...document.querySelectorAll(".checklist-row")].map((row) => ({
    meal: row.dataset.meal,
    item_id: row.dataset.loggedId,
    quantity: 1,
  }));
  const targets = currentData.targets;
  try {
    const analysis = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({
        actual_items: actualItems,
        daily_targets: {
          calories_kcal: targets.estimated_daily_calories_kcal,
          protein_g: targets.protein_target_g,
          carbs_g: targets.carb_target_g,
          fat_g: targets.fat_target_g,
        },
        budget_sgd: +$("#budget").value,
      }),
    });
    const result = $("#intake-result");
    result.classList.remove("hidden");
    result.innerHTML = `<h3>Completed-day analysis</h3>
      <p>${escapeHtml(analysis.message)}</p>
      <div class="analysis-grid">
        <div><strong>${analysis.actual_totals.kcal}</strong><span>kcal logged</span></div>
        <div><strong>${analysis.actual_totals.protein_g}g</strong><span>protein logged</span></div>
        <div><strong>${money(analysis.actual_totals.price_sgd)}</strong><span>${analysis.within_budget ? "within budget" : "above budget"}</span></div>
      </div>
      <small>This is a general planning comparison, not a medical judgment.</small>`;
    result.scrollIntoView({behavior: "smooth", block: "center"});
  } catch (error) {
    toast(error.message);
  }
});

init();
